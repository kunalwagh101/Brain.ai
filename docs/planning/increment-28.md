# Increment 28 — Author-safe Message Lifecycle

Story: `S-10.12.01`

Status: `IN_REVIEW`

## Sprint goal

Allow a human author to correct or retract their own Brain-native channel message without silently rewriting evidence, widening authority or losing thread continuity.

## Vertical slice

A current channel writer edits their own message using an expected revision. Brain stores the prior body plus its prior RawEvent/CanonicalEvent IDs in append-only revision history, appends a new immutable lifecycle RawEvent + CanonicalEvent, retires the previous SearchDocument version, updates current conversation/search/mentions, increments revision and exposes “edited”. Retraction appends its own immutable lifecycle event; conversation becomes a content-free tombstone, all SearchDocument versions are retired, Activity/unread stop presenting the content, existing thread replies remain, and audit history retains hashes/revision metadata.

## Reuse

Use existing NativeMessage, SearchDocument, NativeMessageMention/Reaction, Activity references, SecurityAuditEvent, channel authorization, WorkOS BFF route helpers and S-10.10 live refresh. No new service or dependency.

## Explicit non-scope

No admin moderation override, no hard evidence deletion, no agent-message mutation, no DM edit/delete, no edit-time-window policy and no message restoration. Each changes authority/retention semantics and requires its own story.

## Acceptance truth

Repository implementation can reach `IN_REVIEW`. Final DONE requires executable migration/backend/frontend/verifier evidence and authenticated two-user WorkOS UAT for author/non-author/revocation/race/search/activity/thread behaviour.


## Retrospective — 2026-09-18

No accepted S-10.12 requirement was cut.

The first implementation correctly protected author ownership, stale writes, Search visibility and tombstones, but a deeper provenance review found that mutating the existing SearchDocument body would make edited text cite the original CanonicalEvent. That was rejected before review. The final design appends a new RawEvent + CanonicalEvent for every lifecycle revision and retires derived Search versions instead of rewriting immutable evidence.

A second security issue appeared from that design: restricted-channel history grants originally covered only each message's current canonical node. Historical revision evidence is now included in the channel evidence scope, so access changes apply across the full revision chain.

Historical revision plaintext is governed by the existing derived-content retention period and legal hold rather than becoming an unbounded hidden store.

Estimate miss: the user-visible edit/retract UI was small; evidence-versioning, access-history and retention correctness were the real work. This is why the story remains IN_REVIEW until executable migrations/tests/frontend/verifier and authenticated WorkOS UAT actually run.
