# Increment 4 Retrospective — Slack + Raw Ingestion

## Goal

Accept authorised Slack activity as durable, replay-safe, permission-labelled raw evidence without ingesting DMs.

## What worked

- Building Slack and raw ingestion as one vertical slice prevented a connector that had nowhere trustworthy to persist evidence.
- Reusing the existing IntegrationConnection, SecretStore and RBAC paths avoided duplicate credential/permission architecture.
- Standard-library HMAC/JSON/urllib were sufficient for the current Slack boundary; no Slack SDK was needed.
- Exact webhook bytes are preserved, so request provenance is not lost before later canonicalisation.
- CI caught three style violations before tests; those were corrected rather than weakening lint.
- The final implementation run passed all 62 backend tests and the delivery verifier.

## What changed during implementation

- The first OAuth callback signature would have made Slack's optional `error` query parameter required. A route audit caught it before PR verification; the callback was corrected.
- The initial Slack route grew too broad. It was split into OAuth, channel-admin and webhook modules while retaining one public router, which keeps the security-critical webhook path easier to audit.

## What was deliberately not added

- SQS/Redis queue: PostgreSQL is sufficient as the durable raw boundary until S-03.02 introduces actual downstream canonical processing requirements.
- Slack SDK: current calls are small and stable enough for standard HTTP; add a dependency only if provider surface/error handling materially grows.
- DM ingestion: prohibited by the current privacy decision.
- Canonical events/embeddings/LLM enrichment: belong to later backlog IDs and would blur the raw-evidence boundary.

## Estimate/scope lesson

The vertical slice was larger than a connector-only estimate because real Slack ingestion requires OAuth, request authentication, permission mapping, backfill and persistence together. Keeping WIP at two linked stories was appropriate; splitting those layers into separate unfinished increments would have produced unusable intermediate states.

## Acceptance status

Engineering verification is complete. Real Slack/data UAT and frontend/manual UAT are still pending and are tracked in `UAT/F-02.02.md` and `UAT/F-03.01.md`.
