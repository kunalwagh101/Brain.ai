#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from app.performance_budget import PerformanceBudget, evaluate_budget, summarize_performance

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class BenchmarkConfigurationError(RuntimeError):
    pass


def _expand(value: Any) -> Any:
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            resolved = os.getenv(name)
            if resolved is None:
                raise BenchmarkConfigurationError(
                    f"Required environment variable is missing: {name}"
                )
            return resolved

        return _ENV_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_expand(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand(item) for key, item in value.items()}
    return value


def _enabled(scenario: dict[str, Any]) -> bool:
    enabled_env = scenario.get("enabled_env")
    if not enabled_env:
        return True
    return os.getenv(str(enabled_env), "").strip().lower() in {"1", "true", "yes", "on"}


def _headers(scenario: dict[str, Any]) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    auth_env = scenario.get("auth_env")
    if auth_env:
        token = os.getenv(str(auth_env))
        if not token:
            raise BenchmarkConfigurationError(
                f"Required benchmark bearer token is missing: {auth_env}"
            )
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _single_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    *,
    method: str,
    path: str,
    headers: dict[str, str],
    query: dict[str, Any] | None,
    body: dict[str, Any] | None,
    expected_statuses: set[int],
    timeout_seconds: float,
) -> tuple[float, bool, int | None, str | None]:
    async with semaphore:
        started = time.perf_counter()
        try:
            response = await client.request(
                method,
                path,
                headers=headers,
                params=query,
                json=body,
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            return (
                elapsed_ms,
                response.status_code in expected_statuses,
                response.status_code,
                None,
            )
        except httpx.TimeoutException:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return elapsed_ms, False, None, "timeout"
        except httpx.HTTPError:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return elapsed_ms, False, None, "transport_error"


async def _usage_snapshot(
    client: httpx.AsyncClient,
    scenario: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, int] | None:
    tracking = scenario.get("cost_tracking")
    if not isinstance(tracking, dict):
        return None
    path = _expand(tracking["summary_path"])
    query = _expand(tracking.get("query", {}))
    response = await client.get(
        path,
        params=query,
        headers=headers,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("rows") or []
    return {
        "total_cost_nano_usd": sum(int(row.get("total_cost_nano_usd", 0)) for row in rows),
        "known_cost_requests": sum(int(row.get("known_cost_requests", 0)) for row in rows),
        "unknown_cost_requests": sum(int(row.get("unknown_cost_requests", 0)) for row in rows),
    }


def _cost_delta(
    before: dict[str, int] | None,
    after: dict[str, int] | None,
) -> dict[str, Any] | None:
    if before is None or after is None:
        return None
    total_cost = after["total_cost_nano_usd"] - before["total_cost_nano_usd"]
    known = after["known_cost_requests"] - before["known_cost_requests"]
    unknown = after["unknown_cost_requests"] - before["unknown_cost_requests"]
    return {
        "total_cost_nano_usd": max(0, total_cost),
        "known_cost_requests": max(0, known),
        "unknown_cost_requests": max(0, unknown),
        "exact_cost_complete": unknown <= 0,
    }


async def _run_scenario(
    client: httpx.AsyncClient,
    scenario: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    name = str(scenario["name"])
    requests = int(scenario.get("requests", defaults["requests"]))
    concurrency = int(scenario.get("concurrency", defaults["concurrency"]))
    warmup_requests = int(scenario.get("warmup_requests", defaults["warmup_requests"]))
    timeout_seconds = float(scenario.get("timeout_seconds", defaults["timeout_seconds"]))
    minimum_success_rate = float(
        scenario.get("minimum_success_rate", defaults["minimum_success_rate"])
    )
    if requests < 1 or concurrency < 1 or warmup_requests < 0 or timeout_seconds <= 0:
        raise BenchmarkConfigurationError(f"Invalid load configuration for scenario: {name}")

    method = str(scenario.get("method", "GET")).upper()
    path_template = str(scenario["path"])
    path = _expand(path_template)
    query = _expand(scenario.get("query"))
    body = _expand(scenario.get("body"))
    headers = _headers(scenario)
    expected_statuses = {int(code) for code in scenario.get("expected_statuses", [200])}
    semaphore = asyncio.Semaphore(concurrency)

    for _ in range(warmup_requests):
        await _single_request(
            client,
            semaphore,
            method=method,
            path=path,
            headers=headers,
            query=query,
            body=body,
            expected_statuses=expected_statuses,
            timeout_seconds=timeout_seconds,
        )

    cost_before = await _usage_snapshot(client, scenario, headers, timeout_seconds)
    started = time.perf_counter()
    outcomes = await asyncio.gather(
        *[
            _single_request(
                client,
                semaphore,
                method=method,
                path=path,
                headers=headers,
                query=query,
                body=body,
                expected_statuses=expected_statuses,
                timeout_seconds=timeout_seconds,
            )
            for _ in range(requests)
        ]
    )
    elapsed_seconds = time.perf_counter() - started
    cost_after = await _usage_snapshot(client, scenario, headers, timeout_seconds)

    latencies = [item[0] for item in outcomes]
    succeeded = sum(1 for item in outcomes if item[1])
    summary = summarize_performance(
        latencies,
        succeeded=succeeded,
        elapsed_seconds=elapsed_seconds,
    )
    cost = _cost_delta(cost_before, cost_after)
    cost_per_success: int | None = None
    if cost is not None and succeeded > 0:
        cost_per_success = cost["total_cost_nano_usd"] // succeeded

    budget = PerformanceBudget(
        p95_budget_ms=(
            float(scenario["p95_budget_ms"])
            if scenario.get("p95_budget_ms") is not None
            else None
        ),
        minimum_success_rate=minimum_success_rate,
        minimum_throughput_rps=(
            float(scenario["minimum_throughput_rps"])
            if scenario.get("minimum_throughput_rps") is not None
            else None
        ),
        maximum_cost_nano_usd_per_success=(
            int(scenario["maximum_cost_nano_usd_per_success"])
            if scenario.get("maximum_cost_nano_usd_per_success") is not None
            else None
        ),
    )
    tracking = scenario.get("cost_tracking")
    require_exact_cost = bool(
        isinstance(tracking, dict) and tracking.get("require_exact_cost", False)
    )
    evaluation = evaluate_budget(
        summary,
        budget,
        cost_nano_usd_per_success=cost_per_success,
        exact_cost_complete=(cost["exact_cost_complete"] if cost is not None else None),
        require_exact_cost=require_exact_cost,
    )

    status_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}
    for _, _, status_code, error_code in outcomes:
        if status_code is not None:
            key = str(status_code)
            status_counts[key] = status_counts.get(key, 0) + 1
        if error_code:
            error_counts[error_code] = error_counts.get(error_code, 0) + 1

    return {
        "name": name,
        "route_template": path_template,
        "method": method,
        "load": {
            "requests": requests,
            "concurrency": concurrency,
            "warmup_requests": warmup_requests,
            "timeout_seconds": timeout_seconds,
        },
        "summary": asdict(summary),
        "budget": asdict(budget),
        "evaluation": asdict(evaluation),
        "status_counts": status_counts,
        "error_counts": error_counts,
        "cost": (
            {
                **cost,
                "cost_nano_usd_per_success": cost_per_success,
                "isolated_test_org_required": True,
            }
            if cost is not None
            else None
        ),
    }


async def _run(args: argparse.Namespace) -> int:
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    defaults = config["defaults"]
    scenarios = config["scenarios"]
    reports: list[dict[str, Any]] = []
    skipped: list[str] = []

    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"),
        follow_redirects=False,
    ) as client:
        for scenario in scenarios:
            if not _enabled(scenario):
                skipped.append(str(scenario["name"]))
                continue
            try:
                reports.append(await _run_scenario(client, scenario, defaults))
            except BenchmarkConfigurationError:
                if scenario.get("required", False):
                    raise
                skipped.append(str(scenario["name"]))

    passed = all(item["evaluation"]["passed"] for item in reports)
    payload = {
        "schema_version": 1,
        "commit_sha": (
            os.getenv("GITHUB_SHA")
            or os.getenv("BRAIN_PERF_COMMIT_SHA")
            or "unknown"
        ),
        "base_url": args.base_url,
        "scenarios": reports,
        "skipped_scenarios": skipped,
        "passed": passed,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for report in reports:
        summary = report["summary"]
        verdict = "PASS" if report["evaluation"]["passed"] else "FAIL"
        print(
            f"{report['name']}: {verdict} "
            f"p50={summary['p50_ms']:.1f}ms p95={summary['p95_ms']:.1f}ms "
            f"p99={summary['p99_ms']:.1f}ms success={summary['success_rate']:.2%} "
            f"throughput={summary['throughput_rps']:.2f}rps"
        )
        if report["cost"] is not None:
            print(
                f"{report['name']}: cost_per_success_nano_usd="
                f"{report['cost']['cost_nano_usd_per_success']} "
                f"exact_complete={report['cost']['exact_cost_complete']}"
            )
        for reason in report["evaluation"]["reasons"]:
            print(f"  - {reason}")

    return 0 if passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Brain deployed performance budgets")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--config", default="ops/performance/budgets.json")
    parser.add_argument("--output", default=".performance/report.json")
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except (BenchmarkConfigurationError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"benchmark configuration error: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(main())
