# Increment 16 — measurable performance and cost budgets

Story: `S-09.04.01` / `F-09.04`.

Branch rule: continue on `increment-10-ai-provider-gateway`; no new branch is created.

## Goal

Make latency, throughput and AI-cost claims reproducible from a versioned workload and machine-readable deployed benchmark report, with explicit failure when agreed budgets regress.

## Dependency state

The benchmark machinery is buildable now, but the complete story remains externally/dependency blocked because:

- permission-aware search is still `IN_REVIEW` without executable passing verification;
- governed AI is still `IN_REVIEW` without executable passing verification;
- F-09.03 has not selected/verified the production-like staging runtime;
- GitHub Actions still fail before runner startup on the active branch.

Therefore implementation may be staged, but S-09.04.01 must not be called DONE/PASSED yet.

## Acceptance refinement

### AC1 — deterministic percentile math
Given a set of request latencies, when the benchmark summarizes them, then p50/p95/p99 use one documented deterministic method and the same samples always produce the same result.

### AC2 — versioned fixed workload
Given a benchmark run, then scenario request count, warmup, concurrency, timeout, route template and budget are loaded from a version-controlled configuration rather than ad-hoc shell values.

### AC3 — product SLO budgets are enforced
Given core/search/AI scenarios, when p95 exceeds 500 ms / 1.5 s / 10 s respectively, then the scenario returns a failed budget result.

### AC4 — errors cannot hide behind latency
Given measured requests, when success rate falls below the configured minimum, then the scenario fails even if successful responses are fast.

### AC5 — throughput is always reported
Given any measured scenario, then total measured requests divided by wall-clock measured duration is reported as requests/second. No throughput floor is invented before a representative baseline is agreed.

### AC6 — AI cost per successful evaluated task is reported
Given the isolated AI benchmark organisation and exact F-06.02 pricing/token attribution, when AI load runs, then the delta exact nano-USD cost divided by successful measured tasks is reported.

### AC7 — unknown AI cost fails exact-cost benchmark
Given `require_exact_cost=true`, when the benchmark produces any new unknown-cost request, then the AI scenario fails; unknown cost is never treated as zero.

### AC8 — cost ceiling is configurable but not invented
Given an agreed maximum AI cost-per-task later, when `maximum_cost_nano_usd_per_success` is configured and exceeded, then the scenario fails. Until an agreed value exists, the field remains unset.

### AC9 — benchmark artifacts contain no credentials/content
Given a benchmark report, then it may contain aggregate performance/cost metadata and route templates but not bearer tokens, prompts, completions, request bodies, response bodies or provider credentials.

### AC10 — deployed comparison is environment-aware
Given a claimed performance regression/improvement, then the compared reports record enough environment/workload context to establish that the comparison is materially like-for-like.

## Tasks

- `T-09.04.01.a` Add deterministic percentile/summary/budget engine.
- `T-09.04.01.b` Add versioned core/search/AI workload configuration.
- `T-09.04.01.c` Add async real-HTTP benchmark runner.
- `T-09.04.01.d` Add exact AI cost delta/reporting through F-06.02 usage ledger.
- `T-09.04.01.e` Add budget regression unit tests.
- `T-09.04.01.f` Add staging Performance Gate workflow and report artifact.
- `T-09.04.01.g` Document methodology, limitations and comparison rules.
- `T-09.04.01.h` Run production-like backend benchmark with representative data.
- `T-09.04.01.i` Record at least three comparable baseline runs before setting throughput/cost ceilings.
- `T-09.04.01.j` Perform frontend/manual performance acceptance.

## Rules

- Do not benchmark customer production data without explicit approved purpose and safeguards.
- Do not log or artifact authentication tokens or AI prompt/completion content.
- Do not call local SQLite/TestClient timing a production performance result.
- Do not alter an agreed threshold solely to make a regression pass.
- Do not compare unlike instance/data/provider configurations without clearly labeling the confounder.
- Search/AI latency claims require the corresponding vertical slice to be functionally verified first.
- A real AI benchmark should use a dedicated budget-limited test organisation.

## Current status

Implementation is staged. Formal status remains `BLOCKED` pending executable verification of the underlying search/AI verticals, an executable runner, and a production-like staging benchmark/UAT with real measurements.
