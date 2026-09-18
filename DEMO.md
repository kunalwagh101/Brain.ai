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
