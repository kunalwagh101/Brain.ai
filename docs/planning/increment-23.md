# Increment 23 — Governed Files & Evidence Workspace

## Goal

Ship the Brain workspace surface for S-02.04 evidence without bypassing the existing permission, provenance, deletion or WorkOS boundaries.

## Story

**S-10.05.01 — Upload, browse and inspect governed documents/transcripts from the workspace**

Priority: **P0**  
Formal implementation state: **IN_PROGRESS**  
Acceptance state: **PENDING**

## Why this is next

S-10.02 Workspace Shell and S-10.03 Live Intelligence have their repository implementation staged, but real browser acceptance is gated by S-10.04 official WorkOS/AuthKit activation. Opening another WorkOS-dependent acceptance task would consume WIP without producing executable progress.

S-10.05 can still advance materially because its backend evidence lifecycle already exists in S-02.04. The increment therefore builds the real evidence read model, UI, same-origin mutation contracts and UAT now, while preserving the rule that authenticated browser acceptance remains blocked until S-10.04 is activated.

## Vertical slice

### Backend read-model hardening

- evidence workspace listing must return up to the requested number of **visible** sources, not apply `LIMIT` before restricted-source filtering;
- hidden restricted rows must not starve a visible page or leak through counts/metadata;
- evidence responses expose a server-computed `can_delete` capability so the frontend does not reproduce ownership/role rules;
- deletion authority remains enforced by FastAPI regardless of the UI capability flag;
- no raw content/download endpoint is added merely for convenience.

### Server-side frontend boundary

- typed evidence-source contract;
- authenticated server-side list call through `BRAIN_API_BASE_URL`;
- organisation selection is resolved from current Brain memberships before evidence is loaded;
- Owner/Admin/Manager/Member may be presented upload controls; backend remains authoritative;
- Executive/Guest remain read-only where their current role permits evidence read.

### Workspace UI

- real Files & evidence surface inside the existing Brain shell;
- source title, filename, kind, size, lifecycle status, visibility, chunks and timestamps;
- SHA-256, evidence-source ID, integration ID and uploader/source provenance;
- client-side filtering of already-authorised server data only;
- supported-format guidance matching S-02.04 exactly;
- explicit read-only state while the authenticated BFF is unavailable;
- two-step delete confirmation;
- no fake OCR, preview/download, folder hierarchy or collaboration semantics.

### Same-origin evidence BFF

Reviewed WorkOS activation templates stage:

- `POST /api/brain/organizations/{organizationId}/evidence/uploads`;
- `DELETE /api/brain/organizations/{organizationId}/evidence/{sourceId}`;
- server-side `withAuth()` access token only;
- current Brain membership validation before FastAPI mutation authority;
- writable-role early rejection without replacing FastAPI authorisation;
- multipart Content-Type/idempotency validation;
- 10 MB file contract and 10.5 MB bounded multipart body;
- bounded stream read before forwarding;
- safe status/error mapping with `Cache-Control: no-store`;
- no WorkOS/FastAPI bearer token in browser code.

## Explicit non-goals

- Browser-direct FastAPI uploads using a reusable bearer token.
- A new object-storage system or presigned-upload architecture without a measured need.
- Raw evidence download endpoints.
- OCR/audio/video transcription.
- Folder/Drive clone behavior.
- User-created arbitrary ACL editing; current S-02.04 organisation/restricted policy remains authoritative.
- Treating source metadata as proof that Search/Ask Brain acceptance passed.

## Verification staged

Backend regression contracts cover:

- hidden restricted evidence cannot consume the requested visible list limit;
- uploader/Owner/Admin delete capability is represented server-side;
- unrelated readers do not receive delete capability;
- deleted sources return `can_delete=false`.

Frontend source contracts cover:

- production workspace loads evidence from FastAPI;
- evidence UI uses only same-origin browser mutations;
- no browser bearer-token/localStorage/sessionStorage path exists;
- WorkOS activation contains bounded evidence upload and delete BFF templates.

These tests are written/staged, not claimed as executed.

## Acceptance dependency

Final S-10.05 browser acceptance depends on:

1. S-02.04 deployed/migrated evidence lifecycle;
2. S-05.01 executable permission-aware retrieval acceptance;
3. S-10.04 official AuthKit package install, genuine lockfile, authenticated root/BFF activation;
4. real UAT in `UAT/F-10.05.md` proving upload -> evidence projection -> Search/Ask Brain -> delete/revoke disappearance.

No DONE/PASSED state or EVIDENCE block is allowed from repository presence alone.