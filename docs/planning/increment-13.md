# Increment 13 — Production Observability and SLOs

Branch policy: this increment intentionally continues on `increment-10-ai-provider-gateway`; no new branch is created.

Story: S-09.01.01 — Trace requests, connector jobs and AI calls.

## Goal

Make Brain incidents diagnosable from correlated, secret-safe telemetry and define measurable reliability objectives before claiming production reliability.

## Acceptance contract

1. Every HTTP request receives a bounded safe request ID, returns it to the caller and emits method, route template, status and duration without logging request bodies or authorization headers.
2. W3C trace context is accepted and Brain creates OpenTelemetry spans for HTTP and governed AI execution; optional OTLP export is operator-configured.
3. Tenant identifiers may appear in structured logs/traces for incident correlation but are never Prometheus labels. User IDs are not emitted as metric labels.
4. Raw connector persistence emits provider/integration/source-event-type lifecycle telemetry without raw payload content, while shared integration sync success/failure emits provider/integration/error metadata.
5. Governed AI calls emit provider/model/status/latency and resolved cost metadata without prompt, completion or credential values.
6. `/health/live` reports process liveness only. `/health/ready` verifies PostgreSQL dependency health and reports bounded dependency latency; dependency failure returns 503 without making liveness fail.
7. `/metrics` exports bounded Prometheus metrics. Production metrics exposure requires an application bearer token and should also be ingress-restricted.
8. Structured logging redacts common bearer/API-key/token/secret patterns and includes only a strict allowlist of structured extra fields.
9. Core API, search and AI latency SLOs are separate so external-provider latency does not falsely breach the core API objective.
10. Alert rules and runbooks exist for readiness failure, API error rate, core/search/AI latency, AI provider errors and connector sync failure.
11. No engineering-DONE claim is allowed until Ruff, Pytest and the delivery verifier execute successfully. Real deployed telemetry and alert firing remain separate UAT evidence.

## Reliability objectives

- Service availability target: >=99.9% monthly for accepted core API requests.
- Core structured API p95: <500 ms, excluding external provider execution and dedicated search/AI routes.
- Search p95: <1.5 s.
- Governed AI answer/provider p95 target: <10 s.
- Cross-tenant telemetry leakage: 0 known occurrences.

## Tasks

- T-09.01.01.a structured JSON logging, request/tenant/trace context and redaction
- T-09.01.01.b Prometheus HTTP/dependency/connector/AI/cost metrics
- T-09.01.01.c OpenTelemetry request + AI tracing with optional OTLP export
- T-09.01.01.d liveness/readiness dependency separation and timing
- T-09.01.01.e connector raw-event + sync lifecycle instrumentation
- T-09.01.01.f AI provider/model/error/latency/cost instrumentation
- T-09.01.01.g SLO/error-budget/alert rules and incident runbook
- T-09.01.01.h redaction, metrics-auth, health and correlation tests
- T-09.01.01.i UAT on a deployed environment and truthful delivery evidence

## Explicit non-goals

- Buying or selecting a hosted observability vendor.
- Logging prompts, completions, webhook bodies, API keys, OAuth tokens or customer document/message content.
- Using organisation/user IDs as Prometheus labels.
- Claiming exact SLO compliance before representative production traffic exists.
- Distributed tracing across third-party SaaS systems that do not propagate Brain trace context.
