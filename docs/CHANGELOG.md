# Changelog

## Unreleased

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
