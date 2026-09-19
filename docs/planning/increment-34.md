# Increment 34 — DM Unread & Resume

Story: `S-10.18.01`

Status: `IN_PROGRESS`

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
