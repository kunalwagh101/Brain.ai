# Brain Delivery Board

Method: two-week Scrum increments with Kanban flow inside the sprint. WIP limit: 2 engineering items in `IN PROGRESS` at once.

## DONE

- BRN-000 Product boundary and production architecture agreed.
- BRN-001A FastAPI runtime and configuration.
- BRN-001B PostgreSQL connection layer and readiness probe.
- BRN-001C Core organisation/user/membership schema and first migration.
- BRN-001D Backend tests and CI workflow.

## IN PROGRESS

- BRN-002 Organisations and identity API.

## READY

- BRN-003 Authentication provider integration.
- BRN-004 Tenant/RBAC enforcement dependency layer.

## BACKLOG

- BRN-005 Integration framework.
- BRN-006 Slack connector.
- BRN-007 GitHub connector.
- BRN-008 Canonical event platform.
- Remaining items live in `PRODUCT_BACKLOG.md`.

## Definition of Ready

A story has a measurable user/system outcome, acceptance criteria, known security boundary, dependencies identified, and test strategy.

## Definition of Done

Implementation, migrations, negative-path handling, tests, lint, security boundary, observability required by the slice, documentation and staging acceptance are complete. A UI mock or happy-path-only implementation is not Done.
