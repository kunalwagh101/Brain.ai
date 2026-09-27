# Increment 35 — Conversation History Pagination

Story: `S-10.19.01`

Status: `IN_REVIEW`

## Sprint goal

Make long-running native channels and participant-only DMs browsable beyond the initial message window using stable sequence cursors.

## Vertical slice

Both conversation surfaces expose **Load older**. The browser sends the oldest rendered message sequence as `before_sequence`, receives one bounded chronological page, merges without duplicates, and disables the control when history is exhausted. Current authorization and DM visibility floors are rechecked on every page.

## Reuse

Reuse existing channel/DM sequence columns, current list services, same-origin WorkOS routes, exact message IDs and current panel state. No OFFSET, no new database objects, no second history store and no infinite-scroll dependency.

## Explicit non-scope

Thread-reply pagination, automatic intersection-observer infinite scrolling and DOM virtualisation.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`. DONE requires executable backend/frontend/verifier checks and authenticated long-history/revocation UAT.

## Retrospective — 2026-09-19

No accepted S-10.19.01 requirement was cut.

Stable monotonic sequence columns already existed on both message models, so the correct solution was to expose them and add `before_sequence` rather than add timestamp cursors, OFFSET scans or another paging store.

The client keeps a separate contiguous-history cursor. This matters because an exact deep-link/unread target can be injected from much older history; using that isolated target as the next page cursor would skip the gap between it and the recent window.

Loaded pages merge by ID and sequence. Native live refresh now merges current server messages into local history instead of replacing the entire root list, preserving older pages and current interaction state.

Estimate miss: preserving previously loaded pages across live refresh was the main client-state issue; the backend cursor work itself was small.

Thread-reply pagination, automatic infinite scrolling and virtualised rendering remain explicit later scope.

The story is IN_REVIEW, not DONE. Focused backend/frontend/verifier execution and authenticated long-history/revocation UAT remain required.
