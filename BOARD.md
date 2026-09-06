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
BACKLOG | S-04.02.01 | F-04.02 | Depends on work graph + retrieval evaluation
IN_PROGRESS | S-05.01.01 | F-05.01 | Increment 8: permission-aware keyword + semantic retrieval
BACKLOG | S-05.02.01 | F-05.02 | OQ-005 before generation provider contract is frozen
BACKLOG | S-06.01.01 | F-06.01 | Depends on RBAC
BACKLOG | S-06.02.01 | F-06.02 | Depends on AI provider registry/gateway
BACKLOG | S-06.03.01 | F-06.03 | Depends on RBAC + integration secret-reference model
BACKLOG | S-07.01.01 | F-07.01 | Depends on work graph + decision/blocker memory
BACKLOG | S-07.02.01 | F-07.02 | Depends on project status + usage/cost
BACKLOG | S-08.01.01 | F-08.01 | Depends on AI gateway + audit/retention
BACKLOG | S-09.01.01 | F-09.01 | Foundation exists; acceptance evidence incomplete
BACKLOG | S-09.02.01 | F-09.02 | OQ-006 retention defaults unresolved
BACKLOG | S-09.03.01 | F-09.03 | Phase 3 verifier is merged and green; full production deployment story remains
BACKLOG | S-09.04.01 | F-09.04 | Benchmarks attach to implemented vertical slices
DEFERRED | S-10.01.01 | F-10.01 | Revisit after E-01 through E-05 prove external-tool wedge

## Sprint planning

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
- Current WIP count: 1 (`S-05.01.01`), within WIP <= 2.
- Increment 7 Work Graph is merged on `main` at `ddd12921ec7ac025dc21de41275b8532c811ab24`.
- F-05.01 dependencies S-01.03.01 and S-03.02.01 are engineering-DONE.
- Existing Work Graph authorization semantics are reused rather than replaced.
- OQ-005 does not block retrieval shape because this increment does not freeze a generation provider; embeddings are operator-configured behind a provider-neutral contract.
- Existing frontend still contains preview/sample state. No fake search wiring will be used to claim frontend acceptance.
- GitHub Actions for the first implementation commit failed before runner startup (`runner_id=0`, no steps); this is external verification blockage, not passing or failing code evidence.
