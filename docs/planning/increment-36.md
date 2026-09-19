# Increment 36 — Direct-Message Lifecycle

Story: `S-10.20.01`

Status: `IN_PROGRESS`

## Sprint goal

Allow a DM author to correct or retract their own currently visible private message while preserving participant-only privacy, optimistic concurrency and retention.

## Vertical slice

An author edits with an expected revision or retracts. Brain snapshots the prior private revision, updates/tombstones the current DM atomically, removes retracted messages from unread attention, and returns safe participant-only state. Nonauthors/nonparticipants/revoked/old-epoch actors fail closed.

## Reuse

Reuse DM participant/epoch authorization, private_message_days/legal hold, existing exact message route, S-10.18 unread state and same-origin WorkOS mutation patterns. Do not reuse native-channel evidence/audit projection.

## Explicit non-scope

Admin moderation override, edit time limits, hard-delete/eDiscovery, DM attachments/reactions and organisation-wide DM audit/search.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`. DONE requires migration round-trip, focused privacy/concurrency/retention tests, frontend checks, verifier and authenticated WorkOS UAT.
