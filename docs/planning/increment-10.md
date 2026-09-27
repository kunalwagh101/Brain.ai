# Increment 10 — AI Provider Registry and Gateway

Story: S-06.01.01 / F-06.01

Goal: route approved AI requests through one tenant-scoped, provider-neutral gateway that records provider/model/org/user/project attribution when known, keeps credentials in the existing secret store, surfaces provider failures explicitly, and never logs prompt/credential secrets by default.

## Readiness

- Dependency S-01.03.01 (RBAC/ACL) is engineering-DONE.
- Existing AWS Secrets Manager reference contract is reused; plaintext API credentials must not be persisted in PostgreSQL.
- OQ-005 does not block gateway shape. This increment creates a provider-neutral registry/runtime; it does not select the first production RAG generation default.
- The gateway must be useful to later Ask Brain and agents without widening source-data permissions.

## Acceptance criteria

1. Given an authorised admin, when an AI provider configuration is created, PostgreSQL stores only non-secret metadata plus a secret reference.
2. Given an organisation user with `ai.use`, when a request targets an enabled model, the gateway records organisation, requesting user, provider, model, request status, latency and provider request ID when returned.
3. Given project/work-item attribution is supplied, it is accepted only for a same-organisation resource the user may access; unknown attribution remains null rather than guessed.
4. Given a disabled provider/model or a caller without `ai.use`, no provider call is made.
5. Given provider timeout/HTTP/malformed response failure, the request is recorded as failed with a bounded error code and the API surfaces a safe failure; credentials and prompt bodies are not written to logs or usage rows.
6. Given a provider credential is revoked, later calls fail closed before external execution.
7. Provider/model identifiers are validated and tenant-scoped; one organisation cannot enumerate/use another organisation's provider configuration.
8. The provider runtime uses a provider-neutral contract; vendor-specific response parsing is isolated in adapters.
9. Tests cover tenant isolation, RBAC, secret-reference persistence, provider failure, idempotent status recording, metadata attribution and log redaction.
10. Migration downgrade removes gateway-derived/configuration tables without touching existing source evidence, graph, search or identity data.

## Tasks

- T-06.01.01.a provider/model + request-record schema and migration
- T-06.01.01.b secret-store extension for AI provider credentials
- T-06.01.01.c provider-neutral adapter/runtime contract
- T-06.01.01.d admin provider/model lifecycle API
- T-06.01.01.e governed invoke API with attribution and failure recording
- T-06.01.01.f security/idempotency/failure tests
- T-06.01.01.g docs, UAT, board/traceability

## Out of scope

- Choosing the production RAG model/provider (OQ-005)
- Ask Brain answer generation (F-05.02)
- Token-cost/budget enforcement (F-06.02)
- Agent execution/approval tools (F-08.01)
- Storing full prompts/completions for analytics by default
