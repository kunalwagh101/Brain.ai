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
IN_REVIEW | S-02.04.01 | F-02.04 | Generic governed file/transcript ingestion, migration, tests, docs and UAT are staged; executable verification is intentionally not claimed in this pass
DONE | S-03.01.01 | F-03.01 | Engineering evidence in TRACEABILITY.md; realistic raw-data inspection UAT remains pending
DONE | S-03.02.01 | F-03.02 | Engineering evidence in TRACEABILITY.md; Slack/GitHub real-data + frontend UAT remains pending
DONE | S-03.03.01 | F-03.03 | Engineering evidence in TRACEABILITY.md; real provider identity + frontend/manual UAT remains pending
DONE | S-04.01.01 | F-04.01 | Engineering evidence in TRACEABILITY.md; real Slack/GitHub graph + frontend/manual UAT remains pending
BLOCKED | S-04.02.01 | F-04.02 | Backend implementation is staged and hardened for generic evidence + human-authoritative review; formal review remains blocked until S-05.01.01 has executable passing verification
IN_REVIEW | S-05.01.01 | F-05.01 | Implementation/docs/tests including provenance contract exist; project owner explicitly deferred local pytest + Render verification on 2026-09-10, so no passing evidence is claimed
BLOCKED | S-05.02.01 | F-05.02 | Backend RAG implementation is staged including generic evidence integration, strict output contract and cache-aware exact cost; dependency verification, real staging/eval/performance, WorkOS frontend build and manual UAT remain open
IN_REVIEW | S-06.01.01 | F-06.01 | Provider registry/gateway implementation, migration, tests, docs and cache-token usage propagation are staged; executable passing verification remains outstanding
BLOCKED | S-06.02.01 | F-06.02 | Cache-aware usage/cost/budget implementation and request-scoped cost audit are staged; tests are written but unexecuted and S-06.01.01 remains unverified
IN_REVIEW | S-06.03.01 | F-06.03 | External API registry/lifecycle/expiry implementation is staged; executable passing verification remains outstanding
BLOCKED | S-07.01.01 | F-07.01 | Evidence-backed project-status backend, deterministic structured progress, migration, tests/docs/UAT are staged; depends on S-04.02.01 completion plus executable verification and production frontend UAT
BACKLOG | S-07.02.01 | F-07.02 | Depends on project status + usage/cost
BLOCKED | S-08.01.01 | F-08.01 | Governed agent runtime is staged; dependencies and this story still lack executable passing verification
IN_REVIEW | S-09.01.01 | F-09.01 | Observability implementation/tests/docs/UAT are staged; executable passing verification remains outstanding
IN_REVIEW | S-09.02.01 | F-09.02 | Audit/retention/deletion implementation/tests/docs/UAT are staged; executable PostgreSQL/Ruff/Pytest/Delivery Verifier evidence remains outstanding
BLOCKED | S-09.03.01 | F-09.03 | Release/rollback/restore work plus a concrete Render staging Blueprint are staged; real deployment/recovery exercise and OQ-007 production topology remain unresolved
BLOCKED | S-09.04.01 | F-09.04 | Performance/cost benchmark work is staged; no real Ask Brain staging performance run exists yet
DEFERRED | S-10.01.01 | F-10.01 | Revisit after E-01 through E-05 prove external-tool wedge

## Current implementation train — S-02.04 / S-05.02 / S-04.02 / S-07.01

Project-owner direction on 2026-09-10: continue implementation on the existing `increment-10-ai-provider-gateway` branch without running the deferred S-05.01.01 local pytest/Render acceptance gate yet. Dependency rules remain binding for formal story status; implementation presence is not a PASS.

### S-02.04.01 Meeting/document evidence

Staged now:

- generic governed upload for UTF-8 text/Markdown/CSV/JSON/VTT/SRT plus text-extractable PDF and DOCX;
- immutable SHA-256 source identity, bounded parsing and deterministic overlapping chunks;
- RawEvent -> CanonicalEvent -> Work Graph -> Search projection with source/chunk provenance;
- organisation or restricted visibility using the existing Work Graph resource-grant boundary;
- idempotency, source lifecycle, retention/deletion integration and audit events;
- migration `20260910_0017`, tests, docs and UAT contract.

Formal state: `IN_REVIEW`. No executable test/UAT evidence is claimed.

### S-05.02.01 Ask Brain

Staged now:

- permission-aware Ask Brain retrieval with no-evidence/no-provider-call behaviour;
- source-agnostic RAG, including generic meeting/document evidence through the same Search contract;
- explicit tenant provider/model selection and safe organisation/runtime discovery for normal `ai.use` users;
- prompt-injection boundary, bounded evidence/citation excerpts and an 8,192-token output ceiling;
- exact JSON output contract: unexpected top-level or claim fields fail closed;
- every factual claim must cite one or more server-issued evidence IDs; unknown/malformed citations fail closed;
- two-phase deployed evaluation separating automatic retrieval/security checks from human semantic claim-citation review;
- OQ-005 resolution: OpenAI API + `gpt-5.6-terra` first candidate, conditional on all acceptance gates;
- cache-aware token/cost accounting, request-scoped exact-cost audit and Render staging bootstrap/runbooks;
- generic-evidence and strict-output regression tests written but not executed.

Formal state: `BLOCKED`, because S-05.01.01 is still `IN_REVIEW` and the real provider/eval/performance/frontend acceptance evidence does not exist.

### S-04.02.01 Decision and Blocker Memory

Staged now:

- deterministic explicit-marker candidate extraction from permission-aware Search evidence, including generic meeting/document evidence;
- machine output remains candidate-only with confidence/state/evidence identifiers;
- idempotent extraction and supersession for unreviewed machine candidates;
- human review history is authoritative: reviewed/reopened candidates are not silently superseded or rewritten by later machine extraction;
- review mutation locks the candidate row before state transition to prevent concurrent review races;
- confirm/reject/edit/resolve/reopen history remains immutable and permission-aware;
- regression contracts for generic transcript extraction and human-authority re-extraction are written but not executed.

Formal state: `BLOCKED` until S-05.01.01 receives executable passing verification and this story's own precision/UAT gates run.

### S-07.01.01 Project Command Centre

Staged now:

- explicit `ProjectProgressItem` structured work state/weight model;
- percentage is calculated only from currently visible configured structured work; no configuration returns `null`, never an AI estimate;
- project status is deterministic; unconfirmed blocker candidates cannot mark a project blocked;
- project/work-item visibility uses Work Graph permissions;
- project evidence is discovered via permission-aware Work Graph traversal and intersected again with live permission-aware Search before provenance is returned;
- human-confirmed decisions/blockers and machine candidates are separate response collections;
- progress mutations are audited and arbitrary unlinked work items cannot affect a project;
- project list/detail/progress APIs, migration `20260910_0018`, tests, docs and `UAT/F-07.01.md` are staged.

Formal state: `BLOCKED` because its S-04.02.01 dependency is not DONE and no executable/backend/frontend UAT evidence exists.

## Deferred acceptance gate

`S-05.01.01` stays `IN_REVIEW`. The project owner explicitly deferred its local pytest + Render verification. That gate must later prove tenant isolation, current permission filtering, revocation, provenance and retrieval quality before dependent features can advance to accepted states.

After that verification, run the dependent executable suites/migrations, real OpenAI/Terra compatibility and cache-aware exact-cost smoke, representative Ask Brain retrieval/RAG evaluation, human citation review, staging performance, decision-memory precision/UAT, project-status permission/revocation UAT, and the official WorkOS authenticated frontend/manual paths.

Production quality gates remain: retrieval recall >=90%, zero forbidden evidence exposure/grounding-contract failures, every exact generated claim-citation pair human reviewed, semantic citation correctness >=98%, Decision/Blocker precision >=90% on the agreed representative set, and Ask Brain p95 <10 seconds on the accepted staging runtime.

No new `EVIDENCE` block may be added for these stories and no story may be marked `DONE/PASSED` until its required checks actually execute successfully.
