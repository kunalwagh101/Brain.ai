# Increment 36 — Direct-Message Lifecycle

Story: `S-10.20.01`

Status: `IN_REVIEW`

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

## Retrospective — 2026-09-19

No accepted S-10.20.01 requirement was cut.

The important architecture decision was not to reuse native-channel lifecycle projection. Brain-native DMs are participant-private under OQ-008, so their revision history remains in private DM tables and never enters company-wide RawEvent/CanonicalEvent/Search/Work Graph/audit surfaces.

Optimistic concurrency uses the same minimal pattern as channel lifecycle: expected revision + row lock + one revision increment. Authority is stricter because a DM author must also remain inside the current participant visibility epoch.

Retraction keeps the stored private body only behind the current tombstone until existing private-message retention removes the message. Revision rows cascade with that deletion, so no second retention scheduler/class was added.

Estimate miss: the persistence change was straightforward; proving the absence of organisation-wide evidence/audit projection and old-epoch mutation was the higher-risk part.

The story is IN_REVIEW, not DONE. Migration round-trip, focused backend/frontend/verifier execution and authenticated WorkOS UAT remain required.
