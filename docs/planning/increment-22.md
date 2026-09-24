# Increment 22 — Brain Workspace Frontend

## Goal

Turn Brain from a backend-heavy control plane plus sample preview into the Slack/Discord-style company workspace requested by the product owner, without weakening the permission, provenance or authentication boundaries already built.

## Product correction

The previous backlog treated `S-10.01.01` native chat as the only explicit collaboration/frontend story and deferred it. That incorrectly conflated two decisions:

1. Brain does not need to clone all of Slack before the external-tool intelligence wedge is proven.
2. Brain still requires a Slack/Discord-style **workspace frontend** for the MVP.

Increment 22 separates those concerns. The workspace shell and live intelligence are P0. Native message persistence, threads/DMs and advanced collaboration are separate P1 stories.

## Frontend feature train

| Story | Capability | Priority | Current state |
|---|---|---:|---|
| S-10.02.01 | Workspace shell + permission-aware navigation | P0 | IN_PROGRESS |
| S-10.03.01 | Ask Brain / projects / memory / company pulse inside workspace | P0 | IN_PROGRESS |
| S-10.04.01 | Official WorkOS Next.js 16 auth + same-origin BFF | P0 | BLOCKED on official package install/lockfile + authenticated execution |
| S-10.05.01 | Governed files/evidence workspace | P0 | BACKLOG |
| S-10.01.01 | Brain-native channels/messages | P1 | BACKLOG |
| S-10.06.01 | Threads/mentions/reactions/unread | P1 | BACKLOG |
| S-10.06.02 | Permission-safe DMs | P1 | BLOCKED on OQ-002 private-message policy |
| S-10.07.01 | Developer/agent workspace | P1 | BACKLOG |
| S-10.08.01 | Workspace admin/integrations/governance UI | P1 | BACKLOG |

WIP remains within the repository limit: S-10.02.01 and S-10.03.01 are the only frontend stories intentionally `IN_PROGRESS`; S-10.04.01 remains `BLOCKED` rather than consuming a WIP slot.

## S-10.02.01 — workspace shell

Staged:

- `GET /api/v1/organizations/{organization_id}/workspace-navigation` read model;
- navigation exposes only permission-visible Work Graph `project` and `track` nodes;
- hidden resource names/counts are filtered before response serialization;
- cross-tenant and restricted-node regression contracts;
- typed frontend workspace-navigation API contract;
- `ProductionWorkspace` lets normal members use Brain and gates Executive Overview separately;
- real organisation switcher derived from authenticated Brain memberships;
- Slack/Discord-style four-region desktop shell: workspace rail, navigation sidebar, main surface and context rail;
- real project/track labels from Brain data rather than hard-coded departments;
- responsive layouts, skip navigation and focus contracts;
- no fake channel/chat/file data while their live routes are not yet wired.

## S-10.03.01 — live intelligence

Staged:

- Project Command Centre embedded in the workspace with deterministic progress/status;
- expandable structured work and permission-filtered project evidence;
- confirmed decisions/blockers with canonical/search/work-graph provenance identifiers;
- Executive/Company Pulse rendered only for Owner/Admin/Executive roles and backed by S-07.02;
- known AI spend remains exact nanoUSD-derived money and incomplete cost remains explicit;
- governed AI runtime discovery for roles with `ai.use`;
- Ask Brain panel uses only a same-origin endpoint, exposes no bearer-token prop and renders bounded errors;
- Ask Brain citation drill-down exposes server-issued evidence/source/provenance identifiers;
- source-contract tests cover role separation, real navigation, no employee scoring, same-origin Ask Brain and BFF membership validation;
- `UAT/F-10.03.md` defines real browser/data reconciliation gates.

Ask Brain remains visibly disabled in the active root until S-10.04 activates the authenticated BFF. This is deliberate; the UI does not point a button at a dead route or move a reusable backend credential into the browser.

## S-10.04.01 — WorkOS/BFF

Repo-side staging completed without fabricating dependencies:

- current official Next.js 16 contract reviewed: `authkitProxy()`, `handleAuth()`, `getSignInUrl()`, `withAuth()`, `AuthKitProvider`, `signOut()`;
- `scripts/install-workos-authkit.sh` installs official npm packages and verifies real lockfile `resolved`/`integrity` entries;
- reviewed source templates live under `docs/workos-activation/` for root proxy, callback, sign-in, provider layout, protected root workspace and Ask Brain BFF route;
- `scripts/activate-workos-authkit.sh` refuses missing/unpinned packages or missing environment values, copies only reviewed templates, then runs lint/build/frontend tests;
- BFF request parser uses an exact field allowlist, UUID checks and bounded query/output limits;
- BFF helper confirms the requested organisation is present in the authenticated Brain membership list before forwarding;
- BFF route template limits body size/content type and never reflects raw upstream/provider detail;
- production workspace has a WorkOS `signOut()` server-action slot;
- `UAT/F-10.04.md` defines PKCE/session/token/browser-secret/logout/organisation-denial acceptance.

The actual `app/page.tsx` remains the labelled preview and no AuthKit imports are active until npm can install the official packages and generate a trusted lockfile. This is a security/build-integrity boundary, not unfinished intent.

## Rules

- Do not hard-code sample teams such as Sales/Backend/AI just to make the sidebar look full. They may appear only when real tenant data/configuration creates them.
- A hidden project/track must not leak through labels, counts, badges or navigation ordering.
- Executive access is a capability inside the workspace; lack of `audit.read` must not lock a normal member out of Brain itself.
- Root production routing remains on the honest sample preview until official WorkOS AuthKit is installed and a real lockfile/build exists.
- No hand-written OAuth/PKCE/session replacement is permitted.
- Native channels/messages are not simulated in S-10.02.01; they belong to S-10.01.01.
- The browser never receives a reusable Brain/WorkOS backend bearer token for ordinary API use.
- No story may be moved to DONE from source presence alone.

## Acceptance boundary

- S-10.02.01 may move to `IN_REVIEW` only after frontend lint/build/tests and permission-negative backend contracts execute successfully; DONE also requires authenticated browser navigation/responsive/accessibility UAT.
- S-10.03.01 may move to `IN_REVIEW` only after its dependencies and frontend contracts execute; DONE requires real project/memory/executive/Ask-Brain reconciliation in `UAT/F-10.03.md`.
- S-10.04.01 remains `BLOCKED` until official packages/lockfile exist and activation compiles; DONE requires the authenticated browser/security evidence in `UAT/F-10.04.md` and `docs/WORKOS_FRONTEND_ACCEPTANCE.md`.

## CHECK closure work orders — 2026-09-24

Mode: **CHECK**. Role: **Senior full-stack engineer / systems architect, architect tier**. These are verification/closure work orders for already-implemented stories. Production behaviour is DO NOT TOUCH unless an executable check exposes a defect.

### Work order — S-10.07.01 Developer & Agent Workspace

**GOAL** — verify that an authorised engineer can run only governed agents in currently visible project/channel context, see approval-gated actions clearly, and never receive a generic shell or reusable credential.

**FILES UNDER REVIEW**
- `backend/app/agent_workspace.py`
- `backend/app/agent_workspace_models.py`
- `backend/app/routes/agent_workspace.py`
- `backend/app/routes/agent_workspace_actions.py`
- `backend/tests/test_agent_workspace.py`
- `app/agent-workspace-api.ts`
- `app/agent-workspace-bff.ts`
- `app/agent-workspace-panel.tsx`
- `tests/agent-workspace-contract.test.mjs`
- `UAT/F-10.07.md`

**DO NOT TOUCH** — S-08.01 agent-runtime policy semantics, S-10.02 workspace navigation/auth boundaries, WorkOS activation templates, provider/model business rules, or any database schema unless a failing accepted test proves the current contract is wrong.

**INTERFACES** — preserve the existing `resolve_workspace_context(...)`, `create_workspace_run(...)`, requester-private run reads, `/agent-workspace/runs`, `/advance`, approval, cancel, and same-origin BFF contracts exactly.

**TEST**
```bash
cd backend
pytest -q tests/test_agent_workspace.py tests/test_agent_runtime.py tests/test_agent_routes.py tests/test_agent_kill_switch.py
cd ..
node --test tests/agent-workspace-contract.test.mjs
```

**FULL REGRESSION / RELEASE**
```bash
cd backend && ruff check app tests migrations && pytest -q
cd ..
npm run build
node --test tests/*.test.mjs
python scripts/verify_board.py
```

**DONE WHEN** — the automated commands pass, migration/release recovery stays green, and the authenticated WorkOS browser UAT in `UAT/F-10.07.md` passes. If WorkOS/browser UAT cannot be executed, do not call the story DONE; record the external blocker.

### Work order — S-10.08.01 Workspace Administration

**GOAL** — verify Owner/Admin governance for members, integrations, AI providers/models and external API grants without exposing stored secrets or allowing role spoofing.

**FILES UNDER REVIEW**
- `backend/app/routes/admin_center.py`
- `backend/app/ai_provider_credentials.py`
- `backend/app/routes/ai_provider_credentials.py`
- `backend/tests/test_admin_center.py`
- `backend/tests/test_membership_governance.py`
- `backend/tests/test_ai_provider_credentials.py`
- `backend/tests/test_api_registry.py`
- `app/admin-center-api.ts`
- `app/admin-center-bff.ts`
- `app/admin-center-panel.tsx`
- `tests/admin-center-contract.test.mjs`
- `UAT/F-10.08.md`

**DO NOT TOUCH** — membership role policy, integration secret lifecycle, S-06.01/S-06.03 credential semantics, WorkOS auth/session design, or database schema unless a failing accepted test proves a defect.

**INTERFACES** — preserve the existing Admin Center aggregate, membership governance routes, AI credential rotation, API-registry lifecycle, exact allow-listed BFF actions, 32 KiB same-origin mutation boundary, and secret-reference-only persistence.

**TEST**
```bash
cd backend
pytest -q tests/test_admin_center.py tests/test_membership_governance.py tests/test_ai_provider_credentials.py tests/test_api_registry.py tests/test_api_registry_worker.py
cd ..
node --test tests/admin-center-contract.test.mjs
```

**FULL REGRESSION / RELEASE**
```bash
cd backend && ruff check app tests migrations && pytest -q
cd ..
npm run build
node --test tests/*.test.mjs
python scripts/verify_board.py
```

**DONE WHEN** — automated commands pass, release/migration recovery stays green, and the real secret-store plus authenticated Owner/Admin/Member browser UAT in `UAT/F-10.08.md` passes. If those external checks cannot run, record the blocker instead of claiming DONE.
