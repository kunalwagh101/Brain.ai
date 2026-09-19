# Increment 35 — Conversation History Pagination

Story: `S-10.19.01`

Status: `IN_PROGRESS`

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
