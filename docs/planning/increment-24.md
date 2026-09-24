# Increment 24 — Slack/Discord-quality Brain channel conversations

## Sprint goal

Make one Brain-native channel usable as the daily communication surface: open the channel as the primary workspace, reply in threads, mention exact permitted members, react idempotently, and see personal unread state without leaking restricted content.

## Vertical slice

S-10.06.01 is one user-visible path across schema, service, API, secure same-origin frontend boundary and responsive UI. It reuses S-10.01 native messages, permissions, evidence projection and channel membership. No second chat store or client-side permission model is introduced.

## Measurable success

- Zero cross-tenant or revoked-access disclosures across channel, root, reply, reaction, mention and read-state tests.
- Thread replies belong to exactly one root in the same channel.
- Mentions resolve only exact active member email addresses that can currently read the channel.
- Reaction writes are allow-listed, per-user unique and idempotent.
- Unread counts are per user, exclude the caller's own messages, and never move backwards after a late read request.
- The selected channel becomes the main work surface; unread badges, thread context, agent labels, errors, empty states, focus states and responsive behaviour are inspectable.
- No reusable backend/WorkOS token enters browser code.

## AI decision

AI is not needed for this slice. Threads, mentions, reactions and unread state are deterministic collaboration rules. Using an LLM would add cost, latency and unsafe identity guessing with no product benefit.

## Baseline

The existing S-10.01 surface provides flat persisted messages, restricted-channel membership and visible agent attribution. It has no thread relationship, mention record, reaction state, per-user read cursor or focused channel-first layout. The baseline success rate for those four affordances is therefore 0/4.

## Data and privacy assessment

Conversation bodies remain in the existing NativeMessage and evidence pipeline. New rows store only relationship state: message IDs, exact resolved user IDs, an allow-listed reaction and a monotonic numeric read sequence. There is no fuzzy name matching, cross-tenant lookup, outbound notification body, new model training data or analytics score.

## Scope

- PostgreSQL schema and reversible Alembic migration for thread links, mentions, reactions and per-user read cursors.
- Permission-aware service and API contracts.
- Secure WorkOS BFF templates with bounded JSON and safe errors.
- Channel-first workspace layout, thread pane, reactions, mention rendering/guidance and unread badges.
- Backend security/idempotency tests, frontend source-contract tests and manual UAT.

## Explicitly not in this increment

- Direct messages: S-10.06.02.
- Voice/video calls, typing presence, emoji picker, file attachments inside the composer, message editing/deletion and external push/email notifications.
- Fuzzy @name matching or AI-based identity resolution.
- New WebSocket infrastructure. Server rendering plus refresh is retained until measured live-presence needs justify SSE/WebSockets.

## Dependencies and acceptance truth

S-10.01 repository implementation is the upstream code foundation and is in review. Final DONE still requires an executable backend/migration run and S-10.04 authenticated WorkOS browser UAT. Until those gates pass, S-10.06.01 may advance only to IN_REVIEW.

## Retrospective — 2026-09-13

No accepted S-10.06.01 scope was cut. Direct messages, voice/video, presence, editing/deletion, attachments and push notifications were already explicit later-stage or out-of-scope work and remain visible in the backlog/planning record.

The estimate understated integration repair. The staged baseline did not import cleanly, reused a request-specific audit value under a semantic idempotency key, used a timestamp/random-UUID unread cursor, lacked the actual thread/reaction/read WorkOS routes and rendered only a flat feed. The L size was still appropriate, but more of it belonged to correctness and secure integration than visual styling.

What worked: reusing NativeMessage, current channel permissions, evidence projection and the existing server-session BFF boundary avoided a second chat store or client-side authorization model. The permanent unread fix is an atomic per-channel sequence, not a timing delay.

Next-process change: create and inspect the Ready record before a story is pulled. Compile the staged backend and enumerate every browser endpoint during refinement so missing route/decorator drift is found before `IN_PROGRESS`.

The final delivery-verifier run was not completed after its dynamic test execution was stopped by the environment safety layer and the product owner directed work to move forward without it. This was not converted into a PASS. S-10.06.01 stays `IN_REVIEW`, and the verifier remains an explicit acceptance gate.
