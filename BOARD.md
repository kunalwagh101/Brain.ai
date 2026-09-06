# Brain Delivery Board

Method: Scrum + Kanban hybrid. Two-week increments. WIP limit: IN_PROGRESS <= 2. Chat is not state.

Format: `STATUS | STORY_ID | FEATURE | NOTE`

DONE | S-01.01.01 | F-01.01 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.02.01 | F-01.02 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.03.01 | F-01.03 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-02.01.01 | F-02.01 | Engineering evidence in TRACEABILITY.md; real-data/frontend UAT remains pending
DONE | S-02.02.01 | F-02.02 | Engineering evidence in TRACEABILITY.md; real Slack + frontend UAT remains pending
IN_PROGRESS | S-02.03.01 | F-02.03 | Increment 5: GitHub App webhook + repository backfill + source visibility into raw/canonical evidence
BACKLOG | S-02.04.01 | F-02.04 | OQ-004 selects first provider
DONE | S-03.01.01 | F-03.01 | Engineering evidence in TRACEABILITY.md; realistic raw-data inspection UAT remains pending
IN_PROGRESS | S-03.02.01 | F-03.02 | Increment 5: versioned provider-neutral canonical events proven with Slack + GitHub
BACKLOG | S-03.03.01 | F-03.03 | Depends on identity + canonical event model
BACKLOG | S-04.01.01 | F-04.01 | Depends on canonical events + identity resolution
BACKLOG | S-04.02.01 | F-04.02 | Depends on work graph + retrieval evaluation
BACKLOG | S-05.01.01 | F-05.01 | Depends on RBAC + canonical evidence
BACKLOG | S-05.02.01 | F-05.02 | OQ-005 before provider contract is frozen
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

Increment 5 goal: **authorised GitHub App activity and backfill land exactly once as raw evidence and are normalised into the same versioned canonical event contract used for Slack, with repository visibility and provenance preserved.**

Vertical slice: canonical event schema/normaliser -> Slack canonical mapping -> GitHub App connection contract -> GitHub HMAC webhook -> repository visibility mapping -> repository/PR/issue/commit/deployment backfill -> canonical processing -> tests/migration/docs/UAT.

## Increment 4 review

- Slack OAuth uses a signed, expiring state containing organisation/user identifiers and re-checks the user's current `integration.manage` permission at callback time.
- Required bot scopes are limited to channel/group read + history; direct-message scopes are not requested.
- Admins explicitly authorise channels; the app must be a channel member first. DMs/MPDMs are rejected.
- Private-channel authorisation records Slack member IDs as source ACL evidence and membership join/leave events update that state.
- Slack Events API requests are HMAC-verified against the exact raw body before JSON parsing and rejected outside a five-minute timestamp window.
- Live Slack payload bytes are stored exactly with SHA-256 provenance, source visibility, source ACL, source event ID and processing state.
- Slack retries are idempotent on `(integration_connection_id, source_event_id)`.
- History backfill is cursor-resumable, page-bounded, and replay-safe using deterministic per-message source IDs.
- PostgreSQL is the durable raw-ingestion boundary in this increment; no premature queue/Slack SDK dependency was added.
- Alembic revision `20260906_0005` has an explicit downgrade.
- Backend CI and Delivery Verifier passed on the final DONE-state commit before merge.
- F-02.02 and F-03.01 remain `UAT_PENDING`; they are not called passed/accepted until real Slack/data and frontend/manual UAT are recorded.

## Session-open self-audit

- Six stories are engineering-DONE; user acceptance remains independently tracked in UAT.md.
- Current WIP count: 2 (at limit): S-02.03.01 and S-03.02.01.
- GitHub webhook signatures must be validated against the unmodified request body before parsing; only subscribed/handled event types are accepted.
- Canonicalisation must preserve source permissions and raw-event provenance; unsupported fields/events must be explicitly retained as metadata or quarantined, never silently discarded.
- No third story may enter IN_PROGRESS until one of the two current stories leaves WIP.
