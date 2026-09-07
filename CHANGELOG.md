# Changelog

## Unreleased

### Increment 9 — Decision and blocker memory

- Added tenant-scoped decision/blocker candidate storage plus versioned extraction bookkeeping and immutable human review history.
- Added a conservative deterministic extractor over whitelisted search evidence; machine extraction always creates `candidate` state and never auto-confirms a fact.
- Added explicit decision/blocker confidence, extraction method/version and SHA-256 statement fingerprints for idempotency.
- Added same-document PostgreSQL row locking, content/version reprocessing and `superseded` state for stale unreviewed machine candidates.
- Added current-permission-aware reads by reusing the Permission-Aware Retrieval candidate boundary, including live Slack/GitHub revocation behavior.
- Added human `confirm`, `reject`, `edit`, blocker-only `resolve` and `reopen` transitions with immutable before/after review records.
- Added bounded historical reconciliation/API/worker, Alembic revision `20260907_0010`, security/state/idempotency tests, synthetic precision instrumentation and realistic-data UAT instructions.

Verification is not yet claimed. This story is formally `BLOCKED` on S-05.01.01 because Permission-Aware Retrieval is still `IN_REVIEW`, and GitHub-hosted Actions runners are currently failing before job startup. The synthetic precision fixture is not a production precision claim; representative labelled data and frontend/manual UAT remain required.

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