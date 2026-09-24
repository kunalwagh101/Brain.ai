# Increment 11 — Usage, Cost and Budgets

Branch policy: this increment intentionally continues on `increment-10-ai-provider-gateway`; no new branch is created.

Story: S-06.02.01 — Attribute AI/API usage and enforce budgets.

Dependency state: S-06.01.01 is implemented on this same branch but has no executable passing CI evidence because GitHub-hosted runners are still failing before startup. Under the repository's Definition of Ready/Done, F-06.02 implementation may be staged but cannot be called engineering-DONE until F-06.01 and F-06.02 both receive passing executable verification.

## Goal

Turn the governed AI request ledger into deterministic cost accounting and enforceable budget controls without inventing attribution or treating missing pricing/token data as zero cost.

## Acceptance contract

1. Given a successful AI request with known token counts and an effective configured rate card, cost is calculated deterministically with integer nano-USD arithmetic and linked to the exact rate card used.
2. Given missing token counts or no effective rate card, the request receives an explicit `unknown` cost-resolution record with a bounded reason; cost is never silently zero.
3. Given an attribution dimension that is absent, usage remains unattributed for that dimension; Brain does not guess a user/project/track/team.
4. Usage can be aggregated by organisation, provider, model, user, and existing Work Graph attribution node.
5. Budget policies can target organisation, provider, model, user, or a Work Graph project/track/work-item and use a calendar-month period.
6. Threshold alerts are unique per budget + month + threshold, so repeated evaluation cannot duplicate an alert.
7. A hard budget blocks future provider execution once known spend has reached/exceeded its limit. If the period has unknown-cost requests, the budget status exposes that enforcement is incomplete rather than pretending spend is fully known.
8. Budget/provider/model/user/node targets are validated inside the same organisation before persistence.
9. Budget administration requires `ai.manage`; organisation-wide usage/cost reads reuse the existing `audit.read` permission and are not available to ordinary Members/Guests.
10. No prompt, completion, API key, or provider response body is added to usage/cost/budget storage or logs.

## Tasks

- T-06.02.01.a rate-card, cost-resolution, budget and deduplicated-alert schema/migration
- T-06.02.01.b deterministic cost materialisation and historical effective-rate selection
- T-06.02.01.c usage aggregation with explicit unknown cost/attribution counts
- T-06.02.01.d monthly budget evaluation and hard-limit preflight gate
- T-06.02.01.e API and permission surface
- T-06.02.01.f gateway integration after provider usage returns
- T-06.02.01.g concurrency/idempotency/security/tenant tests
- T-06.02.01.h operator docs, UAT, rollback and truthful delivery evidence

## Explicit non-goals

- Provider invoice reconciliation or tax/currency conversion
- Guessing team/project attribution from text
- Employee productivity/worth scoring
- Forecasting future spend with an LLM
- API-registry credential governance (F-06.03)

## Accounting unit

Cost uses integer **nano-USD** (`1 USD = 1,000,000,000 nano-USD`). Rate cards store nano-USD per token. This avoids floating-point drift and supports sub-micro-dollar token rates such as $0.15 / 1M tokens = 150 nano-USD/token.
