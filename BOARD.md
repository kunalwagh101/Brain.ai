# Brain Delivery Board

Method: Scrum + Kanban hybrid. Two-week increments. WIP limit: IN_PROGRESS <= 2. Chat is not state.

Format: `STATUS | STORY_ID | FEATURE | NOTE`

IN_PROGRESS | S-01.01.01 | F-01.01 | Increment 1 vertical slice: authenticated organisation ownership and membership boundary
IN_PROGRESS | S-01.02.01 | F-01.02 | OQ-001 resolved: WorkOS AuthKit/JWT first provider; required by S-01.01.01
BACKLOG | S-01.03.01 | F-01.03 | Depends on S-01.02.01 and OQ-002
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

Current sprint goal: **Increment 1 — a verified user can establish an organisation ownership boundary and manage membership without cross-tenant leakage.**

Vertical slice: provider JWT -> Brain identity -> organisation owner membership -> membership read/write -> negative tenant tests.

## Session-open self-audit

- Increment 0 delivery verifier passed before this slice was pulled.
- WIP count: 2 stories, at the enforced limit.
- OQ-001 is resolved in OPEN_QUESTIONS.md.
- No additional story may enter IN_PROGRESS until one of these leaves WIP.
