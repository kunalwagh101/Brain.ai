# Increment 14 — Audit, Retention and Deletion

Branch policy: this increment intentionally continues on `increment-10-ai-provider-gateway`; no new branch is created.

Story: S-09.02.01 — Maintain immutable sensitive-action audit evidence and enforce retention.

## Goal

Give Brain a tenant-safe, auditable and recoverable data-governance boundary: security-sensitive mutations and denials have durable evidence, retention is explicit per organisation, legal hold overrides deletion, and customer evidence can be deleted without later reconciliation silently recreating it.

## Acceptance contract

1. Sensitive security/governance events are stored in a tenant-scoped durable audit ledger with actor, outcome, resource, bounded metadata, request correlation and SHA-256 payload digest.
2. PostgreSQL rejects `UPDATE` of audit ledger rows at the database layer. Retention may delete audit rows only when an explicit organisation policy makes them eligible.
3. Audit metadata rejects credential/token/secret-shaped field names; audit records never store request bodies, prompts, raw webhook payloads, API keys or OAuth credentials.
4. Retention policy is explicit per organisation for raw events, derived content and audit events. An unset duration means no automatic age-based purge for that class.
5. Legal hold overrides scheduled retention and blocks new/existing explicit deletion execution until the hold is removed.
6. Raw-event retention deletes eligible raw evidence and its canonical/search/work-graph/decision derivatives.
7. Derived-content retention deletes canonical/search/work-graph/decision derivatives while retaining raw evidence. A durable tombstone prevents the retained raw event from rebuilding purged derived content.
8. A source-object deletion request deletes the target raw evidence even when its canonical row was already removed by derived retention; the retention tombstone therefore preserves only the minimal provider/object locator required for later deletion.
9. Integration-wide deletion is allowed only after the integration is fully revoked and is tenant validated.
10. Explicit deletion requests are idempotency-keyed, recover stale `processing` work, record stable target reference/counts/completion digest, and do not retain deleted customer content as completion evidence.
11. Canonicalisation suppresses evidence covered by an active/completed deletion target or a derived-retention tombstone so deleted/purged material cannot silently reappear.
12. Orphan source identities are sanitised after evidence deletion and return to `unresolved` state rather than keeping stale resolved identity claims.
13. Owner/Admin may manage retention/deletion through `data_governance.manage`; organisation-wide governance/audit reads use `audit.read`. Executive may read but not mutate; Member cannot read organisation-wide audit data.
14. ACL create/delete mutations fail closed if their durable audit event cannot be persisted. Authorization-denial audit persistence is best-effort so an audit-store problem cannot widen access.
15. The bounded worker processes retention and pending/failed/stale deletion requests; PostgreSQL uses row locks / `SKIP LOCKED` where concurrent workers could otherwise duplicate work.
16. No engineering-DONE claim is allowed until Ruff, Pytest, migration verification and the delivery verifier execute successfully. PostgreSQL trigger/cascade behavior and real-data/manual deletion remain UAT evidence.

## Retention-default decision

OQ-006 remains a customer/compliance policy question. The engineering-safe default is:

- `raw_event_days = NULL` → do not automatically purge raw events
- `derived_content_days = NULL` → do not automatically purge derived evidence
- `audit_event_days = NULL` → do not automatically purge audit events

Brain does not hard-code a legal retention duration without customer/regulatory evidence.

## Tasks

- T-09.02.01.a durable tenant-scoped audit ledger + database append-only enforcement
- T-09.02.01.b explicit per-organisation retention policy + legal hold
- T-09.02.01.c raw/derived/audit bounded retention engine
- T-09.02.01.d derived-retention tombstones and reconstruction suppression
- T-09.02.01.e integration/source-object deletion requests and completion evidence
- T-09.02.01.f stale-work recovery + bounded PostgreSQL-safe worker
- T-09.02.01.g ACL/authorization governance audit integration
- T-09.02.01.h security, tenant, cascade, idempotency and worker tests
- T-09.02.01.i operator documentation, rollback and deployed UAT

## Explicit non-goals

- Choosing a legal/compliance retention duration for every customer.
- Erasing backup/snapshot copies without the deployment provider's separate lifecycle controls.
- A public API that lets ordinary users delete arbitrary database rows.
- Persisting deleted customer content inside deletion receipts/audit metadata.
- Claiming GDPR/CCPA/ISO/SOC compliance solely because retention/deletion mechanics exist.
