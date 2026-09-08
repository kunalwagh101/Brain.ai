# Changelog

## Unreleased

### Increment 14 — Audit, retention and deletion

- Added tenant-scoped durable security audit events with actor/resource/request correlation, bounded metadata and normalized-payload SHA-256 digests.
- Added PostgreSQL append-only enforcement that rejects audit-row updates while allowing explicit audit-retention deletion; actor UUID evidence is deliberately not a mutable user foreign key.
- Added `data_governance.manage` for Owner/Admin retention/deletion administration while organisation-wide governance/audit reads reuse `audit.read`.
- Added explicit per-organisation raw-event, derived-content and audit-event retention durations plus legal hold. Unset durations mean no automatic age-based purge; Brain does not invent a legal retention period.
- Added bounded raw retention and derived retention with reconstruction-suppressing tombstones. Derived tombstones preserve only raw-event ID plus minimal provider/object locator, not source content.
- Added integration-wide deletion gated on full revocation and typed source-object deletion with idempotency keys, stable target references, counts and completion digests.
- Closed the retained-raw deletion gap: a source-object deletion can still find and delete raw evidence after its canonical row was previously removed by derived retention.
- Added canonicalisation suppression so deleted/purged evidence cannot silently reappear through connector replay or reconciliation.
- Added orphan source-identity sanitation that clears unsupported identity evidence and returns the identity to `unresolved` state.
- Added pending/failed/stale-processing deletion recovery, bounded worker execution and PostgreSQL row-lock/`SKIP LOCKED` concurrency semantics.
- Added fail-closed durable audit coupling for ACL create/delete mutations; authorization-denial audit persistence remains best-effort so an audit-store problem cannot widen access.
- Added Alembic revision `20260908_0014`, service/route/worker/audit/retained-raw regression tests, operator documentation and realistic PostgreSQL/frontend UAT instructions.

Verification is not yet claimed. `S-09.02.01` remains `IN_REVIEW` until Ruff, Pytest, migration verification and the Delivery Verifier actually execute. PostgreSQL append-only-trigger/cascade/concurrency behavior, realistic deletion/replay behavior, frontend/manual acceptance and backup/PITR lifecycle remain separate `UAT_PENDING` evidence.

### Increment 13 — Production observability and SLOs

- Added correlated structured JSON logging with bounded request IDs, W3C trace/span context, tenant/integration/provider/model operational context and strict structured-field allowlisting.
- Added defense-in-depth redaction for bearer credentials, API/access/refresh/secret fields and common OpenAI/GitHub/Slack token shapes; prompts, completions, webhook bodies and customer content remain forbidden telemetry inputs.
- Added OpenTelemetry HTTP server spans plus governed AI child spans, with optional OTLP/HTTP export and production HTTPS enforcement for configured exporters.
- Added protected Prometheus `/metrics` exposure with production bearer-token enforcement and finite code-controlled metric labels only; tenant-configurable organisation/user/integration/provider/model values are deliberately excluded from metric labels.
- Added route-template HTTP request/error/latency metrics, PostgreSQL readiness/latency metrics, aggregate connector lifecycle metrics and aggregate governed-AI success/failure/latency/exact-cost metrics.
- Preserved provider/model/integration drill-down in structured logs, traces and durable domain ledgers instead of high-cardinality Prometheus series.
- Separated process liveness from PostgreSQL readiness; readiness now reports dependency status/latency and returns 503 while liveness remains process-only.
- Added raw connector persistence spans/logs and shared connector sync success/failure telemetry without raw event payloads.
- Added SLO/error-budget documentation, Prometheus-compatible alert rules and an incident runbook for database, API, search, AI and connector failures.
- Added observability security/health/correlation tests plus deployed backend/monitoring/frontend UAT instructions.

Verification is not yet claimed. `S-09.01.01` remains `IN_REVIEW` until Ruff, Pytest and the Delivery Verifier obtain an executable passing run. Deployed metrics/trace collection, alert firing and representative monthly SLO compliance remain separate `UAT_PENDING` evidence.

### Increment 12 — External API registry

- Added tenant-scoped external API service and credential-grant inventory with explicit owner, scopes, environment, status and optional expiry.
- Added dedicated `api.manage` administration permission while organisation-wide registry/history/usage reads reuse `audit.read`.
- Added AWS Secrets Manager storage for external API credentials; PostgreSQL persists only secret references and read APIs expose only `credential_present`.
- Added safe internal credential loading that refuses disabled, revoked, revoke-failed and time-expired grants before secret retrieval; no public credential-read endpoint exists.
- Added credential rotation without changing the stored reference or persisting old/new credential values.
- Added fail-closed `revoking`, `revoke_failed` and `revoked` transitions with retryable secret deletion and immutable lifecycle history.
- Added bounded expiry processing plus separate secret-cleanup retries so an expired grant remains unusable even when external secret deletion temporarily fails.
- Added trusted internal, idempotent API usage observations with PostgreSQL grant-row locking to avoid lost concurrent usage-count updates; normal clients cannot fabricate usage through a public write route.
- Added Alembic revision `20260907_0013`, security/lifecycle/worker/secret-store tests, operator documentation and realistic-data/frontend UAT instructions.

Verification is not yet claimed. The latest checked Backend CI job for this branch failed before runner startup with `runner_id=0` and no executed steps, so Ruff/Pytest/Delivery Verifier evidence does not exist and `S-06.03.01` remains `IN_REVIEW`.

### Increment 11 — Usage, cost and budgets

- Added historical provider/model rate cards and deterministic integer nano-USD cost accounting.
- Added explicit `calculated` versus `unknown` cost-resolution state; missing provider token counts or pricing are never silently treated as zero spend.
- Added usage aggregation by organisation, provider, model, user and existing Work Graph attribution node without guessing missing attribution.
- Added UTC calendar-month budgets for organisation/provider/model/user/project-track-work-item scopes with tenant-validated targets.
- Added deduplicated warning and 100% alerts plus a post-exhaustion hard-stop before provider secret lookup/execution.
- Added explicit incomplete-enforcement state when a budget period contains unknown-cost requests rather than pretending known spend equals the invoice.
- Added bounded cost reconciliation with PostgreSQL `FOR UPDATE SKIP LOCKED` for successful requests whose cost is missing or later becomes resolvable.
- Added Alembic revision `20260907_0012`, API routes, accounting/security tests, operator documentation and real-provider/frontend UAT instructions.

Verification is not yet claimed. `S-06.02.01` is staged on the same branch but remains `BLOCKED` because its S-06.01.01 dependency has not received executable passing verification and F-06.02 itself has no passing CI evidence.

### Increment 10 — Governed AI provider gateway

- Added tenant-scoped AI provider/model configuration with separate `ai.manage` administration and `ai.use` invocation permissions.
- Added secret-reference provider credentials, credential rotation, fail-closed revocation and no plaintext API-key persistence.
- Added production HTTPS/provider-host egress controls, redirect rejection and bounded provider response/error handling.
- Added a provider-neutral runtime contract with an isolated OpenAI-compatible chat-completions adapter.
- Added durable AI request metadata for organisation, user, provider, model, optional Work Graph attribution, status, latency, provider request ID and provider-returned token counts.
- Prompts, system text and model completions are not persisted in the AI request ledger by default.
- Added Alembic revision `20260907_0011`, gateway/adapter/route/security tests, documentation and real-provider/frontend UAT instructions.

Verification is not yet claimed because GitHub-hosted Actions cannot currently obtain a runner; `S-06.01.01` remains `IN_REVIEW` until Ruff, Pytest and the Delivery Verifier actually execute successfully.

### Increment 9 — Decision and blocker memory

- Added tenant-scoped decision/blocker candidate storage plus versioned extraction bookkeeping and immutable human review history.
- Added a conservative deterministic extractor over whitelisted search evidence; machine extraction always creates `candidate` state and never auto-confirms a fact.
- Added explicit decision/blocker confidence, extraction method/version and SHA-256 statement fingerprints for idempotency.
- Added same-document PostgreSQL row locking, content/version reprocessing and `superseded` state for stale unreviewed machine candidates.
- Added current-permission-aware reads by reusing the Permission-Aware Retrieval candidate boundary, including live Slack/GitHub revocation behavior.
- Added human `confirm`, `reject`, `edit`, blocker-only `resolve` and `reopen` transitions with immutable before/after review records.
- Added bounded historical reconciliation/API/worker, Alembic revision `20260907_0010`, security/state/idempotency tests, synthetic precision instrumentation and realistic-data UAT instructions.

Verification is not yet claimed. This story is formally `BLOCKED` on S-05.01.01 because Permission-Aware Retrieval is still `IN_REVIEW`, and GitHub-hosted Actions runners are currently failing before job startup. The synthetic precision fixture is not a production precision claim; representative labelled data and frontend/manual UAT remain required.

### Increment 8 — Permission-aware retrieval

- Added a rebuildable tenant-scoped search projection over canonical Slack/GitHub evidence.
- Added live Slack channel/membership and GitHub/resource-grant filtering before result rows are returned.
- Added PostgreSQL full-text keyword retrieval with a matching GIN expression index.
- Added provider-neutral semantic embeddings and pgvector cosine retrieval without choosing the later RAG generation provider.
- Added explicit hybrid-search degradation when the embedding service is absent/unavailable.
- Added a bounded database-backed reconciliation/embedding worker with stale-claim recovery and retry backoff.
- Added revocation/deletion handling so derived search content becomes unavailable while raw/canonical audit evidence remains.
- Added Alembic revision `20260907_0009`, rollback notes, security-focused tests, architecture docs and UAT instructions.
- Added `DEFINITION_OF_READY.md` because the delivery contract required an inspectable DoR artifact and the repository did not previously contain one.

Verification is not yet claimed: GitHub Actions for the current Increment 8 PR failed before runner startup, so `S-05.01.01` must remain non-DONE until tests and the delivery verifier actually run successfully.
