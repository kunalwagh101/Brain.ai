# Increment 12 — External API Registry

Branch policy: this increment intentionally continues on `increment-10-ai-provider-gateway`; no new branch is created.

Story: S-06.03.01 — Inventory external API access without plaintext credentials.

## Goal

Give security/admin users a tenant-scoped inventory of external API access with explicit ownership, scopes, environment, lifecycle, expiry and usage metadata while keeping credential material exclusively in the configured secret store.

## Acceptance contract

1. A registered API service and credential grant belong to exactly one organisation; cross-tenant reads/mutations return no foreign fields.
2. PostgreSQL stores only a secret reference. API keys/tokens/client secrets are accepted only for transfer into the server-side secret store and are never returned by read APIs.
3. Every grant has an active Brain-member owner, explicit scopes, environment, status, optional expiry and creator.
4. Scope/environment/provider/service identifiers are normalized and bounded; an empty scope set is rejected.
5. Owner reassignment is allowed only to another active member in the same organisation and writes immutable before/after history.
6. Disable/re-enable is allowed only before revocation starts. Revocation fails closed: `revoking` and `revoke_failed` cannot be used or re-enabled; successful deletion ends in `revoked` with the secret reference cleared.
7. Due expiry moves an eligible grant to `expired` and writes one immutable expiry history event; replay is idempotent.
8. Credential rotation replaces the secret in the secret store, records `credential_rotated_at`, and writes audit history without storing old/new credential values.
9. Internal usage observation updates bounded usage metadata and appends an immutable usage event without accepting arbitrary plaintext request/response payloads.
10. Organisation-wide registry reads require the existing `audit.read`; mutations require a dedicated `api.manage` permission (Owner/Admin).
11. No feature claims production usage coverage until real calling systems are wired to the internal usage-observation contract and UAT proves it.

## Tasks

- T-06.03.01.a tenant-scoped API service/grant/history/usage schema and migration
- T-06.03.01.b server-side secret-store create/rotate/delete lifecycle
- T-06.03.01.c owner/scope/environment/status validation and fail-closed transitions
- T-06.03.01.d expiry reconciliation worker with idempotent audit history
- T-06.03.01.e permissioned registry/read/mutation API
- T-06.03.01.f internal usage-observation contract and visible usage metadata
- T-06.03.01.g tenant/security/idempotency/revocation/expiry tests
- T-06.03.01.h operator docs, rollback and real-data/frontend UAT

## Explicit non-goals

- Generic HTTP proxying through Brain
- Storing or displaying plaintext API credentials
- Guessing owners or scopes from traffic
- Network traffic discovery without an authorised integration
- Provider invoice reconciliation (F-06.02)
- Agent tool execution/approval policy (F-08.01)
