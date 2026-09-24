# Increment 24 — Activity & Notification Center

Story: `S-10.09.01`

Status: `IN_REVIEW`

## Outcome

Give every Brain user one permission-aware attention queue across collaboration surfaces without copying restricted/private content into a second data store.

## First vertical slice

- exact mentions;
- thread replies;
- reactions to the user's messages;
- Brain-native direct messages;
- per-user unread/read state;
- mark one / mark all read;
- global Activity dock/drawer with unread badge;
- deep links back to the authorised channel/DM;
- same-origin WorkOS mutation routes.

## Security model

`ActivityNotification` is reference-only. It stores recipient, actor, event kind, resource/context identifiers, dedupe key and read timestamps. It intentionally stores no message body, preview, excerpt or copied DM content.

Every response dereferences the source and re-runs the current access rule:

- native-channel events use current channel visibility/membership;
- DM events require current participant state, current visibility epoch and current native-messaging capability;
- a revoked/hidden source remains absent even if a notification row was materialized earlier.

No privileged-role override is introduced for DMs.

## Materialization strategy

Activity materializes recent notifications idempotently from authoritative collaboration, agent, project/blocker and integration state. This avoids coupling mature mutation transactions to a second notification write path. Dedupe keys make repeated reads safe, and default preference creation recovers from the unique-row race on concurrent first reads.

A background projector/event-driven path may replace or augment this later without changing the persisted notification contract.

## Deliberate boundaries

- no push/email/mobile notifications in this slice;
- no copied message previews;
- no organisation-wide notification feed;
- no notification-based permission bypass;
- agent approval, completion/failure, project/blocker and integration-failure events are now included through current-permission rechecking;
- Activity is a personal attention queue, not employee-monitoring telemetry.

## Acceptance

See `UAT/F-10.09.md` and `backend/tests/test_activity.py`.

No DONE/PASS claim is valid until focused backend/frontend tests, PostgreSQL migration round-trip, official WorkOS activation and authenticated multi-user browser UAT execute successfully.


## Retrospective — 2026-09-18

No accepted S-10.09.01 requirement was cut. The implementation reuses existing collaboration, agent, project and integration sources instead of introducing an event bus or a second content store.

The main hidden complexity was migration convergence: workspace notifications and Activity had both used revision number `0025`. The permanent fix preserves both immutable parent migrations, merges them at `20260918_0026`, and applies the unified inbox extension at `20260918_0027`.

Static review also found a first-read race in default Activity preference creation. The code now catches the unique-constraint collision and re-reads the winner, matching the inbox's idempotent materialisation model.

The story remains `IN_REVIEW` because current GitHub-hosted jobs fail before step execution and real PostgreSQL/WorkOS/browser acceptance has not run. Repository presence is not converted into a PASS.

## CHECK closure work order — 2026-09-24

Mode: **CHECK**. Role: **Senior full-stack engineer / systems architect, architect tier**. This is verification/closure work for the already-implemented Activity slice.

### Work order — S-10.09.01 Activity & Notifications

**GOAL** — verify one personal, permission-aware attention queue with exact authorised deep links, personal read state/preferences, reference-only persistence and no copied private/secret content.

**FILES UNDER REVIEW**
- `backend/app/activity.py`
- `backend/app/activity_inbox.py`
- `backend/app/activity_models.py`
- `backend/app/routes/activity.py`
- migrations `20260918_0025`, `20260918_0026`, `20260918_0027`
- `backend/tests/test_activity.py`
- `backend/tests/test_activity_inbox.py`
- `app/activity-api.ts`
- `app/activity-bff.ts`
- `app/activity-panel.tsx`
- `app/activity-dock.tsx`
- `tests/activity-contract.test.mjs`
- `UAT/F-10.09.md`

**DO NOT TOUCH** — S-10.06 channel/DM privacy semantics, S-08.01 agent policy, S-07.01 project-status meaning, S-10.04 WorkOS session design, or notification source objects merely to make Activity tests pass.

**INTERFACES** — preserve reference-only `ActivityNotification`/preference semantics, current-permission materialisation, exact source links, recipient-scoped mark-one/mark-all, boolean preference updates, and same-origin WorkOS mutations.

**TEST**
```bash
cd backend
pytest -q tests/test_activity.py tests/test_activity_inbox.py tests/test_native_conversation.py tests/test_direct_messages.py
cd ..
node --test tests/activity-contract.test.mjs
```

**MIGRATION / FULL REGRESSION**
```bash
cd backend
alembic heads
alembic upgrade head
alembic downgrade 20260918_0026
alembic upgrade head
ruff check app tests migrations
pytest -q
cd ..
npm run build
node --test tests/*.test.mjs
python scripts/verify_board.py
```

**DONE WHEN** — automated checks and migration recovery pass, S-10.07/S-10.08 and other upstream contracts are satisfied, and authenticated multi-user WorkOS UAT in `UAT/F-10.09.md` passes. If the external WorkOS/UAT dependency or S-07.01 remains unresolved, leave this story non-DONE and name the blocker.
