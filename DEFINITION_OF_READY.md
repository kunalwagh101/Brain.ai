# Definition of Ready

A story may enter `READY` only when all conditions below are true. `IN_PROGRESS` may be entered only from a Ready-compliant story and only when the board WIP limit permits it.

- Acceptance criteria are written as observable, machine-testable Given/When/Then outcomes.
- Upstream backlog dependencies are engineering-DONE or named external dependencies with a usable contract.
- Required source data, schemas, API contracts and state transitions are known.
- No open question can materially change the story's shape, security boundary, persistence contract or external interface.
- Tenant isolation, authentication/authorization and sensitive-data handling are explicit.
- Failure, retry, idempotency and rollback expectations are explicit where state changes.
- Required migration/data backfill strategy is known.
- Success metric and leading indicator are named.
- Out-of-scope items are explicit; nothing is silently removed from scope.
- Tasks are small engineering steps and the story remains an independently shippable vertical slice.

## Increment 18 readiness record — S-05.02.01

Decision: `BLOCKED`. Production code/tests/docs/deployment tooling are staged on the existing `increment-10-ai-provider-gateway` branch because the project owner explicitly asked to continue the story, but formal Ready and Done are not satisfied.

Dependencies: S-05.01.01 Permission-Aware Retrieval has a usable implementation contract but remains `IN_REVIEW` without executable passing verification. On 2026-09-10 the project owner explicitly deferred running its pytest verification locally and on Render until later. F-06.01 governed AI gateway is staged and provider-neutral but also lacks executable passing verification.

Data/contracts known: authorised `SearchDocument` retrieval, live integration/resource authorization, source provenance, governed tenant-scoped provider/model configuration, secret references, AI request budgets, optional Work Graph attribution, organisation/runtime discovery, and request-scoped AI cost audit provide the required engineering contracts.

Open questions: OQ-005 was resolved on 2026-09-10. The first production runtime candidate is OpenAI API with `gpt-5.6-terra`, conditional on the same real quality, security, compatibility, latency and exact-cost gates defined for this story. OQ-007 still owns the final production runtime/image-registry/managed-database topology; the checked-in Render Blueprint is a staging candidate, not that production decision.

Security boundary: source authorization executes inside permission-aware retrieval before content is selected; no evidence means no provider call; evidence is bounded and treated as untrusted prompt data; every accepted claim must cite one or more server-issued evidence IDs; missing/unknown citations fail closed; returned citation excerpts are bounded and come only from already-authorised context; provider credentials remain inside the existing secret store/gateway; generation is capped at 8,192 output tokens even if a generic provider configuration permits more.

Cost boundary: Terra's reviewed ordinary input, cached input and output rates are represented separately. Provider-reported cached token usage is persisted. If a distinct cached rate applies but cached usage is unavailable, or if cached usage is invalid, Brain resolves the request cost as `unknown` rather than guessing. The staging bootstrap verifies the exact request ID and independently recomputes input/output/total cost from the request-scoped ledger.

Evaluation boundary: automatic retrieval relevance cannot be called semantic citation correctness. Phase 1 measures retrieval recall, forbidden evidence and grounding-contract safety. Phase 2 requires a human to judge every exact generated claim-citation pair from the same run. The report, sensitive review packet and review template are bound by evaluation run ID plus SHA-256. Only the final scorer's `production_passed=true` can satisfy the >=98% citation-correctness gate. Real labelled datasets and evaluation artifacts remain under gitignored `.local/` and `.evaluation/` paths.

State/idempotency: Ask Brain adds no mutable answer store. Answers are transient. Existing AI request metadata/cost records remain authoritative for provider execution. Migration `20260910_0016` adds cached-input accounting only. Repeated questions may invoke the provider again and are independently governed by current permissions/budgets.

Rollback: code-only removal of the Ask Brain route/service/evaluation tooling plus the defined migration downgrade for cached-input accounting if required. Search documents, raw/canonical evidence and historical AI request ledgers are not rewritten by feature rollback.

Leading indicators: unauthorised evidence exposure = 0; retrieval recall >=90%; human-reviewed semantic citation correctness >=98%; AI answer p95 <10 seconds; provider/model total/cached/output usage and exact request cost recorded before production acceptance.

Current verification: implementation/tests/runbooks/Render staging configuration are staged, but no new local pytest or Render verification is claimed in this pass per the owner's explicit deferral. Real Terra compatibility/cost smoke, labelled retrieval/RAG evaluation, human semantic citation review, staging performance, official WorkOS frontend build and browser/manual UAT remain unexecuted external acceptance gates.

Unblock condition: the project owner later executes and records passing S-05.01.01 verification; Ask Brain/gateway/cost tests plus Ruff/verifier pass; Terra compatibility and exact cache-aware cost smoke pass; real two-phase evaluation passes >=90% retrieval recall and >=98% human-reviewed semantic citation correctness with zero forbidden evidence/grounding-contract failures; staging p95/error/cost is recorded; official WorkOS frontend integration builds; and authenticated frontend/manual UAT passes.

## Increment 9 readiness record — S-04.02.01

Decision: `BLOCKED` on 2026-09-07. The implementation is being staged on a stacked branch because the user explicitly asked to begin the next feature, but the story does not satisfy formal Ready while S-05.01.01 remains `IN_REVIEW` without executable passing verification.

Dependencies: S-04.01.01 Work Graph = engineering-DONE. S-05.01.01 Permission-Aware Retrieval = usable implementation contract but not engineering-DONE; this is the blocking dependency.

Data/contracts known: `CanonicalEvent`, `SearchDocument`, Work Graph evidence, integration/channel/resource authorisation and the current retrieval predicate provide the evidence/provenance/access inputs.

Open questions: OQ-005 does not block the deterministic `explicit-markers-v1` extractor because this increment does not choose an LLM provider. Any future model-backed extractor must preserve the same candidate/review contract and undergo its own data-policy/evaluation gate.

Security boundary: machine candidates are derived only from whitelisted search evidence; user-facing reads reuse the live retrieval authorisation boundary; role alone cannot widen restricted evidence access; cross-tenant access fails closed.

State/idempotency: machine output starts only as `candidate`; statement fingerprints plus extraction version/content digest prevent unchanged replay; stale unreviewed machine candidates become `superseded`; human review appends immutable before/after history.

Rollback: migration `20260907_0010` removes decision-memory candidate/extraction/review tables only. Raw/canonical/search/work-graph evidence remains. Human review history must be exported before downgrade if it must survive the rollback itself.

Leading indicators: unauthorised memory retrieval failures = 0; synthetic explicit-marker precision instrumentation >=90%; representative labelled decision and blocker precision each >=90% before production acceptance.

Unblock condition: S-05.01.01 receives truthful executable passing verification and is moved to engineering-DONE; then S-04.02.01 may be reevaluated for READY/IN_PROGRESS against this record.

## Increment 8 readiness record — S-05.01.01

Decision: `READY` then pulled to `IN_PROGRESS` on 2026-09-07; current board state is `IN_REVIEW`.

Dependencies: S-01.03.01 RBAC/resource ACL = engineering-DONE; S-03.02.01 canonical event model = engineering-DONE; S-04.01.01 Work Graph authorization semantics = engineering-DONE and reused.

Data/contracts known: `CanonicalEvent`, immutable `RawEvent`, `IntegrationConnection`, `SlackChannelAuthorization`, `SourceIdentity`, `ResourceGrant`, and Work Graph evidence nodes provide the source/provenance/access inputs.

Open questions: OQ-005 was a later RAG generation-provider question and did not change this retrieval storage/API shape. Embeddings use an operator-configured provider-neutral HTTP contract.

Security boundary: organisation membership is checked first; current source/resource authorization is applied inside the search candidate predicate before result content is selected; role alone cannot bypass restricted-resource access.

Rollback: search projection and embeddings are derived/rebuildable. Migration downgrade removes only derived retrieval tables/indexes; raw/canonical evidence remains intact.

Leading indicators: unauthorised retrieval failures = 0; synthetic retrieval evaluation >=90% recall target; real-provider recall and p95 latency recorded in UAT before production acceptance.

Current verification note: the project owner explicitly deferred local pytest and Render execution verification on 2026-09-10. This is a deferred acceptance gate, not a passing result; S-05.01.01 remains `IN_REVIEW` until evidence is captured.
