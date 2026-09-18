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
