# Increment 28 — Author-safe Message Lifecycle

Story: `S-10.12.01`

Status: `IN_PROGRESS`

## Sprint goal

Allow a human author to correct or retract their own Brain-native channel message without silently rewriting evidence, widening authority or losing thread continuity.

## Vertical slice

A current channel writer edits their own message using an expected revision. Brain stores the prior body in append-only revision history, updates current conversation/search/mentions, increments revision and exposes “edited”. The author may retract the message; conversation becomes a content-free tombstone, Search/Activity/unread stop presenting the content, existing thread replies remain, and audit history retains hashes/revision metadata.

## Reuse

Use existing NativeMessage, SearchDocument, NativeMessageMention/Reaction, Activity references, SecurityAuditEvent, channel authorization, WorkOS BFF route helpers and S-10.10 live refresh. No new service or dependency.

## Explicit non-scope

No admin moderation override, no hard evidence deletion, no agent-message mutation, no DM edit/delete, no edit-time-window policy and no message restoration. Each changes authority/retention semantics and requires its own story.

## Acceptance truth

Repository implementation can reach `IN_REVIEW`. Final DONE requires executable migration/backend/frontend/verifier evidence and authenticated two-user WorkOS UAT for author/non-author/revocation/race/search/activity/thread behaviour.
