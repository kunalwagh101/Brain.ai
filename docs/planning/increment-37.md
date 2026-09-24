# Increment 37 — Thread History Pagination

Story: `S-10.21.01`

Status: `IN_REVIEW`

## Sprint goal

Let users browse older replies in long native threads without losing live state, composer state or permission safety.

## Vertical slice

The existing thread GET accepts a stable `before_sequence`; the thread pane exposes **Load older replies**, merges pages by ID/sequence and keeps live refresh additive rather than destructive.

## Reuse

Existing `NativeMessage.message_sequence`, exact root authorization, WorkOS reply route and S-10.19 cursor pattern. No schema, OFFSET or new history store.

## Non-scope

Independent thread unread state belongs to S-10.22. Automatic virtualised infinite scroll remains separate optimisation.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`; executable checks and authenticated UAT are still required for DONE.

## Retrospective — 2026-09-20

No accepted requirement was cut. The backend was a direct extension of S-10.19, but the important client fix was making live refresh additive so loaded older replies are not silently lost. A lifecycle conflict was caught before shipping: retracted roots with historical replies must stay addressable under S-10.12, so only hidden/revoked access fails closed. No migration was needed. The story remains IN_REVIEW pending executable checks and authenticated UAT.
