# Increment 42 — Channel Administration

Story: `S-10.26.01`

Status: `IN_PROGRESS`

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
