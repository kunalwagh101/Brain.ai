# AI Usage, Cost and Budgets

## Purpose

F-06.02 turns governed AI gateway requests into auditable usage and cost data. It does not infer spend from prompts, employee activity, or model guesses.

This feature is intentionally staged on the existing `increment-10-ai-provider-gateway` branch. No additional feature branch was created.

## Accounting unit

All configured rates and calculated costs use integer nano-USD:

`1 USD = 1,000,000,000 nano-USD`

A rate card stores `input_nano_usd_per_token` and `output_nano_usd_per_token`. Example: `$0.15 / 1M tokens` is exactly `150 nano-USD/token`.

For a request with provider-returned token counts:

`input_cost = input_tokens * input_nano_usd_per_token`

`output_cost = output_tokens * output_nano_usd_per_token`

`total_cost = input_cost + output_cost`

No floating-point arithmetic is used for persisted cost.

## Rate cards

Rate cards are tenant-scoped and tied to one configured provider/model. They have an explicit effective window and a human-readable `source_label` describing where the configured price came from. Overlapping rate windows for the same model are rejected by the service. The schema also prevents duplicate model/effective-start entries; concurrent overlap behavior must be verified against PostgreSQL before production acceptance rather than assumed from unit fixtures.

Brain does not scrape or silently update provider prices. An authorised operator must configure the source rate and effective date. Provider invoice reconciliation, taxes, credits, and currency conversion are outside this feature.

## Cost resolution states

Every successful request should converge to one `AIUsageCostRecord`:

- `calculated`: token counts and an effective rate card were available.
- `unknown`: exact cost could not be calculated.

Unknown reasons are bounded codes such as:

- `token_usage_unavailable`
- `rate_card_unavailable`

Unknown is not zero. Usage summaries expose unknown-cost request counts separately.

## Reconciliation

The gateway tries to materialise cost immediately after a successful provider response. A provider answer is not turned into an error merely because the subsequent accounting write has a transient database failure; doing that could cause a client retry and duplicate provider spend.

Run the bounded reconciliation worker to repair missing cost rows and to re-evaluate previously unknown costs after historical pricing is added:

```bash
cd backend
python -m app.ai_usage_worker --once --batch-size 100
```

On PostgreSQL concurrent workers claim request rows with `FOR UPDATE SKIP LOCKED`.

## Attribution

Request attribution is copied only from deterministic gateway fields:

- organisation
- provider
- model
- user
- optional Work Graph node

Allowed Work Graph attribution nodes are `project`, `track`, and `work_item`. A `track` can represent a team/workstream when the company has explicitly modelled it that way. Brain does not infer a missing team/project from prompt text.

A missing attribution node remains `NULL` and appears as an unknown attribution group in summaries.

## Read permissions

- rate-card and budget mutations: `ai.manage` (Owner/Admin)
- organisation-wide usage, cost, budget status and alerts: existing `audit.read` (Owner/Admin/Executive)
- ordinary Members and Guests cannot read organisation-wide spend

## Budget policies

Current budget period: UTC calendar month.

Supported scopes:

- organisation
- provider configuration
- model configuration
- Brain user who is a member of that organisation
- Work Graph project/track/work-item in that organisation

Scope targets are tenant-validated before storage. A canonical non-null `scope_key` makes the database uniqueness constraint work for organisation-wide budgets as well as targeted budgets.

A policy contains:

- nano-USD limit
- one warning threshold percentage
- automatic 100% threshold
- optional hard-stop flag
- enabled/disabled state

## Alerts

When known spend reaches the warning or 100% threshold, Brain inserts an alert. The database unique key is:

`budget_policy_id + period_start + threshold_percent`

Repeated evaluation, worker replay, or concurrent calls therefore cannot create duplicate alerts for the same threshold/month.

## Hard-stop semantics

Before provider credential lookup or external execution, the gateway checks every matching enabled hard budget. If known spend is already at or above a limit, the next request is blocked with an explicit budget-exhausted response.

This is a **post-exhaustion hard stop**, not a prepaid reservation system. Concurrent requests already in flight can make final spend exceed the configured limit. Exact pre-reservation would require a deterministic upper-bound cost before provider execution, which is not currently available for arbitrary provider tokenisation. This limitation must remain visible rather than being described as an exact financial cap.

If a period contains unknown-cost requests, the budget snapshot returns `enforcement_complete=false`. Brain does not pretend the known-spend value is the full invoice.

## API

Under `/api/v1/organizations/{organization_id}/ai`:

- `POST /rate-cards`
- `GET /rate-cards`
- `POST /budgets`
- `GET /budgets`
- `POST /budgets/{budget_id}/status`
- `GET /budgets/{budget_id}/snapshot`
- `GET /budget-alerts`
- `GET /usage/summary?dimension=provider|model|user|work_graph_node|organization`

Cost reconciliation is intentionally a bounded operator worker rather than an unauthenticated background loop.

## Migration and rollback

Revision `20260907_0012` creates only derived governance/accounting tables. Downgrade removes budget alerts, budgets, cost-resolution rows, and rate cards in that order. The underlying `ai_request_records` remain intact, so cost state can be rebuilt after a rollback/redeploy.
