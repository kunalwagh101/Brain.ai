# Increment 30 — Ephemeral Presence & Typing

Story: `S-10.14.01`

Status: `IN_PROGRESS`

## Sprint goal

Make Brain channels and participant-only DMs feel live by showing current authorised online/typing state without creating durable employee activity history.

## Vertical slice

A signed-in user with a visible browser tab renews one short-lived organisation presence lease. Channel/DM composers refresh a short-lived typing lease only while non-empty text is being composed. Readers receive only current authorised users for the exact context. Hidden/offline clients stop renewing; expired rows are ignored/purged.

## Reuse

Reuse WorkOS server sessions, existing organisation membership, `can_read_channel`/`can_write_channel`, participant-only DM authorization, current same-origin BFF patterns and frontend polling patterns. Use PostgreSQL because it is already required. Do not introduce Redis, WebSockets, SSE, brokers or a second realtime store without measured need.

## Privacy boundary

Persist only IDs, context and lease expiry. Do not store draft text, keystrokes, cursor position, IP, user-agent, exact last-seen history or audit events for normal presence/typing.

## Explicit non-scope

No manual away/custom status, durable last-seen, group-DM presence, mobile push/background presence, organisation-wide people surveillance, typing analytics, WebSocket/SSE infrastructure or employee productivity scoring.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`. Final DONE requires focused backend expiry/revocation/concurrency tests, migration round-trip, frontend lint/build/source contracts, verifier and authenticated two-user WorkOS timing/privacy UAT.
