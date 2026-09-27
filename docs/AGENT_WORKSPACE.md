# Developer & Agent Workspace

Story: `S-10.07.01` / feature `F-10.07`.

## Purpose

Brain places governed agent work beside the project/channel context it operates on. This is not a browser terminal and it does not grant a generic shell. The workspace only exposes agents and tools already authorized by the S-08.01 runtime.

## Context contract

A workspace-originated run must bind to at least one current, permission-visible scope:

- a Work Graph `project` node; and/or
- a Brain-native channel.

The backend validates context before creating the run. Cross-tenant IDs and currently restricted resources fail closed. The binding is persisted in `agent_run_contexts` and audited separately from the underlying run.

If project/channel access is later revoked, the requester can retain the run as audit/history, but the current context name/details are redacted from the workspace read model.

## Identity and tool contract

The workspace returns:

- approved agent definition identity;
- provider key/display name and model key/display name;
- configured tool policies;
- tool risk and replay-safety metadata;
- explicit `approval_required` state for `act_with_approval` tools;
- run and step state;
- known structured artifacts produced by approved tools.

It never returns provider `secret_ref`, API credentials or a reusable Brain/WorkOS token.

Current approved tool catalog remains intentionally narrow:

- `search.query` — read-only;
- `work_graph.create_work_item` — high-risk action requiring explicit approval when enabled.

There is no arbitrary shell, git command executor, filesystem browser or browser-side repository credential path in S-10.07.

## Objective handling

The S-08 runtime stores objective SHA-256 and character count, not objective plaintext. S-10.07 preserves that boundary. A browser can use the objective for the live request, but after a reload the user must re-enter it to continue a run that requires another planning step.

This is deliberate: convenience does not silently widen prompt retention.

## Workspace API

- `GET /api/v1/organizations/{organization_id}/agent-workspace`
- `POST /api/v1/organizations/{organization_id}/agent-workspace/runs`
- `GET /api/v1/organizations/{organization_id}/agent-workspace/runs/{run_id}`

Core governed run mutations remain in S-08.01 and are wrapped by the production same-origin BFF:

- advance run;
- approve/reject step;
- cancel run.

The workspace list/read model is requester-scoped. A user cannot enumerate another user's runs simply because they share an organization.

## Frontend architecture

Authenticated server rendering loads the user's approved agents and requester-owned runs. Visible projects/channels already returned by Brain are used as selector options. Browser mutation code calls only same-origin Next.js routes.

Production flow:

`browser -> WorkOS encrypted session -> Next.js BFF -> server access token -> FastAPI -> Brain authorization/runtime`

The browser never receives the reusable access token.

## Artifacts

Artifacts are not inferred from model prose. They are created only from known successful tool result metadata. Today the workspace renders `work_graph.create_work_item` output as a structured work-item artifact.

Patch/PR artifacts must not be displayed until a separately governed tool actually produces reviewed patch/PR metadata. S-10.07 does not fabricate repository-writing capability.

## Acceptance boundary

Implementation presence is not acceptance. S-10.07 remains non-DONE until:

1. migration `20260916_0021` is verified on PostgreSQL;
2. backend requester/context/approval regressions execute successfully;
3. frontend lint/build/source-contract tests pass;
4. official WorkOS AuthKit routes are activated with genuine packages/lockfile;
5. authenticated browser UAT proves context filtering, approval/cancel flows and absence of browser credentials;
6. no hidden project/channel label or unauthorized tool can be surfaced.
