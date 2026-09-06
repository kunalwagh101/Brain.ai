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

## Session-open self-audit

- Ten stories are engineering-DONE; their external/user acceptance is tracked separately in UAT.md.
- Current WIP count: 1 (`S-05.01.01`), within WIP <= 2.
- Increment 7 Work Graph is merged on `main` at `ddd12921ec7ac025dc21de41275b8532c811ab24`.
- F-05.01 dependencies S-01.03.01 and S-03.02.01 are engineering-DONE.
- Existing Work Graph authorization semantics are reused rather than replaced.
- OQ-005 does not block retrieval shape because this increment does not freeze a generation provider; embeddings are operator-configured behind a provider-neutral contract.
- Existing frontend still contains preview/sample state. No fake search wiring will be used to claim frontend acceptance.
