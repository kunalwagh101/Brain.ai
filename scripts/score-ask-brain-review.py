#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.ask_brain_evaluation import (
    CitationPairReview,
    ObservedCitationPair,
    score_semantic_reviews,
)


class ReviewConfigurationError(RuntimeError):
    pass


def _load_object(path: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = Path(path).read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewConfigurationError(f"could not read JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ReviewConfigurationError(f"JSON root must be an object: {path}")
    return payload, raw


def _review_timestamp(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewConfigurationError("reviewed_at is required")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ReviewConfigurationError("reviewed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ReviewConfigurationError("reviewed_at must include a timezone")
    return value.strip()


def _observed_pairs(report: dict[str, Any]) -> list[ObservedCitationPair]:
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ReviewConfigurationError("automatic report cases are missing")
    result: list[ObservedCitationPair] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ReviewConfigurationError("automatic report case is invalid")
        pairs = case.get("claim_citation_pairs")
        if not isinstance(pairs, list):
            raise ReviewConfigurationError("automatic report citation pairs are missing")
        for pair in pairs:
            if not isinstance(pair, dict):
                raise ReviewConfigurationError("automatic report citation pair is invalid")
            try:
                result.append(
                    ObservedCitationPair(
                        case_id=str(pair["case_id"]),
                        claim_index=int(pair["claim_index"]),
                        citation_index=int(pair["citation_index"]),
                        canonical_event_id=str(pair["canonical_event_id"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ReviewConfigurationError(
                    "automatic report citation pair is malformed"
                ) from exc
    return result


def _reviews(payload: dict[str, Any]) -> list[CitationPairReview]:
    values = payload.get("reviews")
    if not isinstance(values, list):
        raise ReviewConfigurationError("review file reviews are missing")
    result: list[CitationPairReview] = []
    for value in values:
        if not isinstance(value, dict):
            raise ReviewConfigurationError("review entry is invalid")
        supported = value.get("supported")
        if not isinstance(supported, bool):
            raise ReviewConfigurationError(
                "every claim-citation pair must be reviewed as true or false"
            )
        try:
            result.append(
                CitationPairReview(
                    case_id=str(value["case_id"]),
                    claim_index=int(value["claim_index"]),
                    citation_index=int(value["citation_index"]),
                    canonical_event_id=str(value["canonical_event_id"]),
                    supported=supported,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ReviewConfigurationError("review entry is malformed") from exc
    return result


def _write_private_json(path: str, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output.chmod(0o600)


def _run(args: argparse.Namespace) -> int:
    report, report_raw = _load_object(args.report)
    review, _ = _load_object(args.review)
    if report.get("schema_version") != 2:
        raise ReviewConfigurationError("automatic report schema_version must be 2")
    if review.get("schema_version") != 1:
        raise ReviewConfigurationError("review schema_version must be 1")

    run_id = report.get("evaluation_run_id")
    if not isinstance(run_id, str) or review.get("evaluation_run_id") != run_id:
        raise ReviewConfigurationError("review does not match evaluation_run_id")
    report_sha256 = hashlib.sha256(report_raw).hexdigest()
    if review.get("automatic_report_sha256") != report_sha256:
        raise ReviewConfigurationError("review is not bound to this automatic report")
    if review.get("dataset_id") != report.get("dataset_id"):
        raise ReviewConfigurationError("review dataset_id does not match report")

    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ReviewConfigurationError("reviewer is required")
    reviewed_at = _review_timestamp(review.get("reviewed_at"))

    summary_value = report.get("summary")
    if not isinstance(summary_value, dict):
        raise ReviewConfigurationError("automatic report summary is missing")
    dataset_eligible = bool(summary_value.get("dataset_eligible"))
    automatic_gate_passed = bool(summary_value.get("automatic_gate_passed"))

    summary = score_semantic_reviews(
        _observed_pairs(report),
        _reviews(review),
        dataset_eligible=dataset_eligible,
        automatic_gate_passed=automatic_gate_passed,
    )
    final_report = {
        "schema_version": 1,
        "evaluation_run_id": run_id,
        "automatic_report_sha256": report_sha256,
        "dataset_id": report.get("dataset_id"),
        "provider_id": report.get("provider_id"),
        "model_id": report.get("model_id"),
        "reviewer": reviewer.strip(),
        "reviewed_at": reviewed_at,
        "summary": asdict(summary),
        "content_retained": False,
    }
    _write_private_json(args.output, final_report)

    print(
        "Ask Brain semantic citation review: "
        f"citation_correctness={summary.citation_correctness:.2%} "
        f"pairs={summary.citation_pairs} "
        f"review_complete={summary.review_complete} "
        f"production_passed={summary.production_passed}"
    )
    return 0 if summary.production_passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score human-reviewed Ask Brain claim-citation pairs"
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument(
        "--output",
        default=".evaluation/ask-brain-reviewed-report.json",
    )
    args = parser.parse_args()
    try:
        return _run(args)
    except (ReviewConfigurationError, ValueError) as exc:
        print(f"Ask Brain review error: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
