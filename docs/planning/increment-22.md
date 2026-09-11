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
