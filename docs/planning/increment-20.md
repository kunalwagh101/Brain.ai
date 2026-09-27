# Increment 20 — F-07.01 Project Command Centre

Story: `S-07.01.01`

Implementation branch: `increment-10-ai-provider-gateway` (reused by explicit project-owner direction; no new branch).

Formal state: **BLOCKED** until `S-04.02.01` becomes engineering-DONE. Implementation may be staged against the existing Work Graph/decision-memory contracts, but this record does not waive dependency or acceptance gates.

## Goal

Expose project status that is useful to leaders without inventing progress or leaking restricted evidence.

## Vertical slice

`Work Graph project -> configured structured work items -> deterministic progress/status -> currently authorised project evidence -> human-confirmed decisions/blockers -> project-status API`

## Implemented scope

- `ProjectProgressItem` model for explicit structured project work state and weight.
- Deterministic progress percentage; `null` when no structured progress configuration exists.
- Deterministic status rules; machine blocker candidates cannot directly mark a project blocked.
- Current Work Graph node visibility enforcement for projects/work items.
- Permission-aware Work Graph traversal to discover project evidence.
- Second permission intersection through Search before evidence metadata/provenance is returned.
- Confirmed decisions/blockers separated from unconfirmed candidates.
- Audit events for progress item create/update/delete.
- Project list/detail endpoints and structured progress mutation endpoints.
- Migration `20260910_0018_project_status.py`.
- Contract tests and `UAT/F-07.01.md` staged but not executed in this pass.

## Explicit non-goals

- No AI-generated project completion percentage.
- No employee productivity/worth score.
- No inferred hidden-work count or percentage adjustment for resources the caller cannot access.
- No separate project-document ACL system; Work Graph + Search remain the authorization/evidence authorities.
- No production frontend authentication workaround. The official WorkOS frontend path remains required before browser UAT.

## Acceptance gates still required

1. Upstream `S-05.01.01` executable permission-aware retrieval verification passes.
2. `S-04.02.01` receives its required executable/security/precision/UAT evidence and becomes engineering-DONE.
3. Project-status backend tests and migration checks execute successfully.
4. Real restricted-source and revocation UAT passes.
5. Deterministic percentage is independently recomputed from structured work in UAT.
6. Production WorkOS frontend can display progress basis, contributing work, evidence, confirmed/candidate memory states and permission-safe empty states.
7. Manual browser/accessibility UAT passes.

Until those gates pass, implementation presence must not be represented as `DONE` or `PASSED`.
