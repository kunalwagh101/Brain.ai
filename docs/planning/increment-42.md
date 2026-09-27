# Increment 42 — Channel Administration

Story: `S-10.26.01`

Status: `IN_REVIEW`

## Sprint goal

Finish the channel-management workflow: rename/describe, archive/restore, and edit restricted-member read/write access from the production workspace.

## Vertical slice

A channel creator or Owner/Admin edits current channel identity with optimistic concurrency, archives/restores the channel, and changes existing restricted-member access through the already-tested membership service. Archived channels have a dedicated permission-filtered manager surface.

## Invariants

- visibility type cannot be converted by this story;
- message bodies/revisions/RawEvent/CanonicalEvent history are not rewritten;
- archive changes writeability/list placement, not read ACL/evidence retention;
- member access changes reuse `upsert_channel_member` and its current ResourceGrant propagation;
- Team/group placement survives archive/restore.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`; executable migration/tests/verifier and authenticated creator/Admin/member UAT remain required for DONE.

## Retrospective — 2026-09-20

No accepted requirement was cut. The main reuse win was that restricted-member access already had one authoritative service, `upsert_channel_member`, which updates membership plus current Work Graph/evidence grants. S-10.26 therefore exposed that path instead of creating a second permission implementation.

The channel model already had archive/status fields, so the only schema addition required was optimistic `settings_revision`. Rename updates the current channel + Work Graph track identity but deliberately does not rewrite historical message/RawEvent/CanonicalEvent evidence. Visibility conversion remains rejected because it would require a separate migration/grant/revocation contract.

The remaining acceptance risk is execution, not known implementation scope: PostgreSQL 0040 round-trip, backend/frontend/verifier runs and authenticated creator/Admin/member UAT have not yet produced PASS evidence.
