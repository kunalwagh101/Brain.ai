# Brain Delivery Board

Method: Scrum + Kanban hybrid. Two-week increments. WIP limit: IN_PROGRESS <= 2. Chat is not state.

Format: `STATUS | STORY_ID | FEATURE | NOTE`

DONE | S-01.01.01 | F-01.01 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.02.01 | F-01.02 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.03.01 | F-01.03 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-02.01.01 | F-02.01 | Engineering evidence in TRACEABILITY.md; 46 tests + verifier green; real-data/frontend UAT remains pending
BACKLOG | S-02.02.01 | F-02.02 | Depends on integration framework and raw event model
BACKLOG | S-02.03.01 | F-02.03 | Depends on integration framework and raw event model
BACKLOG | S-02.04.01 | F-02.04 | OQ-004 selects first provider
BACKLOG | S-03.01.01 | F-03.01 | Depends on tenant/RBAC enforcement
BACKLOG | S-03.02.01 | F-03.02 | Depends on S-03.01.01
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

Increment 3 goal: **an authorised admin can create, inspect and safely revoke a scoped external connection without storing plaintext credentials in PostgreSQL, while connector workers have persisted health and sync-cursor state.**

Vertical slice: integration schema -> AWS Secrets Manager reference -> create/list/read/revoke API -> sync-state helpers -> negative security/error tests -> migration/rollback -> docs.

## Increment 3 review

- AWS Secrets Manager is the first production credential backend; PostgreSQL stores only a secret reference and non-secret connection metadata.
- Owner/Admin can create, inspect and revoke connections through the central `integration.manage` permission; members are denied and cross-tenant access is hidden.
- Duplicate organisation/provider/external-account connections are rejected before another secret is created.
- Connector workers have one syncability guard plus persisted health, opaque cursor, last-sync timestamp and bounded error-code state.
- Revocation is fail-closed: the connection leaves ACTIVE before AWS deletion is attempted; deletion failure leaves `REVOKE_FAILED`, which remains non-syncable.
- Database failure after secret creation triggers best-effort orphan-secret retirement.
- CI uses fake secret-store/AWS clients and therefore requires no real AWS credentials.
- Backend CI passed lint and 46 tests on GitHub Actions run `34032491893`.
- Delivery Verifier passed on run `34032491900` before engineering-DONE was claimed.
- F-02.01 remains `UAT_PENDING` until real-data backend and manual frontend validation are recorded.

## Increment 2 review

- One Brain-owned role matrix covers owner, admin, executive, manager, member and guest.
- Restricted resources require both role capability and an explicit user ACL grant.
- Admin privilege escalation is blocked; only owners may assign owner/admin roles.
- Authorization denial and ACL changes emit structured security events.
- Slack DMs are excluded from MVP and private channels require explicit opt-in.
- Backend CI passed lint and 34 tests before merge.

## Session-open self-audit

- Four stories are engineering-DONE; all corresponding feature acceptance remains tracked separately in UAT.md.
- OQ-003 is resolved: AWS Secrets Manager is the first production secret backend.
- Current WIP count: 0.
- Slack/GitHub ingestion is not yet pulled because the raw-event story must be sequenced with the first connector vertical slice.
