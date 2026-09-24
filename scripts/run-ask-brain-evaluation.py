#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.ask_brain_evaluation import evaluate_case, summarize_evaluation


class EvaluationConfigurationError(RuntimeError):
    pass


def _uuid(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise EvaluationConfigurationError(f"{field} must be a UUID string")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise EvaluationConfigurationError(f"{field} must be a valid UUID") from exc


def _string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvaluationConfigurationError(f"{field} must be a list of strings")
    return list(value)


def _load_dataset(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationConfigurationError("evaluation dataset could not be read") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 2:
        raise EvaluationConfigurationError("evaluation dataset schema_version must be 2")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise EvaluationConfigurationError("evaluation dataset requires non-empty cases")
    return payload


def _headers() -> dict[str, str]:
    token = os.getenv("BRAIN_EVAL_TOKEN")
    if not token:
        raise EvaluationConfigurationError("BRAIN_EVAL_TOKEN is required")
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _json_object(response: httpx.Response) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _search_event_ids(payload: dict[str, Any] | None) -> list[str]:
    if payload is None:
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    values: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        event_id = item.get("canonical_event_id")
        if isinstance(event_id, str):
            values.append(event_id)
    return values


def _answer_review_data(
    payload: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    if payload is None:
        return [], [], 0
    citations = payload.get("citations")
    claims = payload.get("claims")
    if not isinstance(citations, list) or not isinstance(claims, list):
        return [], [], 0

    citation_map: dict[str, dict[str, Any]] = {}
    for item in citations:
        if not isinstance(item, dict):
            continue
        evidence_id = item.get("evidence_id")
        if isinstance(evidence_id, str):
            citation_map[evidence_id] = item

    observed_pairs: list[dict[str, Any]] = []
    packet_claims: list[dict[str, Any]] = []
    unresolved = 0
    for claim_index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            continue
        text = claim.get("text") if isinstance(claim.get("text"), str) else ""
        citation_ids = claim.get("citation_ids")
        if not isinstance(citation_ids, list):
            citation_ids = []
        packet_citations: list[dict[str, Any]] = []
        for citation_index, evidence_id in enumerate(citation_ids):
            citation = citation_map.get(evidence_id) if isinstance(evidence_id, str) else None
            if citation is None:
                unresolved += 1
                continue
            event_id = citation.get("canonical_event_id")
            if not isinstance(event_id, str):
                unresolved += 1
                continue
            observed_pairs.append(
                {
                    "claim_index": claim_index,
                    "citation_index": citation_index,
                    "evidence_id": evidence_id,
                    "canonical_event_id": event_id,
                }
            )
            packet_citations.append(
                {
                    "citation_index": citation_index,
                    "evidence_id": evidence_id,
                    "canonical_event_id": event_id,
                    "source_provider": citation.get("source_provider"),
                    "title": citation.get("title"),
                    "excerpt": citation.get("excerpt"),
                }
            )
        packet_claims.append(
            {
                "claim_index": claim_index,
                "text": text,
                "citations": packet_citations,
            }
        )
    return observed_pairs, packet_claims, unresolved


def _case_config(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise EvaluationConfigurationError("each case must be an object")
    case_id = raw.get("id")
    question = raw.get("question")
    expected_status = raw.get("expected_status")
    if not isinstance(case_id, str) or not case_id.strip():
        raise EvaluationConfigurationError("case id is required")
    if not isinstance(question, str) or not question.strip():
        raise EvaluationConfigurationError(f"case {case_id}: question is required")
    if expected_status not in {"answer", "insufficient_evidence"}:
        raise EvaluationConfigurationError(f"case {case_id}: invalid expected_status")
    supporting = _string_list(
        raw.get("supporting_canonical_event_ids", []),
        field=f"case {case_id} supporting_canonical_event_ids",
    )
    forbidden = _string_list(
        raw.get("forbidden_canonical_event_ids", []),
        field=f"case {case_id} forbidden_canonical_event_ids",
    )
    for index, value in enumerate(supporting):
        supporting[index] = _uuid(value, field=f"case {case_id} supporting evidence")
    for index, value in enumerate(forbidden):
        forbidden[index] = _uuid(value, field=f"case {case_id} forbidden evidence")
    if set(supporting) & set(forbidden):
        raise EvaluationConfigurationError(
            f"case {case_id}: supporting and forbidden evidence overlap"
        )
    if expected_status == "answer" and not supporting:
        raise EvaluationConfigurationError(
            f"case {case_id}: answer cases require labelled supporting evidence"
        )
    return {
        "id": case_id.strip(),
        "question": " ".join(question.split()),
        "expected_status": expected_status,
        "supporting": supporting,
        "forbidden": forbidden,
    }


def _write_private_json(path: str, payload: dict[str, Any]) -> bytes:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output_path.write_bytes(encoded)
    output_path.chmod(0o600)
    return encoded


def _run(args: argparse.Namespace) -> int:
    dataset = _load_dataset(args.dataset)
    cases = [_case_config(item) for item in dataset["cases"]]
    headers = _headers()
    organization_id = _uuid(args.organization_id, field="organization_id")
    provider_id = _uuid(args.provider_id, field="provider_id")
    model_id = _uuid(args.model_id, field="model_id")
    if not 1 <= args.search_limit <= 8:
        raise EvaluationConfigurationError("search_limit must be between 1 and 8")

    dataset_eligible = bool(dataset.get("production_labelled")) and bool(
        dataset.get("retrieval_labels_human_reviewed")
    )
    evaluation_run_id = str(uuid.uuid4())
    generated_at = datetime.now(UTC).isoformat()
    evaluations = []
    case_reports: list[dict[str, Any]] = []
    review_packet_cases: list[dict[str, Any]] = []
    review_pairs: list[dict[str, Any]] = []

    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        headers=headers,
        follow_redirects=False,
        timeout=args.timeout_seconds,
    ) as client:
        for case in cases:
            search_response = client.get(
                f"/organizations/{organization_id}/search",
                params={
                    "q": case["question"],
                    "mode": "hybrid",
                    "limit": args.search_limit,
                },
            )
            search_payload = _json_object(search_response)
            retrieved = (
                _search_event_ids(search_payload)
                if search_response.status_code == 200
                else []
            )

            started = time.perf_counter()
            ask_response = client.post(
                f"/organizations/{organization_id}/ask-brain",
                json={
                    "question": case["question"],
                    "provider_configuration_id": provider_id,
                    "model_configuration_id": model_id,
                    "search_mode": "hybrid",
                    "search_limit": args.search_limit,
                },
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            ask_payload = _json_object(ask_response)
            actual_status = (
                str(ask_payload.get("status"))
                if ask_response.status_code == 200 and ask_payload is not None
                else f"http_{ask_response.status_code}"
            )
            pairs, packet_claims, unresolved = _answer_review_data(ask_payload)
            cited = [pair["canonical_event_id"] for pair in pairs]
            evaluation = evaluate_case(
                case_id=case["id"],
                expected_status=case["expected_status"],
                actual_status=actual_status,
                supporting_canonical_event_ids=case["supporting"],
                forbidden_canonical_event_ids=case["forbidden"],
                retrieved_canonical_event_ids=retrieved,
                cited_canonical_event_ids=cited,
                unresolved_citations=unresolved,
            )
            evaluations.append(evaluation)
            case_pairs = [{"case_id": case["id"], **pair} for pair in pairs]
            review_pairs.extend(case_pairs)
            case_reports.append(
                {
                    **asdict(evaluation),
                    "search_http_status": search_response.status_code,
                    "ask_http_status": ask_response.status_code,
                    "ask_latency_ms": latency_ms,
                    "ai_request_id": (
                        ask_payload.get("ai_request_id")
                        if isinstance(ask_payload, dict)
                        else None
                    ),
                    "claim_citation_pairs": case_pairs,
                }
            )
            review_packet_cases.append(
                {
                    "case_id": case["id"],
                    "question": case["question"],
                    "actual_status": actual_status,
                    "claims": packet_claims,
                }
            )

    summary = summarize_evaluation(
        evaluations,
        dataset_eligible=dataset_eligible,
    )
    report = {
        "schema_version": 2,
        "evaluation_run_id": evaluation_run_id,
        "generated_at": generated_at,
        "dataset_id": dataset.get("dataset_id", "unknown"),
        "dataset_production_labelled": bool(dataset.get("production_labelled")),
        "retrieval_labels_human_reviewed": bool(
            dataset.get("retrieval_labels_human_reviewed")
        ),
        "provider_id": provider_id,
        "model_id": model_id,
        "search_limit": args.search_limit,
        "summary": asdict(summary),
        "cases": case_reports,
        "content_retained": False,
    }
    report_bytes = _write_private_json(args.output, report)
    report_sha256 = hashlib.sha256(report_bytes).hexdigest()

    review_packet = {
        "schema_version": 1,
        "evaluation_run_id": evaluation_run_id,
        "automatic_report_sha256": report_sha256,
        "sensitive_customer_content": True,
        "generated_at": generated_at,
        "cases": review_packet_cases,
    }
    _write_private_json(args.review_packet, review_packet)

    review_template = {
        "schema_version": 1,
        "evaluation_run_id": evaluation_run_id,
        "automatic_report_sha256": report_sha256,
        "dataset_id": report["dataset_id"],
        "reviewer": "",
        "reviewed_at": "",
        "reviews": [
            {
                "case_id": pair["case_id"],
                "claim_index": pair["claim_index"],
                "citation_index": pair["citation_index"],
                "canonical_event_id": pair["canonical_event_id"],
                "supported": None,
            }
            for pair in review_pairs
        ],
    }
    _write_private_json(args.review_template, review_template)

    print(
        "Ask Brain automatic evaluation: "
        f"retrieval_recall={summary.retrieval_recall:.2%} "
        f"citation_target_precision={summary.citation_target_precision:.2%} "
        f"status_accuracy={summary.status_accuracy:.2%} "
        f"forbidden_exposures={summary.forbidden_exposures} "
        f"contract_failures={summary.contract_failures}"
    )
    print(
        "Semantic citation correctness is not inferred automatically. "
        f"Review the sensitive packet at {args.review_packet} and complete "
        f"{args.review_template}."
    )
    if not dataset_eligible:
        print(
            "Dataset is not eligible for production evidence: production_labelled "
            "and retrieval_labels_human_reviewed must both be true.",
            file=sys.stderr,
        )
        return 3
    return 0 if summary.automatic_gate_passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the automatic phase of the deployed Ask Brain evaluation"
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", default=".evaluation/ask-brain-report.json")
    parser.add_argument(
        "--review-packet",
        default=".evaluation/ask-brain-review-packet.json",
    )
    parser.add_argument(
        "--review-template",
        default=".evaluation/ask-brain-review.json",
    )
    parser.add_argument("--search-limit", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.timeout_seconds > 120:
        print("timeout_seconds must be between 0 and 120", file=sys.stderr)
        return 64
    try:
        return _run(args)
    except (EvaluationConfigurationError, httpx.HTTPError, ValueError) as exc:
        print(f"Ask Brain evaluation error: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
