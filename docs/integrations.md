# Brain Integration Framework

## Scope

`F-02.01 / S-02.01.01` defines the provider-neutral connection lifecycle used by Slack, GitHub and later external systems. Provider-specific ingestion is intentionally not implemented here.

## Credential boundary

PostgreSQL contains only non-secret metadata and an AWS Secrets Manager reference (`secret_ref`). OAuth access tokens, refresh tokens and API keys are accepted only long enough to write the encrypted secret and are never modeled as database columns or returned by API responses.

Production uses AWS Secrets Manager through the standard AWS SDK credential chain. Do not configure static AWS credentials in source files or `.env.example`.

## Lifecycle

```text
CREATE
  -> permission: integration.manage
  -> validate provider/account/scopes
  -> reject duplicate organisation+provider+external account
  -> write credential payload to AWS Secrets Manager
  -> persist connection with secret reference
  -> ACTIVE

SYNC
  -> only ACTIVE + non-empty secret_ref may sync
  -> connector records health, cursor, last_synced_at/error code

REVOKE
  -> ACTIVE -> REVOKING committed first
  -> schedule AWS secret deletion with 7-day recovery window
  -> success: REVOKED + secret_ref cleared
  -> failure: REVOKE_FAILED (still non-syncable) + retry required
```

Moving out of `ACTIVE` before deleting the secret is intentional. If AWS is unavailable during revocation, connector workers still cannot continue syncing.

## Permissions

Only roles with `integration.manage` can create, inspect or revoke connections. In the current role matrix that is Owner and Admin. Cross-tenant requests fail through the existing tenant-safe authorization layer.

## Sync state

`app.integrations.connection_can_sync()` is the common worker guard. Provider workers must call it (or `ensure_connection_can_sync`) before loading credentials or making provider calls.

`record_sync_success()` persists a new opaque cursor, healthy state and sync timestamp. `record_sync_failure()` persists a bounded non-secret error code. Never persist provider response bodies, access tokens or customer source content in `last_error_code`.

## Failure handling

If database persistence fails after a new secret was created, Brain attempts to schedule the orphaned secret for deletion. A cleanup failure is logged without the secret value and must be operationally alerted when observability is expanded under F-09.01.

If Secrets Manager deletion fails during revocation, the API returns 503 and the connection remains `REVOKE_FAILED`, which is non-syncable.

## AWS permissions

The production workload identity needs only the Secrets Manager actions required by this slice: create a connection secret, retrieve it for connector execution, and schedule deletion. IAM scope should be restricted to the configured Brain secret prefix and environment.

AWS documents that `CreateSecret` stores encrypted secret material, `GetSecretValue` retrieves it, and secret values should not be copied into logs. Repeated retrieval should use caching only when connector load makes it worthwhile.

## Migration and rollback

Upgrade: `20260906_0004` creates `integration_connections`.

Rollback: stop connector workers first, then downgrade `20260906_0004`. Downgrading drops connection metadata but does not automatically delete external AWS secrets. Before rollback in an environment with real credentials, export the secret references and execute the credential-retirement runbook so no orphan credentials remain.

## UAT

Engineering-DONE is not feature acceptance. Real-data backend and frontend/manual acceptance remain tracked separately in `UAT.md`.
