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

Decision: `BLOCKED` on 2026-09-09. Production code/tests/docs/UAT are staged on the existing `increment-10-ai-provider-gateway` branch because the user explicitly asked to start the story, but formal Ready and Done are not satisfied.

Dependencies: S-05.01.01 Permission-Aware Retrieval has a usable implementation contract but remains `IN_REVIEW` without executable passing verification. F-06.01 governed AI gateway is staged and provider-neutral, but also lacks executable passing verification.

Data/contracts known: authorised `SearchDocument` retrieval, live integration/resource authorization, source provenance, governed tenant-scoped provider/model configuration, secret references, AI request budgets and optional Work Graph attribution provide the required engineering contracts.

Open questions: OQ-005 still controls the first production provider/model and data-policy/evaluation baseline. The implementation does not guess a default. The Ask Brain API requires explicit configured provider/model IDs, so OQ-005 does not change the retrieval/grounding code shape, but it still blocks production acceptance and the real provider/model evaluation baseline.

Security boundary: source authorization executes inside permission-aware retrieval before content is selected; no evidence means no provider call; evidence is bounded and treated as untrusted prompt data; every accepted claim must cite one or more server-issued evidence IDs; missing/unknown citations fail closed; returned citation excerpts are bounded and come only from already-authorised context; provider credentials remain inside the existing secret store/gateway; generation is capped at 8,192 output tokens even if a generic provider configuration permits more.

Evaluation boundary: automatic retrieval relevance cannot be called semantic citation correctness. Phase 1 measures retrieval recall, forbidden evidence and grounding-contract safety. Phase 2 requires a human to judge every exact generated claim-citation pair from the same run. The report, sensitive review packet and review template are bound by evaluation run ID plus SHA-256. Only the final scorer's `production_passed=true` can satisfy the >=98% citation-correctness gate. Real labelled datasets and evaluation artifacts remain under gitignored `.local/` and `.evaluation/` paths.

State/idempotency: Ask Brain adds no mutable answer store or migration. Answers are transient. Existing AI request metadata/cost records remain authoritative for provider execution. Repeated questions may invoke the provider again and are independently governed by current permissions/budgets.

Rollback: code-only removal of the Ask Brain route/service/evaluation tooling. Search documents, raw/canonical evidence and AI request ledgers are not deleted or rewritten.

Leading indicators: unauthorised evidence exposure = 0; retrieval recall >=90%; human-reviewed semantic citation correctness >=98%; AI answer p95 target <10 seconds with observed provider/model cost recorded before production acceptance.

Current verification: implementation is staged through commit `f4ff8217ac02b6392cede6e709ccdbcab124b33f`. Backend CI run 34405201146 completed as failure before any workflow step; its test job has no executed steps. No Ruff/Pytest/Delivery Verifier pass is claimed. The current frontend also remains an honestly labelled preview without the production WorkOS browser-session-to-FastAPI access-token path, so frontend/manual UAT is still pending and must not be faked with a hardcoded token.

Unblock condition: S-05.01.01 receives executable passing verification; OQ-005 is resolved for the production provider/model/data policy; Ask Brain tests and verifier execute successfully; the real two-phase evaluation passes >=90% retrieval recall and >=98% human-reviewed semantic citation correctness with zero forbidden evidence/grounding-contract failures; staging latency/cost is recorded; and authenticated frontend/manual UAT passes.

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

Decision: `READY` then pulled to `IN_PROGRESS` on 2026-09-07.

Dependencies: S-01.03.01 RBAC/resource ACL = engineering-DONE; S-03.02.01 canonical event model = engineering-DONE; S-04.01.01 Work Graph authorization semantics = engineering-DONE and reused.

Data/contracts known: `CanonicalEvent`, immutable `RawEvent`, `IntegrationConnection`, `SlackChannelAuthorization`, `SourceIdentity`, `ResourceGrant`, and Work Graph evidence nodes provide the source/provenance/access inputs.

Open questions: OQ-005 is about the later RAG generation provider and does not change this retrieval storage/API shape. Embeddings use an operator-configured provider-neutral HTTP contract, so no provider business rule is invented here.

Security boundary: organisation membership is checked first; current source/resource authorization is applied inside the search candidate predicate before result content is selected; role alone cannot bypass restricted-resource access.

Rollback: search projection and embeddings are derived/rebuildable. Migration downgrade removes only derived retrieval tables/indexes; raw/canonical evidence remains intact.

Leading indicators: unauthorised retrieval failures = 0; synthetic retrieval evaluation >=90% recall target; real-provider recall and p95 latency recorded in UAT before production acceptance.