# Increment 8 — Permission-Aware Retrieval

Story: `S-05.01.01` / Feature: `F-05.01` / Epic value: `E-05`

## Problem and baseline

Brain already captures authorised Slack/GitHub activity, normalises it into canonical evidence, resolves identities and projects a tenant-safe Work Graph. It still lacks a retrieval layer that can find that evidence safely.

AI is not needed for the security boundary or keyword baseline. Those stay deterministic. AI-style embeddings are justified only for semantic similarity where exact words differ.

Baseline: PostgreSQL full-text/keyword retrieval over a rebuildable search projection. Semantic retrieval must beat or complement that baseline on the evaluation set; it cannot weaken permissions.

## Refined user story

As a Brain user, I want keyword and semantic search across evidence I am currently authorised to read, so that I can find company context without exposing restricted or revoked information.

### Acceptance criteria

AC1 — tenant isolation: Given a user in Org A and evidence in Org B, when Org A search runs, then zero Org B result identifiers, content or provenance are returned.

AC2 — permission-before-content: Given restricted evidence without a current matching access basis, when search candidates are built, then that evidence is excluded by the authorization predicate before result content is selected.

AC3 — current Slack authorization: Given an explicitly authorised public Slack channel, when an organisation member searches, then matching evidence may appear; given a private channel, only a Brain user currently resolved to a listed Slack member may receive it; after channel authorization/membership is removed, the same search returns no evidence from that channel.

AC4 — restricted GitHub: Given private/internal GitHub repository evidence, when no matching current `github.repository` or Work Graph node grant exists, then the result is absent even for Owner/Admin; after a READ/WRITE grant exists, matching evidence may appear.

AC5 — revocation/deletion: Given an integration changes out of ACTIVE or a source object receives a canonical delete event, when search runs, then revoked/deleted derived content is absent without deleting raw/canonical audit evidence.

AC6 — keyword baseline: Given authorised documents containing the query terms, when keyword search runs, then relevant documents are ranked and returned with canonical/source provenance.

AC7 — semantic retrieval: Given authorised embedded documents where a relevant document lacks exact query terms, when hybrid search runs with a configured embedding service, then vector similarity can retrieve that document; unembedded/wrong-model documents are not falsely treated as semantic candidates.

AC8 — embedding failure: Given the embedding service is unavailable, when hybrid search runs, then keyword results remain available and the response explicitly reports degraded semantic status.

AC9 — indexing durability: Given canonical events arrive while the embedding provider is unavailable, when the indexing worker runs, then the searchable text projection is still durable, embedding work retries without duplicating documents, and source ingestion remains independent of embedding availability.

AC10 — provenance: Given any returned result, then it includes source provider, canonical event ID, source event/object reference and timestamp/provenance needed to resolve back to evidence.

## Tasks

- `T-05.01.01.a` search projection schema + Alembic migration + rollback
- `T-05.01.01.b` canonical-event reconciliation and idempotent update/delete projection
- `T-05.01.01.c` live authorization predicate reusing current ACL semantics
- `T-05.01.01.d` PostgreSQL full-text baseline and SQLite test fallback
- `T-05.01.01.e` provider-neutral embedding client + pgvector semantic retrieval + hybrid ranking
- `T-05.01.01.f` durable embedding worker with retry/stale-claim protection
- `T-05.01.01.g` search API validation/error/degradation contract
- `T-05.01.01.h` leakage/revocation/idempotency/semantic/evaluation tests
- `T-05.01.01.i` architecture/security/operator docs, UAT and evidence ledger

## Rejected alternatives

External vector database: rejected now because PostgreSQL is already the tenant/source-of-truth boundary and pgvector is sufficient until measured scale proves otherwise.

LLM-first search: rejected because generation cannot be trusted to enforce source authorization and would add cost/latency before retrieval quality is measurable.

Post-filtering restricted results: rejected because restricted content must not be loaded as a candidate and then hidden afterwards.

Embedding inside connector webhook processing: rejected because an embedding-provider outage must not break durable source ingestion.

Hardcoded embedding vendor/model: rejected because provider policy and customer data terms are not yet frozen; the retrieval contract stays provider-neutral.

## Out of scope for Increment 8

Ask Brain answer generation (`F-05.02`), decision/blocker extraction (`F-04.02`), AI provider governance (`F-06.01`), and employee productivity scoring are not part of this slice.

The existing preview frontend will not be wired to fake organisation/authentication state. Real frontend/manual search acceptance remains `UAT_PENDING` until the production frontend has real auth/org context; the backend API, indexing worker and real-data UAT script are the inspectable shippable interface for this increment.
