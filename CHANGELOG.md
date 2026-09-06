# Changelog

## Unreleased

### Increment 8 — Permission-aware retrieval

- Added a rebuildable tenant-scoped search projection over canonical Slack/GitHub evidence.
- Added live Slack channel/membership and GitHub/resource-grant filtering before result rows are returned.
- Added PostgreSQL full-text keyword retrieval with a matching GIN expression index.
- Added provider-neutral semantic embeddings and pgvector cosine retrieval without choosing the later RAG generation provider.
- Added explicit hybrid-search degradation when the embedding service is absent/unavailable.
- Added a bounded database-backed reconciliation/embedding worker with stale-claim recovery and retry backoff.
- Added revocation/deletion handling so derived search content becomes unavailable while raw/canonical audit evidence remains.
- Added Alembic revision `20260907_0009`, rollback notes, security-focused tests, architecture docs and UAT instructions.
- Added `DEFINITION_OF_READY.md` because the delivery contract required an inspectable DoR artifact and the repository did not previously contain one.

Verification is not yet claimed: GitHub Actions for the current Increment 8 PR failed before runner startup, so `S-05.01.01` must remain non-DONE until tests and the delivery verifier actually run successfully.
