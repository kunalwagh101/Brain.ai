# Increment 33 — First-Unread Divider & Jump to Unread

Story: `S-10.17.01`

Status: `IN_REVIEW`

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

## Retrospective — 2026-09-19

No accepted S-10.17.01 requirement was cut.

The implementation reused the existing monotonic `NativeChannelReadState.last_read_sequence` and exact message-read contract. A windowed unread query now returns both unread count and the exact first unread message ID for all visible channels without adding a per-channel query loop or another persistence model.

The main hidden complexity was lifecycle timing: the selected channel already marks itself read immediately and refreshes the server-rendered workspace. The permanent fix was to capture the initial first-unread boundary in the mounted channel panel and stop remounting that panel merely because the latest-message cursor changes. Persisted unread authority remains the existing monotonic server cursor.

A second edge case appeared during review: an unread thread reply can remain valid below a retracted root because S-10.12 intentionally preserves existing replies. Jump recovery therefore permits a tombstoned root while still refusing a retracted unread target itself.

Older targets outside the initial root window reuse the current permission-aware exact-message route and same-origin WorkOS BFF; no history cache, copied message content, new database table, Redis/WebSocket dependency or migration was added.

Estimate miss: supporting exact thread/old-window recovery safely required a read-only GET in the existing WorkOS message route plus explicit focus/accessibility handling, not only a visual divider.

The story is IN_REVIEW, not DONE. Focused backend tests, frontend source contracts/build, delivery verifier and authenticated WorkOS multi-user root/thread/old-window/revocation UAT must execute successfully before DONE/PASSED can be claimed.
