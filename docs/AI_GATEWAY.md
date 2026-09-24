# Governed AI Provider Gateway

Feature: F-06.01 / S-06.01.01

## Purpose

Brain must not let each feature call model providers directly. The AI gateway is the single governed boundary for provider/model configuration, credential loading, request attribution and provider failure handling.

This increment does **not** choose the production RAG model. OQ-005 remains open. It creates the provider-neutral contract that Ask Brain, later agents and other AI features can use.

## Security invariants

- Provider configuration is tenant-scoped.
- Provider/model management requires `ai.manage` (Owner/Admin only in the current role matrix).
- Invocation requires `ai.use`.
- PostgreSQL never stores provider API keys. It stores an AWS Secrets Manager reference only.
- Provider credentials are loaded only immediately before an authorised invocation.
- Disabled/revoked providers and disabled models fail before external execution.
- Provider revocation first disables the configuration, so a failed Secrets Manager deletion still fails closed.
- Prompt/system text and model completion bodies are not persisted in `ai_request_records` by default.
- Provider HTTP error bodies are not returned or stored.
- In production, provider URLs must use HTTPS and the hostname must be present in `BRAIN_AI_PROVIDER_ALLOWED_HOSTS`.
- Optional project/work-item attribution is accepted only for a same-organisation Work Graph node currently visible to the caller. Unknown attribution stays null.

## Stored data

### `ai_provider_configurations`

Non-secret provider metadata: organisation, provider key, display name, adapter kind, API URL, secret reference, status and creator.

### `ai_model_configurations`

Provider-bound model key, display name, enabled state and optional maximum output-token default.

### `ai_request_records`

One row per actual provider attempt. The row records:

- organisation and requesting Brain user;
- provider/model IDs and stable keys;
- optional project/work-item attribution;
- pending/succeeded/failed status;
- input/output character counts;
- provider-reported token counts when available;
- latency;
- provider request ID when returned;
- bounded safe error code;
- timestamps.

It deliberately does not contain prompt or completion text.

## Runtime contract

`AIProviderAdapter.invoke(...)` receives the approved endpoint, credential, model, input and bounded generation settings and returns `AIProviderResult`.

The first adapter is `openai_chat_completions`. Vendor-specific request/response parsing lives only inside that adapter. Future provider adapters must preserve the gateway result/error contract rather than leaking vendor response shapes into product code.

## Request lifecycle

1. Authorise the organisation and `ai.use` permission.
2. Resolve the tenant-scoped provider and model.
3. Reject disabled/revoked provider/model before any network access.
4. Validate optional Work Graph attribution against the caller's current visibility.
5. Insert a `pending` request record and commit it.
6. Load the provider secret from AWS Secrets Manager.
7. Call the adapter.
8. On success, update the same request record to `succeeded` with latency/usage metadata.
9. On failure, update the same request record to `failed` with a safe bounded code and surface a safe API error containing the Brain request ID.

## Provider administration API

All paths are below `/api/v1/organizations/{organization_id}/ai`.

- `POST /providers`
- `GET /providers`
- `POST /providers/{provider_id}/status`
- `POST /providers/{provider_id}/revoke`
- `POST /providers/{provider_id}/models`
- `GET /providers/{provider_id}/models`
- `POST /models/{model_id}/status`
- `POST /invoke`

Provider response models never include `secret_ref` or credentials.

## Production egress

Set:

```text
BRAIN_AI_PROVIDER_ALLOWED_HOSTS=api.provider-a.example,api.provider-b.example
BRAIN_AI_PROVIDER_TIMEOUT_SECONDS=30
```

In production the configured endpoint must be HTTPS and its exact hostname must be on the allowlist. Do not add wildcard domains. Provider/API-key approval remains an operator/customer security decision.

## Migration and rollback

Revision: `20260907_0011`.

Upgrade creates only AI gateway configuration/request tables. Downgrade removes:

1. `ai_request_records`
2. `ai_model_configurations`
3. `ai_provider_configurations`

It does not remove organisations, users, integration evidence, Work Graph, search, decision memory or Secrets Manager credentials. Before downgrade, revoke/delete active AI provider credentials through the provider API or operator secret-management procedure; database rollback cannot delete an external secret after the configuration row is gone.

## Known boundaries for later features

- F-06.02 owns deterministic cost/rate tables, budget thresholds and alerts.
- F-05.02 Ask Brain owns retrieval + evidence-backed generation behavior.
- F-08.01 owns agent tool execution and approval controls.
- Prompt/completion retention is intentionally not introduced here; any future retention requires an explicit privacy/retention decision rather than silently expanding telemetry.
