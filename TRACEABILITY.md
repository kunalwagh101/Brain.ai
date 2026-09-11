# Brain Traceability

This file is the engineering evidence index. A row is completed only after its story is engineering-DONE and has a resolvable evidence block. Real-data/manual feature acceptance is tracked separately in `UAT.md` and feature-specific UAT files.

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
| S-05.01.01 | E-05 | authenticated permission-aware retrieval | backend/tests/test_auth.py + backend/tests/test_permissions.py + backend/tests/test_organizations.py + backend/tests/test_search.py + backend/tests/test_search_evaluation.py + backend/tests/test_search_contract.py + backend/tests/test_acceptance_chain.py + UAT/F-05.01.md | backend/app/auth.py + backend/app/search.py + backend/app/routes/search.py + backend/app/search_worker.py + backend/run_acceptance_chain.py + backend/Dockerfile.staging + render.yaml + docs/RENDER_STAGING.md | IN_REVIEW |
| S-05.02.01 | E-05 | evidence-backed Ask Brain | backend/tests/test_ask_brain.py + backend/tests/test_ask_brain_routes.py + backend/tests/test_ask_brain_citations.py + backend/tests/test_ask_brain_limits.py + backend/tests/test_ask_brain_evaluation.py + backend/tests/test_ask_brain_generic_evidence.py + backend/tests/test_ask_brain_contract_hardening.py + backend/tests/test_runtime_discovery.py + backend/tests/test_ai_cached_cost.py + backend/tests/test_ai_cost_routes.py + UAT/F-05.02.md | backend/app/ask_brain.py + backend/app/routes/ask_brain.py + backend/app/ask_brain_evaluation.py + backend/app/routes/runtime_discovery.py + backend/run_acceptance_chain.py + scripts/run-ask-brain-evaluation.py + scripts/score-ask-brain-review.py + scripts/configure-ask-brain-openai.py + app/brain-api.ts + app/brain-bff.ts + app/ask-brain-panel.tsx + docs/ASK_BRAIN_STAGING.md + docs/WORKOS_FRONTEND_ACCEPTANCE.md | BLOCKED |
| S-06.01.01 | E-06 | governed AI gateway | backend/tests/test_ai_gateway.py + backend/tests/test_ai_gateway_adapter.py + backend/tests/test_ai_gateway_routes.py + backend/tests/test_ai_cached_cost.py | backend/app/ai_provider_registry.py + backend/app/ai_provider_adapter.py + backend/app/routes/ai_gateway.py | IN_REVIEW |
| S-06.02.01 | E-06 | AI/API usage and budgets | backend/tests/test_ai_usage.py + backend/tests/test_ai_usage_reconciliation.py + backend/tests/test_ai_cached_cost.py + backend/tests/test_ai_cost_routes.py | backend/app/ai_usage.py + backend/app/ai_usage_models.py + backend/app/ai_usage_reconciliation.py + backend/app/routes/ai_usage.py + backend/migrations/versions/20260910_0016_ai_cached_input_cost.py | BLOCKED |
| S-06.03.01 | E-06 | external API credential registry | backend/tests/test_api_registry.py + backend/tests/test_api_registry_worker.py + backend/tests/test_api_registry_usage_route.py + backend/tests/test_secrets.py | backend/app/api_registry.py + backend/app/routes/api_registry.py + backend/app/routes/api_registry_usage.py + backend/app/api_registry_worker.py | IN_REVIEW |
| S-07.01.01 | E-07 | evidence-backed deterministic project command centre | backend/tests/test_project_status.py + backend/tests/test_project_status_routes.py + UAT/F-07.01.md | backend/app/project_status_models.py + backend/app/project_status.py + backend/app/routes/project_status.py + backend/migrations/versions/20260910_0018_project_status.py + app/production-executive-workspace.tsx + app/live-workspace.tsx + docs/PROJECT_STATUS.md | BLOCKED |
| S-07.02.01 | E-07 | permission-aware evidence-backed executive overview | backend/tests/test_executive_overview.py + backend/tests/test_executive_overview_budget_permissions.py + backend/tests/test_executive_overview_memory.py + backend/tests/test_api_registry_usage_route.py + UAT/F-07.02.md | backend/app/executive_overview.py + backend/app/routes/executive_overview.py + backend/app/routes/api_registry_usage.py + app/production-executive-workspace.tsx + app/live-workspace.tsx + docs/EXECUTIVE_OVERVIEW.md + docs/WORKOS_FRONTEND_ACCEPTANCE.md + docs/planning/increment-21.md | BLOCKED |
| S-08.01.01 | E-08 | governed agent runtime | pending | pending | BLOCKED |
| S-09.01.01 | E-09 | production observability and SLOs | backend/tests/test_observability.py | backend/app/observability.py + backend/app/health.py + backend/app/integrations.py + backend/app/raw_events.py + backend/app/ai_provider_registry.py | IN_REVIEW |
| S-09.02.01 | E-09 | audit/retention/deletion | backend/tests/test_data_governance.py + backend/tests/test_data_governance_routes.py + backend/tests/test_data_governance_worker.py + backend/tests/test_data_governance_retained_raw.py + backend/tests/test_data_governance_audit.py | backend/app/data_governance.py + backend/app/data_governance_models.py + backend/app/data_governance_worker.py + backend/app/routes/data_governance.py + backend/app/security_audit.py + backend/app/canonical_events.py | IN_REVIEW |
| S-09.03.01 | E-09 | CI/deploy/rollback/restore | backend/tests/test_release_contract.py + backend/tests/test_database_url.py + backend/tests/test_acceptance_chain.py + UAT/F-09.03.md | .github/workflows/release-gate.yml + backend/Dockerfile.staging + backend/run_acceptance_chain.py + scripts/postgres-backup.sh + scripts/postgres-restore.sh + render.yaml + backend/app/database.py + docs/DEPLOYMENT.md + docs/RENDER_STAGING.md | BLOCKED |
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

Historical note: the S-01.02.01 evidence above is tied to its recorded commit. The current branch subsequently hardened the WorkOS AuthKit token contract to validate `client_id`, optional explicit custom `aud`, exact issuer/expiry/signature and the required `urn:brain:user_email` JWT Template claim while refusing to identify the subject from optional `act` actor context. Those later changes are included in the active S-05.01 acceptance stage and are **not** claimed as newly passing until that stage executes successfully with synthetic and real WorkOS evidence.

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

S-02.04.01 intentionally has no EVIDENCE block yet. Generic governed file/transcript ingestion, immutable source hashing, bounded extraction/chunking, RawEvent/CanonicalEvent/Work Graph/Search projection, live ACL reuse, source deletion, migration `20260910_0017`, docs, UAT and cross-feature regression contracts are staged. The ordered acceptance runner now places this stage immediately after S-05.01. No executable PostgreSQL/real-data/browser PASS is claimed, so the story remains IN_REVIEW.

S-05.01.01 intentionally has no EVIDENCE block yet. Acceptance is now active. The branch stages a fail-closed ordered runner, portable build-time verification and isolated PostgreSQL/pgvector execution on Render. Its first stage includes current WorkOS token binding, organisation/RBAC, permission/revocation/tenant retrieval, synthetic retrieval evaluation and provenance contracts. Repeated GitHub-hosted Backend CI/Delivery Verifier/Release Gate attempts have shown `runner_id=0`, empty runner names and zero executed steps, so they provide no code-test verdict. Local/Render execution, real WorkOS token validation and realistic permission/revocation/recall/latency UAT are still pending; the story remains IN_REVIEW.

S-05.02.01 intentionally has no EVIDENCE block yet. OQ-005 is resolved to OpenAI API with `gpt-5.6-terra` as the first conditional production candidate. The branch stages permission-aware/no-evidence retrieval, governed explicit provider/model execution, fail-closed grounding, exact JSON output, bounded citations, generic meeting/document evidence, runtime discovery, two-phase evaluation, cache-aware exact cost and the ordered acceptance stage including gateway/cost dependencies. The frontend now also has typed server API contracts, strict BFF request parsing, a live workspace renderer and citation-first Ask Brain component, but the official WorkOS SDK/lockfile activation remains externally blocked by npm registry availability. Real provider compatibility/cost smoke, >=90% retrieval evaluation, >=98% human-reviewed citation correctness, p95 <10s, official WorkOS frontend build and manual browser UAT have not run. S-05.01 is still unverified, so S-05.02 remains BLOCKED.

S-04.02.01 intentionally has no EVIDENCE block yet. Its deterministic candidate extractor, permission-aware reads, human review history, generic meeting/document path and evaluation contracts are staged. Human-reviewed/reopened candidates are protected from machine supersession/rewrites and review mutations lock the candidate row. The ordered acceptance runner places this after Ask Brain. Its S-05.01 dependency is not engineering-DONE and representative >=90% precision/UAT has not run, so the story remains BLOCKED.

S-07.01.01 intentionally has no EVIDENCE block yet. The branch stages structured project-progress persistence, deterministic weighted progress, permission-aware Work Graph evidence traversal intersected with Search authorization, separate confirmed decision/blocker vs candidate-memory views, audit-backed progress mutation, APIs, migration `20260910_0018`, tests/docs/UAT and a live frontend renderer. The ordered acceptance runner places Project Command Centre after Decision Memory. S-04.02 is not engineering-DONE and no real backend/permission/frontend UAT has executed, so S-07.01 remains BLOCKED.

S-07.02.01 intentionally has no EVIDENCE block yet. The branch stages an `audit.read` executive read model over visible projects, confirmed memory, exact/incomplete AI spend/budgets and trusted external API usage. Metric provenance and Work Graph budget privacy are explicit; API monetary cost is unavailable rather than guessed; no employee productivity/worth score field exists. Backend contracts, live frontend renderer, WorkOS acceptance documentation and UAT are staged, but S-07.01 and S-06.02 are not DONE and no executable reconciliation/permission/browser acceptance has run. S-07.02 remains BLOCKED.

S-06.01.01 intentionally has no EVIDENCE block yet. Provider registry/gateway code, secret handling, provider adapter, cache-token propagation, tests/migration/docs/UAT are staged. These contracts now run inside the Ask Brain acceptance stage, but no executable PASS exists; the story remains IN_REVIEW.

S-06.02.01 intentionally has no EVIDENCE block yet. The usage ledger models ordinary/cached/output token usage and optional cached pricing. Invalid/missing required billing dimensions fail closed to `unknown`, and request-scoped cost audit supports independent recomputation. These contracts run inside the Ask Brain acceptance stage, but no executable PASS exists and S-06.01 is unverified, so S-06.02 remains BLOCKED.

S-06.03.01 intentionally has no EVIDENCE block yet. Tenant-scoped API service/grant inventory, secret-reference lifecycle, owner/scope/environment history, rotation, fail-closed revocation, expiry cleanup, internal usage observation, tests/docs/UAT and Executive Overview API-usage drill-down are staged. Relevant API registry contracts run in the Executive Overview acceptance stage. Executable verification remains outstanding, so the story remains IN_REVIEW.

S-09.01.01 intentionally has no EVIDENCE block yet. Structured JSON logging/redaction, bounded Prometheus metrics, OpenTelemetry tracing, PostgreSQL readiness telemetry, connector/AI instrumentation, protected metrics access, SLO alert rules, incident runbook, tests and deployed-UAT instructions are staged. No new executable pass is claimed; the story remains IN_REVIEW.

S-09.02.01 intentionally has no EVIDENCE block yet. Durable append-only audit storage, configurable retention, legal hold, reconstruction-suppressing tombstones, integration/source-object deletion, stale-work recovery, migration `20260908_0014`, worker/API/security tests, operator docs and deployed UAT are staged. PostgreSQL trigger/cascade/concurrency checks and full executable verification remain outstanding, so the story remains IN_REVIEW.

S-09.03.01 intentionally has no EVIDENCE block yet. A provider-neutral Release Gate, Alembic upgrade/downgrade/forward-recovery exercise, production container readiness smoke, PostgreSQL backup/restore, restored-data sentinel verification, release manifest, Render Blueprint and the new ordered staging acceptance chain are staged. GitHub-hosted runners still fail allocation before step execution and no real Render deploy/rollback/restore exercise is yet recorded. OQ-007 production topology remains open, so S-09.03 remains BLOCKED.

S-09.04.01 intentionally has no EVIDENCE block yet. Deterministic percentile/budget evaluation, versioned core/search/AI workload, deployed HTTP runner, exact cost handling, Performance Gate, regression tests, methodology and UAT are staged. No real Ask Brain benchmark report has run and underlying search/AI acceptance remains open. The story remains BLOCKED; no latency/throughput/cost performance claim is made.
