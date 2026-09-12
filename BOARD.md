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
IN_REVIEW | S-05.01.01 | F-05.01 | Implementation/docs/tests including provenance contract exist; acceptance phase started on 2026-09-11, but latest GitHub jobs failed before any workflow step executed and no local/Render passing evidence exists
BLOCKED | S-05.02.01 | F-05.02 | Backend RAG implementation is staged including generic evidence integration, strict output contract and cache-aware exact cost; dependency verification, real staging/eval/performance, WorkOS frontend build and manual UAT remain open
IN_REVIEW | S-06.01.01 | F-06.01 | Provider registry/gateway implementation, migration, tests, docs and cache-token usage propagation are staged; executable passing verification remains outstanding
BLOCKED | S-06.02.01 | F-06.02 | Cache-aware usage/cost/budget implementation and request-scoped cost audit are staged; tests are written but unexecuted and S-06.01.01 remains unverified
IN_REVIEW | S-06.03.01 | F-06.03 | External API registry/lifecycle/expiry implementation is staged; executable passing verification remains outstanding
BLOCKED | S-07.01.01 | F-07.01 | Evidence-backed project-status backend, deterministic structured progress, migration, tests/docs/UAT are staged; depends on S-04.02.01 completion plus executable verification and production frontend UAT
BLOCKED | S-07.02.01 | F-07.02 | Permission-aware executive overview, AI spend/budget risk, API activity, provenance, tests/docs/UAT are staged; depends on S-07.01.01 + S-06.02.01 completion and executable/frontend UAT
BLOCKED | S-08.01.01 | F-08.01 | Governed agent runtime is staged; dependencies and this story still lack executable passing verification
IN_REVIEW | S-09.01.01 | F-09.01 | Observability implementation/tests/docs/UAT are staged; executable passing verification remains outstanding
IN_REVIEW | S-09.02.01 | F-09.02 | Audit/retention/deletion implementation/tests/docs/UAT are staged; executable PostgreSQL/Ruff/Pytest/Delivery Verifier evidence remains outstanding
BLOCKED | S-09.03.01 | F-09.03 | Release/rollback/restore work plus a concrete Render staging Blueprint are staged; real deployment/recovery exercise and OQ-007 production topology remain unresolved
BLOCKED | S-09.04.01 | F-09.04 | Performance/cost benchmark work is staged; no real Ask Brain staging performance run exists yet
IN_REVIEW | S-10.01.01 | F-10.01 | Native channel/message persistence, evidence projection, restricted memberships, API/BFF/UI and tests are implemented; executable CI, migration and authenticated browser UAT evidence remain pending
BLOCKED | S-10.02.01 | F-10.02 | Workspace shell, real organisation switching, navigation API/client, responsive controls, tests/docs/UAT are staged; authenticated browser acceptance cannot advance until S-10.04 official WorkOS activation exists
BLOCKED | S-10.03.01 | F-10.03 | Project/memory/company-pulse/evidence surfaces, runtime discovery and citation-first Ask Brain UI are staged; live authenticated Ask Brain/browser acceptance depends on S-10.04
BLOCKED | S-10.04.01 | F-10.04 | Official WorkOS Next.js 16 templates, guarded install/activation scripts and BFF security contract are staged; blocked on real npm package/lockfile installation plus authenticated browser execution
BLOCKED | S-10.05.01 | F-10.05 | Repository implementation is staged; external S-10.04 WorkOS activation plus executable backend/browser acceptance remain pending
IN_PROGRESS | S-10.06.01 | F-10.06 | Building focused channel UX plus tenant-safe threads, exact-member mentions, reactions and per-user unread state on the existing S-10.01 foundation
BLOCKED | S-10.06.02 | F-10.06 | Permission-safe DMs require S-10.01.01 plus explicit OQ-002 private-message policy
BACKLOG | S-10.07.01 | F-10.07 | Developer/agent workspace over governed repo/agent contracts
BACKLOG | S-10.08.01 | F-10.08 | Workspace admin UI for integrations, members, permissions and AI/API governance

## Current implementation train — S-02.04 / S-05.02 / S-04.02 / S-07.01 / S-07.02

Project-owner direction on 2026-09-10 allowed implementation to continue without the S-05.01.01 execution gate. On 2026-09-11 the project owner said to proceed into the acceptance phase. Dependency rules remain binding: implementation presence is not a PASS, and a workflow failure before step execution is not a test result.

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

### S-07.02.01 Executive Overview

Staged now:

- `audit.read`-gated month-to-date executive overview API;
- full currently visible S-07.01 portfolio with deterministic project status/progress and per-project metric provenance;
- organisation-level deduplicated human-confirmed blockers and decisions with canonical/search/work-graph source IDs and visible project links;
- exact S-06.02 AI request/token/cached-token/known-cost totals plus provider breakdown and explicit incomplete-cost state;
- live enabled budget warnings/exhaustion/incomplete-enforcement math, with Work-Graph-scoped warnings filtered by current node visibility;
- trusted S-06.03 external API activity and active-grant counts plus an audited `/api-registry/usage` drill-down that exposes no secret material;
- external API monetary cost deliberately remains `null` / `not_modeled` because no reviewed API tariff ledger exists; call counts are never converted into money;
- deterministic risks only from project blocked state, budget state, incomplete AI cost and explicit API-cost-model absence;
- no employee productivity/worth/activity ranking and no productivity-score field exists in the API contract;
- backend contract/security tests, `docs/EXECUTIVE_OVERVIEW.md`, Increment 21 planning and `UAT/F-07.02.md` are staged.

Formal state: `BLOCKED`. Its S-07.01.01 and S-06.02.01 dependencies are not DONE, and no executable backend, reconciliation, permission/revocation, frontend or accessibility UAT has run.

## Frontend delivery train — E-10

The product owner clarified on 2026-09-11 that Brain's requested frontend is a Slack/Discord-style company workspace. The earlier single deferred native-chat story did not adequately represent that requirement. `PRODUCT_BACKLOG.md` separates the P0 workspace frontend from P1 native collaboration.

The board WIP rule is now explicit in this train: S-10.02 and S-10.03 have their repository implementation staged but cannot advance through authenticated browser acceptance without S-10.04. They are therefore represented as `BLOCKED`, freeing the active implementation slot for S-10.05 rather than accumulating a third unfinished story.

### S-10.02.01 Workspace Shell and Navigation — BLOCKED

Staged now:

- permission-aware `/workspace-navigation` read model over Work Graph projects/tracks;
- restricted resource labels are filtered before serialization;
- cross-tenant and restricted-resource regression contracts;
- typed frontend workspace-navigation client;
- role-aware `ProductionWorkspace` that allows normal members into Brain and only gates Company Pulse itself;
- desktop organisation picker plus responsive server-driven organisation switch form;
- Slack/Discord-style workspace rail + navigation sidebar + main work surface + context rail;
- real visible project/track labels and status;
- responsive CSS module, keyboard skip path and focus treatment;
- frontend source-contract tests included in `npm test`;
- `docs/planning/increment-22.md` and `UAT/F-10.02.md`.

Formal state: `BLOCKED` on S-10.04 for real authenticated root/browser execution. Frontend/backend tests and responsive/accessibility UAT are not claimed as passed.

### S-10.03.01 Live Intelligence Surfaces — BLOCKED

Staged now:

- real Project Command Centre progress/status inside the workspace;
- expandable structured work and permission-filtered project evidence;
- human-confirmed decision/blocker views with source provenance identifiers;
- role-gated Executive/Company Pulse without locking normal members out of Brain;
- governed runtime discovery only for roles with `ai.use`;
- citation-first Ask Brain component using only a same-origin endpoint;
- bounded browser error states that do not reflect arbitrary backend/provider detail;
- Ask Brain BFF helper validates request shape and authenticated Brain organisation membership before forwarding;
- `UAT/F-10.03.md` defines live browser/data reconciliation.

Formal state: `BLOCKED`. Ask Brain browser mutation remains deliberately inactive in the current preview root until S-10.04 activates official WorkOS/BFF. No frontend execution/UAT PASS is claimed.

### S-10.04.01 Production WorkOS Auth + BFF — BLOCKED

Repo-side staging now:

- official current Next.js 16 AuthKit contract reviewed;
- official npm installer verifies real package-lock resolution/integrity and never invents package metadata;
- reviewed templates for `authkitProxy()`, `handleAuth()`, `getSignInUrl()`, `AuthKitProvider`, protected `withAuth()` root, `signOut()`, Ask Brain BFF and evidence upload/delete BFF routes;
- guarded activation script requires installed/pinned packages plus WorkOS/Brain environment values before copying templates and running lint/build/tests;
- same-origin BFF routes use server-side `withAuth()`, bounded request validation, membership validation and secret-safe errors;
- evidence upload BFF additionally performs a bounded multipart stream read and preserves the 10 MB backend file contract;
- `UAT/F-10.04.md` and `docs/WORKOS_FRONTEND_ACCEPTANCE.md` remain the authenticated security gates.

Formal state: `BLOCKED`. The current environment cannot obtain the official npm packages/real lockfile, and no authenticated WorkOS browser/session execution has occurred. The active root remains the explicitly labelled preview until this external gate is satisfied.

### S-10.05.01 Governed Files & Evidence Workspace — IN_PROGRESS

Staged now:

- permission-correct evidence workspace read model that applies requested limits after visibility filtering rather than allowing hidden rows to starve the page;
- server-computed `can_delete` capability while FastAPI remains the authoritative deletion boundary;
- backend regressions for hidden-row pagination and uploader/Owner/Admin delete presentation;
- typed evidence-source frontend API plus server-side evidence loading;
- Files & evidence surface embedded in the Brain shell with lifecycle state, source hash, provenance, local filtering and role-aware read-only/upload behavior;
- supported-format guidance matching S-02.04 and no fake OCR/download/folder semantics;
- browser mutations target same-origin BFF only and never receive a reusable backend bearer token;
- reviewed WorkOS templates for bounded multipart upload and governed delete routes;
- two-step deletion confirmation plus safe browser error messages;
- frontend source-contract tests, `docs/planning/increment-23.md` and `UAT/F-10.05.md`.

Still required before review/acceptance:

- execute backend evidence workspace tests and the S-02.04/S-05.01 dependency gates;
- execute frontend lint/build/source-contract tests;
- activate S-10.04 with official WorkOS packages and a genuine generated lockfile;
- run real browser UAT proving upload -> Search/Ask Brain -> delete/revoke disappearance and restricted-source isolation;
- run accessibility/responsive verification.

Formal state: `IN_PROGRESS`. No executable PASS or browser UAT is claimed.

## Acceptance phase

`S-05.01.01` stays `IN_REVIEW`. Acceptance execution has now started, but the latest branch-head GitHub runs for Backend CI, Delivery Verifier and Release Gate all failed before any workflow step executed; their job step lists were empty. This supplies no pytest/Ruff/verifier result and does not satisfy the gate. The required local and Render verification must still prove tenant isolation, current permission filtering, revocation, provenance and retrieval quality before dependent features can advance to accepted states.

After S-05.01.01 obtains real passing execution evidence, run the dependent executable suites/migrations, real OpenAI/Terra compatibility and cache-aware exact-cost smoke, representative Ask Brain retrieval/RAG evaluation, human citation review, staging performance, decision-memory precision/UAT, project-status permission/revocation UAT, Executive Overview permission/cost/budget/API reconciliation UAT, and the official WorkOS authenticated frontend/manual paths including S-10.05 evidence lifecycle UAT.

Production quality gates remain: retrieval recall >=90%, zero forbidden evidence exposure/grounding-contract failures, every exact generated claim-citation pair human reviewed, semantic citation correctness >=98%, Decision/Blocker precision >=90% on the agreed representative set, and Ask Brain p95 <10 seconds on the accepted staging runtime.

No new `EVIDENCE` block may be added for these stories and no story may be marked `DONE/PASSED` until its required checks actually execute successfully.