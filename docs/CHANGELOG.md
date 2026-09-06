# Changelog

## Unreleased

### Increment 5 — GitHub connector and canonical event model

- Added a verified GitHub App installation flow with Brain-signed, expiring organisation/user state and installation-selection tokens.
- Added GitHub installation re-verification against the configured App before a connection can be persisted; the generic integration endpoint rejects `provider=github` to prevent bypass.
- Added secret-reference loading for the GitHub App private key, OAuth client secret and webhook secret; installation access tokens are short-lived and never persisted.
- Added exact-body HMAC-SHA256 GitHub webhook verification and delivery-ID idempotency for supported engineering events.
- Added repository visibility and `github:repository:<id>` ACL provenance for restricted repositories.
- Added signed, connection-bound, resumable GitHub backfill for repository metadata, commits, pull requests, issues and deployments, with deterministic replay-safe source IDs.
- Added schema-versioned `canonical_events`, one canonical row per raw event, carrying actor/action/object/source/timestamp/permissions/provenance/provider metadata.
- Wired both Slack and GitHub live/backfill evidence through the same canonicalisation engine.
- Unsupported or malformed mappings are quarantined while the original raw evidence remains intact.
- Added Alembic revision `20260906_0006` with downgrade support.
- Added GitHub/canonical model, signature, tamper, replay, ACL, cursor and cross-provider tests; Backend CI passed 73 tests.
- Added GitHub deployment documentation and real-data/manual UAT scripts. Engineering-DONE remains separate from user acceptance.

Rollback: stop Slack/GitHub ingestion and canonicalisation before downgrading `20260906_0006`. The downgrade removes canonical-event storage and GitHub provider metadata added by this increment. Raw events remain the recovery evidence; export any canonical records required for investigation before rollback.

### Increment 4 — Slack connector and raw event ingestion

- Added Slack OAuth v2 installation with signed, expiring state and permission re-check at callback time.
- Added minimal Slack channel/group read/history scopes; no DM/MPIM scopes are requested.
- Added explicit channel discovery/authorisation with private-channel source membership capture.
- Added signed Slack Events API endpoint using the exact raw body, timestamp replay window and HMAC verification before JSON parsing.
- Added durable `raw_events` storage with exact payload bytes, SHA-256 provenance, source visibility/ACL, processing state and retry-safe uniqueness.
- Added Slack membership event handling to keep private-channel source ACL state current.
- Added resumable, page-bounded Slack history backfill with deterministic historical message IDs and replay deduplication.
- Added Slack channel authorisation and raw-event tables in Alembic revision `20260906_0005` with downgrade support.
- Added tests for OAuth state tampering, signatures, replay window, DM rejection, channel authorisation, private ACL state, raw bytes/checksum, retry idempotency, payload limit and backfill replay.
- Added real-data/manual UAT scripts; engineering-DONE remains separate from user acceptance.

Rollback: stop Slack event delivery/backfill and any future raw-event processor before downgrading `20260906_0005`. The downgrade removes raw events and Slack channel authorisations, so export any evidence required for investigation/audit before rollback. Integration connection metadata and AWS secrets from Increment 3 are retained.

### Increment 3 — integration connection framework

- Added provider-neutral integration connection lifecycle scoped to an organisation.
- Added AWS Secrets Manager credential storage; PostgreSQL stores only the secret ARN/reference and non-secret metadata.
- Added create/list/read/revoke FastAPI endpoints protected by `integration.manage`.
- Added duplicate organisation/provider/account prevention before secret creation.
- Added connection health, opaque sync cursor, last-sync timestamp and bounded error-code state for connector workers.
- Added fail-closed revocation: connection leaves ACTIVE before secret deletion is attempted, and deletion failure leaves it non-syncable.
- Added orphan-secret cleanup when database persistence fails after credential creation.
- Added Alembic revision `20260906_0004` and explicit rollback notes.
- Added fake-AWS tests so automated verification requires no real AWS credential or network secret.
- Resolved OQ-003: AWS Secrets Manager is the first production secrets backend.

Rollback: stop connector workers before downgrading `20260906_0004`. The downgrade removes integration metadata but does not delete AWS secrets. Export/retire referenced secrets first in any environment that has real credentials.

### Increment 2 — RBAC and resource ACL

- Added one server-side role permission matrix for owner, admin, executive, manager, member and guest roles.
- Added reusable FastAPI organisation and restricted-resource permission dependencies.
- Added active-user enforcement and tenant-safe 404 behaviour for non-members.
- Added explicit `resource_grants` ACL storage and owner/admin grant management endpoints.
- Restricted-resource access now requires both role capability and a matching user grant before endpoint, connector, LLM or tool code can run.
- Admins can manage normal members, but only owners may assign owner/admin roles.
- Added structured `brain.security` authorization-denial and ACL-change audit hooks without secrets or content payloads.
- Resolved the Slack privacy boundary: DMs excluded from MVP; private channels opt-in; public/shared channels still require admin authorisation.
- Added Alembic revision `20260906_0003` with downgrade support and tenant/resource indexes.
- Added role-matrix, cross-tenant, restricted-resource, ACL lifecycle and deny-before-handler tests.

Rollback: disable code paths that depend on resource ACLs, then downgrade Alembic revision `20260906_0003`. The downgrade removes `resource_grants` and therefore all explicit restricted-resource grants; it does not modify users, memberships or external identities.

### Increment 1 — secure organisation boundary

- Added WorkOS AuthKit access-token verification for FastAPI protected routes.
- Added provider-subject identity linking so client-supplied email/role is never trusted as authentication authority.
- Added authenticated organisation creation with atomic owner membership.
- Added tenant-safe organisation reads and owner-controlled membership creation/listing.
- Added the `external_identities` migration with downgrade support.
- Added authentication and cross-tenant negative-path tests.

Rollback: downgrade Alembic revision `20260906_0002` before deploying code that does not understand `external_identities`. Existing organisation/user/membership tables are unchanged by this revision.
