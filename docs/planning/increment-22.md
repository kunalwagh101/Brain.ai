# Increment 22 — Brain Workspace Frontend

## Goal

Turn Brain from a backend-heavy control plane plus sample preview into the Slack/Discord-style company workspace requested by the product owner, without weakening the permission, provenance or authentication boundaries already built.

## Product correction

The previous backlog treated `S-10.01.01` native chat as the only explicit collaboration/frontend story and deferred it. That incorrectly conflated two decisions:

1. Brain does not need to clone all of Slack before the external-tool intelligence wedge is proven.
2. Brain still requires a Slack/Discord-style **workspace frontend** for the MVP.

Increment 22 separates those concerns. The workspace shell is P0. Native message persistence, threads/DMs and advanced collaboration are separate P1 stories.

## Frontend feature train

| Story | Capability | Priority | State at start |
|---|---|---:|---|
| S-10.02.01 | Workspace shell + permission-aware navigation | P0 | IN_PROGRESS |
| S-10.03.01 | Ask Brain / projects / memory / company pulse inside workspace | P0 | BACKLOG |
| S-10.04.01 | Official WorkOS Next.js 16 auth + same-origin BFF | P0 | BLOCKED on official package install/lockfile |
| S-10.05.01 | Governed files/evidence workspace | P0 | BACKLOG |
| S-10.01.01 | Brain-native channels/messages | P1 | BACKLOG |
| S-10.06.01 | Threads/mentions/reactions/unread | P1 | BACKLOG |
| S-10.06.02 | Permission-safe DMs | P1 | BLOCKED on OQ-002 private-message policy |
| S-10.07.01 | Developer/agent workspace | P1 | BACKLOG |
| S-10.08.01 | Workspace admin/integrations/governance UI | P1 | BACKLOG |

## S-10.02.01 vertical slice

Staged in this increment:

- new `GET /api/v1/organizations/{organization_id}/workspace-navigation` read model;
- navigation exposes only permission-visible Work Graph `project` and `track` nodes;
- hidden resource names/counts are filtered before response serialization;
- cross-tenant and restricted-node regression contracts;
- typed frontend workspace-navigation API contract;
- `ProductionWorkspace` composition that allows normal members into the workspace and only gates the Executive Overview itself;
- Slack/Discord-style four-region desktop shell: workspace rail, navigation sidebar, main surface and context rail;
- real project/track labels from Brain data rather than hard-coded departments;
- responsive layouts and keyboard skip target;
- no fake channel/chat/file/Ask-Brain data while their live routes are not yet wired.

## Rules

- Do not hard-code sample teams such as Sales/Backend/AI just to make the sidebar look full. They may appear only when real tenant data/configuration creates them.
- A hidden project/track must not leak through labels, counts, badges or navigation ordering.
- Executive access is a capability inside the workspace; lack of `audit.read` must not lock a normal member out of Brain itself.
- Root production routing remains on the honest sample preview until official WorkOS AuthKit is installed and a real lockfile/build exists.
- No hand-written OAuth/PKCE/session replacement is permitted.
- Native channels/messages are not simulated in S-10.02.01; they belong to S-10.01.01.
- Ask Brain is not pointed at a dead or insecure browser endpoint; same-origin BFF wiring belongs to S-10.03.01/S-10.04.01.

## Acceptance boundary

S-10.02.01 may move to IN_REVIEW only after the frontend build/lint/tests execute successfully and the permission-negative backend contracts execute. It may move to DONE only after authenticated browser UAT verifies real organisation/project/track navigation, responsive/keyboard behavior and no restricted-resource leakage.
