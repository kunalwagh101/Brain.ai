# Increment 13 — Production Observability and SLOs

Branch policy: this increment intentionally continues on `increment-10-ai-provider-gateway`; no new branch is created.

Story: S-09.01.01 — Trace requests, connector jobs and AI calls.

## Goal

Make Brain incidents diagnosable from correlated, secret-safe telemetry and define measurable reliability objectives before claiming production reliability.

## Acceptance contract

1. Every HTTP request receives a bounded safe request ID, returns it to the caller and emits method, route template, status and duration without logging request bodies or authorization headers.
2. W3C trace context is accepted and Brain creates OpenTelemetry spans for HTTP and governed AI execution; optional OTLP export is operator-configured.
3. Tenant-configurable identifiers such as organisation, user, integration, provider and model may appear only in structured logs/traces or durable ledgers for incident correlation; they are never Prometheus labels. Metric labels are restricted to finite code-controlled dimensions.
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
- Using tenant-configurable organisation/user/integration/provider/model values as Prometheus labels.
- Claiming exact SLO compliance before representative production traffic exists.
- Distributed tracing across third-party SaaS systems that do not propagate Brain trace context.

## Verification work order — 2026-09-24

Mode: **CHECK** — implementation already exists; this pass verifies and closes engineering evidence only.

Role: **Senior full-stack engineer / systems architect**. Operating tier: **architect**.

Scope:
- verify the existing logging, metrics, tracing, health/readiness and alert/runbook contracts;
- do not select a monitoring vendor or claim measured production SLO compliance;
- keep deployed telemetry, alert firing and browser correlation acceptance as `UAT_PENDING`.

Files under review:
- `backend/app/observability.py`
- `backend/app/health.py`
- `backend/app/integrations.py`
- `backend/app/raw_events.py`
- `backend/app/ai_provider_registry.py`
- `backend/tests/test_observability.py`
- `ops/prometheus/brain-alerts.yml`
- `docs/OBSERVABILITY.md`
- `docs/runbooks/OBSERVABILITY.md`
- `UAT/F-09.01.md`

Required verification:
```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_observability.py
pytest -q
cd ..
python scripts/verify_board.py
```

A green automated run may support engineering `DONE`; it must not be presented as deployed monitoring/alert/SLO UAT.

## Engineering closure — 2026-09-24

Status: **DONE (engineering)**. Deployed telemetry, alert firing, representative SLO measurement and browser/manual correlation remain **UAT_PENDING**.

Evidence baseline: commit `8be45dd4d96a87d9fa5a3cf9a385f8cd3ca6349f`; Backend CI `35930622742` passed Ruff + 385 backend tests; Delivery Verifier `35930622825` passed; Release Gate `35930622874` passed the full release checks. The closure Delivery Verifier re-runs the focused observability test command recorded in TRACEABILITY.md.
