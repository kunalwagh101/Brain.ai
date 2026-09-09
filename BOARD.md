# Brain Delivery Board

Method: Scrum + Kanban hybrid. Two-week increments. WIP limit: IN_PROGRESS <= 2. Chat is not state.

Format: `STATUS | STORY_ID | FEATURE | NOTE`

Historical planning/state before Increment 18 is preserved at `docs/archive/BOARD_before_increment18.md`.

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
BLOCKED | S-04.02.01 | F-04.02 | Implementation is staged; formal review remains blocked until S-05.01.01 has executable passing verification
IN_REVIEW | S-05.01.01 | F-05.01 | Implementation/docs/tests exist; GitHub Actions still cannot start a runner, so no passing verification evidence exists
BLOCKED | S-05.02.01 | F-05.02 | Ask Brain production slice is staged through f4ff8217ac02b6392cede6e709ccdbcab124b33f; blocked by unverified S-05.01.01, OQ-005 provider/model policy, CI runner failure, real two-phase citation eval, latency/cost and authenticated frontend UAT
IN_REVIEW | S-06.01.01 | F-06.01 | Provider registry/gateway implementation, migration, tests, docs and UAT exist; no executable passing verification exists because GitHub Actions cannot start a runner
BLOCKED | S-06.02.01 | F-06.02 | Usage/cost/budget implementation is staged; S-06.01.01 is still unverified and F-06.02 has no executable passing verification
IN_REVIEW | S-06.03.01 | F-06.03 | External API registry/lifecycle/expiry implementation is staged; latest Backend CI had no executable steps
BACKLOG | S-07.01.01 | F-07.01 | Depends on work graph + decision/blocker memory
BACKLOG | S-07.02.01 | F-07.02 | Depends on project status + usage/cost
BLOCKED | S-08.01.01 | F-08.01 | Governed agent runtime is staged; dependencies and this story still lack executable passing verification
IN_REVIEW | S-09.01.01 | F-09.01 | Observability implementation/tests/docs/UAT are staged; executable passing verification remains unavailable
IN_REVIEW | S-09.02.01 | F-09.02 | Audit/retention/deletion implementation/tests/docs/UAT are staged; executable PostgreSQL/Ruff/Pytest/Delivery Verifier evidence remains unavailable
BLOCKED | S-09.03.01 | F-09.03 | Release/rollback/restore work is staged; executable runner, merge-check enforcement and OQ-007 production runtime/registry remain unresolved
BLOCKED | S-09.04.01 | F-09.04 | Performance/cost benchmark work is staged; verified search/AI dependencies, executable runners and production-like measurements remain unavailable
DEFERRED | S-10.01.01 | F-10.01 | Revisit after E-01 through E-05 prove external-tool wedge

## Current increment — Increment 18 / S-05.02.01

Sprint goal: a user can ask a company question and receive either a strictly evidence-cited answer from currently authorised evidence or an explicit no-answer; ungrounded provider text must fail closed.

Vertical slice: Ask Brain API -> permission-aware retrieval -> bounded evidence context -> governed AI gateway -> structured claim/citation validation -> cited response/no-answer.

Branch rule: continue on `increment-10-ai-provider-gateway`; no additional branch is created.

Staged production controls now include: explicit tenant provider/model selection; no-evidence/no-provider-call behavior; live permission and revocation reuse from F-05.01; prompt-injection boundary; strict server-issued citation validation; bounded 800-character citation excerpts; an 8,192-token Ask-Brain-specific generation ceiling; whitespace/client validation before provider access; and a two-phase deployed evaluation that separates automatic retrieval/security checks from human-reviewed semantic claim-citation correctness. `.local/` and `.evaluation/` are gitignored to reduce accidental customer-evidence commits.

Formal Ready/Done state: the story stays `BLOCKED`. `S-05.01.01` is not engineering-DONE, `OQ-005` still owns the production model/provider decision, and the required real-provider evaluation/manual UAT have not run. Backend CI run 34405201146 for implementation commit f4ff8217ac02b6392cede6e709ccdbcab124b33f completed as failure before any workflow step; its test job exposes no executed steps, so no Ruff/Pytest pass is claimed.

Production evaluation remains two-phase: retrieval recall must be >=90% with zero forbidden evidence/grounding-contract failures, then every exact generated claim-citation pair must be human reviewed and semantic citation correctness must be >=98%. Only the final scorer's `production_passed=true` satisfies that citation gate.

The current frontend is still an honestly labelled preview and does not yet have the production WorkOS browser-session-to-FastAPI access-token path. Do not fake frontend UAT with a hardcoded browser token.

Detailed readiness, tasks, AI/data assessment and Done gates: `docs/planning/increment-18.md`.

Backend/evaluation/security design: `docs/ASK_BRAIN.md` and `docs/ASK_BRAIN_EVALUATION.md`.

Manual/real-provider acceptance procedure: `UAT/F-05.02.md`.
