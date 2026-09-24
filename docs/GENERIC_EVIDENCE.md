# Generic meeting/document evidence

Story: `S-02.04.01`

## Decision

OQ-004 selects a Brain-managed generic file/transcript upload adapter as the first meeting/document source. Provider-specific Google Drive, Loom, Zoom/Meet or similar connectors are future adapters and must feed the same governed evidence contract.

The first adapter supports:

- UTF-8 text, Markdown, CSV, JSON, VTT and SRT;
- text-extractable PDF;
- DOCX paragraphs and table cells.

OCR, scanned-image extraction, audio/video transcription and external-provider synchronization are out of scope for this first adapter. They require their own security/data-policy and performance review.

## Data flow

`multipart upload -> EvidenceSource -> RawEvent chunks -> CanonicalEvent -> Work Graph evidence nodes -> SearchDocument -> Search / Ask Brain / decision-memory consumers`

The original upload is retained in `EvidenceSource.raw_content` while the source is active. Its SHA-256, byte count, filename, media type, kind and uploader are durable metadata. Extracted chunks are immutable-addressed through both source and chunk SHA-256 values.

The generic adapter uses one Brain-managed `IntegrationConnection` per organisation (`provider=generic_upload`). No credential is required or stored for that connection. This preserves the same source lifecycle contract used by Search: if the connection is no longer `ACTIVE`, its derived evidence is no longer returned.

## Limits and parser safety

- upload bytes: maximum 10 MB;
- extracted text: maximum 1,000,000 characters;
- search chunk target: 6,000 characters with 500-character overlap;
- PDF: maximum 1,000 pages and encrypted PDFs are rejected;
- DOCX: maximum 10,000 ZIP entries and 50 MB total uncompressed size;
- unsupported binary formats fail closed instead of being guessed as text.

The service never performs OCR as a hidden fallback. A file with no extractable text fails explicitly.

## Permission model

`organization` evidence uses the organisation-wide Search visibility already implemented by S-05.01.01.

`restricted` evidence is not made organisation-wide. Each generated Work Graph evidence node receives an existing `work_graph.node` WRITE grant for the uploader. Search therefore uses its existing resource-grant authorization predicate before returning content. Brain does not introduce a parallel document ACL engine.

Metadata reads follow the same rule: restricted sources are returned only to users listed in the source ACL. Owner/Admin role alone does not silently widen a restricted source's read visibility. Organisation Owner/Admin can delete a source through the governed mutation path; other users may delete only evidence they created.

## Idempotency and failure behavior

Clients may provide `Idempotency-Key`. Replaying the same key for the same active kind/content returns the same source. Reusing the key for different content, a different kind or a non-active prior source returns a conflict.

Extraction is completed before the source is created, so unsupported/malformed content does not create a source row. Once a source exists, processing failures move it to `failed` with a bounded error code. Raw provider errors/content are not surfaced through metadata APIs.

## Deletion and revocation

Deleting one uploaded source uses the existing F-09.02 `SOURCE_OBJECT` deletion machinery. All raw/canonical/search derivatives for that source locator are removed using the source's stable UUID. Only after the governed deletion completes is the original `raw_content` cleared and the source marked `deleted`.

The operation observes organisation legal hold through the existing data-governance service. The evidence-source row then retains only non-content audit metadata such as hash, size, kind and timestamps.

Revoking/disabling the generic integration connection removes all of that connection's content from Search because the common Search base query requires `IntegrationConnection.status == active`.

## Search/rebuild contract

Upload processing writes a fully populated `SearchDocument` for every canonical chunk. If a concurrent generic search projection has already created that row, ingestion overwrites it from the immutable chunk payload and resets embedding state rather than leaving an empty derived document.

The canonical event also carries the chunk text and immutable source/chunk provenance in `event_metadata`, so a future provider-neutral full search rebuild can reproduce the generic projection without reading the original binary. The generic adapter remains responsible for its provider-specific extraction semantics.

## Security notes

- No user-supplied path is used for filesystem access.
- The filename is reduced to a basename before persistence.
- Original bytes are never returned by the metadata API.
- Search authorization occurs before content return through the existing S-05.01 boundary.
- Audits contain hashes/metadata only, not document text.
- Restricted evidence uses existing resource grants.
- Deleted source bytes are cleared only after governed derivative deletion succeeds.

## Verification status

S-02.04.01 is engineering-DONE on verified branch commit `8be45dd4d96a87d9fa5a3cf9a385f8cd3ca6349f`. Backend CI `35930622742` passed Ruff and all 385 backend tests; Delivery Verifier `35930622825` passed; Release Gate `35930622874` passed PostgreSQL migration rollback/forward recovery, backup/restore, frontend verification, production image build and readiness smoke. Representative-file/deployed/manual UAT remains `UAT_PENDING`, so the feature is not externally PASSED/accepted.
