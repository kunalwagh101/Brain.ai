# Increment 21 — F-07.02 Executive Overview

Story: `S-07.02.01`

Implementation branch: `increment-10-ai-provider-gateway` (reused by explicit project-owner direction; no new branch).

Formal state: **BLOCKED** until `S-07.01.01` and `S-06.02.01` satisfy their engineering-DONE gates. The backend implementation is staged against their existing contracts, but implementation presence does not waive dependency or acceptance requirements.

## Goal

Give authorised leaders one evidence-backed organisation pulse across projects, blockers, decisions, AI spend, API activity and budget risk without fabricating project progress, monetary API cost or employee productivity scores.

## Vertical slice

`AUDIT_READ executive -> permission-filtered S-07.01 project portfolio -> confirmed S-04.02 memory -> S-06.02 AI usage/cost/budgets -> S-06.03 API usage observations -> deterministic risks + metric provenance -> executive-overview API`

## Implemented scope

- Month-to-date executive overview API under `/api/v1/organizations/{organization_id}/executive-overview`.
- `audit.read` required before organisation-wide spend/governance metrics are returned.
- Project portfolio reuses the current Work Graph/Search permission boundary from S-07.01; restricted projects are not included merely because the caller is an executive.
- Per-project deterministic status/progress plus blocker/decision/candidate/evidence counts and a drill-down provenance contract.
- Complete portfolio status buckets for `blocked`, `in_progress`, `done`, `not_started` and `unconfigured`.
- Organisation-level active blockers and confirmed decisions expose the actual human-confirmed memory records with source IDs and visible project links; machine-only candidates are not promoted to executive facts.
- AI usage reports request/token totals, cached input tokens, provider breakdown and known nano-USD spend from the existing exact-cost ledger.
- Unknown successful-request costs remain counted and make `cost_complete=false`; zero is never substituted for unknown spend.
- Enabled AI budgets are evaluated using the existing calendar-month budget snapshot math. Work-Graph-scoped budget warnings are exposed only when that target node is visible to the caller.
- External API usage is aggregated from trusted `APIUsageObservation` records and active credential grants.
- External API monetary spend is deliberately `null` with `cost_status=not_modeled` because S-06.03 has no provider tariff/cost ledger. Brain does not infer money from call counts.
- Deterministic risk entries are limited to blocked projects, budget warning/exhaustion/incomplete enforcement, incomplete AI cost, and the explicit absence of an API monetary-cost model when API activity exists.
- Every executive metric family carries source-record/calculation/drill-down provenance.
- The response contract contains no employee ranking, employee worth score, productivity score or productivity-score field.
- Backend contract tests, documentation and UAT are staged but intentionally not claimed as executed in this implementation pass.

## Security invariants

1. `audit.read` is required for the executive endpoint.
2. Organisation membership/tenant validation occurs before endpoint execution.
3. Project visibility is still resource-aware; an executive role alone does not grant access to restricted Work Graph nodes.
4. Work-Graph-scoped budget warnings cannot reveal hidden project/work-item target IDs.
5. Executive project/memory content comes only from the caller's currently visible S-07.01/S-04.02 view.
6. AI spend is organisation-level governance data exposed only to `audit.read`; it does not expose prompt/completion plaintext.
7. API aggregation exposes service/usage metadata only and never secret references or credential values.

## Metric contracts

- `visible_project_count` and status counts: deterministic count of S-07.01 project snapshots visible to the caller.
- `progress_percent`: unchanged S-07.01 weighted structured-work calculation; `null` when unconfigured.
- `active_blocker_count`: unique human-confirmed visible blocker IDs across visible projects.
- `confirmed_decision_count`: unique human-confirmed visible decision IDs across visible projects.
- `ai_spend.known_spend_nano_usd`: sum of calculated S-06.02 request-cost records for the current UTC calendar month through request time.
- `ai_spend.cost_complete`: false whenever a successful AI request in the period lacks a calculated cost.
- `budget_warnings`: current enabled policy snapshots whose warning threshold is reached or whose enforcement is incomplete because of unknown cost.
- `api_usage`: trusted S-06.03 observations for the same month-to-date period.
- `api_usage.known_spend_nano_usd`: always `null` until an explicit API pricing/cost contract exists.

## Explicit non-goals

- No AI-written executive status or risk score.
- No inferred completion percentage.
- No employee productivity, worth, activity-ranking or surveillance score or API field reserved for one.
- No conversion of API call count/latency into monetary cost.
- No weakening of project ACLs for Owner/Admin/Executive convenience.
- No separate executive data store that can become stale from source truth.
- No frontend authentication workaround; WorkOS remains part of the later acceptance phase.

## Acceptance gates still required

1. `S-05.01.01` permission-aware retrieval verification passes locally and on Render when the project owner performs the deferred gate.
2. `S-02.04`, `S-05.02`, `S-04.02`, `S-06.02` and `S-07.01` receive their required executable evidence in dependency order.
3. Executive-overview tests and all dependent backend suites execute successfully on PostgreSQL with migrations at head.
4. Two-user restricted-project UAT proves the executive view omits hidden project names, progress, decisions, blockers, evidence and work-graph-scoped budget target IDs.
5. AI spend is independently reconciled against request-scoped cost records, including cached-token pricing and unknown-cost behavior.
6. Budget warning/exhaustion states are independently recomputed from policy limits and exact known spend.
7. API usage counts are reconciled against trusted API observations; API monetary cost remains unavailable unless a later reviewed cost model is introduced.
8. Production WorkOS frontend renders the organisation pulse and drill-down provenance without exposing tokens/secrets.
9. Manual browser/accessibility UAT passes and confirms no employee productivity-score field or presentation exists.

Until those gates pass, `S-07.02.01` must not be represented as `DONE` or `PASSED`.
