import json
from pathlib import Path

import pytest

from app.performance_budget import (
    PerformanceBudget,
    evaluate_budget,
    percentile_nearest_rank,
    summarize_performance,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_nearest_rank_percentiles_are_deterministic() -> None:
    samples = list(range(1, 101))
    assert percentile_nearest_rank(samples, 50) == 50
    assert percentile_nearest_rank(samples, 95) == 95
    assert percentile_nearest_rank(samples, 99) == 99


def test_summary_reports_success_latency_and_throughput() -> None:
    summary = summarize_performance(
        [10, 20, 30, 40, 50],
        succeeded=4,
        elapsed_seconds=0.5,
    )
    assert summary.requests == 5
    assert summary.succeeded == 4
    assert summary.failed == 1
    assert summary.success_rate == pytest.approx(0.8)
    assert summary.p50_ms == 30
    assert summary.p95_ms == 50
    assert summary.p99_ms == 50
    assert summary.throughput_rps == pytest.approx(10)


def test_latency_or_success_regression_fails_budget() -> None:
    summary = summarize_performance(
        [100, 200, 300, 600, 700],
        succeeded=4,
        elapsed_seconds=1,
    )
    evaluation = evaluate_budget(
        summary,
        PerformanceBudget(
            p95_budget_ms=500,
            minimum_success_rate=0.99,
        ),
    )
    assert not evaluation.passed
    assert any("p95_ms" in reason for reason in evaluation.reasons)
    assert any("success_rate" in reason for reason in evaluation.reasons)


def test_exact_ai_cost_requirement_fails_unknown_cost() -> None:
    summary = summarize_performance([100, 110, 120], succeeded=3, elapsed_seconds=1)
    evaluation = evaluate_budget(
        summary,
        PerformanceBudget(p95_budget_ms=10_000, minimum_success_rate=0.99),
        cost_nano_usd_per_success=5_000,
        exact_cost_complete=False,
        require_exact_cost=True,
    )
    assert not evaluation.passed
    assert evaluation.reasons == ("exact AI cost is incomplete for this scenario",)


def test_configured_ai_cost_ceiling_is_enforced_when_exact() -> None:
    summary = summarize_performance([100, 110, 120], succeeded=3, elapsed_seconds=1)
    evaluation = evaluate_budget(
        summary,
        PerformanceBudget(
            p95_budget_ms=10_000,
            minimum_success_rate=0.99,
            maximum_cost_nano_usd_per_success=4_000,
        ),
        cost_nano_usd_per_success=5_000,
        exact_cost_complete=True,
    )
    assert not evaluation.passed
    assert any("cost_nano_usd_per_success" in reason for reason in evaluation.reasons)


def test_checked_in_latency_budgets_match_product_slos() -> None:
    config = json.loads(
        (REPO_ROOT / "ops/performance/budgets.json").read_text(encoding="utf-8")
    )
    scenarios = {scenario["name"]: scenario for scenario in config["scenarios"]}
    assert scenarios["core_organization_read"]["p95_budget_ms"] == 500
    assert scenarios["permission_aware_search"]["p95_budget_ms"] == 1500
    assert scenarios["governed_ai_invoke"]["p95_budget_ms"] == 10_000
    assert scenarios["governed_ai_invoke"]["cost_tracking"]["require_exact_cost"] is True
    assert "maximum_cost_nano_usd_per_success" not in scenarios["governed_ai_invoke"]
