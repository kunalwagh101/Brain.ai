# Brain Permission-Aware Retrieval

## Boundary

Search is a derived projection over immutable raw/canonical evidence. PostgreSQL remains the source-side retrieval database. The projection can be rebuilt; deleting it does not delete source evidence.

## Data flow

`RawEvent -> CanonicalEvent -> search reconciliation worker -> SearchDocument -> keyword/semantic candidate query -> live authorization predicate -> ranked result with provenance`

Embeddings are asynchronous. Connector ingestion and keyword projection do not depend on an embedding provider being available.

## Security invariants

1. Organisation membership is enforced before the search handler runs.
2. Search candidates are restricted by organisation, active integration and current source/resource authorisation in the database query before result rows are returned.
3. Public Slack is searchable only when the channel remains explicitly authorised.
4. Private Slack additionally requires a current resolved Slack identity listed in current channel membership.
5. Private/internal GitHub evidence requires a current explicit `github.repository` or evidence-node grant. Owner/Admin role is not a bypass.
6. Historical `source_acl` is provenance, not current entitlement.
7. Revoked integrations and deleted source objects are excluded from search.
8. Arbitrary raw payload JSON is never blindly indexed. Slack text and a bounded whitelist of GitHub text fields are projected.
9. Embedding API keys are loaded by secret reference and are not stored in search rows.

## Retrieval modes

`keyword` uses PostgreSQL full-text search in production. The migration creates an expression GIN index matching the production `to_tsvector('simple', ...)` query. SQLite's `ILIKE`-style fallback exists only for portable unit tests.

`hybrid` combines keyword ranking and vector cosine similarity using reciprocal-rank fusion. Semantic candidates are limited to embeddings produced by the currently configured model. If the embedding service is absent or unavailable, keyword search remains available and `semantic_status` explicitly reports `unconfigured` or `degraded`.

## Vector storage

Migration `20260907_0009` enables `pgvector` and stores embeddings in PostgreSQL. The column deliberately has no fixed dimension because the provider/model contract is not frozen yet. This supports exact cosine search across only the current model's rows. Do not add an approximate vector index until a fixed embedding dimension and measured dataset/latency justify it.

For local PostgreSQL, `compose.yaml` uses the official pgvector PostgreSQL 17 image so the extension is available to the migration.

## Worker

Run one bounded indexing batch:

```bash
cd backend
python -m app.search_worker --once --batch-size 100
```

The worker first reconciles missing search documents for every organisation. It does this even when embeddings are not configured or their secret/provider is unavailable. If embeddings are configured, it claims a bounded batch, uses `FOR UPDATE SKIP LOCKED` on PostgreSQL, records attempts, recovers stale claims, and retries failures with bounded exponential backoff.

Schedule `--once` using the production job runner. Do not run a hand-written infinite loop inside the API process.

## API

```text
GET /api/v1/organizations/{organization_id}/search?q=<query>&mode=keyword|hybrid&limit=20
POST /api/v1/organizations/{organization_id}/search/reconcile?limit=100
```

Search requires `resource.read`. Reconciliation requires `resource.write`. Results contain source provider, canonical event ID, source/object reference, timestamp, score and provenance.

## Migration and rollback

Upgrade: apply Alembic through `20260907_0009`. The database role used for migration must be permitted to create the `vector` extension, or the extension must be installed by the database administrator beforehand.

Downgrade drops the derived `search_documents` table and its indexes. It does not drop raw/canonical evidence and deliberately does not drop the shared `vector` extension. Forward recovery is: migrate up, run the reconciliation worker until `remaining=0`, then run embedding batches.

## Performance and scaling

Current keyword search has a PostgreSQL GIN expression index. Current semantic search is exact cosine search because model dimension is not yet frozen. Before claiming production scale, record representative p50/p95 latency and Recall@10 using `UAT/F-05.01.md`.

If measured semantic latency becomes the bottleneck after the embedding model/dimension is stable, add a pgvector HNSW/IVFFlat index as a measured optimisation. Do not introduce an external vector database until PostgreSQL is proven insufficient by load, isolation, or operational requirements.
