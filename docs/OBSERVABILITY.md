# Production Observability and SLOs

## Purpose

F-09.01 makes Brain operationally diagnosable without turning telemetry into another source of customer-data or credential leakage.

The implementation uses three standard signals:

- structured JSON logs for bounded incident context
- Prometheus metrics for aggregation, SLOs and alerting
- OpenTelemetry spans for request/connector/AI correlation and optional OTLP export

These signals complement the durable domain ledgers already stored in PostgreSQL. Telemetry is not the source of truth for permissions, AI billing or audit history.

## Correlation model

### Request ID

Every HTTP request receives `X-Request-ID`.

A caller-supplied ID is reused only when it matches the bounded safe form `[A-Za-z0-9._:-]{1,128}`. Unsafe/high-cardinality values are replaced with a UUID.

The request ID is returned in the response and included in JSON logs. CORS exposes `X-Request-ID` so browser clients can correlate an application error with backend telemetry without reading sensitive headers.

### Trace context

Brain accepts standard W3C `traceparent`, `tracestate` and `baggage` headers and creates an OpenTelemetry server span for the request. Governed AI execution creates a child span with:

- organisation ID
- internal AI request ID
- provider key
- model key
- latency
- resolved nano-USD cost when exact cost is known

`BRAIN_OTEL_EXPORTER_OTLP_ENDPOINT` enables OTLP/HTTP export. Without an endpoint, spans still provide in-process context but are not exported. OTLP exporter availability does not gate application readiness.

Production OTLP endpoints must use HTTPS.

### Organisation, integration, provider and model context

Organisation IDs, integration IDs, provider keys and model keys may be present in structured logs/traces because operators need them to isolate an incident. They are deliberately not Prometheus labels.

Tenant-configurable values are not permitted as metric labels. This prevents unbounded multi-tenant time-series growth and reduces accidental tenant metadata exposure through monitoring systems.

## Structured logging

`JSONLogFormatter` emits UTC JSON with:

- timestamp
- level
- logger
- bounded message
- request ID
- trace/span IDs when active
- organisation ID when bound by authorization
- explicitly allowlisted operational fields

Allowlisted operational fields include integration ID, provider, model, route, HTTP status/duration, bounded error code, exact resolved AI cost, source event type, dependency status and worker counters.

Arbitrary `extra` fields are discarded.

The formatter redacts common forms of:

- Authorization bearer values
- API key fields
- access/refresh tokens
- secret fields
- `sk-...` style API credentials

This is defense in depth, not permission to log sensitive inputs. Code must still never intentionally log prompts, completions, webhook bodies, OAuth tokens, API keys or customer message/document content.

## Prometheus metrics

`GET /metrics` exports Prometheus text format.

Production requirements:

- `BRAIN_METRICS_ENABLED=true`
- `BRAIN_METRICS_BEARER_TOKEN` must be set
- ingress/network policy should additionally restrict the endpoint to the monitoring plane

Key metrics:

- `brain_http_requests_total{method,route,status_class}`
- `brain_http_request_duration_seconds{method,route}`
- `brain_dependency_ready{dependency}`
- `brain_dependency_check_duration_seconds{dependency}`
- `brain_connector_events_total{result}`
- `brain_connector_sync_total{status}`
- `brain_ai_requests_total{status}`
- `brain_ai_request_duration_seconds`
- `brain_ai_cost_nano_usd_total`

Only finite, code-controlled dimensions are used as labels. Provider/model/integration/organisation/user identity is resolved through logs, traces and durable database records instead of becoming a Prometheus label.

The AI cost counter includes only exact calculated cost. Unknown/unresolved cost remains represented in the durable AI usage ledger and must not be interpreted as zero spend.

Route labels use FastAPI route templates instead of raw URLs, so organisation/resource UUIDs do not create a new metric series for every request.

## Connector telemetry

Raw event persistence emits structured log/trace context for:

- organisation
- integration ID
- provider
- source event type
- delivery kind
- created vs duplicate

It never emits the raw payload or source ACL content.

Prometheus exports only created/duplicate counts and sync success/failure. Provider and integration identity remain in logs/traces.

Shared connector sync lifecycle functions emit success/failure with provider, integration and bounded error code. When a sync runs inside an HTTP request, those events inherit the request trace context.

## AI telemetry

Governed AI provider execution emits into logs/traces:

- provider/model
- success/failure
- latency
- bounded error code on failure
- exact resolved cost when available
- trace correlation to the originating HTTP request

Prometheus aggregates AI success/failure, latency and exact resolved cost without provider/model labels. Use the correlated trace/log plus the durable F-06.01/F-06.02 records when diagnosing one provider/model.

Prompt/system/completion content and provider credentials are not logged or stored in telemetry.

## Liveness and readiness

`GET /health/live`

- process-only check
- does not query PostgreSQL or third-party services
- remains healthy when a dependency is unavailable

`GET /health/ready`

- queries PostgreSQL with `SELECT 1`
- returns 200 when ready
- returns 503 when PostgreSQL is unavailable
- reports dependency status and bounded latency
- updates dependency readiness/latency metrics

External AI/Slack/GitHub providers do not gate whole-service readiness because those capabilities can degrade independently. Their failures are represented by connector/AI telemetry and domain health state.

## Reliability objectives

The backlog production objectives are used as the initial SLOs:

| Surface | Objective |
|---|---|
| Accepted core API availability | >=99.9% monthly |
| Core structured API p95 | <500 ms |
| Search p95 | <1.5 s |
| Governed AI/provider p95 target | <10 s |
| Cross-tenant telemetry leakage | 0 known occurrences |

The 500 ms core objective excludes dedicated search and AI/provider execution. Combining all routes into one latency SLO would hide whether Brain itself or an external provider is slow.

A 99.9% monthly availability target corresponds to roughly 43 minutes of error budget in a 30-day month. Do not claim compliance until representative production traffic and a stable monitoring window exist.

## Alert rules

Prometheus-compatible rules live in:

`ops/prometheus/brain-alerts.yml`

They cover:

- PostgreSQL readiness down
- elevated core API 5xx rate, excluding governed AI provider execution
- core API p95 breach
- search p95 breach
- aggregate governed AI p95 breach
- aggregate governed AI error rate
- connector sync failures

Provider/model/integration drill-down happens through correlated logs/traces rather than high-cardinality metric labels.

Alert routing/paging vendor configuration is deployment-specific and intentionally outside application code.

## Configuration

```text
BRAIN_LOG_LEVEL=INFO
BRAIN_METRICS_ENABLED=true
BRAIN_METRICS_BEARER_TOKEN=<deployment-secret>
BRAIN_OTEL_SERVICE_NAME=brain-api
BRAIN_OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example/v1/traces
```

The metrics bearer token belongs in the deployment secret manager/environment, not the repository.

## Operational limitations

- Metrics are process-local. Horizontal deployments require Prometheus scraping/aggregation across replicas.
- OTLP export is optional and asynchronous; exporter failure is not readiness failure.
- Third-party SaaS systems generally do not propagate Brain trace context, so their remote internal work cannot be traced end-to-end.
- SLO compliance requires deployed traffic; unit tests can validate instrumentation mechanics but cannot prove production reliability.
- Telemetry retention/redaction policy is distinct from F-09.02 customer-data retention and deletion policy.
