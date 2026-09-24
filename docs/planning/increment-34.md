# Increment 34 — DM Unread & Resume

Story: `S-10.18.01`

Status: `IN_REVIEW`

## Sprint goal

Give each authorised 1:1 DM participant a private unread badge and exact first-unread resume point without weakening visibility epochs or organisation privacy.

## Vertical slice

A participant sees unread counts in the DM list, opens a conversation, gets one New messages divider before the exact first unread message, and can Jump to unread. Opening advances only that participant's monotonic DM read cursor. Exact recovery remains participant-only and older visibility epochs never reappear.

## Reuse

Reuse `DirectConversation.next_message_sequence`, participant visible-from sequence, current DM permission checks, WorkOS same-origin patterns, S-10.17 divider/focus UX and existing live workspace refresh. No AI, no employer-wide audit, no generic activity history, no second DM content store.

## Explicit non-scope

Read receipts exposed to the other participant, "seen at" timestamps, group DMs, push notifications and message-level delivery receipts.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`. Final DONE requires executable migration/backend/frontend/verifier evidence plus authenticated two-user epoch/revocation UAT.

## Retrospective — 2026-09-19

No accepted S-10.18.01 requirement was cut.

The smallest correct design was two participant read cursors on the existing 1:1 conversation row. A separate read-state table would add abstraction without product value and would make visibility-epoch safety harder to reason about.

The important privacy invariant is that a restored participant starts at `visible_from_sequence - 1`; old hidden messages therefore cannot reappear as unread or exact jump targets. Unread calculations remain participant-only and exclude the current user's own sends.

The UI reuses the S-10.17 boundary pattern: capture the initial first-unread ID, immediately advance the persisted cursor when the selected DM opens, and preserve the mounted divider during the refresh. Exact recovery rechecks participant access server-side.

Estimate miss: participant epoch semantics made the read cursor a migration/data-integrity change rather than a UI-only badge feature.

The story is IN_REVIEW, not DONE. PostgreSQL round-trip, focused backend tests, frontend build/source contracts, verifier and authenticated WorkOS UAT remain required.
