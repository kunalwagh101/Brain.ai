# Increment 19 — S-02.04.01 Generic meeting/document evidence

Target branch: `increment-10-ai-provider-gateway`. No new branch is created.

## Goal

A permitted Brain user can upload a meeting transcript or document and have it become permission-labelled, provenance-preserving company evidence that Search and later intelligence features can consume. Deletion/revocation must remove it from retrieval without creating a separate ACL or governance system.

## Ready decision

Core dependencies S-02.01.01 and S-03.01.01 are engineering-DONE. OQ-004 is resolved to a generic Brain-managed upload adapter before any vendor-specific meeting/document connector.

The story can be implemented now. It cannot be marked engineering-DONE in this pass because the project owner explicitly deferred the current executable pytest/Render verification cycle.

## Acceptance mapping

1. **Immutable-addressed source** — original bytes are stored with SHA-256, byte size, media type, filename and source UUID. No source-content update route exists.
2. **Permission-labelled** — each source is `organization` or `restricted`; restricted chunks reuse existing Work Graph resource grants rather than a new ACL engine.
3. **Chunkable/searchable** — supported text-bearing files are extracted deterministically, chunked and projected into RawEvent, CanonicalEvent, Work Graph and SearchDocument records.
4. **Provenance** — canonical/search evidence carries source ID/hash, chunk hash/index/count, filename/media type and raw/integration identifiers.
5. **Deletion/revocation** — source delete reuses F-09.02 source-object deletion and clears original active bytes after derivative deletion; non-ACTIVE integration state removes evidence from Search.
6. **Fail closed** — unsupported, encrypted or oversized inputs are rejected; no OCR/transcription is guessed; restricted metadata is not returned to users without access.

## Security/data decisions

- No user-provided filename is used as a filesystem path.
- Upload cap is 10 MB; extracted text is capped at 1,000,000 characters.
- PDF count is capped and encrypted PDFs are rejected.
- DOCX ZIP expansion and entry counts are bounded before parser use.
- Raw document bytes are never returned by public metadata APIs.
- Audits store metadata/hashes, not evidence text.
- Organisation legal hold is honored by the deletion path.
- Provider-specific OAuth, OCR and audio/video transcription remain out of scope and require separate review.

## Tasks

- T-02.04.01.a Evidence-source schema/migration — **STAGED**
- T-02.04.01.b Safe text/PDF/DOCX extraction and deterministic chunking — **STAGED**
- T-02.04.01.c Generic managed integration + Raw/Canonical/Work Graph/Search projection — **STAGED**
- T-02.04.01.d Organisation/restricted authorization and idempotency — **STAGED**
- T-02.04.01.e Governed physical source-object deletion/revocation behavior — **STAGED**
- T-02.04.01.f Upload/list/read/delete API — **STAGED**
- T-02.04.01.g Security/regression tests — **STAGED, NOT EXECUTED**
- T-02.04.01.h Operator/security/UAT documentation — **STAGED**
- T-02.04.01.i Execute Ruff/Pytest/migration/verifier and representative deployed UAT — **DEFERRED BY PROJECT OWNER**

## Final state for this pass

`IN_REVIEW`, not `DONE`. No test, migration, deployment, parser-quality or real-file acceptance result is claimed until the named executable and manual UAT gates run.

## Verification work order — 2026-09-24

Mode: **CHECK** — implementation already exists; this pass verifies and closes engineering evidence only.

Role: **Senior full-stack engineer / systems architect**. Operating tier: **architect**.

Scope:
- verify the existing generic meeting/document evidence vertical slice against its accepted backlog contract;
- do not add provider-specific connectors, OCR, audio/video transcription or new ACL semantics;
- keep realistic deployed/manual acceptance as `UAT_PENDING`.

Files under review:
- `backend/app/evidence_ingestion.py`
- `backend/app/evidence_models.py`
- `backend/app/routes/evidence.py`
- `backend/migrations/versions/20260910_0017_generic_evidence_sources.py`
- `backend/tests/test_evidence_ingestion.py`
- `backend/tests/test_ask_brain_generic_evidence.py`
- `backend/tests/test_decision_memory_generic_evidence.py`
- `docs/GENERIC_EVIDENCE.md`
- `UAT/F-02.04.md`

Required verification:
```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_evidence_ingestion.py tests/test_ask_brain_generic_evidence.py tests/test_decision_memory_generic_evidence.py
pytest -q
cd ..
python scripts/verify_board.py
```

Release evidence must also exercise PostgreSQL migration upgrade/downgrade/forward recovery. A green automated run may support engineering `DONE`; it must not be presented as deployed/manual UAT.

