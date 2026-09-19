# Brain Engineering Demo

A demo section is valid only after its named CI evidence exists. A successful engineering demo does not replace real-data/manual UAT.

## Increment 1 — secure organisation boundary

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
alembic upgrade head
pytest tests/test_auth.py tests/test_organizations.py -q
uvicorn app.main:app --reload
```

With a configured WorkOS environment, a valid user can call `/api/v1/auth/me`, create an organisation and exercise the tenant-safe membership APIs.

## Increment 4 — Slack + raw evidence

Automated evidence command:

```bash
cd backend
pytest -q
```

Expected engineering evidence:

- Slack OAuth state is signed/tamper-evident and expires;
- required Slack scopes exclude direct-message scopes;
- DMs cannot be authorised;
- invalid signatures are rejected before storage;
- authorised signed events persist exact raw bytes and checksum;
- retrying the same event ID does not create another row;
- unauthorised channels are ignored;
- private source ACL membership is stored/updated;
- backfill cursor resumes and replay is deduplicated;
- oversized raw payload is rejected.

For actual feature acceptance, run the real provider and frontend steps in `UAT/F-02.02.md` and `UAT/F-03.01.md`.

## Increment 5 — GitHub + canonical events

Automated evidence command:

```bash
cd backend
pytest -q
```

Expected engineering evidence:

- GitHub webhook HMAC verification is exact-body and tamper-sensitive;
- install state and installation-selection tokens are signed and expiring;
- GitHub cannot be connected through the generic credential endpoint;
- a signed private-repository delivery is persisted/canonicalised exactly once;
- private repository ACL provenance reaches the canonical event;
- backfill cursor is signed, connection-bound, resumable and replay-safe;
- Slack and GitHub both produce the same schema-versioned canonical dimensions;
- unsupported mappings quarantine the raw event without losing source evidence;
- migration/model uniqueness keeps one canonical event per raw event.

GitHub Actions run `34037248953` passed lint and 73 tests. For actual feature acceptance, run `UAT/F-02.03.md` and `UAT/F-03.02.md` with a real GitHub App, realistic Slack/GitHub data and the production frontend.

## Increment 6 — identity resolution

Automated evidence command:

```bash
cd backend
pytest -q
```

Expected engineering evidence:

- repeated Slack/GitHub provider actors reuse the same tenant-scoped source identity;
- canonical retry does not duplicate source identity observations;
- WorkOS authentication identities are not overloaded as source identities;
- unverified email never auto-resolves;
- provider-verified exact email can resolve only an active same-organisation member;
- a matching user in another organisation is not linked;
- Owner/Admin can manually resolve, reassign and unresolve with immutable before/after history;
- normal Members cannot use identity-management endpoints;
- canonical source actor fields remain intact while optional `resolved_user_id` changes;
- existing canonical events can be reconciled into the identity layer;
- timezone normalization keeps first/last-seen ordering portable across database implementations.

GitHub Actions run `34038863067` passed lint and 82 tests. Delivery Verifier run `34038863068` passed before engineering-DONE. For actual acceptance, run `UAT/F-03.03.md` using realistic provider identities and the production admin workflow.

## Increment 7 — typed Work Graph

Automated evidence command:

```bash
cd backend
pytest -q
```

Expected engineering evidence:

- canonical Slack/GitHub evidence projects into typed graph nodes without duplicating on replay;
- source identities and Brain users remain distinct person nodes connected only by the current reversible `resolves_to` relationship;
- GitHub repository evidence produces projects/work items and Slack channel evidence produces tracks;
- every relationship exposes source, explicit verified/inferred state, confidence and provenance;
- unsupported manual person-identity assertions and cross-tenant graph edges are rejected;
- traversal is tenant-scoped and depth-bounded;
- private Slack access is recalculated from current channel membership, so historical ACL provenance cannot keep revoked access alive;
- restricted GitHub evidence requires an explicit resource grant and is not bypassed by Owner/Admin role;
- reconciliation is bounded and idempotent;
- migration `20260906_0008` can be rolled back without deleting the raw/canonical evidence needed to rebuild the graph.

GitHub Actions run `34043847195` passed lint and 89 tests on implementation commit `a97d724416191ec8515f5ed90888321343013cda`. Delivery Verifier run `34043847222` also passed before the DONE-state documentation update. For actual acceptance, run `UAT/F-04.01.md` with realistic Slack/GitHub evidence and the production frontend/manual workflow.

## Increment 8 — permission-aware retrieval

Status: **NOT YET A VALID ENGINEERING DEMO.** The commands are recorded now so they are inspectable, but this section becomes valid only after a named passing CI run is recorded. Current GitHub Actions attempts have failed before runner startup and therefore provide no code-verification evidence.

Commands to run:

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
alembic upgrade head
ruff check app tests migrations
pytest tests/test_search.py tests/test_search_evaluation.py -q
pytest -q
python ../scripts/verify_board.py
python -m app.search_worker --once --batch-size 100
```

Expected engineering evidence:

- cross-tenant search returns zero foreign identifiers/content/provenance;
- public Slack requires current explicit channel authorisation;
- private Slack additionally requires current resolved Slack membership;
- removing Slack membership/authorisation removes search access immediately;
- private/internal GitHub stays hidden without an explicit current grant, including for Owner/Admin;
- inactive integrations and deleted source objects disappear from results while raw/canonical evidence remains;
- keyword results carry source/canonical provenance;
- hybrid semantic retrieval can find labelled synonym evidence on the synthetic evaluation set;
- synthetic Recall@3 is at least 90%;
- an embedding outage degrades explicitly to keyword retrieval;
- embedding failure is retryable and does not duplicate the search projection;
- historical search projection can be reconciled without requiring embeddings;
- migration `20260907_0009` can be downgraded without deleting raw/canonical evidence.

For real acceptance, execute `UAT/F-05.01.md` with realistic Slack/GitHub data, PostgreSQL + pgvector, a real embedding model, measured Recall@10/p95 latency, and the authenticated frontend.

## Increment 9 — decision and blocker memory

Status: **NOT YET A VALID ENGINEERING DEMO.** S-04.02.01 is formally `BLOCKED` on the unverified S-05.01.01 dependency. The latest Increment 9 GitHub Actions attempt also failed before runner startup (`runner_id=0`, no steps), so no automated passing evidence exists yet.

Commands to run after the dependency/runner gate is available:

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
alembic upgrade head
ruff check app tests migrations
pytest tests/test_decision_memory.py tests/test_decision_memory_evaluation.py -q
pytest -q
python ../scripts/verify_board.py
python -m app.search_worker --once --batch-size 100
python -m app.decision_memory_worker --once --batch-size 100
```

Expected engineering evidence:

- explicit decision/blocker markers produce only `candidate` machine state;
- ordinary/tentative hard-negative statements are not promoted to confirmed facts;
- unchanged replay and zero-candidate documents do not create duplicate extraction work;
- public/private Slack and private/internal GitHub candidates obey current source authorisation;
- cross-tenant candidates, excerpts, provenance and review history are never returned;
- integration revocation/source deletion removes candidate visibility without rewriting source/audit evidence;
- confirm/reject/edit/blocker-resolve/reopen transitions are validated and append immutable before/after review history;
- decisions cannot use blocker-only resolve semantics;
- changed extraction supersedes stale unreviewed machine candidates without silently overwriting human-reviewed state;
- same-document PostgreSQL row locking serialises concurrent extraction workers;
- migration `20260907_0010` can be downgraded without deleting raw/canonical/search/work-graph evidence;
- synthetic explicit-marker precision instrumentation is at least 90%, while remaining explicitly non-representative of real production quality.

For real acceptance, execute `UAT/F-04.02.md` with representative labelled company evidence. Decision and blocker precision must each reach the agreed >=90% production threshold, and the actual frontend/manual review workflow must be validated.

## Increment 24 — Slack/Discord-quality Brain conversations

Status: **SAFE AUTOMATED CHECKS PASS; FINAL DEMO PENDING.** The focused and repository-wide checks listed below passed on 2026-09-13. The delivery verifier was not completed by product-owner direction. A verifier PASS, real PostgreSQL migration/recovery exercise and authenticated WorkOS browser demo remain mandatory, so S-10.06.01 is `IN_REVIEW`, not DONE.

Commands you can paste from the repository root:

```bash
python -m venv .venv
.venv/bin/pip install -e "./backend[dev]"
npm ci

cd backend
../.venv/bin/ruff check app tests migrations
../.venv/bin/pytest -q
../.venv/bin/ruff check app/native_chat.py app/native_chat_models.py app/native_conversation.py app/native_conversation_models.py app/routes/native_conversation.py tests/test_native_chat.py tests/test_native_conversation.py tests/test_observability.py migrations/versions/20260912_0020_conversation_ux.py
../.venv/bin/pytest -q tests/test_native_chat.py tests/test_native_conversation.py tests/test_observability.py
../.venv/bin/alembic upgrade head --sql

cd ..
npm run lint
npm test
node --test tests/workspace-contract.test.mjs
```

Expected focused output:

- Ruff: `All checks passed!`;
- full backend: `299 passed`;
- backend: `24 passed`;
- frontend: build complete, `12` passed and `1` intentionally skipped; focused source contracts: `11` passed;
- offline Alembic SQL reaches `20260912_0020` and emits scoped foreign keys plus the sequence backfill;
- delivery verifier: **NOT COMPLETED**; no PASS is claimed.

For the final live demo, start PostgreSQL from `compose.yaml`, set `BRAIN_TEST_DATABASE_URL`, execute upgrade/downgrade/forward recovery, activate the official WorkOS templates, then follow `UAT/F-10.06.md`. Show two users' independent unread state, root-only thread placement, exact permitted mention resolution, idempotent aggregate reactions, agent attribution, restricted-channel revocation and keyboard/mobile behaviour. Do not call the story DONE from the local checks alone.


## Increment 25 — Activity & Notifications Inbox

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.09.01 is `IN_REVIEW`, not DONE.

Commands to run from the repository root:

```bash
python -m venv .venv
.venv/bin/pip install -e "./backend[dev]"
npm ci

cd backend
../.venv/bin/ruff check app tests migrations
../.venv/bin/pytest -q tests/test_activity.py tests/test_activity_inbox.py tests/test_native_conversation.py tests/test_direct_messages.py
../.venv/bin/alembic heads
../.venv/bin/alembic upgrade head
../.venv/bin/alembic downgrade 20260918_0026
../.venv/bin/alembic upgrade head

cd ..
npm run lint
npm run build
node --test tests/activity-contract.test.mjs
python scripts/verify_board.py
```

Expected engineering evidence:

- one Alembic head after the notification-branch merge and Activity inbox extension;
- exact mentions, thread replies, generic unread channel activity, direct messages, agent approval/completion/failure, project/blocker updates and integration failures appear only for currently authorised users;
- restricted/revoked source access removes persisted references and unread counts immediately;
- mark-one and mark-all mutate only the authenticated recipient's currently visible items;
- notification preferences are per-user, boolean-only and suppress presentation without deleting source product state;
- first-read preference creation remains idempotent under a uniqueness race;
- Activity responses contain safe labels/IDs only and no copied message/DM bodies, secrets, agent arguments/results or private evidence excerpts;
- exact deep links carry the channel/message/thread, DM conversation/message, agent run/step, project/blocker or integration identifier;
- browser mutations use same-origin WorkOS BFF routes and browser code has no reusable backend bearer token;
- responsive/keyboard Activity UI passes the source-contract test.

For final product acceptance, activate official S-10.04 WorkOS, run authenticated Owner/Admin/Member multi-user browser UAT from `UAT/F-10.09.md`, exercise restricted-channel and DM revocation, integration failure/recovery, agent approval transitions and preference persistence, and inspect network/browser storage for token/content leakage. Do not call S-10.09.01 DONE until those checks plus the delivery verifier pass.


## Increment 26 — Live workspace updates

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.10.01 is `IN_REVIEW`, not DONE.

Commands from the repository root:

```bash
npm run lint
npm run build
node --test tests/live-updates-contract.test.mjs
node --test tests/*.test.mjs
python scripts/verify_board.py
```

Expected repository evidence:

- the browser live client uses same-origin requests only and contains no bearer-token/browser-storage path;
- visible-tab interval is 4 seconds, hidden-tab interval is 30 seconds, and failures back off to a 30-second ceiling;
- identical server revisions do not trigger `router.refresh()`;
- the live BFF revalidates Brain organisation membership and UUID conversation context;
- the server-side revision excludes message/DM bodies, source excerpts and secrets;
- selected channel message/reply/reaction state, unread state, direct conversations/messages and Activity contribute to the structural revision;
- open threads refresh through the existing same-origin replies route;
- WorkOS activation installs the live route and enables `ProductionWorkspace` live refresh.

Final demo requires official WorkOS activation and two authenticated users. Show a second user's channel message, thread reply, reaction and DM appearing within five seconds without manual reload; show unchanged state causing no refresh storm; hide the tab and inspect slower checks; go offline/reconnect; then revoke restricted-channel and DM access and prove stale content disappears on the next revision. Follow `UAT/F-10.10.md`.


## Increment 27 — Workspace Search & Quick Switcher

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.11.01 is `IN_REVIEW`, not DONE.

Commands from the repository root:

```bash
cd backend
pytest -q tests/test_workspace_search.py tests/test_native_conversation.py
cd ..
npm run lint
npm run build
node --test tests/workspace-search-contract.test.mjs
node --test tests/*.test.mjs
python scripts/verify_board.py
```

Expected engineering evidence:

- Ctrl+K/Cmd+K opens the keyboard-first search dialog;
- empty/local search operates over already-authorised channels, projects, tracks and visible DM counterparts without a remote request;
- >=2-character content search is debounced 250 ms and uses the same-origin WorkOS route;
- the BFF normalises queries to 2–120 characters, requests keyword mode with at most 12 results and bounds excerpts to 280 characters;
- a restricted Brain-native message is searchable while access exists and disappears after channel revocation;
- a unique DM-body sentinel produces zero organisation-wide search results;
- Brain-native results carry exact channel/message deep links and the single-message backend read rechecks current channel access;
- no browser bearer-token/storage credential path exists;
- WorkOS activation installs the search route and preserves the `messageId` page context.

Final demo: use two authenticated users. Search a restricted-channel sentinel as an authorised member, open the exact message, then revoke access and prove the same search no longer returns it. Search a unique DM-body sentinel and prove it never appears remotely. Exercise Ctrl+K/Cmd+K, Escape, focus, mobile layout and screen reader labelling. Follow `UAT/F-10.11.md`.


## Increment 28 — Author-safe Message Lifecycle

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.12.01 is `IN_REVIEW`, not DONE.

Commands from the repository root:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_message_lifecycle.py tests/test_native_chat.py tests/test_native_conversation.py tests/test_data_governance.py
alembic heads
alembic upgrade head
alembic downgrade 20260918_0027
alembic upgrade head
cd ..
npm run lint
npm run build
node --test tests/message-lifecycle-contract.test.mjs
node --test tests/*.test.mjs
python scripts/verify_board.py
```

Expected evidence:

- only the original current human author with current channel write access can edit/retract;
- stale `expected_revision` returns conflict and never overwrites a newer edit;
- every accepted lifecycle mutation snapshots the prior body/hash/evidence IDs and appends a new immutable native RawEvent + CanonicalEvent revision;
- edited Search results cite the new canonical revision while prior SearchDocument versions are retired;
- retraction produces a body/hash/mention/reaction-free API tombstone and all SearchDocument versions remain non-searchable;
- mention reconciliation removes old mentions and materialises valid new mentions without duplicate current Activity;
- retracted messages do not contribute to unread/channel Activity and cannot receive new reactions/replies/edits;
- existing replies below a retracted root remain readable;
- restricted-channel membership removal clears Work Graph grants for both current and historical revision evidence nodes;
- revision plaintext obeys `derived_content_days` and legal hold;
- browser mutations are same-origin, bounded and do not expose reusable bearer tokens;
- S-10.10 live revision changes on edit/retract metadata without hashing or exposing message plaintext.

Final browser demo: with two authenticated users, post/edit/search a unique sentinel, prove the result opens the new canonical-backed current message, trigger a stale edit conflict, retract it, prove Search/Activity/unread no longer surface content, verify existing thread replies remain, then remove a restricted member and confirm no historical revision evidence remains visible. Follow `UAT/F-10.12.md`.


## Increment 29 — Governed Channel Attachments

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.13.01 is `IN_REVIEW`, not DONE.

Commands from the repository root:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_channel_attachments.py tests/test_evidence_ingestion.py tests/test_native_conversation.py tests/test_message_lifecycle.py
alembic heads
alembic upgrade head
alembic downgrade 20260918_0029
alembic upgrade head
cd ..
npm run lint
npm run build
node --test tests/channel-attachments-contract.test.mjs
node --test tests/*.test.mjs
python scripts/verify_board.py
```

Expected engineering evidence:

- channel uploads reuse the existing EvidenceSource/generic-evidence pipeline and create no second file-content store;
- supported files are bounded to 10 MB and at most five source IDs per message/reply;
- file-only messages are accepted while empty messages without attachments are rejected;
- organisation-channel files are organisation-visible; restricted-channel files recheck live membership for Evidence reads and carry their channel ID into SearchDocument;
- member add/remove grants/revokes the attachment Work Graph/Search nodes as part of the existing channel evidence scope;
- database composite foreign keys prevent cross-organisation channel scope or attachment-source relations;
- another tenant, another restricted channel, deleted evidence and idempotency attachment mismatch all fail closed;
- attachment message JSON contains safe metadata only and never file bytes or extracted/chunk text;
- message retraction hides attachment cards but does not delete EvidenceSource; evidence deletion makes existing cards unavailable/deleted without restoring removed content;
- successful uploads survive later message-send failure and the client retries the same payload with the same message idempotency key rather than re-uploading;
- thread and channel pending-file state are separate and in-flight upload navigation cannot bind files into another composer;
- S-10.10 live invalidation observes source ID/status/availability only, not filename/title/content;
- downgrade refuses safely while zero-body attachment-only messages/revisions exist and never auto-deletes evidence content;
- WorkOS activation installs the bounded same-origin attachment multipart route.

Final browser demo: use at least two authenticated users. Upload a unique document in an organisation channel and a restricted channel; send both captioned and file-only messages; prove Search/Ask Brain visibility; add/remove a restricted member and prove Evidence/Search/Work Graph access changes; simulate upload-success/send-failure and retry without duplicate upload/message; retract the message and then separately delete evidence to demonstrate the independent lifecycles. Follow `UAT/F-10.13.md`.


## Increment 30 — Ephemeral Presence & Typing

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.14.01 is `IN_REVIEW`, not DONE.

Commands from the repository root:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_collaboration_presence.py tests/test_native_conversation.py tests/test_direct_messages.py
alembic heads
alembic upgrade head
alembic downgrade 20260918_0030
alembic upgrade head
cd ..
npm run lint
npm run build
node --test tests/collaboration-presence-contract.test.mjs
node --test tests/*.test.mjs
python scripts/verify_board.py
```

Expected engineering evidence:

- one presence row is refreshed per organisation/user rather than appending activity history;
- one typing row is refreshed per user/exact channel or 1:1 DM context;
- presence lease is 75 seconds, typing lease is 8 seconds, and expired rows never appear;
- presence polling is read-only; normal heartbeat/typing writes opportunistically purge stale rows;
- restricted-channel online/typing results use current membership, and revoke removes stale visibility on the next read;
- DM presence/typing is participant-only and role privilege does not create Owner/Admin override;
- normal presence/typing traffic creates no organisation-wide SecurityAuditEvent history;
- API/database state contains IDs/context/expiry only, with no draft text, keystrokes, cursor position, IP, user-agent or exact last-seen history;
- browser heartbeat runs only while visible/online and is 30-second throttled;
- typing refresh is 3-second throttled, requires a focused non-empty composer and best-effort clears on stop/hide/context teardown;
- all browser traffic is same-origin WorkOS BFF traffic; no reusable backend bearer token enters client code;
- migration `20260919_0031` adds/removes only ephemeral lease tables.

Final browser demo: use two authenticated users. Show online presence in an organisation channel, hide one tab and prove expiry, show typing appear/disappear without per-keystroke requests, grant/revoke a restricted-channel member and prove current permission filtering, then open a 1:1 DM and prove only its two participants can observe online/typing state. Inspect network/database fields to confirm no draft content or last-seen history. Follow `UAT/F-10.14.md`.


## Increment 31 — Shared Channel Message Pins

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.15.01 is `IN_REVIEW`, not DONE.

Commands from the repository root:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_channel_pins.py tests/test_native_conversation.py tests/test_message_lifecycle.py
alembic heads
alembic upgrade head
alembic downgrade 20260919_0031
alembic upgrade head
cd ..
npm run lint
npm run build
node --test tests/channel-pins-contract.test.mjs
node --test tests/live-updates-contract.test.mjs
node --test tests/*.test.mjs
python scripts/verify_board.py
```

Expected engineering evidence:

- pin persistence contains only organisation/channel/message reference, pinner ID and timestamp;
- repeated/concurrent pin requests converge to one row;
- readers can list current-channel pins; read-only/revoked/guest/cross-tenant/cross-channel mutations fail closed;
- thread replies can be pinned and reopen their existing root thread;
- agent-authored visible messages can be pinned without changing human edit/retract authority;
- editing a pinned message preserves the same pin and shows current message content;
- retracting a pinned message removes its pin before the lifecycle transaction commits;
- pin list is newest-pin-first and materialises through the existing safe message read model;
- S-10.10 live revision hashes pin ID/message ID/timestamp only, never message body or attachments;
- browser pin/list/unpin uses same-origin WorkOS routes with no reusable bearer token;
- migration `20260919_0032` adds/removes only the pin-reference table.

Final browser demo: use two authenticated users in an organisation and restricted channel. Pin roots and replies, retry a pin, edit a pinned message, pin a visible agent message, revoke a restricted member, remotely pin/unpin and observe live refresh, retract a pinned human message and confirm it disappears from Pins, then open an older root and a pinned reply from the Pins panel. Follow `UAT/F-10.15.md`.


## Increment 32 — Personal Saved Messages

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.16.01 is `IN_REVIEW`, not DONE.

Commands from the repository root:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_saved_messages.py tests/test_native_conversation.py tests/test_message_lifecycle.py
alembic heads
alembic upgrade head
alembic downgrade 20260919_0032
alembic upgrade head
cd ..
npm run lint
npm run build
node --test tests/saved-messages-contract.test.mjs
node --test tests/*.test.mjs
python scripts/verify_board.py
```

Expected engineering evidence:

- saved persistence contains only organisation/channel/message identity, saving user and timestamp;
- repeated/concurrent save requests converge to one user/message row;
- only the authenticated user's saves are returned; Owner/Admin/Executive roles cannot query another user's personal Saved state;
- current read visibility, not write permission, controls Save/Unsave eligibility;
- restricted-channel revocation hides saved content immediately while the content-free row can survive for later regrant;
- thread replies save and reopen through the existing exact message/thread deep link;
- visible agent-authored messages can be saved without changing human edit/retract authority;
- editing a saved message preserves the same save reference and current content materialisation;
- retracting a saved message removes all saved references before lifecycle commit;
- normal Saved list/save/unsave traffic creates no organisation-wide SecurityAuditEvent history;
- browser mutations use same-origin WorkOS routes and no reusable bearer token enters client code;
- migration `20260919_0033` adds/removes only private saved-reference rows.

Final browser demo: use at least two authenticated users plus a restricted channel. Save roots/replies as a read-only member, retry a save, prove another Owner/Admin user sees an empty personal Saved list, revoke restricted access and prove content disappears, restore access and prove the content-free saved reference can return, edit a saved message, retract it, then open saved root/reply deep links. Inspect the organisation audit table to confirm normal Saved activity creates no behavioural audit trail. Follow `UAT/F-10.16.md`.

## Increment 33 — First-Unread Divider & Jump to Unread

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.17.01 is `IN_REVIEW`, not DONE.

Commands from the repository root:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_native_conversation.py tests/test_message_lifecycle.py
cd ..
node --test tests/first-unread-contract.test.mjs tests/workspace-contract.test.mjs tests/workspace-search-contract.test.mjs
npm run lint
npm run build
python scripts/verify_board.py
```

Expected engineering evidence:

- a visible channel's unread summary returns the existing unread count/latest cursor plus the exact first unread message ID;
- the current user's own human-authored messages and retracted messages never become first-unread targets;
- unread count + first target are computed set-wise across visible channels rather than one query per channel;
- opening a channel renders at most one accessible **New messages** divider before the exact first unread root or reply;
- **Jump to unread** focuses the existing divider immediately when the target is already rendered;
- an older root outside the initial window is recovered through the exact permission-aware same-origin message GET;
- a first-unread reply opens its owning thread, including when the thread root has already been retracted but the reply remains valid;
- a target that is itself retracted clears the stale boundary rather than exposing deleted content;
- the existing mark-read cursor remains monotonic and authoritative while the captured open-panel divider survives its router refresh;
- restricted-channel revocation prevents both unread-summary visibility and exact-message recovery;
- browser code receives no reusable bearer token and the feature adds no persistence table or migration.

Final browser demo: use two authenticated WorkOS users. Read a channel as User A, create two roots as User B, reopen as A and prove the divider sits before the first root while the badge clears. Repeat with a thread reply, a reply under a retracted root, and an old first-unread root outside the initial message window. Then revoke A from a restricted channel and prove both the summary and exact jump fail closed. Follow `UAT/F-10.17.md`.

Do not call the story DONE until the commands above and the delivery verifier actually pass and the authenticated UAT evidence is recorded.

## Increment 34 — DM Unread & Resume

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.18.01 is `IN_REVIEW`, not DONE.

Commands from repository root:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_direct_messages.py tests/test_direct_message_epochs.py tests/test_direct_message_unread.py
alembic heads
# with test PostgreSQL configured:
alembic upgrade 20260919_0034
alembic downgrade 20260919_0033
alembic upgrade 20260919_0034
cd ..
node --test tests/direct-message-contract.test.mjs tests/direct-message-unread-contract.test.mjs
npm run lint
npm run build
python scripts/verify_board.py
```

Expected: per-participant unread counts exclude own sends; partial/stale reads remain monotonic; exact first-unread IDs stay inside the current visibility epoch; nonparticipants/revoked users cannot read or mutate private read state; re-initiation cannot resurrect old unread; one accessible DM divider/jump remains visible through the selected conversation's immediate mark-read refresh; browser routes are same-origin and token-free.

Final browser demo follows `UAT/F-10.18.md`. Do not call DONE/PASSED without executed tests, migration round-trip, verifier and authenticated two-user UAT.

## Increment 35 — Conversation History Pagination

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.19.01 is `IN_REVIEW`, not DONE.

Commands:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_native_conversation.py::test_native_root_history_uses_stable_sequence_cursor tests/test_direct_messages.py::test_direct_message_history_uses_sequence_cursor tests/test_direct_message_unread.py
cd ..
node --test tests/conversation-pagination-contract.test.mjs tests/direct-message-unread-contract.test.mjs tests/first-unread-contract.test.mjs
npm run lint
npm run build
python scripts/verify_board.py
```

Expected: channel and DM pages use `sequence < before_sequence`; invalid cursors fail validation; DM pages never cross current visibility floors; no OFFSET queries appear; browser merges pages by ID/sequence while keeping composer/resume state; Load older stops after history exhaustion; same-origin server-session routes expose no reusable browser token.

Final manual acceptance follows `UAT/F-10.19.md`. Do not mark DONE/PASSED without executed evidence.

## Increment 36 — Direct-Message Lifecycle

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.20.01 is `IN_REVIEW`, not DONE.

Commands:

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_direct_messages.py tests/test_direct_message_epochs.py tests/test_direct_message_unread.py tests/test_direct_message_lifecycle.py
alembic heads
# with test PostgreSQL configured:
alembic upgrade 20260919_0035
alembic downgrade 20260919_0034
alembic upgrade 20260919_0035
cd ..
node --test tests/direct-message-contract.test.mjs tests/direct-message-unread-contract.test.mjs tests/conversation-pagination-contract.test.mjs tests/direct-message-lifecycle-contract.test.mjs
npm run lint
npm run build
python scripts/verify_board.py
```

Expected: only the original current-epoch author can edit/retract; stale expected revisions return conflict; retraction emits a safe participant tombstone and disappears from unread attention; no company-wide evidence/search/audit record is created; private revisions cascade under existing private-message retention; nonparticipants and old visibility epochs fail closed; browser mutation stays same-origin and token-free.

Final browser acceptance follows `UAT/F-10.20.md`. Do not mark DONE/PASSED without executed migration/tests/verifier and authenticated lifecycle UAT.

## Increment 37 — Thread History Pagination

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.21.01 is `IN_REVIEW`, not DONE.

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_native_conversation.py::test_thread_reply_history_uses_stable_sequence_cursor
cd ..
node --test tests/thread-pagination-contract.test.mjs tests/conversation-pagination-contract.test.mjs
npm run lint
npm run build
python scripts/verify_board.py
```

Expected: reply pages remain exact-root scoped, use `message_sequence < before_sequence`, never OFFSET, merge without duplicates, survive live refresh and fail closed after permission revocation. Final manual acceptance follows `UAT/F-10.21.md`.

## Increment 38 — Thread Unread & Resume

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.22.01 is `IN_REVIEW`, not DONE.

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_native_conversation.py::test_thread_unread_state_is_independent_monotonic_and_excludes_own_replies tests/test_native_conversation.py::test_retracted_reply_is_removed_from_thread_unread_attention
alembic heads
# with test PostgreSQL configured:
alembic upgrade 20260920_0036
alembic downgrade 20260919_0035
alembic upgrade 20260920_0036
cd ..
node --test tests/thread-unread-contract.test.mjs tests/thread-pagination-contract.test.mjs
npm run lint
npm run build
python scripts/verify_board.py
```

Expected: channel reads do not clear independent thread cursors; own/retracted replies do not count unread; stale reads never move backwards; cross-root read targets fail; first-unread recovery stays same-origin and permission-aware. Final browser acceptance follows `UAT/F-10.22.md`.

## Increment 39 — Participant-Private DM Reactions

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.23.01 is `IN_REVIEW`, not DONE.

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_direct_message_reactions.py tests/test_direct_message_lifecycle.py tests/test_direct_message_unread.py
alembic heads
# with test PostgreSQL configured:
alembic upgrade 20260920_0037
alembic downgrade 20260920_0036
alembic upgrade 20260920_0037
cd ..
node --test tests/direct-message-reaction-contract.test.mjs tests/direct-message-lifecycle-contract.test.mjs
npm run lint
npm run build
python scripts/verify_board.py
```

Expected: reaction PUT/DELETE is participant/current-epoch only and idempotent; read models expose aggregate count + reacted-by-me but no user list; retraction/private retention cascades rows; legal hold blocks purge; no company-wide evidence/search/audit projection appears; browser mutation stays same-origin and token-free. Final browser acceptance follows `UAT/F-10.23.md`.

## Increment 40 — Workspace Teams

Status: **IMPLEMENTATION STAGED; EXECUTABLE ACCEPTANCE PENDING.** S-10.24.01 is `IN_REVIEW`, not DONE.

```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_native_workspace.py
alembic heads
# with test PostgreSQL configured:
alembic upgrade 20260920_0038
alembic downgrade 20260920_0037
alembic upgrade 20260920_0038
cd ..
node --test tests/native-teams-contract.test.mjs
npm run lint
npm run build
python scripts/verify_board.py
```

Expected: Teams are revisioned organisation metadata; stale writes conflict; creator/Owner/Admin authority is enforced; Guest/cross-tenant mutations fail; Team lifecycle changes no NativeChannel or ResourceGrant state; browser writes stay same-origin. Final manual acceptance follows `UAT/F-10.24.md`.
