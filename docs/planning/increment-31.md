# Increment 31 — Shared Channel Message Pins

Story: `S-10.15.01`

Status: `IN_REVIEW`

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


## Retrospective — 2026-09-19

No accepted S-10.15.01 requirement was cut.

The implementation stayed deliberately reference-only: `NativeMessagePin` stores organisation/channel/message identity plus who pinned and when; message body, attachments, evidence and revision content remain in their existing stores and are materialised through the existing safe message read path.

The main correctness work was not the Pin button:

- current channel read/write permissions remain authoritative on every list/mutation;
- the composite message-scope foreign key prevents cross-tenant/cross-channel pin corruption below the service layer;
- unique channel/message storage plus IntegrityError recovery makes repeated/concurrent pin requests converge to one row;
- explicit application timestamps preserve newest-pin-first ordering across database timestamp precision differences;
- edits preserve pins because message identity stays stable;
- retraction removes the pin inside the same lifecycle transaction before commit, preventing tombstone pointers;
- agent-authored messages remain pinnable because pinning changes shared channel metadata, while the existing human edit/retract actor restriction remains untouched;
- server-rendered initial pins and structural S-10.10 live revision reuse avoid a second client polling/index system;
- older pinned roots and pinned replies reopen through existing exact message/thread routes rather than adding a new navigation backend.

Estimate miss: cross-context navigation and live-refresh consistency mattered more than persistence itself.

Personal save-for-later/starred items, arbitrary channel bookmarks and custom pin permissions were not absorbed into this story.

The story is IN_REVIEW, not DONE. PostgreSQL migration round-trip, focused backend tests, frontend lint/build/source contracts, verifier and authenticated multi-user WorkOS pin/revoke/retract/thread UAT remain required.
