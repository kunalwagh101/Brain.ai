# Increment 29 — Governed Channel Attachments

Story: `S-10.13.01`

Status: `IN_REVIEW`

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


## Retrospective — 2026-09-19

No accepted S-10.13.01 requirement was cut.

The visible attachment UI was not the hard part. The real engineering work was preserving Brain's existing evidence/security model while bringing files into conversations:

- the implementation reuses EvidenceSource bytes and generic evidence projection instead of creating a second attachment store;
- restricted attachment visibility is resolved from live native-channel membership, while Search/Work Graph grants are extended/removed with the same membership lifecycle;
- the database now enforces organisation-scoped channel and EvidenceSource relationships with composite foreign keys, so cross-tenant linking is impossible even if future service code regresses;
- upload idempotency is bound to channel/visibility scope, and message retry idempotency is preserved across ambiguous network failures without re-uploading successful evidence;
- root and thread composers keep separate pending governed-source state, and in-flight thread/channel navigation is guarded against stale attachment-state races;
- evidence deletion and message retraction remain independent lifecycles: retracting a message hides its cards but does not delete governed evidence; deleting evidence leaves a safe unavailable attachment reference;
- migration downgrade refuses to restore the old non-empty-body constraint while attachment-only message/revision rows exist instead of silently corrupting those rows.

Estimate miss: permission propagation, tenant integrity and failure/retry semantics dominated the work, not upload/rendering.

The story is IN_REVIEW, not DONE. Executable PostgreSQL migration, backend tests, frontend lint/build/source contracts, verifier and official WorkOS multi-user browser UAT are still required.
