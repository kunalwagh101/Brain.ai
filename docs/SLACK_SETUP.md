# Slack Connector Setup

Brain uses Slack OAuth v2, signed Events API requests and explicit per-channel authorisation.
Direct messages and multi-person DMs are intentionally excluded from the MVP.

## Slack app configuration

Configure these bot scopes:

- `channels:read`
- `channels:history`
- `groups:read`
- `groups:history`

Do not request `im:*` or `mpim:*` scopes for the production MVP.

Configure the OAuth redirect URL to the value of `BRAIN_SLACK_REDIRECT_URI`, for example:

`https://api.brain.example.com/api/v1/integrations/slack/oauth/callback`

Configure the Events API request URL:

`https://api.brain.example.com/api/v1/webhooks/slack/events`

Subscribe the bot to:

- `message.channels`
- `message.groups`
- `member_joined_channel`
- `member_left_channel`

Slack signs every request. Brain verifies the raw body, timestamp and HMAC signature before parsing JSON. Requests more than five minutes old are rejected.

## Installation flow

1. An owner/admin calls `GET /api/v1/organizations/{org_id}/integrations/slack/install`.
2. The frontend redirects to the returned Slack authorisation URL.
3. Slack redirects to Brain's OAuth callback.
4. Brain verifies the signed, expiring OAuth state, exchanges the code and stores only the bot token in AWS Secrets Manager.
5. PostgreSQL stores the secret reference, workspace ID, scopes and connection metadata.

## Channel authorisation

1. List accessible channels using `GET /api/v1/organizations/{org_id}/integrations/{connection_id}/slack/channels`.
2. The Brain Slack app must be a member of a channel before it can be authorised for ingestion.
3. Explicitly authorise a channel with `POST .../slack/channels/{channel_id}/authorize`.
4. Private-channel membership IDs are captured as source ACL evidence and updated from membership events.
5. Removing the authorisation immediately prevents new events for that channel from being stored.

## Backfill

`POST .../slack/channels/{channel_id}/backfill` fetches one cursor page at a time. The endpoint caps each history page at 15 messages so it remains compatible with restrictive Slack history rate limits. The channel row stores its own cursor and completion state, so repeated calls resume safely. `reset=true` intentionally replays history; raw-event idempotency prevents duplicate rows.

## Raw evidence boundary

Every accepted Slack event stores:

- organisation and integration connection
- Slack event ID (or deterministic backfill ID)
- exact webhook bytes for live events
- SHA-256 payload checksum
- source timestamp and delivery kind
- public/private visibility
- private-channel Slack member IDs at ingestion time
- processing status for the later canonical-event worker

Slack retries are safe because `(integration_connection_id, source_event_id)` is unique.
