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

## Increment 24 readiness record — S-10.06.01

Decision: `NOT READY` under the formal dependency rule when it was pulled, now `IN_REVIEW`. The session-open audit on 2026-09-13 found no dedicated Ready record while S-10.01.01 remained `IN_REVIEW`. This is recorded process drift, not silently reclassified as compliant. The project owner directed work to continue, so the already-active item was finished rather than pulling another story.

Dependencies: S-10.01.01 supplies the usable NativeChannel/NativeMessage, permission, restricted-membership and evidence-projection contracts but is not engineering-DONE. S-10.04.01 remains the named external dependency for official WorkOS package activation and authenticated browser acceptance.

Data/contracts known: one existing NativeMessage store, exact organisation Membership email, current `can_read_channel`/`can_write_channel`, per-message evidence projection, five explicit reactions, one root-only thread link and a per-channel numeric message sequence define the complete shape. No AI model, fuzzy identity rule, second chat store or browser-held backend token is permitted.

Open questions: none changes S-10.06.01. OQ-002 applies only to the separate S-10.06.02 direct-message privacy policy. Presence/WebSockets, voice/video, editing/deletion, attachments and external notifications are explicit out-of-scope items, not hidden assumptions.

Security/data integrity: every service entry rechecks current organisation/channel visibility; revoked restricted access returns no conversation content; composite foreign keys bind thread, mention, reaction and read rows to one tenant/channel/message; reactions are allow-listed in service and database; messages and reactions are idempotent; the read cursor advances only by atomic message sequence; browser mutations require an authenticated same-origin BFF route with bounded JSON and safe errors.

Migration/rollback: migration `20260912_0020` deterministically backfills existing message order, advances each channel counter, then adds scoped constraints and conversation tables. Rollback requires stopping message writes, exporting conversation relationship/read data if it must survive, downgrading to `20260912_0019`, deploying code that does not read the removed columns/tables, and verifying root message/evidence integrity.

Leading indicators: zero tenant/revocation disclosures; correct per-user unread counts; thread/reaction idempotency; active channel participation and unread-to-read conversion. No production latency, adoption or cost result is invented before real measurement.

Current verification: 24 focused backend tests, 11 frontend source-contract tests, frontend lint/build and PostgreSQL offline migration compilation passed locally on 2026-09-13. Live PostgreSQL upgrade/downgrade, official WorkOS activation and authenticated browser accessibility/responsive UAT remain open; therefore the story cannot enter DONE.

## Increment 21 readiness record — S-07.02.01

Decision: `BLOCKED`. The project owner explicitly directed implementation to continue against the staged upstream contracts, so the Executive Overview backend is present on `increment-10-ai-provider-gateway`; formal Ready is not satisfied while S-07.01.01 and S-06.02.01 are not engineering-DONE.

Dependencies: S-07.01.01 Project Command Centre = staged but BLOCKED by S-04.02.01 and the deferred S-05.01.01 acceptance gate. S-06.02.01 Usage/Cost/Budgets = staged but BLOCKED while S-06.01.01 lacks executable verification. S-06.03.01 provides the trusted external API usage contract but also remains IN_REVIEW.

Data/contracts known: permission-filtered S-07.01 project snapshots, human-confirmed S-04.02 decision/blocker memory, exact/incomplete S-06.02 AI request cost accounting, enabled budget policy snapshots, S-06.03 API usage observations and `audit.read` provide the required backend contracts.

Security boundary: the endpoint requires `audit.read`; organisation membership is checked before execution; project visibility still uses current Work Graph/resource authorization; Executive role alone does not reveal restricted projects; Work-Graph-scoped budget warnings are returned only when their target node is visible; API usage drill-down never returns secret references or credential values.

Metric integrity: every executive metric family carries source/calculation provenance. Project progress/status reuses the deterministic S-07.01 calculation; only human-confirmed memory contributes to confirmed decision/blocker counts; AI spend uses the S-06.02 nano-USD cost ledger and keeps unknown successful-request cost explicit; external API usage comes from trusted observations. Because no reviewed external-API tariff/cost ledger exists, API monetary spend is `null` with `cost_status=not_modelled` rather than guessed from call count or latency.

Employee-scoring boundary: no employee productivity, worth, activity ranking or inferred performance score is calculated. `employee_productivity_score` is explicitly null. User-level cost attribution, where available for governance, must not be relabelled as employee performance.

Persistence/rollback: S-07.02 is a read model and introduces no new persistence table or migration. Rollback removes the executive service/routes/docs without modifying project-status, decision-memory, AI cost/budget or API registry source records. The separate organisation-wide API-usage drill-down is also read-only.

Current verification: service/routes, source-provenance contracts, permission-aware budget filtering, tests, docs and UAT are staged. No pytest, Render, real cost reconciliation, restricted-project UAT, browser UAT or accessibility run is claimed in this pass.

Unblock condition: S-07.01.01 and S-06.02.01 become engineering-DONE in dependency order; Executive Overview backend contracts execute successfully; restricted-project/budget non-disclosure UAT passes; AI spend and budget math reconcile to source ledgers; API usage reconciles while monetary API cost remains explicitly unavailable unless a reviewed tariff model is later added; and the production WorkOS frontend/manual/accessibility path passes.

## Increment 20 readiness record — S-07.01.01

Decision: `BLOCKED`. The project owner explicitly directed implementation to continue against the existing upstream contracts, so the backend slice is staged on `increment-10-ai-provider-gateway`; formal Ready is not satisfied while S-04.02.01 is not engineering-DONE.

Dependencies: S-04.01.01 Work Graph = engineering-DONE. S-04.02.01 Decision/Blocker Memory = usable staged contract but formally BLOCKED by the deferred S-05.01.01 verification.

Data/contracts known: Work Graph project/work-item/evidence nodes, permission-aware node traversal, Search authorization, decision/blocker candidate/review state, audit events and explicit structured progress rows provide the required inputs.

Security boundary: a project/work item must be visible through Work Graph authorization; project evidence is discovered only through permission-aware graph traversal and is intersected again with the live permission-aware Search query before source metadata/provenance is returned. Restricted evidence may disappear without hiding the public project itself. The dashboard must not disclose hidden-resource existence through counts, titles, memory or percentage inputs.

Progress contract: percentage is calculated only from visible explicitly configured `ProjectProgressItem` rows. No configured work returns `progress_percent=null`; Brain does not infer completion from commits, messages, evidence volume, employee activity or AI output. Candidate blockers do not change project status until human-confirmed.

Persistence/rollback: migration `20260910_0018` adds only `project_progress_items`; Work Graph, Search and decision-memory remain independent sources of truth. Downgrade removes the structured progress rows without rewriting upstream evidence.

Current verification: model/service/router/migration/tests/docs/UAT are staged. No pytest, PostgreSQL migration exercise, real permission/revocation UAT or frontend/manual UAT is claimed in this pass.

Unblock condition: S-04.02.01 becomes engineering-DONE; project-status backend/migration tests execute successfully; realistic permission/revocation and deterministic-progress UAT passes; and the production authenticated frontend/manual path passes.

## Increment 19 readiness record — S-02.04.01

Decision: `READY` before implementation and now `IN_REVIEW`. Its backlog dependencies S-02.01.01 and S-03.01.01 are engineering-DONE, and OQ-004 was resolved to generic governed upload first.

Data/contracts known: IntegrationConnection, RawEvent, CanonicalEvent, Work Graph evidence, SearchDocument, ResourceGrant, retention/deletion and security audit contracts are reused rather than duplicated.

Security boundary: organisation membership and `resource.write` guard upload; organisation/restricted visibility is retained on source/chunk/canonical/search/work-graph data; restricted chunks use existing Work Graph grants; source reads are permission-aware; deleted/revoked evidence must become unavailable to retrieval.

Input boundary: 10 MB source limit, 1,000,000 extracted-character limit, bounded PDF pages/DOCX expansion, deterministic 6,000-character chunks with overlap, and explicit supported text-bearing formats. OCR/audio/video transcription/provider sync remain out of scope for this first adapter.

Idempotency/rollback: optional organisation-scoped idempotency keys must not be reusable for different/non-active evidence. Source SHA-256 and chunk SHA-256 preserve immutable addressing. Migration `20260910_0017` removes only generic-source registry persistence; Raw/Canonical/Search/Work Graph derived lifecycle must be handled by the normal data-governance path before destructive rollback in a real environment.

Current verification: implementation, migration, tests, docs and UAT are staged; executable pytest/migration/real-data/browser evidence is intentionally not claimed in this pass.

## Increment 18 readiness record — S-05.02.01

Decision: `BLOCKED`. Production code/tests/docs/deployment tooling are staged on the existing `increment-10-ai-provider-gateway` branch because the project owner explicitly asked to continue the story, but formal Ready and Done are not satisfied.

Dependencies: S-05.01.01 Permission-Aware Retrieval has a usable implementation contract but remains `IN_REVIEW` without executable passing verification. On 2026-09-10 the project owner explicitly deferred running its pytest verification locally and on Render until later. F-06.01 governed AI gateway is staged and provider-neutral but also lacks executable passing verification.

Data/contracts known: authorised `SearchDocument` retrieval, live integration/resource authorization, source provenance, generic meeting/document search evidence, governed tenant-scoped provider/model configuration, secret references, AI request budgets, optional Work Graph attribution, organisation/runtime discovery, and request-scoped AI cost audit provide the required engineering contracts.

Open questions: OQ-005 was resolved on 2026-09-10. The first production runtime candidate is OpenAI API with `gpt-5.6-terra`, conditional on the same real quality, security, compatibility, latency and exact-cost gates defined for this story. OQ-007 still owns the final production runtime/image-registry/managed-database topology; the checked-in Render Blueprint is a staging candidate, not that production decision.

Security boundary: source authorization executes inside permission-aware retrieval before content is selected; no evidence means no provider call; evidence is bounded and treated as untrusted prompt data; provider output must match the exact top-level/claim JSON contract; every accepted claim must cite one or more server-issued evidence IDs; missing/unknown citations or unexpected fields fail closed; returned citation excerpts are bounded and come only from already-authorised context; provider credentials remain inside the existing secret store/gateway; generation is capped at 8,192 output tokens even if a generic provider configuration permits more.

Cost boundary: Terra's reviewed ordinary input, cached input and output rates are represented separately. Provider-reported cached token usage is persisted. If a distinct cached rate applies but cached usage is unavailable, or if cached usage is invalid, Brain resolves the request cost as `unknown` rather than guessing. The staging bootstrap verifies the exact request ID and independently recomputes input/output/total cost from the request-scoped ledger.

Evaluation boundary: automatic retrieval relevance cannot be called semantic citation correctness. Phase 1 measures retrieval recall, forbidden evidence and grounding-contract safety. Phase 2 requires a human to judge every exact generated claim-citation pair from the same run. The report, sensitive review packet and review template are bound by evaluation run ID plus SHA-256. Only the final scorer's `production_passed=true` can satisfy the >=98% citation-correctness gate. Real labelled datasets and evaluation artifacts remain under gitignored `.local/` and `.evaluation/` paths.

State/idempotency: Ask Brain adds no mutable answer store. Answers are transient. Existing AI request metadata/cost records remain authoritative for provider execution. Repeated questions may invoke the provider again and are independently governed by current permissions/budgets.

Rollback: code-only removal of the Ask Brain route/service/evaluation tooling plus the defined migration downgrade for cached-input accounting if required. Search documents, raw/canonical evidence and historical AI request ledgers are not rewritten by feature rollback.

Leading indicators: unauthorised evidence exposure = 0; retrieval recall >=90%; human-reviewed semantic citation correctness >=98%; AI answer p95 <10 seconds; provider/model total/cached/output usage and exact request cost recorded before production acceptance.

Current verification: backend implementation/tests/runbooks/Render staging configuration are staged, including generic-evidence integration and strict model-output contract regression coverage. No new local pytest or Render verification is claimed in this pass per the owner's explicit deferral. Real Terra compatibility/cost smoke, labelled retrieval/RAG evaluation, human semantic citation review, staging performance, official WorkOS frontend build and browser/manual UAT remain unexecuted external acceptance gates.

Unblock condition: the project owner later executes and records passing S-05.01.01 verification; Ask Brain/gateway/cost tests plus Ruff/verifier pass; Terra compatibility and exact cache-aware cost smoke pass; real two-phase evaluation passes >=90% retrieval recall and >=98% human-reviewed semantic citation correctness with zero forbidden evidence/grounding-contract failures; staging p95/error/cost is recorded; official WorkOS frontend integration builds; and authenticated frontend/manual UAT passes.

## Increment 9 readiness record — S-04.02.01

Decision: `BLOCKED`. The implementation is staged because the project owner explicitly asked to continue implementation despite the upstream acceptance gate, but formal Ready remains unsatisfied while S-05.01.01 is `IN_REVIEW` without executable passing verification.

Dependencies: S-04.01.01 Work Graph = engineering-DONE. S-05.01.01 Permission-Aware Retrieval = usable implementation contract but not engineering-DONE; this is the blocking dependency.

Data/contracts known: `CanonicalEvent`, `SearchDocument`, Work Graph evidence, generic meeting/document evidence, integration/channel/resource authorisation and the current retrieval predicate provide the evidence/provenance/access inputs.

Open questions: OQ-005 does not block the deterministic `explicit-markers-v1` extractor because this increment does not choose an LLM provider. Any future model-backed extractor must preserve the same candidate/review contract and undergo its own data-policy/evaluation gate.

Security boundary: machine candidates are derived from Search evidence; user-facing reads reuse the live retrieval authorisation boundary; role alone cannot widen restricted evidence access; cross-tenant access fails closed.

State/idempotency: machine output starts only as `candidate`; statement fingerprints plus extraction version/content digest prevent unchanged replay; stale unreviewed machine candidates may become `superseded`; candidates with human review history are not silently rewritten or superseded by re-extraction; human review locks the candidate row before transition and appends immutable before/after history.

Rollback: migration `20260907_0010` removes decision-memory candidate/extraction/review tables only. Raw/canonical/search/work-graph evidence remains. Human review history must be exported before downgrade if it must survive the rollback itself.

Leading indicators: unauthorised memory retrieval failures = 0; synthetic explicit-marker precision instrumentation >=90%; representative labelled decision and blocker precision each >=90% before production acceptance.

Current verification: existing decision-memory tests plus generic transcript/human-authority regression contracts are staged but are not claimed as executed in this pass.

Unblock condition: S-05.01.01 receives truthful executable passing verification and is moved to engineering-DONE; then S-04.02.01 must pass its own executable tests, realistic permission/revocation UAT and representative >=90% precision gate before DONE.

## Increment 8 readiness record — S-05.01.01

Decision: `READY` then pulled to `IN_PROGRESS` on 2026-09-07; current board state is `IN_REVIEW`.

Dependencies: S-01.03.01 RBAC/resource ACL = engineering-DONE; S-03.02.01 canonical event model = engineering-DONE; S-04.01.01 Work Graph authorization semantics = engineering-DONE and reused.

Data/contracts known: `CanonicalEvent`, immutable `RawEvent`, `IntegrationConnection`, `SlackChannelAuthorization`, `SourceIdentity`, `ResourceGrant`, and Work Graph evidence nodes provide the source/provenance/access inputs.

Open questions: OQ-005 was a later RAG generation-provider question and did not change this retrieval storage/API shape. Embeddings use an operator-configured provider-neutral HTTP contract.

Security boundary: organisation membership is checked first; current source/resource authorization is applied inside the search candidate predicate before result content is selected; role alone cannot bypass restricted-resource access.

Rollback: search projection and embeddings are derived/rebuildable. Migration downgrade removes only derived retrieval tables/indexes; raw/canonical evidence remains intact.

Leading indicators: unauthorised retrieval failures = 0; synthetic retrieval evaluation >=90% recall target; real-provider recall and p95 latency recorded in UAT before production acceptance.

Current verification note: the project owner explicitly deferred local pytest and Render execution verification on 2026-09-10. This is a deferred acceptance gate, not a passing result; S-05.01.01 remains `IN_REVIEW` until evidence is captured.
