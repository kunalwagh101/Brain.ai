# GitHub App production setup

Brain integrates GitHub through a GitHub App. Do not use personal access tokens or the generic integration credential endpoint for GitHub.

## Required app configuration

Set the GitHub App callback URL to the deployed Brain API callback:

`https://<brain-api>/api/v1/integrations/github/oauth/callback`

Set the webhook URL to:

`https://<brain-api>/api/v1/webhooks/github/events`

Subscribe only to the engineering events Brain currently supports:

- push
- pull_request
- issues
- deployment
- deployment_status
- workflow_run
- repository

Grant the minimum read permissions needed for the selected repositories and the backfill APIs. Start with repository metadata and contents read; add pull requests, issues, deployments/actions permissions only where GitHub requires them for the configured events/backfill endpoints. Do not grant write permissions for this read-only ingestion increment.

## Environment contract

Non-secret GitHub App identity/configuration:

- `BRAIN_GITHUB_APP_ID`
- `BRAIN_GITHUB_APP_SLUG`
- `BRAIN_GITHUB_CLIENT_ID`
- `BRAIN_GITHUB_CALLBACK_URL`
- `BRAIN_GITHUB_APP_SECRET_REF`

The secret reference must point to the configured production secrets backend. The referenced secret contains:

- `private_key_pem`
- `client_secret`
- `webhook_secret`

Do not commit those values or put them in PostgreSQL.

## Authentication model

1. A Brain Owner/Admin starts GitHub installation from the organisation-scoped install endpoint.
2. Brain signs a short-lived state token binding Brain organisation + user.
3. GitHub OAuth proves which installations that GitHub user can access.
4. Brain returns signed, expiring installation-selection tokens.
5. When the user selects one installation, Brain re-fetches that installation as the GitHub App and verifies installation ID, account ID/login, and app ID before persisting it.
6. The generic integration endpoint rejects `provider=github`, so the verification flow cannot be bypassed with manually supplied credentials.
7. Brain does not persist installation access tokens. It creates short-lived installation tokens only when GitHub API/backfill work runs.

## Webhook security

Brain verifies `X-Hub-Signature-256` against the exact raw request body using the GitHub App webhook secret and constant-time comparison before parsing JSON.

`X-GitHub-Delivery` is the source event ID. Re-delivery of the same delivery ID for the same integration is idempotent.

Unsupported events are ignored at the route boundary. Supported events are persisted as raw evidence first and then canonicalised. A mapping failure quarantines the raw event instead of dropping it.

## Repository permissions and ACL evidence

Public repositories are stored as `public_repository` and require no repository ACL marker.

Private/internal repositories carry a source ACL marker in the form:

`github:repository:<repository_id>`

This marker is evidence for the later permission-aware retrieval layer. It must not be treated as sufficient authorisation by itself until GitHub user/team identity and repository membership resolution are implemented.

## Backfill

The backfill endpoint walks repositories deterministically and then processes:

1. repository metadata
2. commits
3. pull requests
4. issues
5. deployments

The cursor is HMAC-signed, connection-bound and versioned. Replaying a cursor is safe because each raw source item has a deterministic source ID and each raw event can produce at most one canonical event.

## Deployment order

1. Create/update the GitHub App and its least-privilege permissions.
2. Store GitHub App secrets in the production secrets manager.
3. Set the five `BRAIN_GITHUB_*` configuration variables.
4. Apply Alembic migration `20260906_0006`.
5. Deploy the backend.
6. Confirm `/health/live` and `/health/ready`.
7. Install the app into a non-production/test GitHub organisation first.
8. Perform `UAT/F-02.03.md` and `UAT/F-03.02.md`.

## Rollback

Before downgrading migration `20260906_0006`, stop GitHub/Slack ingestion and any canonicalisation workers. The downgrade removes canonical events and GitHub provider metadata added by this increment; raw events remain the recovery evidence. Export any canonical records needed for investigation before rollback.
