# Brain Delivery Board

Method: Scrum + Kanban hybrid. Two-week increments. WIP limit: IN_PROGRESS <= 2. Chat is not state.

Format: `STATUS | STORY_ID | FEATURE | NOTE`

Historical planning/state before Increment 18 is preserved at `docs/archive/BOARD_before_increment18.md`.

DONE | S-01.01.01 | F-01.01 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.02.01 | F-01.02 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.03.01 | F-01.03 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-02.01.01 | F-02.01 | Engineering evidence in TRACEABILITY.md; real-data/frontend UAT remains pending
DONE | S-02.02.01 | F-02.02 | Engineering evidence in TRACEABILITY.md; real Slack + frontend UAT remains pending
DONE | S-02.03.01 | F-02.03 | Engineering evidence in TRACEABILITY.md; real GitHub + frontend UAT remains pending
IN_REVIEW | S-02.04.01 | F-02.04 | Generic governed file/transcript ingestion, migration, tests, docs and UAT are staged; executable verification is intentionally not claimed in this pass
DONE | S-03.01.01 | F-03.01 | Engineering evidence in TRACEABILITY.md; realistic raw-data inspection UAT remains pending
DONE | S-03.02.01 | F-03.02 | Engineering evidence in TRACEABILITY.md; Slack/GitHub real-data + frontend UAT remains pending
DONE | S-03.03.01 | F-03.03 | Engineering evidence in TRACEABILITY.md; real provider identity + frontend/manual UAT remains pending
DONE | S-04.01.01 | F-04.01 | Engineering evidence in TRACEABILITY.md; real Slack/GitHub graph + frontend/manual UAT remains pending
BLOCKED | S-04.02.01 | F-04.02 | Backend implementation is staged and hardened for generic evidence + human-authoritative review; external dependency: real evidence evaluation/UAT, after S-05.01.01 verification
IN_REVIEW | S-05.01.01 | F-05.01 | Implementation/docs/tests including provenance contract exist; acceptance phase started on 2026-09-11, but latest GitHub jobs failed before any workflow step executed and no local/Render passing evidence exists
BLOCKED | S-05.02.01 | F-05.02 | Backend RAG implementation is staged including generic evidence integration, strict output contract and cache-aware exact cost; external dependency: real AI provider staging/evaluation/performance and WorkOS browser UAT
IN_REVIEW | S-06.01.01 | F-06.01 | Provider registry/gateway implementation, migration, tests, docs and cache-token usage propagation are staged; executable passing verification remains outstanding
BLOCKED | S-06.02.01 | F-06.02 | Cache-aware usage/cost/budget implementation and request-scoped cost audit are staged; external dependency: real provider usage/cost reconciliation, after S-06.01.01 verification
IN_REVIEW | S-06.03.01 | F-06.03 | External API registry/lifecycle/expiry implementation is staged; executable passing verification remains outstanding
BLOCKED | S-07.01.01 | F-07.01 | Evidence-backed project-status backend, deterministic structured progress, migration, tests/docs/UAT are staged; external dependency: production frontend UAT, after S-04.02.01 completion
BLOCKED | S-07.02.01 | F-07.02 | Permission-aware executive overview, AI spend/budget risk, API activity, provenance, tests/docs/UAT are staged; external dependency: production frontend UAT, after S-07.01.01 + S-06.02.01
BLOCKED | S-08.01.01 | F-08.01 | Governed agent runtime is staged; external dependency: real tool/provider safety UAT after upstream dependency verification
IN_REVIEW | S-09.01.01 | F-09.01 | Observability implementation/tests/docs/UAT are staged; executable passing verification remains outstanding
IN_REVIEW | S-09.02.01 | F-09.02 | Audit/retention/deletion implementation including explicit private-message retention is staged; executable PostgreSQL/Ruff/Pytest/Delivery Verifier evidence remains outstanding
BLOCKED | S-09.03.01 | F-09.03 | Release/rollback/restore work plus a concrete Render staging Blueprint are staged; real deployment/recovery exercise and OQ-007 production topology remain unresolved
BLOCKED | S-09.04.01 | F-09.04 | Performance/cost benchmark work is staged; external dependency: a real Ask Brain staging target and provider credentials
IN_REVIEW | S-10.01.01 | F-10.01 | Native channel/message persistence, evidence projection, restricted memberships, API/BFF/UI and tests are implemented; executable CI, migration and authenticated browser UAT evidence remain pending
BLOCKED | S-10.02.01 | F-10.02 | Workspace shell, real organisation switching, navigation API/client, responsive controls, tests/docs/UAT are staged; external dependency: official WorkOS activation and authenticated browser acceptance
BLOCKED | S-10.03.01 | F-10.03 | Project/memory/company-pulse/evidence surfaces, runtime discovery and citation-first Ask Brain UI are staged; external dependency: live authenticated WorkOS/Ask Brain browser acceptance
BLOCKED | S-10.04.01 | F-10.04 | Official WorkOS Next.js 16 templates, guarded install/activation scripts and BFF security contract are staged; external dependency: real WorkOS configuration plus authenticated browser execution
BLOCKED | S-10.05.01 | F-10.05 | Repository implementation is staged; external S-10.04 WorkOS activation plus executable backend/browser acceptance remain pending
IN_REVIEW | S-10.06.01 | F-10.06 | Ruff, 299 backend tests and frontend build/tests pass locally; verifier was skipped by product-owner direction, and live PostgreSQL/WorkOS/browser UAT remain pending
IN_REVIEW | S-10.06.02 | F-10.06 | Participant-only Brain-native DMs, sequence-based revocable visibility epochs, privacy-safe UI/BFF, migrations 0022/0023/0024, explicit private-message retention and regression/UAT contracts are implementation-staged; current-commit Ruff/Pytest/PostgreSQL/frontend/WorkOS browser verification has not executed
IN_REVIEW | S-10.07.01 | F-10.07 | Governed developer/agent workspace, project/channel context binding, approvals, context-aware tool execution, ephemeral final output and privacy/security contracts are implementation-staged; executable verification and authenticated browser UAT remain pending
IN_REVIEW | S-10.08.01 | F-10.08 | Owner/Admin governance center now covers member/integration lifecycle, AI provider/model bootstrap and credential rotation, API service/grant bootstrap, owner/scope/environment/credential lifecycle and safe same-origin WorkOS BFF contracts; executable/backend/browser verification remains outstanding
IN_REVIEW | S-10.09.01 | F-10.09 | Unified personal Activity & Notifications inbox is implementation-staged across collaboration, agent, project/blocker and integration events with reference-only persistence, current-permission rechecks, exact deep links, personal read/unread state, preferences, same-origin BFF UI and migration-branch convergence; executable backend/frontend/verifier/PostgreSQL/WorkOS browser evidence remains outstanding
IN_REVIEW | S-10.10.01 | F-10.10 | Opaque authorised live revision, same-origin WorkOS BFF, adaptive visible/hidden/offline refresh, selected-channel/DM/Activity invalidation and open-thread refresh are implementation-staged; executable frontend/verifier and authenticated two-user WorkOS timing/revocation UAT remain outstanding
IN_REVIEW | S-10.11.01 | F-10.11 | Keyboard-first quick switcher, membership-validated same-origin keyword search, exact authorised Brain-message deep links, restricted-channel revoke regression and DM-content exclusion regression are implementation-staged; executable backend/frontend/verifier and authenticated WorkOS keyboard/privacy UAT remain outstanding
IN_REVIEW | S-10.12.01 | F-10.12 | Author-only edit/retract, expected-revision conflicts, immutable RawEvent/CanonicalEvent lifecycle revisions, retired Search versions, tombstones, historical restricted-evidence access cleanup and governed revision retention are implementation-staged; executable PostgreSQL/backend/frontend/verifier and authenticated WorkOS UAT remain outstanding
IN_REVIEW | S-10.13.01 | F-10.13 | Governed EvidenceSource channel uploads, live restricted membership, tenant-scoped attachment relations, file-only messages, bounded WorkOS multipart UI, retry-safe composer and deletion/retraction independence are implementation-staged; executable PostgreSQL/backend/frontend/verifier and authenticated WorkOS UAT remain outstanding
IN_REVIEW | S-10.14.01 | F-10.14 | Ephemeral 75s presence + 8s typing leases, read-only authorised polling, restricted-channel/participant-only DM privacy, audit-free traffic, same-origin WorkOS BFF and focused-composer UI are implementation-staged; executable PostgreSQL/backend/frontend/verifier and authenticated WorkOS UAT remain outstanding
IN_REVIEW | S-10.15.01 | F-10.15 | Reference-only shared channel pins, current reader/writer permission checks, retry-safe uniqueness, thread/root reopening, same-lifecycle retract cleanup, structural live refresh and WorkOS BFF/UI are implementation-staged; executable PostgreSQL/backend/frontend/verifier and authenticated WorkOS UAT remain outstanding
IN_REVIEW | S-10.16.01 | F-10.16 | Private reference-only Saved messages, membership/message scoped FKs, current visible-channel filtering, read-only Save support, audit-free personal traffic, same-lifecycle retract cleanup, exact deep links and WorkOS UI are implementation-staged; executable PostgreSQL/backend/frontend/verifier and authenticated WorkOS UAT remain outstanding
IN_REVIEW | S-10.17.01 | F-10.17 | Set-based first-unread ID, same-origin exact-message recovery, stable accessible root/thread divider/jump, regressions/docs/UAT staged; executable backend/frontend/verifier and authenticated WorkOS UAT remain outstanding
IN_REVIEW | S-10.18.01 | F-10.18 | Epoch-safe participant DM read cursors, set-based unread/first-target summary, exact participant-only recovery, badges/divider/jump, migration/tests/docs staged; executable verification/UAT outstanding
IN_REVIEW | S-10.19.01 | F-10.19 | Stable before_sequence pagination for channel roots + participant-visible DMs, same-origin GETs, merge-safe Load older UX, tests/docs staged; executable verification/UAT outstanding
IN_REVIEW | S-10.20.01 | F-10.20 | Author/current-epoch DM edit/retract, optimistic revisions, private tombstones/history, unread/retention consistency, WorkOS UI/tests/docs staged; executable verification/UAT outstanding
IN_REVIEW | S-10.21.01 | F-10.21 | Stable before_sequence thread pagination, merge-safe Load older replies/live refresh, tests/docs staged; executable verification/UAT outstanding
IN_REVIEW | S-10.22.01 | F-10.22 | Tenant/root/user thread read state, set-based unread/first target, monotonic mark-read, badge/divider/jump, migration/tests/docs staged; executable verification/UAT outstanding
IN_REVIEW | S-10.23.01 | F-10.23 | Private allow-listed/idempotent DM reactions, aggregate-only reads, retention/privacy-safe WorkOS UI/tests/docs staged; executable verification/UAT outstanding






### S-10.23.01 Participant-Private DM Reactions — IN_REVIEW

Sprint goal: add lightweight reactions to visible participant-private DM messages without exposing participant metadata or creating employer-wide intelligence/audit events.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation scope is in `docs/planning/increment-39.md`.

Implementation staged: private reaction migration/model, current-participant/current-epoch idempotent add/remove, batched aggregate-only reads, same-origin WorkOS route/UI, privacy/retraction/retention/legal-hold tests and full UAT/demo/changelog/traceability. Formal state: `IN_REVIEW`; no executable PASS/UAT is claimed. WIP returns to zero.

### S-10.22.01 Thread Unread & Resume — IN_REVIEW

Sprint goal: preserve an independent monotonic unread boundary for each opened native thread without changing channel-level read semantics.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation scope is in `docs/planning/increment-38.md`.

Implementation staged: independent thread read-state migration, set-based tenant-safe summaries, monotonic mark-read, root unread metadata, same-origin BFF, New replies/Jump UI and negative tests/docs. Formal state: `IN_REVIEW`; no executable PASS/UAT is claimed. WIP returns to zero; S-10.23 may now be pulled.

### S-10.21.01 Thread History Pagination — IN_REVIEW

Sprint goal: make long-running native threads browsable with stable reply sequence cursors while preserving current channel authority and live thread state.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation scope is in `docs/planning/increment-37.md`.

Implementation staged: exact-root sequence cursor backend/API/BFF, merge-safe Load older replies, live-refresh preservation, validation tests, UAT/demo/changelog/traceability. Formal state: `IN_REVIEW`; no executable PASS/UAT is claimed. WIP returns to zero; S-10.22 may now be pulled.

### S-10.20.01 Direct-Message Lifecycle — IN_REVIEW

Sprint goal: let the current author edit/retract a visible private DM with optimistic concurrency and private revision history, without granting organisation roles access or projecting private content into company intelligence/audit.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-36.md`.

Implementation staged: private revision/lifecycle schema + migration, original-author/current-epoch mutation authority, expected-revision conflicts, participant tombstones, unread exclusion, no company-intelligence/audit projection, private-retention cascade, same-origin WorkOS PATCH/DELETE, accessible UI, privacy/concurrency/retention tests and complete UAT/demo/changelog/traceability artifacts.

Formal state: `IN_REVIEW`. No executable PASS or authenticated lifecycle UAT is claimed. WIP returns to zero.

### S-10.19.01 Conversation History Pagination — IN_REVIEW

Sprint goal: let authorised users load older native-channel root history and participant-visible DM history with stable sequence cursors, no OFFSET scans and no permission widening.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-35.md`.

Implementation staged: stable positive sequence cursors, bounded channel/DM list queries, current permission/visibility-floor enforcement, same-origin WorkOS GETs, accessible Load older controls, refresh-safe ID/sequence merging, backend pagination regressions, UAT/demo/changelog/traceability.

Formal state: `IN_REVIEW`. No executable PASS or authenticated long-history UAT is claimed. WIP returns to zero; S-10.20 may now be refined/pulled.

### S-10.18.01 DM Unread & Resume — IN_REVIEW

Sprint goal: give each DM participant an exact monotonic private unread boundary, badge and Jump to unread without exposing private activity outside the participant pair or reviving prior visibility epochs.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-34.md`.

Implementation staged: participant read cursors, visibility-epoch reset, set-based unread/latest/first-unread summaries, exact participant-only reads, monotonic mark-read, workspace/DM badges, accessible divider/jump, same-origin WorkOS routes, migration `20260919_0034`, focused regressions, UAT/demo/changelog/traceability.

Formal state: `IN_REVIEW`. No executable PASS or authenticated browser UAT is claimed. WIP returns to zero; S-10.19 may now be refined/pulled.

### S-10.17.01 First-Unread Divider & Jump to Unread — IN_REVIEW

Sprint goal: let an authorised user resume a Brain channel at the exact first unread root or thread reply without rescanning history or creating a second read-state system.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-33.md`.

Implementation staged:

- existing monotonic read state now exposes exact first-unread identity with a bounded set-based window query;
- own human-authored and retracted messages remain excluded from unread targets;
- same-origin WorkOS exact-message GET reuses current backend channel authorization for old-window/thread recovery;
- the mounted channel captures the initial unread boundary so immediate mark-read/router refresh does not erase the visual resume point;
- one accessible New messages divider and Jump to unread support rendered roots, old roots and thread replies;
- preserved replies remain jumpable under a retracted root, while a retracted target itself clears the stale boundary;
- no AI, second unread store, cache, schema migration, Redis/WebSocket or copied message content was added;
- backend regressions, frontend/query/security source contract, planning, UAT, demo, changelog, retrospective and traceability are staged.

Formal state: `IN_REVIEW`. No executable backend/frontend/verifier PASS or authenticated WorkOS browser UAT is claimed. WIP after review move: zero `IN_PROGRESS` stories.

### S-10.16.01 Personal Saved Messages — IN_REVIEW

Sprint goal: let a user privately save and reopen important authorised channel messages/replies without changing shared channel state or copying message content.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-32.md` and `UAT/F-10.16.md`.

Implementation staged:

- private `NativeMessageSave` stores only organisation/channel/message identity, saving user and timestamp;
- database membership + exact message-scope foreign keys prevent cross-tenant/cross-message corruption;
- current readers may Save/Unsave visible roots/replies even without channel write permission;
- Saved list is derived only from the authenticated user; there is no privileged-role user selector;
- restricted-channel revoke hides inaccessible saved content immediately while preserving the content-free reference for later regrant;
- organisation membership removal cascades saved references through the membership foreign key;
- unique user/message storage plus IntegrityError recovery makes repeated/concurrent saves idempotent;
- visible agent-authored messages are saveable without changing human edit/retract authority;
- edits preserve saves; retraction removes every saved reference for the message before lifecycle commit;
- normal Saved list/save/unsave traffic bypasses organisation-wide SecurityAuditEvent persistence;
- typed API/BFF and same-origin WorkOS Saved routes are staged;
- personal Saved navigation/panel and root/reply Save/Unsave actions are staged;
- exact S-10.11 channel/message deep links reopen saved roots and thread replies;
- migration `20260919_0033`, focused backend regressions, source contracts, UAT/demo/changelog/retro/traceability are staged.

Formal state: `IN_REVIEW`. No executable PostgreSQL/Ruff/Pytest/frontend/verifier/WorkOS browser PASS is claimed. WIP after review move: zero `IN_PROGRESS` stories.

### S-10.15.01 Shared Channel Message Pins — IN_REVIEW

Sprint goal: let channel participants mark and reopen important channel messages/thread replies without copying content or weakening current channel permissions.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-31.md` and `UAT/F-10.15.md`.

Implementation staged:

- reference-only `NativeMessagePin` stores organisation/channel/message identity plus pinner/timestamp, never copied message/evidence content;
- current readers can list pins; current writers can pin/unpin visible non-retracted roots or replies;
- database composite message scope blocks cross-channel/tenant corruption below service code;
- unique channel/message storage plus IntegrityError recovery makes pin retries idempotent;
- high-precision creation timestamps plus UUID tie-breaker preserve newest-pin-first ordering;
- agent-authored visible messages remain pinnable without changing human edit/retract authority;
- edits preserve pins; retraction removes active pins in the same lifecycle transaction before commit;
- typed API/BFF and same-origin WorkOS list/pin/unpin routes are staged;
- selected-channel pins load server-side and feed structural S-10.10 live revision using pin ID/message ID/timestamp only;
- accessible Pins panel, root/reply Pin/Unpin actions, older-root reopening and exact thread reopening are staged;
- migration `20260919_0032`, focused backend regressions, source contracts, UAT/demo/changelog/retro/traceability are staged.

Formal state: `IN_REVIEW`. No executable PostgreSQL/Ruff/Pytest/frontend/verifier/WorkOS browser PASS is claimed. WIP after review move: zero `IN_PROGRESS` stories.

### S-10.14.01 Ephemeral Presence & Typing — IN_REVIEW

Sprint goal: make native channels and participant-only DMs feel live by exposing only current authorised online/typing state through expiring leases, without creating employee activity history or a new realtime infrastructure dependency.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-30.md` and `UAT/F-10.14.md`.

Implementation staged:

- one short-lived presence row per organisation/user; no durable last-seen or append-only activity history;
- one exact channel-or-DM typing lease per user/context with database-level scoped foreign keys;
- 75-second presence and 8-second typing expiry;
- current restricted-channel visibility/write membership is rechecked on every context read/write;
- 1:1 DM presence/typing is participant-only with no Owner/Admin role override;
- presence polling is read-only, batched for restricted channels and sleeps while hidden/offline;
- heartbeat/typing writes opportunistically purge expired leases;
- normal presence/typing traffic deliberately creates no organisation-wide SecurityAuditEvent history;
- same-origin WorkOS heartbeat/context/typing BFF routes expose no reusable browser bearer token;
- visible-tab heartbeat runs every 30 seconds; typing refresh is throttled to 3 seconds and requires focused non-empty composer input;
- channel online count/accessibility typing status and participant-only DM Online/Offline + typing UI are staged;
- migration `20260919_0031`, focused backend regressions, frontend privacy contracts, UAT/demo/changelog/retro/traceability are staged.

Formal state: `IN_REVIEW`. No executable PostgreSQL/Ruff/Pytest/frontend/verifier/WorkOS browser PASS is claimed. WIP after review move: zero `IN_PROGRESS` stories.

### S-10.13.01 Governed Channel Attachments — IN_REVIEW

Sprint goal: connect the existing governed evidence pipeline to native channel/root/thread messages without introducing a second file store or static restricted-file ACL.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-29.md` and `UAT/F-10.13.md`.

Implementation staged:

- reuses existing EvidenceSource ingestion and stores only message↔source references, never duplicate file bytes;
- organisation/restricted channel scope flows into Evidence/RawEvent/CanonicalEvent/Search provenance;
- direct restricted Evidence reads recheck live native-channel membership;
- restricted member add/remove extends/removes attachment Work Graph/Search grants through the existing channel evidence scope;
- composite database foreign keys enforce tenant-safe channel/evidence/message relationships independently of service code;
- max five active sources per message/reply, exact-channel validation, duplicate de-duplication and idempotency attachment-set conflict handling;
- file-only messages are supported without placeholder text; empty-without-attachment remains invalid;
- message retraction hides cards without deleting evidence; evidence deletion leaves safe unavailable metadata;
- <=10 MB same-origin WorkOS multipart upload, root/thread attachment cards and retry-safe pending governed-source state are staged;
- ambiguous send retry reuses the same payload idempotency key, while body/attachment changes reset it;
- channel/thread upload race guards prevent a completed upload from binding to another composer;
- live refresh observes attachment structural status only;
- migration 0030 refuses unsafe downgrade while zero-body attachment-only rows exist and never auto-deletes EvidenceSource content;
- backend regressions, frontend source contracts, UAT, demo, changelog, retrospective and traceability are staged.

Formal state: `IN_REVIEW`. No executable PostgreSQL/Ruff/Pytest/frontend/verifier/WorkOS browser PASS is claimed. WIP after review move: zero `IN_PROGRESS` stories.


### S-10.12.01 Author-safe Message Lifecycle — IN_REVIEW

Sprint goal: let a current human author edit or retract their own Brain-native channel message without rewriting immutable evidence, widening permissions or breaking thread continuity.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-28.md` and `UAT/F-10.12.md`.

Implementation staged:

- only the original current human author with current channel write access can edit/retract;
- optimistic expected-revision conflicts prevent stale overwrite;
- prior revisions retain body/hash plus prior RawEvent/CanonicalEvent links;
- every accepted edit/retraction appends a new immutable native RawEvent + CanonicalEvent revision;
- prior SearchDocument versions are retired; edited search content resolves to the new canonical revision;
- retraction returns a content-free tombstone, removes current Search/mention/reaction/unread/Activity visibility and preserves existing thread replies;
- restricted-channel evidence scope includes historical canonical revisions for access changes;
- revision plaintext obeys derived-content retention and legal hold;
- same-origin WorkOS BFF/UI, live invalidation, migrations 0028/0029, tests/UAT/demo/traceability are staged.

Execution truth: latest Backend CI, Delivery Verifier and Release Gate jobs again ended with `steps: null`; local checkout was also unavailable because the execution environment could not resolve github.com. No executable PASS is claimed. WIP after review move: zero `IN_PROGRESS` stories.


### S-10.11.01 Workspace Search & Quick Switcher — IN_REVIEW

Sprint goal: expose the existing permission-aware search contract as a fast keyboard-first workspace navigation surface without building another index or weakening DM privacy.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation and acceptance scope are in `docs/planning/increment-27.md` and `UAT/F-10.11.md`.

Implementation staged:

- Ctrl+K/Cmd+K accessible command dialog with local authorised channel/project/track/DM-counterpart navigation;
- 250 ms debounced remote search only for >=2-character queries;
- same-origin WorkOS BFF over existing S-05.01 keyword Search with membership revalidation, 12-result cap and 280-character excerpts;
- no new search index/provider/database table;
- exact Brain-native message read/deep-link path with current channel access recheck, message anchors and thread opening;
- restricted-channel search result disappears after membership revocation by contract/test;
- unique Brain DM-body sentinel is never returned by organisation-wide search;
- browser code has no bearer-token or credential-storage path;
- WorkOS activation, tests, UAT, demo, changelog and traceability are staged.

Formal state: `IN_REVIEW`. Backend/frontend/verifier commands have not produced current-session executable PASS evidence. Official WorkOS authenticated keyboard, screen-reader, restricted-source revoke/re-search and DM sentinel browser UAT remain required before DONE.


### S-10.10.01 Live Workspace Updates — IN_REVIEW

Sprint goal: make authorised channel, thread, DM, unread and Activity changes appear without manual browser reload while preserving the existing server-side permission boundary.

Ready evidence is in `DEFINITION_OF_READY.md`; implementation/acceptance scope is in `docs/planning/increment-26.md` and `UAT/F-10.10.md`.

Implementation staged:

- stable opaque Web-Crypto revision over already-authorised Activity/channel/unread/selected-message/DM structural state;
- same-origin WorkOS live-state route with server-side membership/UUID validation;
- 4-second visible checks, 30-second hidden checks, offline recovery and bounded exponential error backoff;
- `router.refresh()` only on revision change;
- selected-channel root/reaction/reply-count invalidation plus direct-message/Activity/unread refresh;
- open threads re-fetch permitted replies through the existing same-origin route;
- no WebSocket, SSE, Redis, broker, new persistent event store or browser bearer-token path;
- source-contract tests, WorkOS activation wiring, UAT/demo/planning/changelog.

Formal state: `IN_REVIEW`. No executable frontend/verifier PASS is claimed in this session yet. Official WorkOS activation and authenticated two-user <=5-second propagation, revocation, hidden/offline/backoff and accessibility UAT remain required before DONE.


### S-10.09.01 Activity & Notifications Inbox — IN_REVIEW

Implementation staged:

- one personal permission-aware attention queue for mentions, thread replies, unread channel activity, agent approvals, agent completion/failure, project/blocker changes and integration failures;
- reference-only `ActivityNotification` rows: no copied message/DM body, secret, tool argument/result or private evidence excerpt;
- current source permission is rechecked at read time, so restricted-channel/DM/project/agent/integration revocation immediately hides stale references and removes them from unread counts;
- exact source links carry channel/message/thread, DM conversation/message, agent run/step, project/blocker or integration identifiers;
- personal mark-one/mark-all read state plus per-user category preferences;
- concurrency-safe first-read creation of the unique Activity preference row;
- same-origin WorkOS mutation templates and a responsive, keyboard-labelled Activity dock/panel;
- migration branch convergence through `20260918_0026` followed by inbox extension `20260918_0027`;
- backend, frontend source-contract and manual UAT coverage in `backend/tests/test_activity.py`, `backend/tests/test_activity_inbox.py`, `tests/activity-contract.test.mjs` and `UAT/F-10.09.md`.

Formal state: `IN_REVIEW`. Latest GitHub Actions for the branch head still fail before any job step executes, so no Ruff/Pytest/verifier/migration PASS can be claimed. Final DONE also requires real PostgreSQL upgrade/downgrade/forward recovery plus official S-10.04 WorkOS authenticated multi-user desktop/mobile/keyboard UAT.

## Current implementation train — S-02.04 / S-05.02 / S-04.02 / S-07.01 / S-07.02

Project-owner direction on 2026-09-10 allowed implementation to continue without the S-05.01.01 execution gate. On 2026-09-11 the project owner said to proceed into the acceptance phase. Dependency rules remain binding: implementation presence is not a PASS, and a workflow failure before step execution is not a test result.

### S-02.04.01 Meeting/document evidence

Staged now:

- generic governed upload for UTF-8 text/Markdown/CSV/JSON/VTT/SRT plus text-extractable PDF and DOCX;
- immutable SHA-256 source identity, bounded parsing and deterministic overlapping chunks;
- RawEvent -> CanonicalEvent -> Work Graph -> Search projection with source/chunk provenance;
- organisation or restricted visibility using the existing Work Graph resource-grant boundary;
- idempotency, source lifecycle, retention/deletion integration and audit events;
- migration `20260910_0017`, tests, docs and UAT contract.

Formal state: `IN_REVIEW`. No executable test/UAT evidence is claimed.

### S-05.02.01 Ask Brain

Staged now:

- permission-aware Ask Brain retrieval with no-evidence/no-provider-call behaviour;
- source-agnostic RAG, including generic meeting/document evidence through the same Search contract;
- explicit tenant provider/model selection and safe organisation/runtime discovery for normal `ai.use` users;
- prompt-injection boundary, bounded evidence/citation excerpts and an 8,192-token output ceiling;
- exact JSON output contract: unexpected top-level or claim fields fail closed;
- every factual claim must cite one or more server-issued evidence IDs; unknown/malformed citations fail closed;
- two-phase deployed evaluation separating automatic retrieval/security checks from human semantic claim-citation review;
- OQ-005 resolution: OpenAI API + `gpt-5.6-terra` first candidate, conditional on all acceptance gates;
- cache-aware token/cost accounting, request-scoped exact-cost audit and Render staging bootstrap/runbooks;
- generic-evidence and strict-output regression tests written but not executed.

Formal state: `BLOCKED`, because S-05.01.01 is still `IN_REVIEW` and the real provider/eval/performance/frontend acceptance evidence does not exist.

### S-04.02.01 Decision and Blocker Memory

Staged now:

- deterministic explicit-marker candidate extraction from permission-aware Search evidence, including generic meeting/document evidence;
- machine output remains candidate-only with confidence/state/evidence identifiers;
- idempotent extraction and supersession for unreviewed machine candidates;
- human review history is authoritative: reviewed/reopened candidates are not silently superseded or rewritten by later machine extraction;
- review mutation locks the candidate row before state transition to prevent concurrent review races;
- confirm/reject/edit/resolve/reopen history remains immutable and permission-aware;
- regression contracts for generic transcript extraction and human-authority re-extraction are written but not executed.

Formal state: `BLOCKED` until S-05.01.01 receives executable passing verification and this story's own precision/UAT gates run.

### S-07.01.01 Project Command Centre

Staged now:

- explicit `ProjectProgressItem` structured work state/weight model;
- percentage is calculated only from currently visible configured structured work; no configuration returns `null`, never an AI estimate;
- project status is deterministic; unconfirmed blocker candidates cannot mark a project blocked;
- project/work-item visibility uses Work Graph permissions;
- project evidence is discovered via permission-aware Work Graph traversal and intersected again with live permission-aware Search before provenance is returned;
- human-confirmed decisions/blockers and machine candidates are separate response collections;
- progress mutations are audited and arbitrary unlinked work items cannot affect a project;
- project list/detail/progress APIs, migration `20260910_0018`, tests, docs and `UAT/F-07.01.md` are staged.

Formal state: `BLOCKED` because its S-04.02.01 dependency is not DONE and no executable/backend/frontend UAT evidence exists.

### S-07.02.01 Executive Overview

Staged now:

- `audit.read`-gated month-to-date executive overview API;
- full currently visible S-07.01 portfolio with deterministic project status/progress and per-project metric provenance;
- organisation-level deduplicated human-confirmed blockers and decisions with canonical/search/work-graph source IDs and visible project links;
- exact S-06.02 AI request/token/cached-token/known-cost totals plus provider breakdown and explicit incomplete-cost state;
- live enabled budget warnings/exhaustion/incomplete-enforcement math, with Work-Graph-scoped warnings filtered by current node visibility;
- trusted S-06.03 external API activity and active-grant counts plus an audited `/api-registry/usage` drill-down that exposes no secret material;
- external API monetary cost deliberately remains `null` / `not_modeled` because no reviewed API tariff ledger exists; call counts are never converted into money;
- deterministic risks only from project blocked state, budget state, incomplete AI cost and explicit API-cost-model absence;
- no employee productivity/worth/activity ranking and no productivity-score field exists in the API contract;
- backend contract/security tests, `docs/EXECUTIVE_OVERVIEW.md`, Increment 21 planning and `UAT/F-07.02.md` are staged.

Formal state: `BLOCKED`. Its S-07.01.01 and S-06.02.01 dependencies are not DONE, and no executable backend, reconciliation, permission/revocation, frontend or accessibility UAT has run.

## Frontend delivery train — E-10

The product owner clarified on 2026-09-11 that Brain's requested frontend is a Slack/Discord-style company workspace. The earlier single deferred native-chat story did not adequately represent that requirement. `PRODUCT_BACKLOG.md` separates the P0 workspace frontend from P1 native collaboration.

The board WIP rule remains binding. Repository-staged stories that are waiting on external/authenticated acceptance stay `BLOCKED` or `IN_REVIEW` rather than consuming implementation WIP. `S-10.06.02` and `S-10.08.01` have now moved to `IN_REVIEW`; there is no active `IN_PROGRESS` E-10 story until the next backlog/dependency pull is explicitly selected.

### S-10.02.01 Workspace Shell and Navigation — BLOCKED

Staged now:

- permission-aware `/workspace-navigation` read model over Work Graph projects/tracks;
- restricted resource labels are filtered before serialization;
- cross-tenant and restricted-resource regression contracts;
- typed frontend workspace-navigation client;
- role-aware `ProductionWorkspace` that allows normal members into Brain and only gates Company Pulse itself;
- desktop organisation picker plus responsive server-driven organisation switch form;
- Slack/Discord-style workspace rail + navigation sidebar + main work surface + context rail;
- real visible project/track labels and status;
- responsive CSS module, keyboard skip path and focus treatment;
- frontend source-contract tests included in `npm test`;
- `docs/planning/increment-22.md` and `UAT/F-10.02.md`.

Formal state: `BLOCKED` on S-10.04 for real authenticated root/browser execution. Frontend/backend tests and responsive/accessibility UAT are not claimed as passed.

### S-10.03.01 Live Intelligence Surfaces — BLOCKED

Staged now:

- real Project Command Centre progress/status inside the workspace;
- expandable structured work and permission-filtered project evidence;
- human-confirmed decision/blocker views with source provenance identifiers;
- role-gated Executive/Company Pulse without locking normal members out of Brain;
- governed runtime discovery only for roles with `ai.use`;
- citation-first Ask Brain component using only a same-origin endpoint;
- bounded browser error states that do not reflect arbitrary backend/provider detail;
- Ask Brain BFF helper validates request shape and authenticated Brain organisation membership before forwarding;
- `UAT/F-10.03.md` defines live browser/data reconciliation.

Formal state: `BLOCKED`. Ask Brain browser mutation remains deliberately inactive in the current preview root until S-10.04 activates official WorkOS/BFF. No frontend execution/UAT PASS is claimed.

### S-10.04.01 Production WorkOS Auth + BFF — BLOCKED

Repo-side staging now:

- official current Next.js 16 AuthKit contract reviewed;
- official npm installer verifies real package-lock resolution/integrity and never invents package metadata;
- reviewed templates for `authkitProxy()`, `handleAuth()`, `getSignInUrl()`, `AuthKitProvider`, protected `withAuth()` root, `signOut()`, Ask Brain BFF and evidence upload/delete BFF routes;
- guarded activation script requires installed/pinned packages plus WorkOS/Brain environment values before copying templates and running lint/build/tests;
- same-origin BFF routes use server-side `withAuth()`, bounded request validation, membership validation and secret-safe errors;
- evidence upload BFF additionally performs a bounded multipart stream read and preserves the 10 MB backend file contract;
- `UAT/F-10.04.md` and `docs/WORKOS_FRONTEND_ACCEPTANCE.md` remain the authenticated security gates.

Formal state: `BLOCKED`. The current environment cannot obtain the official npm packages/real lockfile, and no authenticated WorkOS browser/session execution has occurred. The active root remains the explicitly labelled preview until this external gate is satisfied.

### S-10.05.01 Governed Files & Evidence Workspace — BLOCKED

Staged now:

- permission-correct evidence workspace read model that applies requested limits after visibility filtering rather than allowing hidden rows to starve the page;
- server-computed `can_delete` capability while FastAPI remains the authoritative deletion boundary;
- backend regressions for hidden-row pagination and uploader/Owner/Admin delete presentation;
- typed evidence-source frontend API plus server-side evidence loading;
- Files & evidence surface embedded in the Brain shell with lifecycle state, source hash, provenance, local filtering and role-aware read-only/upload behavior;
- supported-format guidance matching S-02.04 and no fake OCR/download/folder semantics;
- browser mutations target same-origin BFF only and never receive a reusable backend bearer token;
- reviewed WorkOS templates for bounded multipart upload and governed delete routes;
- two-step deletion confirmation plus safe browser error messages;
- frontend source-contract tests, `docs/planning/increment-23.md` and `UAT/F-10.05.md`.

Still required before review/acceptance:

- execute backend evidence workspace tests and the S-02.04/S-05.01 dependency gates;
- execute frontend lint/build/source-contract tests;
- activate S-10.04 with official WorkOS packages and a genuine generated lockfile;
- run real browser UAT proving upload -> Search/Ask Brain -> delete/revoke disappearance and restricted-source isolation;
- run accessibility/responsive verification.

Formal state: `BLOCKED`, matching the fixed board row. No executable PASS or browser UAT is claimed.

### S-10.06.01 Slack/Discord-quality Brain conversations — IN_REVIEW

Implemented and locally verified on 2026-09-13:

- channel-first workspace layout with personal unread badges;
- same-channel root threads with a responsive, keyboard-closeable thread pane;
- exact permitted-member `@email` resolution and server-resolved mention highlighting;
- five allow-listed, per-user idempotent reactions with aggregate counts;
- atomic per-channel message sequence and monotonic per-user read cursor;
- batched unread summaries with the latest message cursor, including thread replies;
- composite tenant/channel/message foreign keys that reject cross-scope conversation rows;
- visibly distinct agent messages and preserved evidence provenance;
- authenticated same-origin WorkOS route templates for roots, replies, reactions, reads and restricted-channel member changes;
- safe bounded JSON, identifier/role validation and cross-site mutation rejection;
- focused backend tests, frontend source-contract tests, frontend lint/build and PostgreSQL offline migration compilation.

Repository-wide Ruff and all 299 backend tests also pass. The full frontend build/test run reports 12 passed and 1 intentional unauthenticated skip. The delivery verifier was not completed after the product owner directed execution to be skipped; no verifier PASS is claimed.

Formal state: `IN_REVIEW`. The session-open audit found that this story had been pulled without a dedicated Definition-of-Ready record while S-10.01 was still `IN_REVIEW`; that process drift is now recorded in `DEFINITION_OF_READY.md`. No accepted S-10.06.01 scope was silently removed. Final DONE remains blocked on a delivery-verifier PASS, real PostgreSQL upgrade/downgrade exercise, official S-10.04 WorkOS activation and the authenticated desktop/mobile/keyboard UAT in `UAT/F-10.06.md`.

### S-10.06.02 Participant-safe Brain-native direct messages — IN_REVIEW

Implementation staged:

- separate one-to-one `DirectConversation` / `DirectMessage` persistence rather than reusing restricted-channel administration semantics;
- participant-only listing and reads with no Owner/Admin/Executive content override;
- same-organisation exact-email creation, self/cross-tenant/read-only-target rejection and idempotent bounded sends;
- no RawEvent/CanonicalEvent/Work Graph/SearchDocument projection, keeping DMs outside organisation-wide Search/Ask Brain/Decision Memory/Project/Executive surfaces;
- no organisation-wide per-message/per-conversation DM audit records;
- composite `(organization_id, conversation_id)` database foreign key;
- migrations `20260916_0022`, `20260916_0023` and `20260916_0024` for DMs, independent `private_message_days` retention, revocable participant access and monotonic visibility/message sequences;
- row-locked PostgreSQL message-sequence allocation, old-epoch idempotency-key rejection and participant visibility floors that avoid clock-skew/resolution bugs;
- membership removal or messaging-role downgrade revokes that participant's DM access without destroying the other participant's permitted history;
- re-add/re-promotion does not silently revive old DM history; explicit DM re-initiation starts a new visibility epoch;
- legal-hold-safe private-message purge through the existing scheduled governance runner;
- Slack-style DM navigation/panel, history-only counterpart state, exact-email new-DM flow, server-computed bubble ownership and explicit privacy messaging;
- server-validated `dmId` selection and suppression of ambient default-channel context while a DM is active;
- same-origin WorkOS BFF templates with bounded JSON, session/membership revalidation and cross-site rejection;
- backend/frontend regression contracts and `UAT/F-10.06.02.md`.

Formal state: `IN_REVIEW`. The implementation, migrations and acceptance contracts are review-ready, but current-commit Ruff/Pytest/frontend execution, live PostgreSQL `0022/0023/0024` upgrade/downgrade/re-upgrade, unique-sentinel Search/Ask Brain negative test and authenticated WorkOS multi-user browser UAT have not executed. Latest GitHub-hosted Backend CI still failed before any step executed (`steps: null`), so no PASS/DONE evidence exists.

### S-10.07.01 Developer & Agent Workspace — IN_REVIEW

Staged now:

- permission-aware agent run context binding to visible project/channel scope;
- requester-only workspace run read model with revoked-context redaction;
- explicit agent/provider/model/tool/risk identity without provider-secret serialization;
- server-controlled workspace start/advance/approval/cancel paths;
- project-scoped high-risk work-item execution inheriting current project visibility/ACL and verified `CONTAINS` edge;
- current context revalidation before planner/tool cycles and approvals;
- final model output returned ephemerally to the live browser response while durable runtime stores only its hash;
- produced artifacts re-filtered against current Work Graph visibility;
- Developer & Agents panel inside the Brain workspace, plus same-origin WorkOS activation templates and security/source contracts;
- `UAT/F-10.07.md`.

Formal state: `IN_REVIEW`. Implementation is staged, but no new executable PASS, PostgreSQL/browser UAT or real provider/tool safety acceptance is claimed.

### S-10.08.01 Workspace Administration — IN_REVIEW

Implementation staged:

- Owner/Admin-only Admin Center aggregate with members, integrations, AI providers/models and API services/grants;
- safe serialization excludes raw credentials, tokens and secret references;
- member invitation, role change and removal with last-Owner protection and Owner/Admin authority separation;
- membership removal clears organisation resource grants, revokes restricted-channel memberships and revokes dormant DM participation so re-adding a user cannot silently recover stale access;
- integration revoke and AI provider/model lifecycle controls;
- AI provider bootstrap from an empty workspace, governed model creation and in-place provider credential rotation through the configured secret store;
- AI credential creation/rotation share one backend validator with a bounded credential shape and required `api_key`;
- external API service bootstrap plus grant creation, owner/scope/environment changes, enable/disable, credential rotation and revocation through the existing API registry lifecycle;
- transient browser secret entry only: no local/session storage, no server echo, no Admin Center serialization of stored secret values, and forms clear after successful secret submission;
- one typed same-origin admin BFF action boundary with strict discriminated parsing, a bounded 32 KiB JSON body, WorkOS session/membership validation and cross-site rejection;
- grant expiry parsing fails safely in the browser before mutation and is validated again server-side;
- workspace UI controls refresh from authoritative backend state rather than optimistic local authority;
- backend credential-rotation tests, frontend source/security contracts and `UAT/F-10.08.md`.

Formal state: `IN_REVIEW`. The implementation scope is now review-ready, including credential creation/rotation and API grant metadata editing. Current Ruff/Pytest/frontend build/source-contract execution, PostgreSQL-backed admin mutation acceptance, real secret-store smoke and authenticated Owner/Admin/Member WorkOS browser/network UAT have not executed. Latest GitHub-hosted jobs continue to fail before step execution, so no PASS/DONE claim exists.

## Acceptance phase

`S-05.01.01` stays `IN_REVIEW`. Acceptance execution has now started, but the latest branch-head GitHub runs for Backend CI, Delivery Verifier and Release Gate all failed before any workflow step executed; their job step lists were empty. This supplies no pytest/Ruff/verifier result and does not satisfy the gate. The required local and Render verification must still prove tenant isolation, current permission filtering, revocation, provenance and retrieval quality before dependent features can advance to accepted states.

After S-05.01.01 obtains real passing execution evidence, run the dependent executable suites/migrations, real OpenAI/Terra compatibility and cache-aware exact-cost smoke, representative Ask Brain retrieval/RAG evaluation, human citation review, staging performance, decision-memory precision/UAT, project-status permission/revocation UAT, Executive Overview permission/cost/budget/API reconciliation UAT, and the official WorkOS authenticated frontend/manual paths including S-10.05 evidence lifecycle, S-10.06 conversation UAT, participant-safe DM UAT, S-10.07 agent-workspace UAT and S-10.08 admin-governance UAT.

Production quality gates remain: retrieval recall >=90%, zero forbidden evidence exposure/grounding-contract failures, every exact generated claim-citation pair human reviewed, semantic citation correctness >=98%, Decision/Blocker precision >=90% on the agreed representative set, and Ask Brain p95 <10 seconds on the accepted staging runtime.

No new `EVIDENCE` block may be added for these stories and no story may be marked `DONE/PASSED` until its required checks actually execute successfully.
