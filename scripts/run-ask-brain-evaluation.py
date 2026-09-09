#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import asdict
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
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise EvaluationConfigurationError("evaluation dataset schema_version must be 1")
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


def _answer_citation_event_ids(
    payload: dict[str, Any] | None,
) -> tuple[list[str], int]:
    if payload is None:
        return [], 0
    citations = payload.get("citations")
    claims = payload.get("claims")
    if not isinstance(citations, list) or not isinstance(claims, list):
        return [], 0

    citation_map: dict[str, str] = {}
    for item in citations:
        if not isinstance(item, dict):
            continue
        evidence_id = item.get("evidence_id")
        event_id = item.get("canonical_event_id")
        if isinstance(evidence_id, str) and isinstance(event_id, str):
            citation_map[evidence_id] = event_id

    resolved: list[str] = []
    unresolved = 0
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        citation_ids = claim.get("citation_ids")
        if not isinstance(citation_ids, list):
            continue
        for evidence_id in citation_ids:
            if not isinstance(evidence_id, str) or evidence_id not in citation_map:
                unresolved += 1
                continue
            resolved.append(citation_map[evidence_id])
    return resolved, unresolved


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


def _run(args: argparse.Namespace) -> int:
    dataset = _load_dataset(args.dataset)
    cases = [_case_config(item) for item in dataset["cases"]]
    headers = _headers()
    organization_id = _uuid(args.organization_id, field="organization_id")
    provider_id = _uuid(args.provider_id, field="provider_id")
    model_id = _uuid(args.model_id, field="model_id")
    if not 1 <= args.search_limit <= 8:
        raise EvaluationConfigurationError("search_limit must be between 1 and 8")

    eligible = bool(dataset.get("production_labelled")) and bool(
        dataset.get("human_reviewed")
    )
    evaluations = []
    case_reports: list[dict[str, Any]] = []

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
            retrieved = _search_event_ids(search_payload) if search_response.status_code == 200 else []

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
            cited, unresolved = _answer_citation_event_ids(ask_payload)
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
            case_reports.append(
                {
                    **asdict(evaluation),
                    "search_http_status": search_response.status_code,
                    "ask_http_status": ask_response.status_code,
                    "ask_latency_ms": latency_ms,
                }
            )

    summary = summarize_evaluation(
        evaluations,
        eligible_for_production_claim=eligible,
    )
    report = {
        "schema_version": 1,
        "dataset_id": dataset.get("dataset_id", "unknown"),
        "dataset_production_labelled": bool(dataset.get("production_labelled")),
        "dataset_human_reviewed": bool(dataset.get("human_reviewed")),
        "provider_id": provider_id,
        "model_id": model_id,
        "search_limit": args.search_limit,
        "summary": asdict(summary),
        "cases": case_reports,
        "content_retained": False,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "Ask Brain evaluation: "
        f"retrieval_recall={summary.retrieval_recall:.2%} "
        f"citation_correctness={summary.citation_correctness:.2%} "
        f"status_accuracy={summary.status_accuracy:.2%} "
        f"forbidden_exposures={summary.forbidden_exposures} "
        f"contract_failures={summary.contract_failures}"
    )
    if not eligible:
        print(
            "Dataset is not eligible for production evidence: "
            "production_labelled and human_reviewed must both be true.",
            file=sys.stderr,
        )
        return 3
    return 0 if summary.passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the labelled deployed Ask Brain evaluation"
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", default=".evaluation/ask-brain-report.json")
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
