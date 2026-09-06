# Brain Delivery Board

Method: Scrum + Kanban hybrid. Two-week increments. WIP limit: IN_PROGRESS <= 2. Chat is not state.

Format: `STATUS | STORY_ID | FEATURE | NOTE`

DONE | S-01.01.01 | F-01.01 | Evidence in TRACEABILITY.md; authenticated organisation ownership and membership boundary verified
DONE | S-01.02.01 | F-01.02 | Evidence in TRACEABILITY.md; WorkOS JWT identity verification and Brain identity linking verified
IN_PROGRESS | S-01.03.01 | F-01.03 | Increment 2: central RBAC policy + restricted-resource ACL + deny-before-handler guard + security audit hooks
BACKLOG | S-02.01.01 | F-02.01 | Depends on S-01.03.01 and OQ-003
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

Increment 2 goal: **every protected organisation or resource action passes through one server-side policy layer, with restricted resources denied before endpoint/AI/tool code executes.**

Vertical slice: role matrix -> organisation permission dependency -> resource ACL grants -> pre-handler resource guard -> negative permission tests -> security audit events.

## Increment 1 review

- WorkOS AuthKit selected as first managed auth authority while Brain keeps its own identity/permission domain.
- Auth token validation pins RS256, issuer and audience and rejects missing/invalid credentials.
- Organisation creation and owner membership are one database transaction.
- Cross-tenant organisation reads return 404 without leaking resource fields.
- Non-owner membership mutation is rejected with 403.
- Backend CI passed lint and 14 tests on implementation commit `b53d3185000da2ebf05d730a07cb899917165707`.

## Session-open self-audit

- Increment 1 is DONE and merged to main.
- OQ-002 is resolved before RBAC implementation: Slack DMs excluded from MVP; private channels opt-in only.
- Current WIP count: 1.
- No integration story enters WIP until S-01.03.01 is verified DONE.
