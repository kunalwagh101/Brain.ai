# Increment 39 — Participant-Private DM Reactions

Story: `S-10.23.01`

Status: `IN_PROGRESS`

## Sprint goal

Let current DM participants acknowledge visible private messages with five bounded reactions while preserving OQ-008 privacy.

## Vertical slice

A participant adds/removes an allow-listed reaction. The DM read model returns only aggregate count and reacted-by-me state. The mutation is idempotent, current-epoch scoped, retraction/retention-safe and never projected into organisation-wide intelligence/audit.

## Reuse

Existing channel reaction allowlist/UX, DM participant/visibility-epoch authorization, WorkOS same-origin patterns and private-message cascade retention.

## Non-scope

Reaction participant lists, arbitrary emoji, reaction notifications, organisation Activity entries and moderation override.

## Acceptance truth

Repository implementation may reach `IN_REVIEW`; migration/tests/verifier/authenticated UAT are required for DONE.
