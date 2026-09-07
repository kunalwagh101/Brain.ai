# External API Registry

## Purpose

F-06.03 inventories external API access without turning Brain into a generic HTTP proxy. It records which external API services exist, which credential grants Brain knows about, who owns them, what scopes/environment they carry, their lifecycle, expiry and observed usage metadata.

Plaintext credentials are never stored in PostgreSQL and are never returned by registry read APIs.

## Data model

### API service

An `APIService` is tenant-scoped metadata for an external API:

- stable `service_key`
- display name
- provider/vendor name
- optional base URL for inventory context
- creator and timestamps

The base URL is descriptive only in this feature. F-06.03 does not execute requests to it.

### Credential grant

An `APICredentialGrant` belongs to one API service and stores:

- stable grant key and display name
- active Brain-member owner
- environment
- explicit scope list
- secret reference only
- lifecycle status
- optional expiry
- credential rotation timestamp
- last-observed usage metadata and count
- creator/revocation/expiry timestamps

Read APIs expose only `credential_present=true|false`; the underlying secret reference is not returned.

### Immutable history

`APIGrantHistory` stores before/after lifecycle metadata for:

- creation
- owner changes
- scope changes
- environment changes
- enable/disable
- credential rotation
- revocation start/failure/success
- expiry

Credential values are never written to history.

### Usage observations

`APIUsageObservation` contains only bounded operational metadata:

- deterministic observation key
- trusted caller component
- optional operation label
- success/failure
- latency
- observed timestamp

No request body, response body, API key or token is stored. There is intentionally no public write endpoint for usage observations; trusted server-side integrations call `record_api_usage(...)` directly so a normal client cannot fabricate usage evidence.

## Permissions

- registry mutations: `api.manage` — Owner/Admin
- organisation-wide registry/history/usage reads: existing `audit.read` — Owner/Admin/Executive
- ordinary Members/Guests cannot read organisation-wide credential inventory

## Secret lifecycle

Credential creation writes the supplied credential dictionary directly to the configured `SecretStore` and persists only the returned reference.

Rotation calls `replace_secret` and retains the same reference. The registry records only `credential_rotated_at` plus a history event.

Revocation is fail closed:

`active|disabled -> revoking -> revoked`

If secret deletion fails:

`revoking -> revoke_failed`

`revoke_failed` cannot be re-enabled, rotated or metadata-mutated. A later revoke retry can finish secret deletion and transition to `revoked`.

## Expiry

A configured expiry is processed by the bounded worker:

```bash
cd backend
python -m app.api_registry_worker --once --batch-size 100
```

The database transition to `expired` happens first, which makes the grant unusable to compliant callers immediately. Secret deletion is then scheduled. If secret deletion fails, the grant remains `expired` with its secret reference retained only for cleanup retry; the next worker run retries deletion and clears the reference after successful scheduling.

PostgreSQL workers use row locking / `SKIP LOCKED` where multiple workers could otherwise claim the same lifecycle row.

## Usage observation contract

A trusted caller records usage with a deterministic `observation_key`. Replay returns the existing observation and does not increment `usage_count` twice. PostgreSQL locks the grant row while applying a new observation so concurrent observations do not lose usage-count increments.

Usage may still be recorded after a grant is disabled, expired or revoked. This is intentional: evidence that a retired credential path was still attempted is security-relevant and must not be hidden.

## API

Under `/api/v1/organizations/{organization_id}/api-registry`:

- `POST /services`
- `GET /services`
- `POST /grants`
- `GET /grants`
- `GET /grants/{grant_id}`
- `POST /grants/{grant_id}/owner`
- `POST /grants/{grant_id}/scopes`
- `POST /grants/{grant_id}/environment`
- `POST /grants/{grant_id}/status`
- `POST /grants/{grant_id}/rotate`
- `POST /grants/{grant_id}/revoke`
- `GET /grants/{grant_id}/history`
- `GET /grants/{grant_id}/usage`

## Migration and rollback

Alembic revision `20260907_0013` creates registry service, credential-grant, immutable history and usage-observation tables.

Downgrade removes only the registry-derived tables. Secret-manager objects are external resources and are not automatically recreated or deleted by Alembic rollback. Operational rollback must therefore preserve the current credential inventory and explicitly decide whether secret references should remain available to a previous application version.

## Production acceptance limitation

The registry can be engineering-complete before it has broad usage coverage. Do not claim “all API usage is governed” until each real calling subsystem has been wired to the internal usage-observation contract and realistic UAT proves that observed usage matches actual calls.
