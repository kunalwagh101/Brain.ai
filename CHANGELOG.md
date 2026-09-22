# Changelog

### Engineering acceptance — S-10.01.01 / S-10.06.01 / S-10.06.02

- Marked Brain-native channels/messages, Slack/Discord-quality conversation UX and participant-safe direct messages engineering-DONE after the current executable gates resolved the older review-only state.
- Release Gate `35789299001` passed Ruff, all 385 backend tests, the production frontend build, 138 source-contract tests, repository verification, PostgreSQL upgrade/downgrade/forward recovery, backup/restore, production-image build and readiness smoke on code head `10a9028685f67ec6db923d3371a67df13276d044`.
- The DM suite includes participant-only access, revocable visibility epochs, retention/legal-hold behavior and the organisation-wide Search exclusion regression for DM-only content.
- Official WorkOS activation and authenticated multi-user browser/privacy/responsive/accessibility UAT remain `UAT_PENDING`; engineering-DONE is not an external acceptance claim.

### Engineering acceptance — S-05.01.01 / S-06.01.01 / S-09.02.01

- Marked S-05.01.01 permission-aware Search engineering-DONE after current authorisation, revocation/deletion, provenance and retrieval-evaluation contracts resolved against the implementation.
- Marked S-06.01.01 AI Provider Registry & Gateway engineering-DONE after provider/model/user/organisation attribution, safe provider failure and secret-reference contracts resolved.
- Marked S-09.02.01 Audit, Retention & Deletion engineering-DONE after append-only audit, legal-hold, deterministic retention/deletion and reconstruction-suppression contracts resolved.
- Fresh Backend CI rerun on the underlying code commit `af9358c5f6d20079160c7fa77c4d771772d54703`: Ruff passed; `384 passed, 2 warnings in 34.25s`.
- The same code commit's Release Gate passed PostgreSQL migration upgrade/downgrade/forward recovery, backup/restore, production-image build and readiness smoke.
- Realistic deployed/browser/provider/customer-policy acceptance remains `UAT_PENDING`; engineering-DONE is not a claim of external feature acceptance.


### Increment 42 — Channel Administration

- Added optimistic `settings_revision` for Brain-native channel settings/lifecycle mutations.
- Channel creator or Owner/Admin can rename/update description; current Work Graph track identity follows the new name/slug without rewriting historical message/evidence records.
- Added archive/restore lifecycle: archived channels leave the default active navigation and become non-postable while authorised history remains readable.
- Added manager-only Archived channels restore surface.
- Reused the existing restricted-channel member PUT path for Read ↔ Read & write changes so membership and current Work Graph/evidence ResourceGrants stay consistent.
- Channel visibility conversion is explicitly rejected; organisation↔restricted migration remains separate scope.
- Added same-origin WorkOS settings/archive/restore activation routes plus bounded BFF validation.
- Added migration `20260920_0040`, backend authority/concurrency/archive/grant regressions, frontend/security source contracts and dedicated UAT.
- Hardened channel settings/lifecycle and restricted-member access so the business mutation and required audit event commit atomically; an audit persistence failure now rolls back the channel/member/grant change, with explicit negative regressions.

Engineering verification passed on code commit `ed0c701685ad` via Release Gate `35786803759`: 385 backend tests passed, frontend production build passed with 138/139 source-contract tests passing and 1 skipped, repository verifier passed, PostgreSQL migration round-trip and backup/restore passed, and production readiness smoke passed. Authenticated WorkOS UAT remains `UAT_PENDING`.

### Increment 41 — Team Channel Groups

- Added revisioned `NativeChannelGroup` metadata scoped to a Team.
- Added nullable `team_id` / `channel_group_id` navigation references to native channels with tenant/team/group database constraints.
- Channel placement requires existing channel-manager authority plus target-Team-manager authority.
- Channel placement deliberately does not call membership/grant/evidence authorization helpers.
- Added nested Team → Group → Channel sidebar composition from the existing permission-filtered channel list.
- Archived group channels fall back to Team **Ungrouped**; archived-Team channels fall back to global **Unassigned channels**.
- DMs remain a separate participant-private section under OQ-010.
- Added migration `20260920_0039`, same-origin WorkOS group/assignment routes, management UI and ACL-invariance/tenant/stale-revision contracts.
- Hardened group lifecycle and channel-placement mutations so navigation changes cannot persist if their audit event fails.

Engineering verification passed on code commit `ed0c701685ad` via Release Gate `35786803759`: 385 backend tests passed, frontend production build passed with 138/139 source-contract tests passing and 1 skipped, repository verifier passed, PostgreSQL migration round-trip and backup/restore passed, and production readiness smoke passed. Authenticated WorkOS UAT remains `UAT_PENDING`.


### Increment 40 — Workspace Teams

- Added organisation-scoped `NativeTeam` metadata with stable UUID/slug, description, active/archive lifecycle and optimistic revision.
- Added creator or Owner/Admin Team management while creation reuses the current native-chat writer role boundary.
- Added content-free Team lifecycle audit events.
- Added migration `20260920_0038` and registered the model in Alembic's explicit metadata imports.
- Added server-side Team loading and a shared workspace Team manager.
- Existing visible channels remain under **Unassigned channels** until explicit group/channel navigation is introduced by S-10.25.
- OQ-009 prevents Team metadata from inheriting/replacing channel ACLs; OQ-010 keeps participant-private DMs outside shared Team hierarchy.
- Added same-origin WorkOS create/edit/archive/restore templates plus tenant, stale-revision, guest/manager and ResourceGrant-invariance contracts.
- Hardened Team lifecycle mutations so Team state and its required audit event are one transaction; audit failure rolls the Team change back, with a dedicated regression.

Engineering verification passed on code commit `ed0c701685ad` via Release Gate `35786803759`: 385 backend tests passed, frontend production build passed with 138/139 source-contract tests passing and 1 skipped, repository verifier passed, PostgreSQL migration round-trip and backup/restore passed, and production readiness smoke passed. Authenticated WorkOS UAT remains `UAT_PENDING`.


### Increment 39 — Participant-Private DM Reactions

- Added private `DirectMessageReaction` rows with the same five-value allowlist as native channel reactions.
- Reaction mutation reuses current participant/current visibility-epoch DM authorization and rejects retracted messages.
- Adds are idempotent with uniqueness-race recovery; removals are idempotent.
- DM message reads batch aggregate reaction counts and personal reacted-by-me state; reaction participant identities are never returned.
- Added same-origin WorkOS PUT/DELETE route and accessible aria-pressed private reaction buttons.
- Normal private reaction changes deliberately create no RawEvent, CanonicalEvent, SearchDocument, Work Graph/Activity or organisation-wide per-message audit projection.
- Message retraction and private-message retention cascade reaction rows; legal hold continues protecting the underlying private message.
- Added migration `20260920_0037`, privacy/idempotency/epoch/retention regressions and frontend/security contracts.

Verification is not claimed as passed. `S-10.23.01` remains `IN_REVIEW`.


### Increment 38 — Thread Unread & Resume

- Added per-user/per-root `NativeThreadReadState` separate from channel read state.
- Added tenant-scoped set-based thread unread/latest/first-unread summaries; current-user and retracted replies do not count.
- Added monotonic cross-root-safe thread mark-read service and same-origin WorkOS route.
- Root reply actions now show personal thread unread counts.
- Thread open captures its first unread reply, persists progress through the latest reply, and preserves one accessible **New replies** divider plus **Jump to unread**.
- Exact first-unread recovery reuses the permission-aware message read path and validates reply ownership by root.
- Added migration `20260920_0036`, regressions, frontend/security contracts and UAT/demo/traceability.

Verification is not claimed as passed. `S-10.22.01` remains `IN_REVIEW`.


### Increment 37 — Thread History Pagination

- Added stable positive `before_sequence` pagination to native thread replies using the existing per-channel message sequence.
- Added bounded same-origin WorkOS reply GET parameters and BFF validation.
- Added **Load older replies** to the thread pane with merge-by-ID/sequence history state.
- Changed live reply refresh to merge recent state instead of discarding older pages already loaded by the user.
- Preserved S-10.12 retracted-root semantics: historical replies remain readable under the tombstone root, but new replies remain disabled.
- Added backend cursor regression, frontend/security contract, UAT/demo/traceability. No migration was required.

Verification is not claimed as passed. `S-10.21.01` remains `IN_REVIEW`.


### Increment 36 — Direct-Message Lifecycle

- Added monotonic DM message revisions, edited/retracted timestamps and append-only participant-private `DirectMessageRevision` snapshots.
- Edit/retract authority is original-author + current participant visibility epoch only; Owner/Admin/Executive role provides no private-content override.
- Added expected-revision optimistic concurrency so stale clients cannot overwrite a newer private edit.
- Retracted DMs serialize as body/hash-free participant tombstones and are removed from unread/latest/first-unread attention state.
- Deliberately created no RawEvent, CanonicalEvent, SearchDocument, Work Graph or organisation-wide per-message audit projection for private lifecycle changes.
- Private revision rows cascade with their message under the existing `private_message_days` retention path; legal hold remains authoritative.
- Added bounded same-origin WorkOS PATCH/DELETE handling plus accessible author-only Edit/Retract confirmation UI.
- Added migration `20260919_0035`, privacy/concurrency/epoch/retention regressions, frontend/security contracts, UAT/demo/traceability.

Verification is not claimed as passed. `S-10.20.01` remains `IN_REVIEW` pending PostgreSQL migration round-trip, executable backend/frontend/verifier evidence and authenticated WorkOS lifecycle UAT.


### Increment 35 — Conversation History Pagination

- Added positive stable `before_sequence` pagination to native-channel root history and participant-only DM history.
- Kept every page on existing permission checks; DM pages always reapply the participant's current visibility floor.
- Bounded browser/backend page sizes and deliberately avoided SQL OFFSET pagination.
- Added server-session GET handling on existing WorkOS channel/DM message routes.
- Added accessible **Load older messages** controls that merge by message ID, sort by sequence, preserve composer/unread context and stop after history exhaustion.
- Changed native-channel refresh merging so loaded historical pages are not discarded by normal live/server refresh.
- Added backend cursor/no-duplicate tests, frontend/security source contracts, UAT/demo/traceability. No schema migration was required.

Verification is not claimed as passed. `S-10.19.01` remains `IN_REVIEW` pending executable backend/frontend/verifier checks and authenticated long-history/revocation UAT.


### Increment 34 — DM Unread & Resume

- Added one monotonic last-read sequence per participant to the existing 1:1 DM conversation aggregate; no generic employer-visible read-history table was introduced.
- Reactivation resets only the restored participant's cursor to immediately before the new visibility floor, preventing old private history from returning as unread.
- Added set-based DM unread/latest/first-unread summaries that exclude the current user's own messages.
- Added exact participant-only DM message reads plus monotonic mark-read API/BFF routes.
- Added unread badges in both workspace and DM navigation, one accessible New messages divider, and Jump to unread with exact-message recovery for targets outside the initial window.
- Kept normal DM unread/read activity out of organisation-wide SecurityAuditEvent history and outside Search/Ask Brain/Work Graph.
- Added migration `20260919_0034`, epoch/revocation/monotonic backend regressions, frontend/security contracts, UAT, demo and traceability.

Verification is not claimed as passed. `S-10.18.01` remains `IN_REVIEW` pending PostgreSQL migration round-trip, executable backend/frontend/verifier evidence and authenticated WorkOS UAT.


### Increment 33 — First-Unread Divider & Jump to Unread

- Extended the existing per-user native-channel unread summary with an exact `first_unread_message_id`; no second unread table, cache or migration was introduced.
- Kept unread calculation set-based across visible channels by using a windowed count + sequence rank, avoiding per-channel N+1 queries.
- Preserved existing semantics: the current user's own human-authored messages and retracted messages do not become unread targets.
- Added a same-origin WorkOS GET to the existing exact permission-aware message route so older roots and thread replies can be recovered without exposing a browser bearer token or creating another content store.
- Added one accessible **New messages** divider plus **Jump to unread** for native channels, including exact thread opening and focus/scroll behaviour.
- Preserved the captured first-unread boundary during the existing immediate mark-read/router refresh without changing the authoritative monotonic server read cursor.
- Supported valid unread replies under retracted thread roots while clearing a stale boundary when the unread target itself is retracted.
- Added backend root/thread/retraction regressions, a frontend/query/security source contract, Increment 33 planning, UAT, demo and traceability artifacts.
- Direct-message first-unread state, independent thread cursors, unread-history analytics, push notifications and a new pagination subsystem remain explicit later scope.

Verification is not claimed as passed. `S-10.17.01` remains `IN_REVIEW` pending focused backend/frontend execution, delivery verifier and authenticated WorkOS multi-user root/thread/old-window/revocation UAT.


## Unreleased

### Increment 32 — Personal Saved Messages

- Added private reference-only saved channel messages with organisation membership and exact organisation/channel/message database scoping.
- Saved rows store only user/message identity and timestamp; no message body, attachment, evidence excerpt or revision content is copied.
- Current channel readers, including read-only members and guests with normal resource-read access, may Save/Unsave visible non-retracted roots or thread replies without changing shared channel state.
- Saved list is derived only from the authenticated user; there is no user selector or privileged Owner/Admin/Executive override.
- Restricted-channel revocation immediately hides inaccessible saved content while preserving the content-free personal row for later regrant; organisation membership removal cascades the row.
- Added retry-safe unique user/message convergence and explicit high-precision save timestamps.
- Message edits preserve saved identity; message retraction removes all saves for that message in the same lifecycle transaction.
- Visible agent-authored messages may be saved without changing existing human edit/retract authority.
- Added audit-free Saved list/save/unsave backend/BFF authority path so ordinary personal follow-up activity does not become organisation-wide SecurityAuditEvent history.
- Added typed API/BFF helpers, WorkOS list/save/unsave routes, personal Saved navigation/panel and Save/Unsave actions on channel roots/replies.
- Saved links reuse the existing exact S-10.11 channel/message deep-link and thread reopening flow.
- Added migration `20260919_0033`, focused backend privacy/idempotency/revocation/retraction regressions, source contracts, UAT, demo and traceability.
- DM saves, reminders, notes, bulk actions and automatic task creation remain explicit later scope.

Verification is not claimed as passed. `S-10.16.01` remains `IN_REVIEW` pending executable PostgreSQL migration round-trip, Ruff/Pytest, frontend lint/build/source contracts, delivery verifier and authenticated WorkOS multi-user Saved UAT.



### Increment 31 — Shared Channel Message Pins

- Added reference-only shared channel message pins with organisation/channel/message scoped foreign keys; pin rows never copy message body, attachment or evidence content.
- Current channel readers may list pins; current channel writers may pin/unpin visible non-retracted roots or replies, including agent-authored messages, without changing message authorship authority.
- Added unique channel/message convergence and IntegrityError recovery so repeated/concurrent pin requests remain idempotent.
- Added explicit high-precision pin timestamps and newest-pin-first ordering.
- Message edits preserve pins; message retraction removes active pins in the same lifecycle transaction before commit.
- Added bounded pin-list and pin/unpin FastAPI routes, typed Brain API/BFF helpers and same-origin WorkOS route templates.
- Selected-channel pins now load server-side and contribute only pin ID/message ID/timestamp to S-10.10 live revision.
- Added accessible channel Pins panel, Pin/Unpin message actions, older-root reopening and exact thread-reply reopening using existing conversation routes.
- Added migration `20260919_0032`, focused backend permission/idempotency/revocation/retraction regressions, agent-authority source contract, frontend/live contracts, UAT, demo and traceability.
- Personal save-for-later/starred messages, arbitrary channel bookmarks and custom pin permission roles remain explicit later scope.

Verification is not claimed as passed. `S-10.15.01` remains `IN_REVIEW` pending executable PostgreSQL migration round-trip, Ruff/Pytest, frontend lint/build/source contracts, delivery verifier and authenticated WorkOS multi-user pin/revoke/retract/thread UAT.



### Increment 30 — Ephemeral Presence & Typing

- Added short-lived collaboration presence leases with one row per organisation/user and no durable last-seen event history.
- Added exact-context typing leases for either a native channel or participant-only 1:1 DM, enforced by scoped foreign keys and an exactly-one-context database check.
- Presence renews for 75 seconds; typing renews for 8 seconds. Polling ignores expired rows without writing, while normal heartbeat/typing writes opportunistically purge stale leases.
- Restricted-channel presence and typing recheck current membership; revoked users disappear without waiting for lease cleanup.
- DM presence/typing remains participant-only. Owner/Admin role alone cannot observe another pair's private collaboration state.
- Normal presence/typing API traffic deliberately bypasses organisation-wide authorization/audit event persistence so the feature cannot become behavioural history by accident.
- Added a small bounded FastAPI surface plus same-origin WorkOS heartbeat/context/typing routes; browser code receives no reusable bearer token.
- Added a visible-tab 30-second heartbeat and shared 3-second presence/typing hook; typing is emitted only for focused non-empty composers and is best-effort cleared on stop/hide/unmount.
- Added channel online counts, accessible typing status, and participant-only DM Online/Offline + typing indicators without exposing exact last-seen timestamps.
- Added migration `20260919_0031`, expiry/concurrency/revocation/guest/no-audit backend regressions, frontend privacy contracts, UAT, demo and traceability.

Verification is not claimed as passed. `S-10.14.01` remains `IN_REVIEW` pending executable PostgreSQL migration round-trip, Ruff/Pytest, frontend lint/build/source contracts, delivery verifier and authenticated WorkOS two-user timing/privacy UAT.



### Increment 29 — Governed Channel Attachments

- Connected native channel/root/thread messages to the existing governed EvidenceSource ingestion pipeline instead of introducing another file store.
- Added nullable native-channel evidence scope plus lightweight message-to-evidence references; file bytes/extracted text remain only in the existing evidence system.
- Added migration `20260918_0030` with organisation-scoped composite foreign keys for channel evidence and message attachments, max-compatible zero-length message body state for file-only messages, and an explicit unsafe-downgrade guard.
- Restricted channel attachments now use live channel membership for direct Evidence visibility and extend/remove Work Graph/Search grants through the existing channel evidence scope.
- Bound evidence-upload idempotency to visibility + native-channel scope so one key cannot replay a file into a different access context.
- Added max-five attachment validation, same-tenant/exact-channel checks, duplicate source de-duplication, active-source checks, and idempotent message retry mismatch protection.
- Added bounded <=10 MB same-origin WorkOS multipart upload for existing supported document/transcript types.
- Added safe attachment cards and separate root/thread composer state, including file-only messages, partial-upload preservation, payload-bound send retry idempotency and in-flight navigation race guards.
- Message retraction hides attachment cards without deleting governed evidence; separate evidence deletion leaves only safe unavailable/deleted attachment metadata.
- Extended S-10.10 live revision with attachment source ID/status/availability only so evidence lifecycle changes refresh the channel without exposing file names/content.
- Added backend restricted-member/tenant/channel/deletion/idempotency regressions, frontend source contracts, UAT, demo and traceability artifacts.

Verification is not claimed as passed. `S-10.13.01` remains `IN_REVIEW` pending executable PostgreSQL migration round-trip, Ruff/Pytest, frontend lint/build/source contracts, delivery verifier and authenticated WorkOS multi-user browser UAT.



### Increment 28 — Author-safe Message Lifecycle

- Added original-author-only edit and retract controls for Brain-native channel messages and thread replies; organisation role alone never grants content override.
- Added monotonic message revisions and expected-revision conflict checks so stale clients cannot overwrite unseen edits.
- Added append-only `NativeMessageRevision` snapshots carrying the prior body/hash and prior RawEvent/CanonicalEvent IDs.
- Each accepted edit/retraction now appends a new immutable Brain-native RawEvent + CanonicalEvent lifecycle revision instead of rewriting the original evidence.
- Brain-native Search now treats lifecycle revisions as versioned objects: prior SearchDocument versions are retired; edited content resolves to the new canonical revision; retraction leaves all versions non-searchable.
- Added body-free retraction tombstones, preserved existing thread replies, and blocked new replies/reactions/edits against retracted messages.
- Reconciled mentions on edit, hid removed/retracted message Activity, and excluded retracted messages from unread/channel-activity calculations.
- Extended restricted-channel evidence scope to include historical message revisions so membership changes apply across the full canonical revision chain.
- Added governed retention for historical message-revision plaintext under existing `derived_content_days` and legal hold, with explicit retention-run counts.
- Added same-origin WorkOS lifecycle routes, strict BFF validation, accessible inline edit/retract UI, live-refresh lifecycle revision inputs, migrations 0028/0029, backend regressions, source contracts, UAT and demo artifacts.
- Fixed an existing Activity inbox field mismatch from `NativeMessage.sequence` to the actual `message_sequence` field while touching lifecycle/unread logic.

Verification is not claimed as passed. Latest Backend CI, Delivery Verifier and Release Gate jobs completed with no job steps, and local checkout could not run because the execution environment could not resolve github.com. `S-10.12.01` remains `IN_REVIEW` pending executable PostgreSQL/migration/backend/frontend/verifier evidence and authenticated WorkOS multi-user UAT.


### Increment 27 — Workspace Search & Quick Switcher

- Added a keyboard-first Ctrl+K/Cmd+K workspace search dialog with instant local switching across currently visible Brain channels, projects, tracks and participant-visible DM counterparts.
- Reused the existing S-05.01 SearchDocument/RBAC path for remote message/evidence search in deterministic keyword mode; no second search engine or index was introduced.
- Added a same-origin WorkOS search BFF with current membership validation, 2–120 character query bounds, a 12-result cap, safe errors and bounded 280-character result excerpts.
- Added exact Brain-native message navigation through a new permission-aware single-message read; deep links now load/authorise the target, open its thread when required and address individual message cards.
- Added restricted-channel search/revocation regression coverage and an executable negative proving Brain-native DM bodies never enter organisation-wide search.
- Kept DM counterpart metadata locally navigable for participants while preserving the resolved no-employer-wide-DM-search boundary.
- Added WorkOS activation wiring, frontend source contracts, UAT, planning and demo artifacts.

Verification is not yet claimed. `S-10.11.01` remains `IN_REVIEW` until backend/frontend/verifier execution and authenticated WorkOS keyboard/revocation/private-source UAT pass.


### Increment 26 — Live workspace updates

- Added an opaque server-side live revision built from already-authorised Activity, visible channel/access metadata, unread cursors, selected-channel message/reply/reaction affordances and participant-visible DM state.
- Added a same-origin WorkOS live-state BFF that revalidates Brain organisation membership and UUID conversation context while keeping reusable access tokens server-side.
- Added adaptive client checks: 4 seconds on visible tabs, 30 seconds while hidden, offline-aware recovery and exponential failure backoff capped at 30 seconds.
- The React server tree refreshes only when the stable revision changes, avoiding repeated reloads against identical source state.
- Open threads independently re-fetch permitted replies through the existing same-origin conversation route so reply/reaction changes can appear without manual reload.
- Reused the existing permission/source APIs instead of adding WebSockets, SSE, Redis, a broker or a second realtime event store before measured need.
- Added source-contract tests, WorkOS activation wiring, planning, UAT and demo evidence contracts.

Verification is not yet claimed. `S-10.10.01` is `IN_REVIEW` until frontend/verifier execution and authenticated two-user WorkOS timing/revocation/offline/accessibility UAT pass.


### Increment 25 — Activity & Notifications Inbox

- Added one personal permission-aware Activity inbox for exact mentions, thread replies, reactions, Brain-native direct messages, unread channel activity, agent approval requests, agent completion/failure events, visible project/blocker updates and authorised integration failures.
- Kept Activity persistence reference-only: notifications store identifiers/read state rather than copied message bodies, DM text, private evidence excerpts, provider/API credentials or agent tool arguments/results.
- Re-check current source permissions and state when Activity is read, so restricted-channel/DM/project/agent/integration revocation or recovery removes stale items and unread counts immediately.
- Added exact source deep links for channel/message/thread, DM conversation/message, agent run/step, project/blocker and integration context.
- Added personal mark-one/mark-all read state plus explicit per-user notification preferences.
- Hardened default preference creation against concurrent first-read uniqueness races by recovering the winning organisation/user preference row after an integrity collision.
- Preserved both existing notification migration parents and converged them with graph-only merge revision `20260918_0026`; the unified inbox extension follows at `20260918_0027`.
- Added responsive Activity dock/panel, same-origin WorkOS BFF contracts, backend/privacy/security tests, frontend source-contract tests, UAT and inspectable demo commands.

Verification is not yet claimed. `S-10.09.01` is `IN_REVIEW`: current GitHub-hosted jobs have been failing before repository steps execute, and the required PostgreSQL migration round-trip plus official WorkOS authenticated multi-user browser/accessibility UAT have not yet produced passing evidence.

### Increment 24 — Slack/Discord-quality Brain conversations

- Made the selected Brain channel the primary workspace surface with unread badges, responsive thread context, visible agent identity, resolved mention highlighting, reaction controls, empty/error states and keyboard-visible controls.
- Added tenant/channel-scoped root replies, exact active readable-member `@email` mentions and five allow-listed per-user idempotent reactions.
- Replaced timestamp/random-UUID unread ordering with an atomic per-channel message sequence and monotonic per-user read cursor; unread summaries are batched and include the latest root or reply cursor.
- Added composite tenant/channel/message foreign keys for thread, mention, reaction and read-state rows, plus a database reaction allow-list.
- Added complete same-origin WorkOS BFF templates for channel messages, replies, reactions, read state and restricted-channel member changes with bounded JSON, UUID/role validation, safe errors and cross-site mutation rejection.
- Hardened structured logging so a caller-provided field cannot overwrite a reserved `LogRecord` attribute and crash ingestion/message projection.
- Added focused backend security/idempotency/read-order tests, frontend source contracts, architecture/rollback documentation, manual UAT and demo commands.

Local automated checks passed on 2026-09-13: repository-wide Ruff, all 299 backend tests, 24 focused conversation tests, frontend lint/build, 12 frontend tests with 1 intentional unauthenticated skip, and PostgreSQL offline migration compilation. The delivery verifier was not completed after the product owner directed the run to be skipped; no verifier PASS is claimed. S-10.06.01 remains `IN_REVIEW` until the verifier, live PostgreSQL upgrade/downgrade, official WorkOS activation and authenticated responsive/keyboard browser UAT pass.

### Increment 21 — Permission-aware Executive Overview

- Added an `audit.read`-gated organisation Executive Overview that composes existing project, decision/blocker, AI usage/cost/budget and external API usage sources of truth rather than persisting a second dashboard state.
- Added the complete caller-visible S-07.01 project portfolio with deterministic `blocked`, `in_progress`, `done`, `not_started` and `unconfigured` status counts, structured progress and per-project provenance/drill-down.
- Added deduplicated organisation-level human-confirmed blockers and decisions with canonical/search/work-graph evidence IDs and all currently visible project links; machine-only candidates are never promoted to executive facts.
- Added month-to-date AI request/success/failure totals, ordinary/cached/output token totals, provider breakdown and exact known nano-USD spend from S-06.02. Successful requests with unknown cost remain explicit and make `cost_complete=false` rather than being treated as zero.
- Added enabled AI budget warning/exhaustion/incomplete-enforcement reporting using the existing deterministic calendar-month budget snapshot. Work-Graph-scoped budget warnings are hidden when the target node is not currently visible to the caller.
- Added month-to-date external API usage/service/success/failure and active-grant reporting from trusted S-06.03 observations, plus an `audit.read` organisation-wide `/api-registry/usage` drill-down that exposes no credential values or secret references.
- External API monetary spend is deliberately returned as `null` with `cost_status=not_modeled` because Brain does not yet have a reviewed external-API tariff/cost ledger; call counts and latency are never converted into invented money.
- Added deterministic risk entries only for blocked projects, AI budget warning/exhaustion/incomplete enforcement, incomplete AI cost, and the explicit absence of an API monetary-cost model when API activity exists.
- Added source/calculation provenance for every executive metric family. There is deliberately no employee productivity/worth/performance score and no productivity-score field in the API contract.
- Added Executive Overview accounting/security/memory-dedup/budget-privacy/API-usage contract tests, `docs/EXECUTIVE_OVERVIEW.md`, Increment 21 planning and `UAT/F-07.02.md`.

Verification is not yet claimed. `S-07.02.01` remains `BLOCKED` because S-07.01.01 and S-06.02.01 are not engineering-DONE and the new tests, cost/budget/API reconciliation, restricted-project UAT, production WorkOS frontend and browser/accessibility UAT have not executed. No DONE/PASSED or production-readiness claim is made from repository implementation alone.

### Increment 20 — Evidence-backed Project Command Centre

- Added explicit structured project progress rows over existing Work Graph project/work-item nodes with `not_started`, `in_progress`, `blocked` and `done` states plus bounded integer weights.
- Added deterministic visible progress calculation. When no structured work is configured, the API returns `progress_percent=null`; Brain does not infer a percentage from messages, commits, evidence volume, employee activity or AI output.
- Added deterministic project status rules and kept machine blocker candidates separate from human-confirmed active blockers so unreviewed extraction cannot turn into a project fact.
- Added permission-aware project evidence discovery through Work Graph traversal, followed by a second intersection with the live Search authorization query before evidence IDs/provenance are returned.
- Added separate response collections for configured progress items, confirmed blockers, confirmed decisions, candidate memories and underlying authorised evidence.
- Added auditable project-progress create/update/delete APIs and reject progress configuration for work items that are not linked to the project.
- Added migration `20260910_0018_project_status.py`, project-status regression contracts, architecture documentation, Increment 20 planning and `UAT/F-07.01.md`.
- Added a restricted-evidence contract showing that a visible project does not disclose related private evidence or its candidate/decision/blocker memory to an unauthorised member.

Verification is not yet claimed. `S-07.01.01` remains `BLOCKED` because `S-04.02.01` is not engineering-DONE, the new backend/migration tests have not executed, realistic permission/revocation UAT has not run, and the production WorkOS-authenticated frontend/manual path remains outstanding.

### Increment 19 — Generic Meeting/Document Evidence

- Resolved OQ-004 to ship a provider-neutral Brain-managed generic upload adapter before committing to Google Drive, Loom, Zoom/Meet or another vendor connector.
- Added bounded authorised ingestion for UTF-8 text/Markdown/CSV/JSON/VTT/SRT, text-extractable PDF and DOCX with source SHA-256 identity, parser safety limits and deterministic overlapping chunks.
- Added RawEvent -> CanonicalEvent -> Work Graph -> Search projection with source/chunk provenance so meeting/document evidence uses the same downstream retrieval and memory contracts as Slack/GitHub.
- Added organisation/restricted evidence visibility using the existing Work Graph resource-grant boundary instead of introducing a second document ACL system.
- Added organisation-scoped idempotency handling, source lifecycle/audit events and integration with the existing physical source-object deletion/retention machinery.
- Added migration `20260910_0017_generic_evidence_sources.py`, evidence ingestion/security tests, `docs/GENERIC_EVIDENCE.md`, Increment 19 planning and `UAT/F-02.04.md`.
- Added cross-feature contracts proving authorised generic evidence can feed Ask Brain citations and Decision/Blocker Memory while restricted evidence prevents provider calls/derived disclosure for users without access.

Verification is not yet claimed. `S-02.04.01` remains `IN_REVIEW`; its pytest/migration/real-data/browser checks have not executed in this pass.

### Increment 18 — Evidence-backed Ask Brain

- Added a production Ask Brain API that reuses the existing permission-aware retrieval boundary before any company evidence reaches an AI provider.
- Added bounded RAG context with server-issued evidence IDs and explicit no-evidence behaviour that returns `insufficient_evidence` without loading provider credentials or invoking a model.
- Reused the governed tenant-scoped AI gateway rather than creating a second provider path and added safe organisation/runtime discovery for ordinary `ai.use` members.
- Resolved OQ-005 on 2026-09-10: OpenAI API with `gpt-5.6-terra` is the first production candidate, conditional on the checked-in security, retrieval, citation, latency, compatibility and exact-cost gates; no silent fallback is allowed.
- Added prompt-injection resistance by treating retrieved evidence as untrusted data and forbidding evidence-contained instructions from becoming model instructions.
- Added fail-closed structured grounding validation: every accepted factual claim must cite one or more server-issued evidence IDs; malformed, empty or unknown citations are rejected and raw provider output is not returned.
- Tightened the model contract so unexpected top-level or claim-level JSON fields also fail closed rather than being silently ignored.
- Added generic meeting/document evidence integration through the same Search-to-RAG path; no document-specific provider/retrieval branch was introduced.
- Added cross-tenant, revocation, no-answer, citation-grounding, provenance-contract, generic-evidence, strict-output and guest-authorization tests plus architecture/security documentation, Increment 18 planning and real-provider UAT.
- Added two-phase deployed evaluation: automatic retrieval/security metrics are separated from human review of every exact generated claim-citation pair.
- Extended governed AI accounting for OpenAI cached input: provider cached-token usage is captured, request records persist it, model rate cards can price normal input/cached input/output separately, and missing/invalid required cache usage fails cost resolution closed to `unknown`.
- Added request-scoped AI cost audit plus staging bootstrap validation that independently recomputes the exact request's input/output/total nano-USD cost from the reviewed Terra rate card.
- Added Alembic revision `20260910_0016`, cache-aware accounting tests, request-cost route tests and managed-Postgres URL normalization tests. These tests are checked in but are not claimed as executed in this pass.
- Added `render.yaml` and `docs/RENDER_STAGING.md` for a reproducible Render staging candidate with API + Postgres, migration-before-start and database readiness checks. This is staging tooling, not the final production topology under OQ-007.
- Updated `docs/ASK_BRAIN_STAGING.md`, `UAT/F-05.02.md`, the board, Definition of Ready, traceability and draft PR without creating another delivery branch.

Verification is not yet claimed. `S-05.01.01` remains `IN_REVIEW`; on 2026-09-10 the project owner explicitly deferred its local pytest and Render verification until later, which is not a PASS. `S-05.02.01` remains `BLOCKED`: the real Render/WorkOS/AWS/OpenAI staging environment is not configured here, the Terra compatibility/exact-cost smoke has not run, representative Phase 1 retrieval/RAG evaluation and Phase 2 human citation review have not run, no staging p95 result exists, and the official WorkOS frontend package/build plus authenticated browser UAT remain outstanding. No DONE/PASSED or runtime performance/cost-quality claim is made from repository code alone.

### Increment 16 — Performance and cost budgets

- Added deterministic nearest-rank percentile and budget evaluation for p50/p95/p99, success rate, throughput and optional cost ceilings.
- Added a versioned benchmark workload for core organisation read, permission-aware search and governed AI under `ops/performance/budgets.json`.
- Reused the existing production SLO budgets rather than inventing new latency thresholds: core p95 <500 ms, search p95 <1.5 s and governed AI p95 <10 s.
- Added an async real-HTTP benchmark runner that records request count, concurrency, warmup, status/error counts, p50/p95/p99/max latency, throughput and explicit budget verdicts without storing request/response bodies or credentials.
- Added F-06.02 usage-ledger cost snapshots so the AI scenario reports exact nano-USD cost per successful evaluated task in an isolated benchmark organisation.
- Added fail-closed exact-cost behavior: when exact cost is required, any new unknown-cost AI request fails the scenario instead of being treated as zero spend.
- Added configurable throughput and maximum AI cost-per-success gates, while intentionally leaving their numeric thresholds unset until representative baselines/product economics establish agreed targets.
- Added a manually dispatched HTTPS staging Performance Gate with secret-backed benchmark authentication and optional low-concurrency governed-AI load.
- Added performance-budget regression tests, methodology/limitations documentation, Increment 16 planning and production-like backend/frontend UAT instructions.

Verification/performance is not yet claimed. `S-09.04.01` remains `BLOCKED`: search and governed AI remain unverified, GitHub-hosted jobs still cannot obtain a runner, F-09.03 has not produced the target staging environment, and no real Performance Gate report has executed. No p95, throughput, scale or AI-cost benchmark claim is made from repository code alone.

### Increment 15 — Deployment, rollback, backup and restore

- Added one provider-neutral `Release Gate` workflow that runs Ruff, backend Pytest and the delivery verifier before later release checks can proceed.
- Added disposable PostgreSQL 17 + pgvector migration verification with `upgrade head`, ORM drift check, full `downgrade base`, forward recovery to `head` and final drift check.
- Added guarded PostgreSQL custom-format backup and restore scripts with archive parsing validation, portable SHA-256 sidecars, owner-only local permissions and explicit destructive-restore confirmation.
- Added an actual restored-data exercise: CI seeds a pre-backup sentinel, mutates it after backup, restores the archive and asserts the original value is recovered.
- Added OCI image build plus production-mode API startup/readiness smoke against the restored PostgreSQL database.
- Added a non-secret release manifest containing commit SHA, local image ID, migration head(s) and verification timestamp; the disposable database archive is deleted before artifact upload.
- Added release-contract regression tests covering shell syntax, destructive restore refusal, required Release Gate stages and non-root production container execution.
- Added deployment/migration/rollback/restore runbook and production-like UAT with immutable image digest, rollback drill, restore drill, observed recovery times and frontend/manual validation.
- Added OQ-007 rather than guessing the final production runtime/image registry/managed PostgreSQL topology.
- Closed nearby F-09.02 test drift caused by integration-scoped source-object deletion hardening.

Verification is not yet claimed. `S-09.03.01` remains `BLOCKED`: the Release Gate has not executed on a GitHub runner, required merge-check enforcement is unavailable/unverified for the current private-repository setup, and OQ-007 still blocks the environment-specific publish/deploy/rollback drill. No backup-restore or recovery-time success is claimed from repository code alone.

### Increment 14 — Audit, retention and deletion

- Added tenant-scoped durable security audit events with actor/resource/request correlation, bounded metadata and normalized-payload SHA-256 digests.
- Added PostgreSQL append-only enforcement that rejects audit-row updates while allowing explicit audit-retention deletion; actor UUID evidence is deliberately not a mutable user foreign key.
- Added `data_governance.manage` for Owner/Admin retention/deletion administration while organisation-wide governance/audit reads reuse `audit.read`.
- Added explicit per-organisation raw-event, derived-content and audit-event retention durations plus legal hold. Unset durations mean no automatic age-based purge; Brain does not invent a legal/compliance period when an organisation has not configured one.
- Added bounded raw retention and derived retention with reconstruction-suppressing tombstones. Derived tombstones preserve only raw-event ID plus minimal provider/object locator, not source content.
- Added integration-wide deletion gated on full revocation and typed source-object deletion with idempotency keys, stable target references, counts and completion digests.
- Closed the retained-raw deletion gap: a source-object deletion can still find and delete raw evidence after its canonical row was previously removed by derived retention.
- Added canonicalisation suppression so deleted/purged evidence cannot silently reappear through connector replay or reconciliation.
- Added orphan source-identity sanitation that clears unsupported identity evidence and returns the identity to `unresolved` state.
- Added pending/failed/stale-processing deletion recovery, bounded worker execution and PostgreSQL row-lock/`SKIP LOCKED` concurrency semantics.
- Added fail-closed durable audit coupling for ACL create/delete mutations; authorization-denial audit persistence remains best-effort so an audit-store problem cannot widen access.
- Added Alembic revision `20260908_0014`, service/route/worker/audit/retained-raw regression tests, operator documentation and realistic PostgreSQL/frontend UAT instructions.

Verification is not yet claimed. `S-09.02.01` remains `IN_REVIEW` until Ruff, Pytest, migration verification and the Delivery Verifier actually execute. PostgreSQL append-only-trigger/cascade/concurrency behavior, realistic deletion/replay behavior, frontend/manual acceptance and backup/PITR lifecycle remain separate `UAT_PENDING` evidence.

### Increment 13 — Production observability and SLOs

- Added correlated structured JSON logging with bounded request IDs, W3C/OpenTelemetry request + AI tracing, structured JSON logging with strict allowlisting and credential/token redaction, protected Prometheus metrics, route-template HTTP metrics, PostgreSQL readiness metrics, connector lifecycle telemetry, aggregate governed-AI status/latency/exact-cost telemetry, SLO/error-budget definitions, alert rules, incident runbook, tests and deployed UAT instructions.
- Tenant-configurable organisation/user/integration/provider/model values are deliberately excluded from Prometheus labels and remain available through correlated logs/traces/durable ledgers.

Verification is not yet claimed. `S-09.01.01` remains `IN_REVIEW` until Ruff, Pytest and the Delivery Verifier obtain an executable passing run. Deployed metrics/trace collection, alert firing and representative monthly SLO compliance remain separate `UAT_PENDING` evidence.

### Increment 12 — External API registry

- Added tenant-scoped external API service and credential-grant inventory with explicit owner, scopes, environment, status and optional expiry.
- Added dedicated `api.manage` administration permission while organisation-wide registry/history/usage reads reuse `audit.read`.
- Added AWS Secrets Manager storage for external API credentials; PostgreSQL persists only secret references and read APIs expose only `credential_present`.
- Added safe internal credential loading that refuses disabled, revoked, revoke-failed and time-expired grants before secret retrieval; no public credential-read endpoint exists.
- Added credential rotation without changing the stored reference or persisting old/new credential values.
- Added fail-closed `revoking`, `revoke_failed` and `revoked` transitions with retryable secret deletion and immutable lifecycle history.
- Added bounded expiry processing plus separate secret-cleanup retries so an expired grant remains unusable even when external secret deletion temporarily fails.
- Added trusted internal, idempotent API usage observations with PostgreSQL grant-row locking to avoid lost concurrent usage-count updates; normal clients cannot fabricate usage through a public write route.
- Added Alembic revision `20260907_0013`, security/lifecycle/worker/secret-store tests, operator documentation and realistic-data/frontend UAT instructions.

Verification is not yet claimed. The latest checked Backend CI job for this branch failed before runner startup with `runner_id=0` and no executed steps, so Ruff/Pytest/Delivery Verifier evidence does not exist and `S-06.03.01` remains `IN_REVIEW`.

### Increment 11 — Usage, cost and budgets

- Added historical provider/model rate cards and deterministic integer nano-USD cost accounting.
- Added explicit `calculated` versus `unknown` cost-resolution state; missing provider token counts or pricing are never silently treated as zero spend.
- Added usage aggregation by organisation, provider, model, user and existing Work Graph attribution node without guessing missing attribution.
- Added UTC calendar-month budgets for organisation/provider/model/user/project-track-work-item scopes with tenant-validated targets.
- Added deduplicated warning and 100% alerts plus a post-exhaustion hard-stop before provider secret lookup/execution.
- Added explicit incomplete-enforcement state when a budget period contains unknown-cost requests rather than pretending known spend equals the invoice.
- Added bounded cost reconciliation with PostgreSQL `FOR UPDATE SKIP LOCKED` for successful requests whose cost is missing or later becomes resolvable.
- Added Alembic revision `20260907_0012`, API routes, accounting/security tests, operator documentation and real-provider/frontend UAT instructions.

Increment 18 extends this accounting contract with cached-input usage/rates and migration `20260910_0016`. Verification is not yet claimed. `S-06.02.01` remains `BLOCKED` because S-06.01.01 lacks executable passing verification and the new cache-aware accounting tests/real-provider exact-cost smoke have not run.

### Increment 10 — Governed AI provider gateway

- Added tenant-scoped AI provider/model configuration with separate `ai.manage` administration and `ai.use` invocation permissions.
- Added secret-reference provider credentials, credential rotation, fail-closed revocation and no plaintext API-key persistence.
- Added production HTTPS/provider-host egress controls, redirect rejection and bounded provider response/error handling.
- Added a provider-neutral runtime contract with an isolated OpenAI-compatible chat-completions adapter.
- Added durable AI request metadata for organisation, user, provider, model, optional Work Graph attribution, status, latency, provider request ID and provider-returned token counts.
- Prompts, system text and model completions are not persisted in the AI request ledger by default.
- Added Alembic revision `20260907_0011`, gateway/adapter/route/security tests, documentation and real-provider/frontend UAT instructions.

Verification is not yet claimed because GitHub-hosted Actions cannot currently obtain a runner; `S-06.01.01` remains `IN_REVIEW` until Ruff, Pytest and the Delivery Verifier actually execute successfully.

### Increment 9 — Decision and blocker memory

- Added tenant-scoped decision/blocker candidate storage plus versioned extraction bookkeeping and immutable human review history.
- Added a conservative deterministic extractor over whitelisted search evidence; machine extraction always creates `candidate` state and never auto-confirms a fact.
- Added explicit decision/blocker confidence, extraction method/version and SHA-256 statement fingerprints for idempotency.
- Added same-document PostgreSQL row locking, content/version reprocessing and `superseded` state for stale unreviewed machine candidates.
- Added current-permission-aware reads by reusing the Permission-Aware Retrieval candidate boundary, including live Slack/GitHub revocation behavior.
- Added human `confirm`, `reject`, `edit`, blocker-only `resolve` and `reopen` transitions with immutable before/after review records.
- Hardened human-authoritative state: candidates with review history are not silently superseded or rewritten by later extraction, and review mutations lock the candidate row before transition to avoid concurrent-review races.
- Added generic meeting/document evidence regression coverage so explicit decisions/blockers in authorised transcripts/documents use the same candidate/review contract.
- Added bounded historical reconciliation/API/worker, Alembic revision `20260907_0010`, security/state/idempotency tests, synthetic precision instrumentation and realistic-data UAT instructions.

Verification is not yet claimed. This story is formally `BLOCKED` on S-05.01.01 because Permission-Aware Retrieval is still `IN_REVIEW`. The synthetic precision fixture is not a production precision claim; representative labelled data, executable tests and frontend/manual UAT remain required.

### Increment 8 — Permission-aware retrieval

- Added a rebuildable tenant-scoped search projection over canonical Slack/GitHub evidence.
- Added live Slack channel/membership and GitHub/resource-grant filtering before result rows are returned.
- Added PostgreSQL full-text keyword retrieval with a matching GIN expression index.
- Added provider-neutral semantic embeddings and pgvector cosine retrieval without choosing the later RAG generation provider.
- Added explicit hybrid-search degradation when the embedding service is absent/unavailable.
- Added a bounded database-backed reconciliation/embedding worker with stale-claim recovery and retry backoff.
- Added revocation/deletion handling so derived search content becomes unavailable while raw/canonical audit evidence remains.
- Added Alembic revision `20260907_0009`, rollback notes, security-focused tests, architecture docs and UAT instructions.
- Added `DEFINITION_OF_READY.md` because the delivery contract required an inspectable DoR artifact and the repository did not previously contain one.

Verification is not yet claimed: the project owner explicitly deferred the next local pytest and Render execution verification on 2026-09-10. `S-05.01.01` remains non-DONE until that verification actually runs successfully and is recorded.
