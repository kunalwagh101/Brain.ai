# Increment 38 — Thread Unread & Resume

Story: `S-10.22.01`

Status: `IN_PROGRESS`

## Sprint goal

Give each user an independent monotonic read boundary per opened thread, with root unread badges and exact first-unread resume.

## Vertical slice

Root messages expose personal thread unread metadata. Opening a thread captures the first-unread reply, then marks through the latest reply using a same-origin route. The pane shows one **New replies** divider and **Jump to unread** while the persisted cursor stays monotonic.

## Reuse

Existing NativeMessage sequence, channel authorization, S-10.17 first-unread pattern and S-10.21 reply pagination.

## Non-scope

Global Threads inbox, push notifications and unread-history analytics.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`; PostgreSQL/tests/verifier/authenticated UAT are required for DONE.
