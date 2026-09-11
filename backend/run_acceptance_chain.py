from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Stage:
    story: str
    name: str
    tests: tuple[str, ...]


STAGES = (
    Stage("S-05.01.01", "Authentication + Permission-Aware Retrieval", (
        "tests/test_auth.py",
        "tests/test_permissions.py",
        "tests/test_organizations.py",
        "tests/test_search.py",
        "tests/test_search_evaluation.py",
        "tests/test_search_contract.py",
    )),
    Stage("S-02.04.01", "Meeting/Document Evidence", (
        "tests/test_evidence_ingestion.py",
        "tests/test_evidence_workspace.py",
    )),
    Stage("S-05.02.01", "Ask Brain + Governed AI/Cost Dependencies", (
        "tests/test_ai_gateway.py",
        "tests/test_ai_gateway_adapter.py",
        "tests/test_ai_gateway_routes.py",
        "tests/test_ai_cached_cost.py",
        "tests/test_ai_cost_routes.py",
        "tests/test_ai_usage.py",
        "tests/test_ai_usage_reconciliation.py",
        "tests/test_runtime_discovery.py",
        "tests/test_ask_brain.py",
        "tests/test_ask_brain_citations.py",
        "tests/test_ask_brain_contract_hardening.py",
        "tests/test_ask_brain_evaluation.py",
        "tests/test_ask_brain_generic_evidence.py",
        "tests/test_ask_brain_limits.py",
        "tests/test_ask_brain_routes.py",
    )),
    Stage("S-04.02.01", "Decision & Blocker Memory", (
        "tests/test_decision_memory.py",
        "tests/test_decision_memory_evaluation.py",
        "tests/test_decision_memory_generic_evidence.py",
    )),
    Stage("S-07.01.01", "Project Command Centre", (
        "tests/test_project_status.py",
        "tests/test_project_status_routes.py",
    )),
    Stage("S-07.02.01", "Executive Overview", (
        "tests/test_executive_overview.py",
        "tests/test_executive_overview_budget_permissions.py",
        "tests/test_executive_overview_memory.py",
        "tests/test_api_registry.py",
        "tests/test_api_registry_worker.py",
        "tests/test_api_registry_usage_route.py",
    )),
)


def _run(command: list[str]) -> int:
    return int(subprocess.run(command, check=False).returncode)


def _database_mode() -> str:
    return "postgresql" if os.getenv("BRAIN_TEST_DATABASE_URL", "").strip() else "portable"


def _write_report(path: Path | None, report: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Brain's ordered backend acceptance chain without claiming UAT."
    )
    parser.add_argument("--lint", action="store_true")
    parser.add_argument("--require-postgres", action="store_true")
    parser.add_argument("--through", choices=[stage.story for stage in STAGES])
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    mode = _database_mode()
    if args.require_postgres and mode != "postgresql":
        print(
            "ACCEPTANCE BLOCKED: --require-postgres was set but "
            "BRAIN_TEST_DATABASE_URL is empty.",
            file=sys.stderr,
        )
        return 2

    report: dict[str, object] = {
        "started_at": datetime.now(UTC).isoformat(),
        "database_mode": mode,
        "commit_sha": (
            os.getenv("RENDER_GIT_COMMIT")
            or os.getenv("GITHUB_SHA")
            or os.getenv("BRAIN_ACCEPTANCE_COMMIT_SHA")
            or "unknown"
        ),
        "uat_claimed": False,
        "stages": [],
    }
    print(f"ACCEPTANCE MODE: {mode}")
    print("NOTE: passing backend stages are executable evidence only; they are not UAT.")

    if args.lint:
        print("LINT START: ruff check app tests migrations", flush=True)
        lint_code = _run(["ruff", "check", "app", "tests", "migrations"])
        report["lint_exit_code"] = lint_code
        if lint_code != 0:
            report["finished_at"] = datetime.now(UTC).isoformat()
            report["result"] = "failed"
            _write_report(args.report, report)
            print("LINT FAIL", file=sys.stderr)
            return lint_code
        print("LINT PASS", flush=True)

    stage_reports = report["stages"]
    assert isinstance(stage_reports, list)

    for stage in STAGES:
        print(f"STAGE START {stage.story}: {stage.name}", flush=True)
        started = time.monotonic()
        exit_code = _run([sys.executable, "-m", "pytest", "-q", *stage.tests])
        elapsed = round(time.monotonic() - started, 3)
        stage_reports.append({
            "story": stage.story,
            "name": stage.name,
            "tests": list(stage.tests),
            "exit_code": exit_code,
            "elapsed_seconds": elapsed,
            "result": "passed" if exit_code == 0 else "failed",
        })

        if exit_code != 0:
            report["finished_at"] = datetime.now(UTC).isoformat()
            report["result"] = "failed"
            report["failed_story"] = stage.story
            _write_report(args.report, report)
            print(f"STAGE FAIL {stage.story}: {stage.name}", file=sys.stderr)
            print(
                "DOWNSTREAM STAGES NOT RUN: dependency evidence must remain blocked.",
                file=sys.stderr,
            )
            return exit_code

        print(f"STAGE PASS {stage.story}: {stage.name}", flush=True)
        if args.through == stage.story:
            break

    report["finished_at"] = datetime.now(UTC).isoformat()
    report["result"] = "passed"
    _write_report(args.report, report)
    print("BACKEND ACCEPTANCE CHAIN PASS")
    print("UAT STATUS: NOT CLAIMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
