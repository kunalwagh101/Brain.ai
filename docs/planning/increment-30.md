# Increment 30 — Ephemeral Presence & Typing

Story: `S-10.14.01`

Status: `IN_REVIEW`

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


## Retrospective — 2026-09-19

No accepted S-10.14.01 requirement was cut.

The visible online dot/typing label was the smallest part. The important work was preventing transient collaboration state from becoming surveillance or an unnecessary realtime subsystem:

- one lease row is refreshed in place rather than appending presence/typing history;
- normal heartbeat/typing traffic bypasses organisation-wide audit-event persistence while still enforcing current membership and exact channel/DM authorization;
- restricted-channel reads batch current membership checks instead of producing per-user N+1 queries;
- participant-only DM presence preserves the existing S-10.06.02 privacy boundary, including no Owner/Admin override;
- polling is read-only and sleeps completely while hidden/offline; normal low-frequency writes own stale-row cleanup;
- browser typing is boolean lease refresh only, never draft text or keystroke payload, and remains throttled at three seconds;
- PostgreSQL scoped foreign keys make cross-tenant/context corruption impossible below the service layer;
- existing WorkOS and PostgreSQL architecture was sufficient, so Redis/WebSockets/SSE were rejected until measured scale requires them.

Estimate miss: privacy/audit semantics and permission-safe data modelling were more important than the UI.

The story is IN_REVIEW, not DONE. Executable PostgreSQL migration, backend tests, frontend lint/build/source contracts, verifier and authenticated WorkOS timing/privacy UAT remain required.
