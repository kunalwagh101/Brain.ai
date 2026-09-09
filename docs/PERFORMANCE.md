# Brain performance and cost budgets

Story: `S-09.04.01` / `F-09.04`.

## Purpose

Brain must not make scale, latency or AI-cost claims from intuition. Performance evidence is produced from a versioned workload, a known deployment, a fixed request count/concurrency level and a machine-readable report.

The initial latency budgets come from the existing production SLOs:

| Scenario | Initial p95 budget |
|---|---:|
| Core structured API | <500 ms |
| Permission-aware search | <1.5 s |
| Governed AI/provider call | <10 s |

These budgets are checked in at `ops/performance/budgets.json`.

No throughput floor or maximum AI cost-per-task is invented yet. Both fields are supported by the budget engine and may become enforced only after representative measured baselines and product economics establish an agreed value.

## Two levels of evidence

### Deterministic engineering tests

`backend/tests/test_performance_budget.py` validates:

- nearest-rank percentile calculation;
- p50/p95/p99/throughput summaries;
- success-rate and p95 regression failure;
- exact-cost fail-closed behavior;
- optional AI cost ceiling enforcement;
- checked-in latency budgets remain aligned with the product SLOs.

These tests verify the **budget machinery**, not production performance.

### Deployed benchmark

`scripts/run-performance-benchmark.py` generates a real HTTP load against a supplied staging/candidate URL.

Each scenario report includes:

- commit SHA when available;
- scenario and route template;
- request count;
- concurrency;
- warmup request count;
- request timeout;
- status/error counts;
- success rate;
- p50, p95, p99 and maximum latency;
- total throughput in requests/second;
- configured budget;
- pass/fail reasons;
- AI known/unknown cost delta and cost per successful task when cost tracking is enabled.

The report never contains the bearer token, request body, response body, prompt, completion or secret values.

## Workload configuration

The versioned workload is `ops/performance/budgets.json`.

Current default load:

- core organisation read: 100 measured requests, concurrency 10;
- permission-aware keyword search: 100 measured requests, concurrency 10;
- governed AI: 10 measured requests, concurrency 1, disabled unless explicitly enabled.

Warmup traffic is excluded from measured latency and AI cost snapshots.

The AI scenario uses low concurrency deliberately. External provider rate limits and per-call spend make a large uncontrolled AI load inappropriate as a default benchmark.

## Required environment

Core/search benchmark variables:

```text
BRAIN_PERF_BEARER_TOKEN=<real test-user token>
BRAIN_PERF_ORGANIZATION_ID=<isolated benchmark organisation UUID>
BRAIN_PERF_SEARCH_QUERY=<representative non-sensitive query>
```

Optional governed-AI benchmark:

```text
BRAIN_PERF_ENABLE_AI=true
BRAIN_PERF_PROVIDER_ID=<configured provider UUID>
BRAIN_PERF_MODEL_ID=<configured model UUID>
BRAIN_PERF_AI_PROMPT="Return exactly this word: acknowledged"
```

Use a dedicated test organisation with representative but non-sensitive data. Do not benchmark against a customer's live production tenant merely for convenience.

## Running manually

With the backend development package installed:

```bash
python scripts/run-performance-benchmark.py \
  --base-url https://staging.example.com \
  --config ops/performance/budgets.json \
  --output .performance/report.json
```

Exit codes:

- `0`: all enabled measured budgets passed;
- `2`: at least one measured budget failed;
- `64`: invalid/missing benchmark configuration.

Transport/HTTP-control errors also fail the run; do not convert them into latency success.

## Performance Gate workflow

`.github/workflows/performance-gate.yml` is manually dispatched against an isolated HTTPS staging candidate.

Why it is not a normal PR workflow:

- PRs do not own a stable production-like environment by default;
- shared staging load creates noisy cross-run measurements;
- a real AI scenario has external monetary cost;
- performance evidence must identify the actual deployed candidate being measured.

The workflow uses repository secrets for the benchmark bearer token and optional AI provider/model IDs. It uploads only `.performance/report.json`.

This workflow being present does not prove a benchmark has run. A real run URL/report is required evidence.

## AI cost per evaluated task

The AI scenario snapshots the existing F-06.02 organisation usage summary immediately before and after the measured requests.

For an isolated benchmark organisation:

```text
cost per successful evaluated task
  = delta exact known nano-USD cost / successful measured AI requests
```

The delta includes known cost incurred by failed measured calls if the provider reports/accounting resolves that cost, so retries/failures cannot make the benchmark appear artificially cheaper.

`require_exact_cost=true` means any new unknown-cost request makes the AI scenario fail. Unknown pricing or token accounting is never interpreted as zero.

The benchmark report marks that the cost delta assumes an isolated test organisation. Concurrent unrelated AI usage in the same organisation invalidates attribution and the run must be repeated in isolation.

## Regression policy

A measured scenario fails when any configured enforced condition is breached, including:

- success rate below the minimum;
- p95 latency above the checked-in budget;
- configured throughput floor not met;
- exact AI cost required but incomplete;
- configured maximum cost per successful task exceeded.

A failing performance report requires investigation/review. Do not simply increase the checked-in threshold to make CI green. A budget change requires a documented product/architecture reason and comparable before/after measurements.

## Interpreting results

A single short run proves only that workload/environment at that time.

Before making a scale claim, record at minimum:

- deployed commit/image digest;
- database topology and approximate representative data volume;
- instance/CPU/memory sizing;
- benchmark-region/network relationship;
- request/concurrency profile;
- p50/p95/p99;
- throughput;
- error rate;
- AI provider/model and exact cost completeness where relevant;
- at least three comparable runs when establishing a baseline.

Do not compare two reports produced against different instance sizes, data sizes or provider configurations as if they were a clean code regression experiment.

## Known limitations

- The current default throughput floor is unset because no representative baseline exists yet.
- The current maximum AI cost-per-task budget is unset because no product-economic target has been agreed yet.
- Search performance depends strongly on indexed data volume and PostgreSQL query plan; small fixtures cannot prove customer-scale latency.
- Governed AI p95 includes the external provider, so provider/model changes must be recorded when comparing runs.
- F-09.03 staging/runtime selection is still unresolved, so deployed performance UAT remains blocked until a suitable candidate environment exists.
