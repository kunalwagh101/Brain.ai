# Brain Delivery Board

Method: Scrum + Kanban hybrid. Two-week increments. WIP limit: IN_PROGRESS <= 2. Chat is not state.

Format: `STATUS | STORY_ID | FEATURE | NOTE`

DONE | S-01.01.01 | F-01.01 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.02.01 | F-01.02 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.03.01 | F-01.03 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-02.01.01 | F-02.01 | Engineering evidence in TRACEABILITY.md; real-data/frontend UAT remains pending
DONE | S-02.02.01 | F-02.02 | Engineering evidence in TRACEABILITY.md; real Slack + frontend UAT remains pending
DONE | S-02.03.01 | F-02.03 | Engineering evidence in TRACEABILITY.md; real GitHub + frontend UAT remains pending
BACKLOG | S-02.04.01 | F-02.04 | OQ-004 selects first provider
DONE | S-03.01.01 | F-03.01 | Engineering evidence in TRACEABILITY.md; realistic raw-data inspection UAT remains pending
DONE | S-03.02.01 | F-03.02 | Engineering evidence in TRACEABILITY.md; Slack/GitHub real-data + frontend UAT remains pending
DONE | S-03.03.01 | F-03.03 | Engineering evidence in TRACEABILITY.md; real provider identity + frontend/manual UAT remains pending
DONE | S-04.01.01 | F-04.01 | Engineering evidence in TRACEABILITY.md; real Slack/GitHub graph + frontend/manual UAT remains pending
BLOCKED | S-04.02.01 | F-04.02 | Implementation is staged on Increment 9, but formal readiness/review is blocked until S-05.01.01 has executable passing verification
IN_REVIEW | S-05.01.01 | F-05.01 | Implementation/docs/tests exist; GitHub Actions cannot start a runner, so no passing verification evidence yet
BACKLOG | S-05.02.01 | F-05.02 | OQ-005 before generation provider contract is frozen
IN_REVIEW | S-06.01.01 | F-06.01 | Provider registry/gateway implementation, migration, tests, docs and UAT exist on the current branch; no executable passing verification exists because GitHub Actions cannot start a runner
BLOCKED | S-06.02.01 | F-06.02 | Usage/cost/budget implementation is staged on the same branch; S-06.01.01 is still unverified and F-06.02 itself has no executable passing verification
IN_REVIEW | S-06.03.01 | F-06.03 | External API registry, lifecycle, expiry worker, migration, tests, docs and UAT exist on the same branch; latest Backend CI again had runner_id=0 and steps=[]
BACKLOG | S-07.01.01 | F-07.01 | Depends on work graph + decision/blocker memory
BACKLOG | S-07.02.01 | F-07.02 | Depends on project status + usage/cost
BACKLOG | S-08.01.01 | F-08.01 | Depends on AI gateway + audit/retention
BACKLOG | S-09.01.01 | F-09.01 | Foundation exists; acceptance evidence incomplete
BACKLOG | S-09.02.01 | F-09.02 | OQ-006 retention defaults unresolved
BACKLOG | S-09.03.01 | F-09.03 | Phase 3 verifier is merged and green; full production deployment story remains
BACKLOG | S-09.04.01 | F-09.04 | Benchmarks attach to implemented vertical slices
DEFERRED | S-10.01.01 | F-10.01 | Revisit after E-01 through E-05 prove external-tool wedge

## Increment 12 planning — external API registry on the existing branch

Increment 12 goal: **inventory external API services and credential grants with explicit owner, scopes, environment, lifecycle, expiry and usage evidence while keeping plaintext credentials exclusively in the configured secret store.**

Branch rule: Increment 12 intentionally continues on `increment-10-ai-provider-gateway`; no additional branch is created.

Dependency state: S-01.03.01 RBAC and S-02.01.01 integration secret-reference patterns are engineering-DONE, so F-06.03 is not dependency-blocked. It remains `IN_REVIEW` only because executable Ruff/Pytest/Delivery Verifier evidence is unavailable while GitHub Actions cannot start a runner.

Vertical slice staged: tenant-scoped API service inventory -> secret-reference credential grant -> active same-org owner/scopes/environment/expiry -> immutable lifecycle history -> safe rotation -> fail-closed revoke/retry -> expiry worker + secret cleanup retry -> internal idempotent usage observation -> permissioned read/mutation API -> migration/tests/docs/UAT.

Rules for this increment:

- Registry mutations require `api.manage`; organisation-wide reads reuse `audit.read`.
- PostgreSQL never stores plaintext API credential material; read APIs expose only whether a credential reference exists.
- Owner targets must be active members of the same organisation.
- Scope/environment identifiers are explicit and bounded; Brain never guesses them from traffic.
- Metadata becomes immutable after revocation or expiry.
- Revocation uses explicit `revoking` / `revoke_failed` / `revoked` fail-closed states and cannot be re-enabled once revocation starts.
- Expiry changes database state before secret cleanup, so compliant callers fail closed even if external secret deletion must be retried.
- Credential rotation changes the secret in place and records only rotation metadata, never old/new credential values.
- Usage observations are internal/trusted-service writes only; there is no public endpoint that lets normal clients fabricate usage evidence.
- Replayed usage observations are idempotent; PostgreSQL locks grant state so concurrent observations do not lose usage-count increments.
- Real calling-system coverage and frontend/manual acceptance remain UAT evidence. Do not claim all API usage is governed until those integrations are actually wired and checked.
- No S-06.03.01 DONE evidence block may be added until Ruff, tests, migration checks and the delivery verifier have executable passing results.

## Increment 11 planning — staged on the existing AI governance branch

Increment 11 goal: **turn governed AI requests into deterministic usage/cost accounting and enforceable monthly budget controls without inventing attribution or treating unknown spend as zero.**

Branch rule: Increment 11 intentionally continues on `increment-10-ai-provider-gateway`; no additional branch is created.

Dependency state: S-06.01.01 has a usable implementation contract on the same branch but remains IN_REVIEW because no GitHub-hosted runner has executed its tests. S-06.02.01 is therefore `BLOCKED` under the Definition of Ready/Done even though its implementation is staged for efficient review.

Vertical slice staged: AI request ledger -> historical provider/model rate card -> deterministic nano-USD cost resolution -> explicit unknown-cost state -> organisation/provider/model/user/Work Graph aggregation -> monthly budget policy -> deduplicated warning/100% alerts -> pre-provider post-exhaustion hard-stop -> bounded PostgreSQL-safe reconciliation worker -> API/migration/tests/docs/UAT.

Rules for this increment:

- Persisted cost uses integer nano-USD; no floating-point currency accounting.
- Missing token metadata or an effective rate card produces an explicit `unknown` cost record, never silent zero spend.
- Missing project/track/work-item attribution remains NULL/unknown; Brain never guesses attribution from prompt text.
- Budget targets are validated against the same organisation before persistence.
- Organisation-wide spend reads reuse `audit.read`; budget/rate administration requires `ai.manage`.
- Alert uniqueness is enforced by budget + UTC calendar month + threshold.
- The hard-stop is checked before secret lookup/provider execution once known spend is already exhausted.
- This is a post-exhaustion hard stop, not an exact prepaid reservation; concurrent in-flight requests may overshoot the configured limit and that limitation remains documented.
- Unknown-cost requests make budget enforcement explicitly incomplete rather than falsely complete.
- A bounded reconciliation worker can resolve previously unknown/missing cost rows after pricing becomes available; PostgreSQL workers use `FOR UPDATE SKIP LOCKED`.
- Real provider pricing, invoice comparison, PostgreSQL concurrency, and frontend/manual acceptance remain UAT evidence, not assumptions.
- No S-06.02.01 DONE evidence block may be added until S-06.01.01 is verified and F-06.02 has its own passing executable verification.

## Increment 10 planning — governed AI provider gateway

Increment 10 goal: **route approved AI calls through one tenant-scoped gateway that keeps provider credentials out of the database, records provider/model/user/project attribution, fails closed on revocation, and does not persist prompts/completions by default.**

Vertical slice staged: admin provider/model registry -> secret-reference credential storage -> production egress allowlist -> provider-neutral adapter -> AI-use authorization -> optional Work Graph attribution -> durable request ledger -> bounded provider failures -> provider/model lifecycle -> migration/tests/docs/UAT.

Rules for this increment:

- Provider/model administration uses `ai.manage`; invocation uses `ai.use`.
- API keys live in the configured secret store; PostgreSQL persists only secret references.
- Production provider URLs require HTTPS and an explicitly approved egress hostname.
- Redirects are rejected so an allowed host cannot redirect the gateway to an internal target.
- Provider response bodies and credentials are not surfaced in bounded gateway errors.
- Prompt/system text and completion content are not persisted in `ai_request_records`.
- Every accepted provider call records organisation, user, provider, model, status and latency; optional project/track/work-item attribution is permission checked.
- Revocation is fail-closed and has explicit `revoking` / `revoke_failed` / `revoked` state; a failed revocation cannot be re-enabled.
- Real-provider interoperability, latency and frontend/manual acceptance remain UAT_PENDING.

## Increment 9 planning — dependency-blocked staged implementation

Increment 9 goal: **surface explicit decisions and blockers from authorised company evidence as reviewable candidates with evidence, confidence and immutable human correction history, without ever presenting machine inference as confirmed fact.**

Dependency state: S-04.01.01 Work Graph is engineering-DONE. S-05.01.01 Permission-Aware Retrieval has a usable implementation contract but is still IN_REVIEW because GitHub-hosted runners have not executed its verification. Under the Definition of Ready, S-04.02.01 therefore remains `BLOCKED`; code may be staged on the stacked branch, but review/DONE is prohibited until the dependency gate is satisfied.

Vertical slice staged: whitelisted SearchDocument evidence -> conservative explicit-marker extractor -> tenant-scoped candidate/extraction ledger -> live retrieval authorization boundary -> decision/blocker read API -> human confirm/reject/edit/resolve/reopen -> immutable review history -> bounded reconciliation worker -> migration/tests/docs/UAT.

Rules for this increment:

- Machine extraction creates `candidate` state only. It can never create `confirmed` state.
- Extraction reads whitelisted `SearchDocument` content, not arbitrary raw JSON.
- Current integration/channel/resource authorization is reused before candidate content/provenance is returned.
- Decisions and blockers remain explicit kinds with confidence and extractor method/version.
- Statement fingerprints and extraction content/version ledgers make replay and extractor upgrades idempotent.
- Unreviewed candidates that disappear on re-extraction become `superseded`; human-reviewed state/summary is not silently overwritten.
- Blockers may be resolved/reopened; decisions cannot be resolved like blockers.
- Every human mutation records actor, reason, previous/new state and previous/new summary.
- No employee scoring, sentiment scoring or hidden performance judgement is introduced.
- The first extractor is intentionally conservative/deterministic and precision-first. Future model extraction must preserve the same candidate/review contract.
- Synthetic fixtures validate plumbing only. A >=90% production precision claim requires representative labelled company evidence and separate real-data/frontend UAT.
- No F-04.02 DONE evidence block may be added until S-05.01.01 is verified and this increment itself has passing executable verification.

## Sprint planning — Increment 8

Increment 8 goal: **make authorised Slack/GitHub evidence searchable by keyword and semantic similarity without ever allowing restricted evidence to enter an unauthorised result set, while preserving source provenance and live revocation semantics.**

Vertical slice: canonical/raw evidence -> durable search projection -> permission predicate using current integration/channel/resource authorization -> PostgreSQL full-text baseline -> provider-neutral embeddings -> pgvector semantic candidates -> hybrid ranking -> provenance-bearing search API -> revoked/deleted evidence removal -> evaluation/tests/migration/worker/docs/UAT.

Rules for this increment:

- PostgreSQL remains the retrieval store; no external vector database is added.
- `pgvector` is added only because semantic retrieval now requires vector similarity.
- Search projection is rebuildable derived state. Raw/canonical evidence remains authoritative.
- Source content is whitelisted into the search projection; arbitrary raw JSON is never blindly indexed.
- Permission filtering is part of the database candidate predicate before search result content is loaded/returned.
- Live integration status, live Slack channel authorization/membership and current resource grants override historical ACL provenance.
- Owner/Admin role does not bypass restricted-resource grants.
- Deleted source objects are removed from derived retrieval content; revoked integrations/resources disappear at query time.
- Embedding generation uses a provider-neutral HTTP contract configured by the operator. F-05.01 does not choose the later RAG generation provider from OQ-005.
- Connector ingestion must not depend on embedding-provider availability. A durable database-backed indexing worker handles derived indexing/retries.
- Semantic degradation is explicit in the API response; it is never silently described as hybrid search.
- Real-provider recall/latency and frontend/manual acceptance remain UAT evidence, not assumptions.

## Increment 7 review

- Added PostgreSQL `work_graph_nodes` and `work_graph_edges`; no graph database dependency was introduced.
- Added typed person/project/track/work-item/evidence nodes plus typed relationships with explicit source, verified/inferred state, confidence and provenance.
- Wired graph projection into canonical Slack/GitHub processing and added bounded reconciliation for existing unprojected canonical events.
- Kept source identities and Brain users as distinct person nodes; current attribution is represented by a reversible `resolves_to` edge.
- Added manual project/track/work-item nodes and constrained manual organisational edges; person identity assertions and cross-tenant relationships are rejected.
- Private Slack graph authorization uses current `SlackChannelAuthorization.member_ids`; historical event ACL snapshots remain provenance only and do not keep revoked access alive.
- Restricted GitHub graph access requires an explicit matching resource grant. Owner/Admin role does not bypass the existing restricted-resource ACL contract.
- Alembic revision `20260906_0008` adds graph storage with downgrade support; canonical/raw evidence remains available to rebuild the projection after rollback.
- Backend CI run `34043847195` passed lint and 89 tests on implementation commit `a97d724416191ec8515f5ed90888321343013cda`.
- Delivery Verifier run `34043847222` passed before the DONE-state documentation update.
- F-04.01 remains `UAT_PENDING`; realistic Slack/GitHub backend validation and frontend/manual acceptance are not claimed by engineering tests.

## Increment 6 review

- Added tenant-scoped source identities that are explicitly separate from WorkOS authentication identities.
- Canonical Slack/GitHub person actors now create/reuse one source identity per organisation/provider/external ID while preserving the original source actor fields.
- Added one append-only source-identity observation per canonical event; replay remains idempotent.
- Automatic resolution is intentionally narrow: only a provider-verified exact email may link to an active member of the same Brain organisation.
- Missing/unverified evidence stays `UNRESOLVED`; conflicting verified evidence moves the source identity to `REVIEW_REQUIRED` and clears unsafe attribution.
- No name-only, username-similarity, domain-only, cross-tenant or LLM identity guessing is used.
- Added Owner/Admin `identity.manage` routes for listing, history, manual resolve/reassign/unresolve and reconciliation of existing canonical events.
- Manual resolution targets must be active members of the same organisation; every material change writes immutable previous/new-user history.
- Canonical events gain optional `source_identity_id` and `resolved_user_id` without rewriting source-provider actor evidence.
- UTC normalization prevents SQLite/PostgreSQL timezone representation differences from corrupting first/last-seen comparisons.
- Alembic revision `20260906_0007` adds source identity, observation and resolution-history storage plus canonical linkage with downgrade support.
- Backend CI passed lint and 82 tests; the final DONE-state Backend CI and Delivery Verifier were green before PR #8 merged.
- F-03.03 remains `UAT_PENDING`; real-provider identity evidence and frontend/manual acceptance are not claimed by engineering tests.

## Increment 5 review

- Added schema-versioned canonical events with one canonical row per raw event and immutable raw-event provenance.
- Slack and GitHub now map into the same actor/action/object/source/permissions/provenance contract.
- Unsupported or malformed mappings are quarantined; raw source evidence remains intact instead of being silently discarded.
- GitHub uses a verified GitHub App installation flow rather than PATs or arbitrary client-supplied installation IDs.
- Brain-signed expiring state binds the initiating Brain organisation/user; a second signed selection token binds the verified GitHub installation/account choice.
- A selected installation is re-fetched and verified as belonging to the configured GitHub App before it is connected.
- The generic integration endpoint rejects `provider=github`, preventing bypass of the verified GitHub App flow.
- GitHub App private key, OAuth client secret and webhook secret are loaded by secret reference; installation access tokens are short-lived and are not persisted.
- Webhooks validate `X-Hub-Signature-256` against the exact raw body before parsing; `X-GitHub-Delivery` provides retry-safe idempotency.
- Private/internal repository evidence carries `github:repository:<id>` source ACL provenance for the later retrieval-authorisation layer.
- GitHub backfill walks repository metadata, commits, pull requests, issues and deployments using a signed, connection-bound, replay-safe cursor.
- Alembic revision `20260906_0006` adds provider metadata and canonical event storage with downgrade support.
- Backend CI passed lint and 73 tests on GitHub Actions run `34037248953`.
- Delivery Verifier passed on run `34037248958` before engineering-DONE was claimed; the final DONE-state gate also passed before merge.
- F-02.03 and F-03.02 remain `UAT_PENDING`; they are not called passed/accepted until real GitHub/Slack data and frontend/manual UAT are recorded.

## Session-open self-audit

- Ten stories are engineering-DONE; external/user acceptance remains independently tracked in UAT.md.
- Current IN_PROGRESS WIP count: 0. S-05.01.01, S-06.01.01 and S-06.03.01 are IN_REVIEW; S-04.02.01 and S-06.02.01 are BLOCKED while their implementations are staged behind unverified dependencies.
- Increment 7 Work Graph is merged on `main` at `ddd12921ec7ac025dc21de41275b8532c811ab24`.
- Existing Work Graph/retrieval authorization semantics are reused rather than replaced by Decision Memory or AI governance.
- Existing frontend still contains preview/sample state. No fake search/memory/AI-cost/API-registry UI wiring will be used to claim frontend acceptance.
- Repeated Backend CI / Delivery Verifier attempts have failed before runner startup (`runner_id=0`, no steps). There is no passing test output for Increment 8 or later staged increments, so engineering-DONE is prohibited by the Definition of Done/Ready.
