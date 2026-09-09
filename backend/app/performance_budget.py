from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class PerformanceSummary:
    requests: int
    succeeded: int
    failed: int
    success_rate: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    throughput_rps: float


@dataclass(frozen=True, slots=True)
class PerformanceBudget:
    p95_budget_ms: float | None
    minimum_success_rate: float
    minimum_throughput_rps: float | None = None
    maximum_cost_nano_usd_per_success: int | None = None


@dataclass(frozen=True, slots=True)
class BudgetEvaluation:
    passed: bool
    reasons: tuple[str, ...]


def percentile_nearest_rank(values: Iterable[float], percentile: float) -> float:
    samples = sorted(float(value) for value in values)
    if not samples:
        raise ValueError("At least one latency sample is required")
    if percentile <= 0 or percentile > 100:
        raise ValueError("percentile must be > 0 and <= 100")
    rank = max(1, math.ceil((percentile / 100) * len(samples)))
    return samples[rank - 1]


def summarize_performance(
    latencies_ms: Iterable[float],
    *,
    succeeded: int,
    elapsed_seconds: float,
) -> PerformanceSummary:
    samples = [float(value) for value in latencies_ms]
    if not samples:
        raise ValueError("At least one latency sample is required")
    if succeeded < 0 or succeeded > len(samples):
        raise ValueError("succeeded must be between 0 and request count")
    if elapsed_seconds <= 0:
        raise ValueError("elapsed_seconds must be positive")

    requests = len(samples)
    failed = requests - succeeded
    return PerformanceSummary(
        requests=requests,
        succeeded=succeeded,
        failed=failed,
        success_rate=succeeded / requests,
        p50_ms=percentile_nearest_rank(samples, 50),
        p95_ms=percentile_nearest_rank(samples, 95),
        p99_ms=percentile_nearest_rank(samples, 99),
        max_ms=max(samples),
        throughput_rps=requests / elapsed_seconds,
    )


def evaluate_budget(
    summary: PerformanceSummary,
    budget: PerformanceBudget,
    *,
    cost_nano_usd_per_success: int | None = None,
    exact_cost_complete: bool | None = None,
    require_exact_cost: bool = False,
) -> BudgetEvaluation:
    reasons: list[str] = []

    if summary.success_rate < budget.minimum_success_rate:
        reasons.append(
            "success_rate "
            f"{summary.success_rate:.4f} < {budget.minimum_success_rate:.4f}"
        )
    if budget.p95_budget_ms is not None and summary.p95_ms > budget.p95_budget_ms:
        reasons.append(
            f"p95_ms {summary.p95_ms:.2f} > {budget.p95_budget_ms:.2f}"
        )
    if (
        budget.minimum_throughput_rps is not None
        and summary.throughput_rps < budget.minimum_throughput_rps
    ):
        reasons.append(
            "throughput_rps "
            f"{summary.throughput_rps:.2f} < {budget.minimum_throughput_rps:.2f}"
        )

    exact_cost_missing = (
        exact_cost_complete is not True or cost_nano_usd_per_success is None
    )
    if require_exact_cost and exact_cost_missing:
        reasons.append("exact AI cost is incomplete for this scenario")
    if budget.maximum_cost_nano_usd_per_success is not None:
        if exact_cost_missing:
            reasons.append("exact AI cost is incomplete; configured cost budget cannot be evaluated")
        elif cost_nano_usd_per_success > budget.maximum_cost_nano_usd_per_success:
            reasons.append(
                "cost_nano_usd_per_success "
                f"{cost_nano_usd_per_success} > "
                f"{budget.maximum_cost_nano_usd_per_success}"
            )

    return BudgetEvaluation(passed=not reasons, reasons=tuple(dict.fromkeys(reasons)))
