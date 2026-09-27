# Observability Incident Runbook

Use request ID + trace ID first. Do not paste secrets, prompts, webhook bodies or customer content into incident notes.

## Database readiness down

Alert: `BrainDatabaseReadinessDown`

1. Check `/health/live`. If liveness is also down, treat this as application/process failure rather than dependency-only failure.
2. Check `/health/ready` and confirm the database dependency is `down`.
3. Inspect `brain_dependency_ready{dependency="database"}` and dependency latency.
4. Check deployment database URL/host resolution, database service state, connection limits and network/DNS policy.
5. Correlate recent application errors by request/trace ID.
6. Do not restart repeatedly if the database itself is unavailable; repeated reconnect storms can worsen an incident.
7. After recovery, confirm readiness returns 200 and database latency returns to baseline.

## API error rate

Alert: `BrainCoreApiHighErrorRate`

1. Break down `brain_http_requests_total` by route/status class.
2. Identify the highest failing route templates; never group by raw path UUIDs.
3. Use request IDs from structured error logs to locate traces.
4. Determine whether failures are application logic, PostgreSQL, permissions/configuration, or an external dependency.
5. If one newly deployed code path caused the increase, follow the deployment rollback procedure rather than applying an unreviewed production hotfix.
6. Confirm the 5xx rate remains below the alert threshold after remediation.

## Core API latency

Alert: `BrainCoreApiLatencySLOBreach`

1. Confirm the affected route is part of the core API objective. Search and AI/provider routes have separate SLOs.
2. Compare route p50/p95 and database readiness latency.
3. Inspect traces for slow SQL/application spans and lock contention.
4. Check recent migrations, traffic changes and database resource pressure.
5. Do not blame external AI latency for the core API SLO; the core alert intentionally excludes that route.

## Search latency

Alert: `BrainSearchLatencySLOBreach`

1. Separate keyword vs hybrid/semantic requests using application/request evidence.
2. Check PostgreSQL latency, search result limit, index health and embedding-provider degradation state.
3. Confirm authorization predicates remain part of retrieval; do not remove permission filtering to improve latency.
4. Record p50/p95 and representative query shape before/after any tuning.
5. If the semantic provider is degraded, preserve explicit degraded behavior rather than silently returning a fake hybrid result.

## AI provider latency

Alert: `BrainAIProviderLatencySLOBreach`

1. Confirm the aggregate `brain_ai_request_duration_seconds` p95 breach.
2. Use request IDs/traces and structured `brain.ai` logs to identify the affected provider/model; provider/model are intentionally not Prometheus labels.
3. Compare Brain HTTP latency with the `ai.provider.invoke` span. If only the provider span is slow, the bottleneck is external/provider-side.
4. Check provider status page/account quota separately if available.
5. Confirm gateway timeout configuration has not been raised to mask a provider incident.
6. Check whether a permitted alternate provider/model is configured before failover; never bypass provider governance or egress policy.

## AI provider errors

Alert: `BrainAIProviderHighErrorRate`

1. Confirm the aggregate failed-request ratio from `brain_ai_requests_total`.
2. Break down the incident by provider/model and bounded error code using correlated structured logs/traces and the durable AI request ledger.
3. Distinguish rate limiting, credential failure, provider 5xx/timeout and Brain-side validation.
4. For credential errors, use the provider registry lifecycle. Never print or fetch credentials into logs/incident chat.
5. For budget exhaustion, treat the 429 as policy enforcement rather than provider outage.
6. Confirm failure rate returns below threshold and request/cost ledgers remain consistent.

## Connector sync failure

Alert: `BrainConnectorSyncFailure`

1. Identify provider and integration ID from the structured connector event; these are intentionally not metric labels.
2. Check integration lifecycle health and bounded `last_error_code`.
3. Use the same request/trace ID to inspect the corresponding backfill/webhook request when the sync was HTTP-triggered.
4. Confirm the integration is still active and its required authorization/grants remain current.
5. Retry only through the connector's idempotent path. Never manually insert canonical/search records to bypass ingestion.
6. Verify replay does not create duplicate raw/canonical events.

## Suspected telemetry secret leak

1. Treat as a security incident.
2. Stop/disable the offending telemetry path if necessary without deleting durable security evidence.
3. Rotate the exposed credential through the governed secret lifecycle.
4. Identify affected log/trace backend retention and access.
5. Fix the source logging call and add a regression test.
6. Coordinate deletion/retention handling under F-09.02 policy; do not silently erase audit evidence outside approved procedure.

## Recovery evidence

For any incident, record:

- start/end timestamps
- affected environment
- alert and route/provider/integration involved
- representative request/trace IDs
- customer-visible impact without copying sensitive content
- root cause
- mitigation/rollback
- verification metrics after recovery
- follow-up test/runbook changes
