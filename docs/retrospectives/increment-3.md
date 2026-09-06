# Increment 3 Retrospective — Integration Framework

## Goal

Create one production-safe external connection lifecycle before Slack/GitHub provider-specific ingestion.

## What worked

- Reused existing tenant/RBAC dependencies instead of introducing connector-specific authorization.
- Chose AWS Secrets Manager because the deployment architecture is already AWS-oriented rather than building custom credential encryption/storage.
- Split engineering-DONE from real-data/manual UAT, so green CI is no longer presented as feature acceptance.
- Designed revocation fail-closed: connection leaves ACTIVE before external secret deletion, preventing continued sync during provider failure.
- Fake AWS/secret-store tests exercise failure paths without needing CI credentials.

## What changed from the initial estimate

- Credential lifecycle required explicit orphan-secret cleanup because secret creation precedes database persistence.
- Revocation needed a `REVOKE_FAILED` state; a simple ACTIVE/REVOKED boolean could not represent a safe partial failure.
- A separate UAT artifact was added because repository automation cannot prove real provider credentials and the actual frontend workflow.

## What was deliberately not pulled

- Slack OAuth/events and GitHub App/webhooks remain separate stories.
- Raw event persistence is not hidden inside this feature; the first connector ingestion slice will require S-03.01.01 explicitly.
- Provider token rotation is not invented generically; Slack/GitHub provider contracts will define rotation/refresh semantics from their real APIs.

## Next planning implication

The next executable vertical slice should combine **S-03.01.01 Raw Event Ingestion** with one first real connector story rather than building a connector that has nowhere durable/idempotent to land events. Slack is the recommended first connector because communication/context is Brain's primary product wedge.
