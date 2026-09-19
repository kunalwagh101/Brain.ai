# Increment 32 — Personal Saved Messages

Story: `S-10.16.01`

Status: `IN_REVIEW`

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


## Retrospective — 2026-09-19

No accepted S-10.16.01 requirement was cut.

The implementation stayed reference-only: `NativeMessageSave` stores organisation/channel/message identity, saving user and timestamp. Message body, attachments, evidence and revision content remain in their existing stores and are materialised only through current permission-aware reads.

The main engineering risks were privacy and permission semantics rather than UI:

- Save/Unsave requires current read visibility, not channel write permission, because it changes only personal state;
- saved rows are bound by database foreign keys to both organisation membership and exact organisation/channel/message scope;
- repeated/concurrent saves converge through unique user/message storage plus IntegrityError recovery;
- restricted-channel revocation hides saved content immediately while preserving the content-free personal reference for possible later regrant;
- organisation membership removal cascades saved references through the membership foreign key;
- message edits preserve saved identity while retraction deletes every save for that message before lifecycle commit;
- agent-authored messages remain saveable without weakening the existing human edit/retract actor boundary;
- there is no user selector in the Saved API, so Owner/Admin/Executive roles cannot request another user's Saved state;
- normal Saved list/save/unsave traffic deliberately bypasses organisation-wide authorization audit persistence to avoid creating employee behavioural history;
- server-rendered Saved items reuse the S-10.11 exact channel/message deep link, including thread replies, instead of adding another router/search subsystem.

Estimate miss: avoiding indirect audit-history leakage required a separate backend/BFF authority path even though the persistence model itself was small.

DM saves, reminders, notes, bulk actions and automatic task creation remain explicit later scope.

The story is IN_REVIEW, not DONE. PostgreSQL migration round-trip, focused backend tests, frontend lint/build/source contracts, verifier and authenticated multi-user WorkOS Saved UAT remain required.
