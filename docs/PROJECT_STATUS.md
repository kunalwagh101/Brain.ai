# Project Command Centre — F-07.01

Story: `S-07.01.01 — Show evidence-backed project progress and blockers`

## Contract

Brain does not infer a project completion percentage from messages, commits, AI judgement, evidence volume, employee activity, or time spent.

A percentage exists only when authorised users explicitly configure structured Work Graph `work_item` nodes as project progress items. Each configured item has:

- a structured state: `not_started`, `in_progress`, `blocked`, or `done`;
- an integer weight from 1 to 10,000;
- an optional operator note;
- an auditable updater and timestamp.

The visible percentage is:

`100 * sum(weight for visible configured items in done) / sum(weight for all visible configured items)`

If no visible structured work is configured, `progress_percent` is `null` and `progress_basis` is `unconfigured`. Brain must never replace that `null` with an AI estimate.

Because Brain is permission-aware, a user's percentage is explicitly labelled `visible_configured_work_items`: restricted work that the user cannot access is not counted and its existence is not leaked.

## Status semantics

The deterministic status is derived from visible structured facts:

- `blocked` when at least one visible configured work item is `blocked`, or a visible blocker memory is human-confirmed;
- `unconfigured` when there are no visible configured progress items;
- `done` when every visible configured item is `done`;
- `in_progress` when at least one visible configured item is `in_progress` or `done` and the project is not blocked/done;
- `not_started` otherwise.

Machine-extracted blocker candidates do **not** make a project blocked. They remain in `candidate_memories` until a human confirms them through F-04.02.

## Evidence model

Project evidence is discovered through the existing permission-aware Work Graph, depth two from the project node, and then intersected with the live permission-aware Search query before any title/provenance is returned.

This supports the existing graph shapes, including:

- GitHub project -> evidence;
- GitHub project -> work item -> evidence;
- an explicitly related generic meeting/document evidence node.

A revoked integration, deleted Search document, removed Slack authorisation, removed private-channel membership, or revoked restricted-resource grant therefore disappears from the project snapshot through the same retrieval boundary used by Search and Ask Brain.

Decision/blocker memory is included only when its underlying Search evidence is currently visible and its evidence Work Graph node is part of the visible project graph.

## API

Read:

- `GET /api/v1/organizations/{organization_id}/project-status`
- `GET /api/v1/organizations/{organization_id}/project-status/{project_node_id}`

Configure structured progress:

- `PUT /api/v1/organizations/{organization_id}/project-status/{project_node_id}/progress-items/{work_item_node_id}`
- `DELETE /api/v1/organizations/{organization_id}/project-status/{project_node_id}/progress-items/{work_item_node_id}`

The work item must already be linked to the project in the Work Graph through `contains`, `related_to`, or `depends_on`. This prevents an arbitrary node from being counted toward another project's progress.

Read operations require `resource.read`; progress mutations require `resource.write`. Work Graph node visibility is checked again inside the service.

## Response evidence

A project snapshot exposes:

- deterministic status and progress basis;
- structured progress items and weights;
- human-confirmed active blockers;
- human-confirmed decisions;
- unconfirmed candidate memories separately;
- authorised source evidence with document/canonical IDs and source provenance.

The response deliberately does not include an AI-created project score or employee productivity/quality score.

## Persistence and audit

`project_progress_items` is the only new persistent domain table. Progress create/update/delete actions append security/governance audit events. Work Graph, Search and decision-memory data remain their own source-of-truth tables rather than being copied into dashboard state.

Migration: `20260910_0018_project_status.py`.

## Current verification state

The implementation and tests are staged on `increment-10-ai-provider-gateway`. They are not claimed as executed in this pass. `S-07.01.01` cannot be marked DONE while its upstream `S-04.02.01` / `S-05.01.01` acceptance dependency remains unresolved and realistic backend/frontend UAT has not run.
