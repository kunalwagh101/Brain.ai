# Increment 41 — Team Channel Groups

Story: `S-10.25.01`

Status: `IN_PROGRESS`

## Sprint goal

Deliver Team → channel group → channel hierarchy without turning navigation metadata into an authorization system.

## Vertical slice

Create/edit/archive/restore channel groups inside active Teams. An authorised channel manager can assign, move or unassign a channel. Workspace navigation nests only already-visible channels and provides safe Ungrouped/Unassigned fallbacks.

## Invariants

- channel visibility and NativeChannelMembership are unchanged by navigation moves;
- ResourceGrant/evidence/Search access is unchanged;
- hidden restricted channels are never leaked by hierarchy reads;
- DMs remain outside shared hierarchy under OQ-010;
- archived groups/Teams never make a visible channel unreachable.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`; executable migration/tests/verifier plus authenticated multi-role/revocation UAT remain required for DONE.
