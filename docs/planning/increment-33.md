# Increment 33 — First-Unread Divider & Jump to Unread

Story: `S-10.17.01`

Status: `IN_PROGRESS`

## Sprint goal

Let an authorised user resume a Brain-native channel at the exact first unread root or thread reply without rescanning conversation history or creating another unread-state system.

## Vertical slice

The existing per-user/channel cursor identifies the exact first unread message. The workspace shows one accessible New messages divider and a Jump to unread action. If the exact target is not in the currently rendered root/thread window, the browser uses the existing same-origin permission-aware message path to recover the target and opens its thread when required. Existing mark-read semantics remain monotonic.

## Reuse

Reuse `NativeChannelReadState.last_read_sequence`, `NativeMessage.message_sequence`, current channel authorization, the exact message read, S-10.11 message anchors, S-10.12 retraction semantics, the existing WorkOS same-origin message route, and the current channel/thread components. No AI, Redis, WebSocket, new table, second unread ledger or copied message content.

## Measurable success

At most one divider per open channel; exact first-unread target reached for roots and replies; own/retracted messages never become first unread; restricted revocation returns no target; unread summary remains set-based with no N+1 query; browser receives no reusable backend token.

## Explicit non-scope

Direct-message first-unread dividers, independent thread cursors, unread-history analytics, push/mobile notifications and a new infinite-history pagination subsystem.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`. Final DONE requires executable backend/frontend/verifier evidence plus authenticated multi-user WorkOS root/thread/old-window/revocation UAT.
