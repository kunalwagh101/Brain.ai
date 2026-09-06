# Changelog

## Unreleased

### Increment 1 — secure organisation boundary

- Added WorkOS AuthKit access-token verification for FastAPI protected routes.
- Added provider-subject identity linking so client-supplied email/role is never trusted as authentication authority.
- Added authenticated organisation creation with atomic owner membership.
- Added tenant-safe organisation reads and owner-controlled membership creation/listing.
- Added the `external_identities` migration with downgrade support.
- Added authentication and cross-tenant negative-path tests.

Rollback: downgrade Alembic revision `20260906_0002` before deploying code that does not understand `external_identities`. Existing organisation/user/membership tables are unchanged by this revision.
