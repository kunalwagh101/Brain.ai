# Audit, Retention and Deletion

## Purpose

F-09.02 gives Brain an explicit data-governance boundary for security audit evidence, customer-evidence retention and targeted deletion. It does not claim a legal retention duration on behalf of a customer.

## Security model

### Administration

`data_governance.manage` is an Owner/Admin capability. It controls:

- retention-policy changes
- legal-hold changes
- manual retention execution
- creation and execution of deletion requests

Organisation-wide governance and audit reads use `audit.read`. Owner, Admin and Executive can read those records through the existing role matrix; ordinary Members cannot.

### Durable audit evidence

`security_audit_events` stores bounded security/governance evidence:

- organisation
- event key/type/outcome
- actor when known
- resource type/id
- request ID when available
- allowlisted bounded metadata
- SHA-256 digest of the normalized audit payload
- creation timestamp

It never intentionally stores request bodies, raw webhook bodies, prompts, completions, API keys, OAuth tokens or document/message content.

Audit metadata rejects field names containing credential/token/secret patterns. This is defense in depth; callers must still never pass sensitive values.

On PostgreSQL, migration `20260908_0014` installs a trigger that rejects `UPDATE` on `security_audit_events`. Audit rows are append-only. `DELETE` remains possible only so an explicit audit-retention policy can be enforced.

ACL create/delete mutations are fail-closed with their durable audit record. Authorization-denial audit persistence is best-effort so an audit-store failure cannot accidentally widen access.

## Retention policy

Each organisation may independently configure:

- `raw_event_days`
- `derived_content_days`
- `audit_event_days`
- `legal_hold`

A `NULL` duration means **no automatic age-based purge for that class**. Brain does not guess a compliance period.

Allowed configured duration range is 1–36,500 days.

### Raw-event retention

When raw evidence is older than the configured cutoff, a bounded retention run removes the eligible `raw_events` rows. Their canonical/search/work-graph/decision derivatives are removed through the evidence chain/cascades.

### Derived-content retention

Derived retention is intentionally different. Brain:

1. identifies eligible canonical evidence;
2. records a minimal `derived_retention_tombstone` containing only raw-event ID plus provider/object locator;
3. removes the canonical evidence and its search/work-graph/decision derivatives;
4. retains the raw event until raw-event retention or an explicit deletion request removes it.

The tombstone prevents reconciliation/canonicalisation from rebuilding purged derived evidence.

The minimal provider/object locator also allows a later explicit source-object deletion to locate the retained raw event even though the canonical row no longer exists. It does not retain the deleted message/document body.

### Audit retention

Audit rows older than the configured audit cutoff are deleted in bounded batches. The retention-run control record and newly generated completion audit evidence are not the old rows being purged.

## Legal hold

`legal_hold=true` overrides normal purge behavior:

- scheduled/manual retention performs no customer-data deletion;
- creating a new deletion request is blocked;
- executing an existing deletion request is blocked.

Removing a legal hold is itself a retention-policy mutation and is auditable.

This application flag is a governance control, not a substitute for a legal/compliance review or storage-provider backup hold.

## Explicit deletion

Two scopes are implemented.

### Integration deletion

The target integration must belong to the same organisation and must already be fully `revoked`. Brain then removes raw events for that integration and the corresponding derived evidence.

### Source-object deletion

The request identifies:

- source provider
- object type
- source object external ID

Brain finds matching live canonical rows and matching derived-retention tombstones. Therefore raw evidence is still deleted when derived evidence was purged earlier.

## Deletion evidence

Deletion requests are idempotency-keyed by `organization_id + request_key`.

A completed request retains only control evidence such as:

- stable `target_reference`
- deletion scope
- requesting actor and reason
- raw/canonical row counts
- completion timestamp
- SHA-256 completion digest over IDs/count context

The completion digest is not a copy of deleted customer content.

Reusing the same request key for a different target is rejected.

## Reconstruction suppression

Deletion is not considered complete if the same evidence can immediately reappear through replay/reconciliation.

Canonicalisation therefore checks:

- derived-retention tombstones by raw-event ID;
- integration deletion requests in suppressing states;
- source-object deletion requests in suppressing states.

A new raw delivery for an explicitly deleted source object is discarded rather than reintroduced into the canonical/search graph.

## Orphan identity sanitation

Evidence deletion may remove all observations supporting a source identity. When that happens Brain clears stale display/email/resolution data and moves the identity back to `unresolved` rather than leaving an unsupported resolved-person claim.

## Worker

Run one bounded pass with:

```bash
cd backend
python -m app.data_governance_worker --once --batch-size 100
```

The command:

1. enumerates organisations;
2. performs one bounded retention pass for organisations with a policy;
3. finds pending, failed or stale-processing deletion requests;
4. executes each request through the same idempotent service path.

The maximum batch size is 500. Production PostgreSQL selection uses row locks / `SKIP LOCKED` where appropriate. The deletion executor itself locks a request row and returns immediately when the request is already completed, so concurrent workers cannot legitimately double-delete a completed request.

A `processing` deletion older than 15 minutes is eligible for recovery.

## API surface

Base path:

`/api/v1/organizations/{organization_id}/data-governance`

Available operations include:

- `GET /retention-policy`
- `PUT /retention-policy`
- `POST /retention/run`
- `GET /retention/runs`
- `POST /deletions`
- `POST /deletions/{deletion_request_id}/execute`
- `GET /deletions`
- `GET /audit-events`

There is no generic endpoint that accepts arbitrary table names/IDs for deletion.

## Migration and rollback

Revision:

`20260908_0014`

Upgrade creates:

- `organization_retention_policies`
- `security_audit_events`
- `retention_runs`
- `data_deletion_requests`
- `derived_retention_tombstones`
- PostgreSQL audit-update rejection trigger/function

Normal migration command:

```bash
cd backend
alembic upgrade head
```

Rollback of this schema revision:

```bash
alembic downgrade 20260907_0013
```

Rollback removes governance control/evidence tables and the append-only trigger. It **cannot restore customer evidence that a completed retention/deletion run already deleted**. Before rolling back in a real environment, operators must understand that distinction and use the approved backup/restore procedure if restoration is legally and operationally permitted.

## Backup and snapshot boundary

Application deletion covers the active Brain database rows governed by these tables. It does not by itself prove deletion from:

- managed PostgreSQL backups
- point-in-time recovery logs
- infrastructure snapshots
- exported analytics/log archives
- third-party source systems such as Slack or GitHub

Those lifecycles belong to deployment/provider controls and must be included in the organisation's actual retention/deletion policy. Do not claim end-to-end regulatory erasure until those systems are verified too.

## Verification boundary

Unit tests can prove service mechanics, permissions, idempotency and SQLite-compatible cascade behavior. Engineering acceptance still requires PostgreSQL verification for:

- migration upgrade/downgrade
- append-only trigger enforcement
- foreign-key cascades
- concurrent worker locking
- bounded retention counts

Real-data UAT must separately prove that deleted evidence disappears from search/work graph/decision memory and does not reappear after connector replay or reconciliation.
