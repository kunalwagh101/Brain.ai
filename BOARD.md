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
IN_REVIEW | S-05.01.01 | F-05.01 | Implementation/docs/tests including provenance contract exist; project owner explicitly deferred local pytest + Render verification on 2026-09-10, so no passing evidence is claimed
BLOCKED | S-05.02.01 | F-05.02 | OQ-005 resolved to OpenAI/Terra candidate; RAG/runtime discovery/cache-aware exact-cost/staging tooling are staged, but dependency verification, real staging/eval/performance, WorkOS frontend build and manual UAT remain open
IN_REVIEW | S-06.01.01 | F-06.01 | Provider registry/gateway implementation, migration, tests, docs and cache-token usage propagation are staged; executable passing verification remains outstanding
BLOCKED | S-06.02.01 | F-06.02 | Cache-aware usage/cost/budget implementation and request-scoped cost audit are staged; tests are written but unexecuted and S-06.01.01 remains unverified
IN_REVIEW | S-06.03.01 | F-06.03 | External API registry/lifecycle/expiry implementation is staged; executable passing verification remains outstanding
BACKLOG | S-07.01.01 | F-07.01 | Depends on work graph + decision/blocker memory
BACKLOG | S-07.02.01 | F-07.02 | Depends on project status + usage/cost
BLOCKED | S-08.01.01 | F-08.01 | Governed agent runtime is staged; dependencies and this story still lack executable passing verification
IN_REVIEW | S-09.01.01 | F-09.01 | Observability implementation/tests/docs/UAT are staged; executable passing verification remains outstanding
IN_REVIEW | S-09.02.01 | F-09.02 | Audit/retention/deletion implementation/tests/docs/UAT are staged; executable PostgreSQL/Ruff/Pytest/Delivery Verifier evidence remains outstanding
BLOCKED | S-09.03.01 | F-09.03 | Release/rollback/restore work plus a concrete Render staging Blueprint are staged; real deployment/recovery exercise and OQ-007 production topology remain unresolved
BLOCKED | S-09.04.01 | F-09.04 | Performance/cost benchmark work is staged; no real Ask Brain staging performance run exists yet
DEFERRED | S-10.01.01 | F-10.01 | Revisit after E-01 through E-05 prove external-tool wedge

## Current increment — Increment 18 / S-05.02.01

Sprint goal: a user can ask a company question and receive either a strictly evidence-cited answer from currently authorised evidence or an explicit no-answer; ungrounded provider text must fail closed.

Vertical slice: Ask Brain API -> permission-aware retrieval -> bounded evidence context -> governed AI gateway -> structured claim/citation validation -> cited response/no-answer.

Branch rule: continue on `increment-10-ai-provider-gateway`; no additional branch is created.

### What is staged now

- permission-aware Ask Brain retrieval with no-evidence/no-provider-call behaviour;
- explicit tenant provider/model selection and safe organisation/runtime discovery for normal `ai.use` users;
- prompt-injection boundary and strict server-issued citation validation;
- bounded citation excerpts and an Ask-Brain-specific 8,192-token output ceiling;
- two-phase deployed evaluation separating automatic retrieval/security checks from human semantic claim-citation review;
- OQ-005 resolution: OpenAI API + `gpt-5.6-terra` is the first candidate, conditional on all acceptance gates;
- provider-reported cached-input token capture;
- separate normal-input/cached-input/output Terra rate-card support;
- fail-closed unknown cost when required cached usage is absent or invalid;
- request-scoped cost audit and staging bootstrap that independently recomputes exact cost for one real provider request;
- Alembic revision `20260910_0016` for cached-input accounting;
- regression tests for cache parsing/costing, exact request-cost API and managed Postgres URL handling; these tests are written but not claimed as executed;
- `render.yaml` plus `docs/RENDER_STAGING.md` for a reproducible API + PostgreSQL staging candidate;
- `docs/ASK_BRAIN_STAGING.md` and `UAT/F-05.02.md` for compatibility, quality, performance and browser acceptance.

### Formal state

`S-05.01.01` stays `IN_REVIEW`. On 2026-09-10 the project owner explicitly deferred running its pytest verification locally and on Render. That is a deliberate deferred gate, not a PASS.

`S-05.02.01` stays `BLOCKED`. OQ-005 is resolved, but the following acceptance evidence does not exist yet: executable dependency/Ask Brain verification, deployed Render staging with real WorkOS/AWS/OpenAI configuration, real Terra compatibility + cache-aware exact-cost smoke, representative Phase 1 retrieval/RAG evaluation, Phase 2 human claim-citation review, p95/error/cost performance run, official WorkOS frontend package/build, and manual authenticated browser UAT.

The production frontend must not be faked with ChatGPT-host authentication or a hardcoded bearer token. The current controlled environment cannot install the WorkOS AuthKit dependency and regenerate a trustworthy lockfile, so that integration remains externally blocked until package installation/build is available.

Production quality gates remain: retrieval recall >=90%, zero forbidden evidence exposure/grounding-contract failures, every exact generated claim-citation pair human reviewed, semantic citation correctness >=98%, and Ask Brain p95 <10 seconds on the accepted staging runtime.

No `EVIDENCE S-05.01.01` or `EVIDENCE S-05.02.01` block may be added and no merge may occur until those checks actually pass.

Detailed readiness/tasks: `docs/planning/increment-18.md`.

Backend/evaluation/security design: `docs/ASK_BRAIN.md`, `docs/ASK_BRAIN_EVALUATION.md`, and `docs/ASK_BRAIN_STAGING.md`.

Staging deployment procedure: `docs/RENDER_STAGING.md`.

Manual/real-provider acceptance procedure: `UAT/F-05.02.md`.
