# Increment 29 — Governed Channel Attachments

Story: `S-10.13.01`

Status: `IN_PROGRESS`

## Sprint goal

Let Brain users share governed documents/transcripts directly in native channels and threads without creating a second file store or weakening restricted-channel permissions.

## Vertical slice

A current channel writer uploads up to five already-supported evidence files from the composer. Brain creates normal EvidenceSource records through the existing bounded ingestion path, scopes restricted uploads to the selected channel, and links source IDs to a root/reply. Conversation reads return safe attachment metadata only. Search/Ask Brain use the same evidence projection. Restricted access follows live channel membership.

## Reuse

Reuse EvidenceSource, generic evidence ingestion, Work Graph/Search projections, native-channel membership, ResourceGrant, existing WorkOS evidence multipart limits, native message BFF/UI and live refresh. No new object storage, OCR/media processor, search index or attachment-content table.

## Explicit non-scope

No arbitrary image/video/audio binary support, no native DM attachments, no inline media preview, no per-attachment detach mutation and no automatic evidence deletion when a message is retracted.

## Acceptance truth

Repository implementation can reach `IN_REVIEW`. Final DONE requires PostgreSQL upgrade/downgrade/re-upgrade, backend/file-permission tests, frontend lint/build/source contracts, verifier and authenticated two-user WorkOS browser UAT.
