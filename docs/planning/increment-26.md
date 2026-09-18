# Increment 26 — Live workspace updates

Story: `S-10.10.01`

Status: `IN_PROGRESS`

## Sprint goal

Make Brain conversations feel live without introducing a second authorization model or premature WebSocket infrastructure.

## Vertical slice

One authenticated user keeps Brain open while another user changes authorised collaboration state. Within five seconds on a visible tab, Brain detects the state revision and refreshes the server-rendered workspace. Channels, unread badges, DMs and Activity therefore update from the existing permission-aware APIs. An open thread refreshes through its existing same-origin reply route.

## Architecture

Use a stable server-side revision built from already-authorised API results. The revision includes only structural state needed to detect change: visible channel/access metadata, unread cursors, selected-channel message/reply/reaction affordances, visible DM conversation/message identifiers and Activity identifiers/read state.

The browser receives only `revision` and `unread_count`. It never receives the server access token through this path and never receives copied message/DM content from the live-state response.

Polling is adaptive: 4 seconds when visible, 30 seconds when hidden, exponential backoff up to 30 seconds after failures, and recovery on visibility/online events. `router.refresh()` runs only after a revision change.

## Rejected alternatives

- WebSockets now: requires connection infrastructure, cross-instance fan-out, lifecycle/observability and backpressure work before measured need.
- SSE now: still creates long-lived server connections and platform/runtime coupling while the backend source remains request/response APIs.
- Browser polling FastAPI directly: rejected because it would expose or require reusable bearer-token handling in client code.
- Persisted realtime event bus/table: rejected because the current source tables already own truth and the slice only needs invalidation.

## Security and privacy

All source data is loaded server-side with the current WorkOS access token and existing Brain authorization. The live response is content-free. Restricted-channel or DM access loss is reflected because the next server revision is computed from the newly authorised view.

## Acceptance truth

Repository implementation can reach `IN_REVIEW`. Final DONE requires executable frontend/test/verifier evidence and real authenticated two-user WorkOS browser UAT proving <=5 second visible-tab propagation, hidden/offline backoff, no refresh storm and revocation cleanup.
