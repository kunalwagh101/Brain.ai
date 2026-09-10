# Executive Overview — F-07.02

Story: `S-07.02.01`

The Executive Overview is a permission-aware read model over existing Brain sources of truth. It does not persist a second executive state and it does not ask an LLM to invent progress, risk or spend.

## Endpoint

`GET /api/v1/organizations/{organization_id}/executive-overview`

Required permission: `audit.read`.

The Executive role has `audit.read`; Owner/Admin also have it. Organisation membership is still checked first. Project content remains resource-aware: role alone does not make a restricted project visible.

## Data flow

1. S-07.01 Project Status returns every project currently visible to the caller.
2. S-04.02 supplies candidate/confirmed decision and blocker memory already intersected with current evidence permissions.
3. S-06.02 supplies AI request/token/cost records and budget snapshots.
4. S-06.03 supplies trusted external API usage observations and credential lifecycle state.
5. The executive service computes deterministic portfolio counts, month-to-date spend/activity and risk flags.
6. Every metric family includes provenance describing its source records, calculation, source count, period and drill-down where a real drill-down endpoint exists.

## Portfolio

Each visible project contains:

- project Work Graph node ID and name;
- deterministic status from S-07.01;
- deterministic progress percentage or `null` when structured progress is unconfigured;
- progress basis;
- active confirmed blocker count;
- confirmed decision count;
- machine-candidate memory count;
- authorised evidence count;
- provenance pointing to the full project-status view.

The organisation summary exposes separate counts for `blocked`, `in_progress`, `done`, `not_started` and `unconfigured` so every valid S-07.01 state reconciles to the visible portfolio.

Restricted projects are omitted unless the current user has the underlying Work Graph/resource access. The endpoint never substitutes an organisation role for a resource grant.

## Decisions and blockers

The organisation-level `active_blockers` and `confirmed_decisions` collections contain only human-confirmed S-04.02 memory that is visible through currently authorised project evidence.

A memory item contains its canonical/search/work-graph source identifiers plus all visible projects to which it contributes. If one confirmed blocker is linked to multiple visible projects, it is returned once with multiple project links and counted once in the organisation-level blocker count.

Machine-only candidates remain visible only as project candidate counts; they are never promoted into confirmed executive facts.

## AI spend

AI spend is month-to-date in UTC and uses the existing S-06.02 cost ledger.

The response includes:

- request/success/failure counts;
- known-cost and unknown-cost successful request counts;
- total input, cached-input and output tokens;
- known spend in integer nano-USD;
- provider breakdown;
- `cost_complete`.

`cost_complete=false` whenever at least one successful request in the period does not have a calculated cost. Unknown spend is never converted to zero.

## Budget warnings

Only enabled policies are evaluated. A warning is included when:

- known spend reaches the configured warning threshold; or
- budget enforcement is incomplete because successful AI requests have unknown cost.

The response includes exact known spend, limit, percentage used, threshold, hard-limit flag, exhaustion and enforcement completeness.

A Work-Graph-scoped budget is returned only if its target project/track/work-item is currently visible to the caller. Hidden target IDs must not leak through the executive endpoint.

## External API usage and monetary cost

S-06.03 currently provides trusted external API usage observations but no provider tariff/rate-card/cost ledger.

Therefore the Executive Overview returns real month-to-date API activity by service, success/failure counts and currently usable grant count, but deliberately returns:

- `known_spend_nano_usd = null`
- `cost_status = "not_modeled"`

This is intentional. Call counts, latency and credential presence are not a defensible monetary-cost model. A future API-cost feature must introduce explicit reviewed pricing/allocation semantics before money is displayed.

The provenance drill-down `/api/v1/organizations/{organization_id}/api-registry/usage` is protected by `audit.read` and exposes usage/service identifiers only; it does not expose credential values or secret references.

## Deterministic risk rules

The service may return these evidence-backed risks:

- `project_blocked:*` — only when S-07.01 says a visible project is blocked from a human-confirmed blocker or an explicitly blocked configured work item;
- `budget:*` — warning threshold reached, budget exhausted, or cost-unknown enforcement incomplete;
- `ai_cost_incomplete` — successful AI requests have unknown monetary cost;
- `external_api_cost_not_modeled` — external API usage exists but Brain has no monetary API cost model.

There is no generic AI-written risk score.

## Employee scoring prohibition

The endpoint does not calculate or return employee productivity, worth, performance ranking, message-count score, coding-output score or inferred employee value.

There is deliberately **no employee productivity-score field in the API schema**. This is regression-tested by asserting that productivity-score keys are absent rather than present with a null value.

Usage/cost governance may still contain user attribution where required for budget/cost accountability; that data must not be repurposed as a productivity score.

## Privacy and secrets

The Executive Overview never returns:

- AI prompt/completion plaintext from the request ledger;
- provider API keys;
- WorkOS tokens;
- integration secret references;
- API credential values;
- hidden project names/evidence merely because the caller is an executive.

## Performance note

The first MVP implementation deliberately computes aggregate project metrics from the full caller-visible S-07.01 portfolio instead of silently truncating counts to a page limit. Before production-scale acceptance, staging performance must measure realistic organisation sizes. If pagination/materialisation is later needed, it must preserve exact aggregate semantics rather than changing the numbers based on the displayed page.

## Acceptance status

Repository implementation and tests may be staged while dependencies remain blocked. This document is not acceptance evidence. See `UAT/F-07.02.md` and `docs/planning/increment-21.md` for the required production verification path.
