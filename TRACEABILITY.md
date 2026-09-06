# Brain Traceability

This file is the engineering evidence index. A row is completed only after its story is engineering-DONE and has a resolvable evidence block. Real-data/manual feature acceptance is tracked separately in `UAT.md`.

| Story | Epic | Requirement / outcome | Tests | Code | Status |
|---|---|---|---|---|---|
| S-01.01.01 | E-01 | organisation membership + tenant boundary | backend/tests/test_organizations.py | backend/app/routes/organizations.py | DONE |
| S-01.02.01 | E-01 | real authentication | backend/tests/test_auth.py | backend/app/auth.py | DONE |
| S-01.03.01 | E-01 | RBAC/ACL before retrieval | backend/tests/test_permissions.py + backend/tests/test_organizations.py | backend/app/permissions.py + backend/app/routes/organizations.py | DONE |
| S-02.01.01 | E-02 | scoped integration lifecycle | backend/tests/test_integrations.py + backend/tests/test_secrets.py | backend/app/routes/integrations.py + backend/app/secrets.py | DONE |
| S-02.02.01 | E-02 | Slack ingestion | pending | pending | BACKLOG |
| S-02.03.01 | E-02 | GitHub ingestion | pending | pending | BACKLOG |
| S-02.04.01 | E-02 | meeting/document evidence | pending | pending | BACKLOG |
| S-03.01.01 | E-03 | raw durable/idempotent ingestion | pending | pending | BACKLOG |
| S-03.02.01 | E-03 | canonical event model | pending | pending | BACKLOG |
| S-03.03.01 | E-03 | identity resolution | pending | pending | BACKLOG |
| S-04.01.01 | E-04 | work graph | pending | pending | BACKLOG |
| S-04.02.01 | E-04 | decision/blocker memory | pending | pending | BACKLOG |
| S-05.01.01 | E-05 | permission-aware retrieval | pending | pending | BACKLOG |
| S-05.02.01 | E-05 | evidence-backed Ask Brain | pending | pending | BACKLOG |
| S-06.01.01 | E-06 | governed AI gateway | pending | pending | BACKLOG |
| S-06.02.01 | E-06 | AI/API usage and budgets | pending | pending | BACKLOG |
| S-06.03.01 | E-06 | API access registry | pending | pending | BACKLOG |
| S-07.01.01 | E-07 | project command centre | pending | pending | BACKLOG |
| S-07.02.01 | E-07 | executive overview | pending | pending | BACKLOG |
| S-08.01.01 | E-08 | governed agent runtime | pending | pending | BACKLOG |
| S-09.01.01 | E-09 | production observability | pending | pending | BACKLOG |
| S-09.02.01 | E-09 | audit/retention/deletion | pending | pending | BACKLOG |
| S-09.03.01 | E-09 | CI/deploy/rollback/restore | pending | pending | BACKLOG |
| S-09.04.01 | E-09 | latency/cost benchmarks | pending | pending | BACKLOG |
| S-10.01.01 | E-10 | native tracks/chat | pending | pending | DEFERRED |

EVIDENCE S-01.01.01
tests: backend/tests/test_organizations.py::test_cross_tenant_organization_read_returns_not_found
command: cd backend && pytest -q
result: 14 passed (GitHub Actions run 34027972498, 2026-09-06)
code: backend/app/routes/organizations.py
commit: b53d3185000da2ebf05d730a07cb899917165707

EVIDENCE S-01.02.01
tests: backend/tests/test_auth.py::test_verify_access_token_validates_signature_and_claims
command: cd backend && pytest -q
result: 14 passed (GitHub Actions run 34027972498, 2026-09-06)
code: backend/app/auth.py
commit: b53d3185000da2ebf05d730a07cb899917165707

EVIDENCE S-01.03.01
tests: backend/tests/test_permissions.py::test_resource_dependency_denies_before_endpoint_body
command: cd backend && pytest -q
result: 34 passed (GitHub Actions run 34031342636, 2026-09-06)
code: backend/app/permissions.py
commit: 65d0fbc4a3d843e81c1bd036febe7749a9409a8d

EVIDENCE S-02.01.01
tests: backend/tests/test_integrations.py::test_admin_creates_connection_without_persisting_plaintext_credentials
command: cd backend && pytest -q
result: 46 passed (GitHub Actions run 34032491893, 2026-09-06)
code: backend/app/routes/integrations.py
commit: 906985fad5c5cbf8a5419d94f3200cef0b259ae7
