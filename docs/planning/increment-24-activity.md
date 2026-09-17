# Increment 24 — Activity & Notification Center

Story: `S-10.09.01`

Status: `IN_PROGRESS`

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

The first slice materializes recent notifications idempotently when Activity is read from authoritative collaboration tables. This avoids coupling four mature message mutation transactions to a new notification write path. Dedupe keys make repeated reads safe.

A background projector/event-driven path may replace or augment this later without changing the persisted notification contract.

## Deliberate boundaries

- no push/email/mobile notifications in this slice;
- no copied message previews;
- no organisation-wide notification feed;
- no notification-based permission bypass;
- `agent_approval` is reserved in the schema but not accepted until its agent-run/approval access contract is implemented;
- Activity is a personal attention queue, not employee-monitoring telemetry.

## Acceptance

See `UAT/F-10.09.md` and `backend/tests/test_activity.py`.

No DONE/PASS claim is valid until focused backend/frontend tests, PostgreSQL migration round-trip, official WorkOS activation and authenticated multi-user browser UAT execute successfully.
