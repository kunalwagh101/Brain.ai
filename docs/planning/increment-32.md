# Increment 32 — Personal Saved Messages

Story: `S-10.16.01`

Status: `IN_PROGRESS`

## Sprint goal

Let each user privately save and reopen authorised Brain channel messages/thread replies without changing shared channel state or copying message content.

## Vertical slice

A current channel reader saves/unsaves a visible non-retracted message. Brain stores one private organisation/user/message reference. The signed-in user's Saved surface materialises current message content through the existing safe read model and exact S-10.11 deep links. Retracting a message removes all saved references in the same lifecycle transaction.

## Reuse

Reuse NativeMessage identity, current channel visibility checks, existing message read materialisation, exact channel/message links, same-origin WorkOS BFF patterns and S-10.12 lifecycle transaction. No copied message body, no second content store and no personal search index.

## Explicit non-scope

DM saves, reminders/due dates, notes on saved items, bulk actions and automatic task creation.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`. Final DONE requires PostgreSQL migration round-trip, focused privacy/idempotency/revocation/retraction tests, frontend lint/build/source contracts, verifier and authenticated multi-user WorkOS Saved UAT.
