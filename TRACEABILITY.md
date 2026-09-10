# Brain Traceability

This file is the engineering evidence index. A row is completed only after its story is engineering-DONE and has a resolvable evidence block. Real-data/manual feature acceptance is tracked separately in `UAT.md`.

| Story | Epic | Requirement / outcome | Tests | Code | Status |
|---|---|---|---|---|---|
| S-01.01.01 | E-01 | organisation membership + tenant boundary | backend/tests/test_organizations.py | backend/app/routes/organizations.py | DONE |
| S-01.02.01 | E-01 | real authentication | backend/tests/test_auth.py | backend/app/auth.py | DONE |
| S-01.03.01 | E-01 | RBAC/ACL before retrieval | backend/tests/test_permissions.py + backend/tests/test_organizations.py | backend/app/permissions.py + backend/app/routes/organizations.py | DONE |
| S-02.01.01 | E-02 | scoped integration lifecycle | backend/tests/test_integrations.py + backend/tests/test_secrets.py | backend/app/routes/integrations.py + backend/app/secrets.py | DONE |
| S-02.02.01 | E-02 | Slack ingestion | backend/tests/test_slack.py | backend/app/routes/slack_oauth.py + backend/app/routes/slack_channels.py + backend/app/routes/slack_webhooks.py | DONE |
| S-02.03.01 | E-02 | GitHub ingestion | backend/tests/test_github_connector.py | backend/app/routes/github_oauth.py + backend/app/routes/github_webhooks.py + backend/app/routes/github_backfill.py | DONE |
| S-02.04.01 | E-02 | meeting/document evidence | backend/tests/test_evidence_ingestion.py + backend/tests/test_ask_brain_generic_evidence.py + backend/tests/test_decision_memory_generic_evidence.py + UAT/F-02.04.md | backend/app/evidence_models.py + backend/app/evidence_ingestion.py + backend/app/routes/evidence.py + backend/migrations/versions/20260910_0017_generic_evidence_sources.py + docs/GENERIC_EVIDENCE.md | IN_REVIEW |
| S-03.01.01 | E-03 | raw durable/idempotent ingestion | backend/tests/test_raw_events.py + backend/tests/test_slack.py | backend/app/raw_events.py + backend/app/models.py | DONE |
| S-03.02.01 | E-03 | canonical event model | backend/tests/test_canonical_events.py + backend/tests/test_github_connector.py | backend/app/canonical_events.py + backend/app/models.py | DONE |
| S-03.03.01 | E-03 | tenant-safe identity resolution | backend/tests/test_identity_resolution.py + backend/tests/test_canonical_events.py | backend/app/identity_resolution.py + backend/app/routes/identities.py + backend/app/canonical_events.py | DONE |
| S-04.01.01 | E-04 | typed tenant-safe work graph | backend/tests/test_work_graph.py | backend/app/work_graph.py + backend/app/routes/work_graph.py | DONE |
| S-04.02.01 | E-04 | decision/blocker memory | backend/tests/test_decision_memory.py + backend/tests/test_decision_memory_evaluation.py + backend/tests/test_decision_memory_generic_evidence.py + UAT/F-04.02.md | backend/app/decision_memory.py + backend/app/routes/decision_memory.py + backend/app/decision_memory_worker.py | BLOCKED |
| S-05.01.01 | E-05 | permission-aware retrieval | backend/tests/test_search.py + backend/tests/test_search_evaluation.py + backend/tests/test_search_contract.py | backend/app/search.py + backend/app/routes/search.py + backend/app/search_worker.py | IN_REVIEW |
| S-05.02.01 | E-05 | evidence-backed Ask Brain | backend/tests/test_ask_brain.py + backend/tests/test_ask_brain_routes.py + backend/tests/test_ask_brain_citations.py + backend/tests/test_ask_brain_limits.py + backend/tests/test_ask_brain_evaluation.py + backend/tests/test_ask_brain_generic_evidence.py + backend/tests/test_ask_brain_contract_hardening.py + backend/tests/test_runtime_discovery.py + backend/tests/test_ai_cached_cost.py + backend/tests/test_ai_cost_routes.py + UAT/F-05.02.md | backend/app/ask_brain.py + backend/app/routes/ask_brain.py + backend/app/ask_brain_evaluation.py + backend/app/routes/runtime_discovery.py + scripts/run-ask-brain-evaluation.py + scripts/score-ask-brain-review.py + scripts/configure-ask-brain-openai.py + render.yaml + docs/ASK_BRAIN_STAGING.md + docs/RENDER_STAGING.md | BLOCKED |
| S-06.01.01 | E-06 | governed AI gateway | backend/tests/test_ai_gateway.py + backend/tests/test_ai_gateway_adapter.py + backend/tests/test_ai_gateway_routes.py + backend/tests/test_ai_cached_cost.py | backend/app/ai_provider_registry.py + backend/app/ai_provider_adapter.py + backend/app/routes/ai_gateway.py | IN_REVIEW |
| S-06.02.01 | E-06 | AI/API usage and budgets | backend/tests/test_ai_usage.py + backend/tests/test_ai_usage_reconciliation.py + backend/tests/test_ai_cached_cost.py + backend/tests/test_ai_cost_routes.py | backend/app/ai_usage.py + backend/app/ai_usage_models.py + backend/app/ai_usage_reconciliation.py + backend/app/routes/ai_usage.py + backend/migrations/versions/20260910_0016_ai_cached_input_cost.py | BLOCKED |
| S-06.03.01 | E-06 | external API credential registry | backend/tests/test_api_registry.py + backend/tests/test_api_registry_worker.py + backend/tests/test_secrets.py | backend/app/api_registry.py + backend/app/routes/api_registry.py + backend/app/api_registry_worker.py | IN_REVIEW |
| S-07.01.01 | E-07 | evidence-backed deterministic project command centre | backend/tests/test_project_status.py + UAT/F-07.01.md | backend/app/project_status_models.py + backend/app/project_status.py + backend/app/routes/project_status.py + backend/migrations/versions/20260910_0018_project_status.py + docs/PROJECT_STATUS.md | BLOCKED |
| S-07.02.01 | E-07 | executive overview | pending | pending | BACKLOG |
| S-08.01.01 | E-08 | governed agent runtime | pending | pending | BLOCKED |
| S-09.01.01 | E-09 | production observability and SLOs | backend/tests/test_observability.py | backend/app/observability.py + backend/app/health.py + backend/app/integrations.py + backend/app/raw_events.py + backend/app/ai_provider_registry.py | IN_REVIEW |
| S-09.02.01 | E-09 | audit/retention/deletion | backend/tests/test_data_governance.py + backend/tests/test_data_governance_routes.py + backend/tests/test_data_governance_worker.py + backend/tests/test_data_governance_retained_raw.py + backend/tests/test_data_governance_audit.py | backend/app/data_governance.py + backend/app/data_governance_models.py + backend/app/data_governance_worker.py + backend/app/routes/data_governance.py + backend/app/security_audit.py + backend/app/canonical_events.py | IN_REVIEW |
| S-09.03.01 | E-09 | CI/deploy/rollback/restore | backend/tests/test_release_contract.py + backend/tests/test_database_url.py + UAT/F-09.03.md | .github/workflows/release-gate.yml + scripts/postgres-backup.sh + scripts/postgres-restore.sh + render.yaml + backend/app/database.py + docs/DEPLOYMENT.md + docs/RENDER_STAGING.md | BLOCKED |
| S-09.04.01 | E-09 | latency/cost benchmarks | backend/tests/test_performance_budget.py + backend/tests/test_ai_cached_cost.py + UAT/F-09.04.md | backend/app/performance_budget.py + scripts/run-performance-benchmark.py + ops/performance/budgets.json + .github/workflows/performance-gate.yml + docs/PERFORMANCE.md | BLOCKED |
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

EVIDENCE S-02.02.01
tests: backend/tests/test_slack.py::test_signed_authorized_event_is_stored_once_with_exact_payload
command: cd backend && pytest -q
result: 62 passed (GitHub Actions run 34034605245, 2026-09-06)
code: backend/app/routes/slack_webhooks.py
commit: e75d9864fcf81331d332ae8a6959b79650887299

EVIDENCE S-03.01.01
tests: backend/tests/test_raw_events.py::test_raw_event_preserves_exact_bytes_and_checksum
command: cd backend && pytest -q
result: 62 passed (GitHub Actions run 34034605245, 2026-09-06)
code: backend/app/raw_events.py
commit: e75d9864fcf81331d332ae8a6959b79650887299

EVIDENCE S-02.03.01
tests: backend/tests/test_github_connector.py::test_signed_private_repo_webhook_is_exactly_once_and_acl_preserved
command: cd backend && pytest -q
result: 73 passed (GitHub Actions run 34037248953, 2026-09-06)
code: backend/app/routes/github_webhooks.py
commit: 59155580a3e743309d2b9cbeff83d324ef1bf053

EVIDENCE S-03.02.01
tests: backend/tests/test_canonical_events.py::test_slack_backfill_message_maps_to_versioned_canonical_event
command: cd backend && pytest -q
result: 73 passed (GitHub Actions run 34037248953, 2026-09-06)
code: backend/app/canonical_events.py
commit: 59155580a3e743309d2b9cbeff83d324ef1bf053

EVIDENCE S-03.03.01
tests: backend/tests/test_identity_resolution.py::test_verified_exact_email_auto_resolves_only_same_org_member
command: cd backend && pytest -q
result: 82 passed (GitHub Actions run 34039308232, 2026-09-06)
code: backend/app/identity_resolution.py + backend/app/routes/identities.py + backend/app/canonical_events.py
commit: be307d8b26bf97fa2ae8eaad52b1a370885a3123

EVIDENCE S-04.01.01
tests: backend/tests/test_work_graph.py::test_private_slack_graph_uses_current_membership_not_historical_acl
command: cd backend && pytest -q
result: 89 passed (GitHub Actions run 34043847195, 2026-09-06)
code: backend/app/work_graph.py + backend/app/routes/work_graph.py + backend/app/work_graph_models.py
commit: a97d724416191ec8515f5ed90888321343013cda

S-02.04.01 intentionally has no EVIDENCE block yet. Generic governed file/transcript ingestion, immutable source hashing, bounded extraction/chunking, RawEvent/CanonicalEvent/Work Graph/Search projection, live ACL reuse, source deletion, migration `20260910_0017`, docs, UAT and cross-feature regression contracts are staged. No pytest/migration/real-data/browser run is claimed, so the story remains IN_REVIEW.

S-05.01.01 intentionally has no EVIDENCE block yet. Implementation and acceptance coverage include the permission/revocation/tenant tests, synthetic retrieval evaluation and API provenance contract test. On 2026-09-10 the project owner explicitly deferred running pytest locally and on Render until later. That deferral is not a PASS, so the story remains IN_REVIEW.

S-05.02.01 intentionally has no EVIDENCE block yet. OQ-005 is resolved to OpenAI API with `gpt-5.6-terra` as the first conditional production candidate. The branch now stages permission-aware/no-evidence retrieval, governed explicit provider/model execution, fail-closed grounding, an exact JSON output contract, bounded citation excerpts, generic meeting/document evidence integration, safe organisation/runtime discovery, two-phase deployed evaluation, cache-aware Terra token/cost accounting, a request-scoped cost audit endpoint, a fail-closed exact-cost bootstrap, and a Render staging Blueprint/runbook. The generic-evidence and strict-output contract tests plus cached-cost/runtime tests are written but not claimed as passing. Real staging deployment, OpenAI compatibility/cost smoke, >=90% retrieval evaluation, >=98% human-reviewed citation correctness, p95 <10s measurement, official WorkOS frontend build and manual browser UAT have not run. The S-05.01.01 dependency is also unverified, so the story remains BLOCKED.

S-04.02.01 intentionally has no EVIDENCE block yet. Its deterministic candidate extractor, permission-aware reads, human review history, generic meeting/document ingestion path and worker/evaluation contracts are staged. Human-reviewed/reopened candidates are now protected from machine supersession/rewrites, and review mutations lock the candidate row before transitions. Its S-05.01.01 dependency is not engineering-DONE and its representative >=90% precision/UAT gates have not run. The story therefore remains BLOCKED and no passing result is claimed.

S-07.01.01 intentionally has no EVIDENCE block yet. The branch stages structured project-progress persistence, deterministic weighted progress, permission-aware Work Graph evidence traversal intersected with Search authorization, separate confirmed decision/blocker vs candidate-memory views, audit-backed progress mutation, project-status APIs, migration `20260910_0018`, tests, docs and UAT. Restricted related evidence is covered by a written non-disclosure regression contract. S-04.02.01 is not engineering-DONE and no backend/migration/real-data/frontend UAT has executed, so S-07.01.01 remains BLOCKED.

S-06.01.01 intentionally has no EVIDENCE block yet. Provider registry/gateway code, secret handling, provider adapter, cache-token usage propagation, tests, migration/docs and UAT are staged on `increment-10-ai-provider-gateway`, but there is no current executable Ruff/Pytest/Delivery Verifier result. The story remains IN_REVIEW.

S-06.02.01 intentionally has no EVIDENCE block yet. The usage ledger now models ordinary/cached/output token usage and optional cached-input pricing. Requests with missing required cached usage or invalid billing dimensions fail closed to `unknown`; request-scoped cost audit allows exact independent recomputation; migration `20260910_0016` and regression tests are staged. None of those new tests has executed in this pass, and S-06.01.01 is still unverified, so S-06.02.01 remains BLOCKED.

S-06.03.01 intentionally has no EVIDENCE block yet. Tenant-scoped API service/grant inventory, secret-reference credential lifecycle, owner/scope/environment history, rotation, fail-closed revocation, expiry cleanup, internal usage observation, migration, tests, docs and UAT are staged on the same branch. Executable verification remains outstanding, so the story remains IN_REVIEW.

S-09.01.01 intentionally has no EVIDENCE block yet. Structured JSON logging/redaction, bounded Prometheus metrics, OpenTelemetry request/AI tracing, PostgreSQL readiness telemetry, connector/AI instrumentation, protected metrics access, SLO alert rules, incident runbook, tests and deployed-UAT instructions are staged on the same branch. No new Ruff/Pytest/Delivery Verifier pass is claimed; the story remains IN_REVIEW.

S-09.02.01 intentionally has no EVIDENCE block yet. Durable append-only audit storage, configurable raw/derived/audit retention, legal hold, reconstruction-suppressing tombstones, integration/source-object deletion, stale-work recovery, migration `20260908_0014`, worker/API/security tests, operator docs and deployed UAT are staged on the same branch. PostgreSQL trigger/cascade/concurrency checks and full executable verification remain outstanding, so the story remains IN_REVIEW.

S-09.03.01 intentionally has no EVIDENCE block yet. A provider-neutral Release Gate, full Alembic upgrade/downgrade/forward-recovery exercise, production-mode container readiness smoke, guarded PostgreSQL backup/restore scripts, restored-data sentinel verification, release manifest, regression tests and deployment runbook are staged. Increment 18 additionally adds a concrete Render staging Blueprint plus managed Postgres URL normalisation and `docs/RENDER_STAGING.md`; this does not resolve OQ-007's final production topology. No staging deployment/rollback/restore exercise is claimed, so S-09.03.01 remains BLOCKED.

S-09.04.01 intentionally has no EVIDENCE block yet. Deterministic percentile/budget evaluation, a versioned core/search/AI workload, async deployed HTTP runner, exact cost handling, manually dispatched Performance Gate, regression tests, methodology and production-like UAT are staged. Ask Brain now has cache-aware request-cost accounting, but no real deployed benchmark report has run and the underlying search/AI acceptance gates remain open. The story therefore remains BLOCKED and no latency/throughput/cost performance claim is made.
