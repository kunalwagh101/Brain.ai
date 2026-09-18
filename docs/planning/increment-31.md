# Increment 31 — Shared Channel Message Pins

Story: `S-10.15.01`

Status: `IN_PROGRESS`

## Sprint goal

Let authorised channel participants pin and reopen important channel messages or thread replies without duplicating message content or adding another search/index system.

## Vertical slice

A current channel writer pins/unpins a visible non-retracted message. Brain stores one lightweight channel/message reference. Current readers list pins through the existing safe message representation. Retracting a pinned message removes the pin in the same lifecycle transaction. Selected-channel live refresh reacts to pin-set changes.

## Reuse

Reuse NativeMessage identity, current channel reader/writer permission checks, existing message read materialisation, same-origin WorkOS BFF patterns, open-thread APIs and S-10.10 live revision. No copied message body, no second search index, no pin-specific content store.

## Explicit non-scope

No personal save-for-later/starred inbox, arbitrary URL/channel bookmarks, custom pin roles, pin notifications or pin ranking beyond newest-pin-first.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`. Final DONE requires PostgreSQL migration round-trip, focused pin/idempotency/revocation/retraction tests, frontend lint/build/source contracts, verifier and authenticated multi-user WorkOS pin/revoke/thread UAT.
