# Changelog

## Unreleased

### Increment 18 — Evidence-backed Ask Brain

- Added a production Ask Brain API that reuses the existing permission-aware retrieval boundary before any company evidence reaches an AI provider.
- Added bounded RAG context with server-issued evidence IDs and explicit no-evidence behaviour that returns `insufficient_evidence` without loading provider credentials or invoking a model.
- Reused the governed tenant-scoped AI gateway rather than creating a second provider path and added safe organisation/runtime discovery for ordinary `ai.use` members.
- Resolved OQ-005 on 2026-09-10: OpenAI API with `gpt-5.6-terra` is the first production candidate, conditional on the checked-in security, retrieval, citation, latency, compatibility and exact-cost gates; no silent fallback is allowed.
- Added prompt-injection resistance by treating retrieved evidence as untrusted data and forbidding evidence-contained instructions from becoming model instructions.
- Added fail-closed structured grounding validation: every accepted factual claim must cite one or more server-issued evidence IDs; malformed, empty or unknown citations are rejected and raw provider output is not returned.
- Added cross-tenant, revocation, no-answer, citation-grounding, provenance-contract and guest-authorization tests plus architecture/security documentation, Increment 18 planning and real-provider UAT.
- Added two-phase deployed evaluation: automatic retrieval/security metrics are separated from human review of every exact generated claim-citation pair.
- Extended governed AI accounting for OpenAI cached input: provider cached-token usage is captured, request records persist it, model rate cards can price normal input/cached input/output separately, and missing/invalid required cache usage fails cost resolution closed to `unknown`.
- Added request-scoped AI cost audit plus staging bootstrap validation that independently recomputes the exact request's input/output/total nano-USD cost from the reviewed Terra rate card.
- Added Alembic revision `20260910_0016`, cache-aware accounting tests, request-cost route tests and managed-Postgres URL normalization tests. These tests are checked in but are not claimed as executed in this pass.
- Added `render.yaml` and `docs/RENDER_STAGING.md` for a reproducible Render staging candidate with API + Postgres, migration-before-start and database readiness checks. This is staging tooling, not the final production topology under OQ-007.
- Updated `docs/ASK_BRAIN_STAGING.md`, `UAT/F-05.02.md`, the board, Definition of Ready, traceability and draft PR without creating another delivery branch.

Verification is not yet claimed. `S-05.01.01` remains `IN_REVIEW`; on 2026-09-10 the project owner explicitly deferred its local pytest and Render verification until later, which is not a PASS. `S-05.02.01` remains `BLOCKED`: the real Render/WorkOS/AWS/OpenAI staging environment is not configured here, the Terra compatibility/exact-cost smoke has not run, representative Phase 1 retrieval/RAG evaluation and Phase 2 human citation review have not run, no staging p95 result exists, and the official WorkOS frontend package/build plus authenticated browser UAT remain outstanding. No DONE/PASSED or runtime performance/cost-quality claim is made from repository code alone.

### Increment 16 — Performance and cost budgets

- Added deterministic nearest-rank percentile and budget evaluation for p50/p95/p99, success rate, throughput and optional cost ceilings.
- Added a versioned benchmark workload for core organisation read, permission-aware search and governed AI under `ops/performance/budgets.json`.
- Reused the existing production SLO budgets rather than inventing new latency thresholds: core p95 <500 ms, search p95 <1.5 s and governed AI p95 <10 s.
- Added an async real-HTTP benchmark runner that records request count, concurrency, warmup, status/error counts, p50/p95/p99/max latency, throughput and explicit budget verdicts without storing request/response bodies or credentials.
- Added F-06.02 usage-ledger cost snapshots so the AI scenario reports exact nano-USD cost per successful evaluated task in an isolated benchmark organisation.
- Added fail-closed exact-cost behavior: when exact cost is required, any new unknown-cost AI request fails the scenario instead of being treated as zero spend.
- Added configurable throughput and maximum AI cost-per-success gates, while intentionally leaving their numeric thresholds unset until representative baselines/product economics establish agreed targets.
- Added a manually dispatched HTTPS staging Performance Gate with secret-backed benchmark authentication and optional low-concurrency governed-AI load.
- Added performance-budget regression tests, methodology/limitations documentation, Increment 16 planning and production-like backend/frontend UAT instructions.

Verification/performance is not yet claimed. `S-09.04.01` remains `BLOCKED`: search and governed AI remain unverified, GitHub-hosted jobs still cannot obtain a runner, F-09.03 has not produced the target staging environment, and no real Performance Gate report has executed. No p95, throughput, scale or AI-cost benchmark claim is made from repository code alone.

### Increment 15 — Deployment, rollback, backup and restore

- Added one provider-neutral `Release Gate` workflow that runs Ruff, backend Pytest and the delivery verifier before later release checks can proceed.
- Added disposable PostgreSQL 17 + pgvector migration verification with `upgrade head`, ORM drift check, full `downgrade base`, forward recovery to `head` and final drift check.
- Added guarded PostgreSQL custom-format backup and restore scripts with archive parsing validation, portable SHA-256 sidecars, owner-only local permissions and explicit destructive-restore confirmation.
- Added an actual restored-data exercise: CI seeds a pre-backup sentinel, mutates it after backup, restores the archive and asserts the original value is recovered.
- Added OCI image build plus production-mode API startup/readiness smoke against the restored PostgreSQL database.
- Added a non-secret release manifest containing commit SHA, local image ID, migration head(s) and verification timestamp; the disposable database archive is deleted before artifact upload.
- Added release-contract regression tests covering shell syntax, destructive restore refusal, required Release Gate stages and non-root production container execution.
- Added deployment/migration/rollback/restore runbook and production-like UAT with immutable image digest, rollback drill, restore drill, observed recovery times and frontend/manual validation.
- Added OQ-007 rather than guessing the final production runtime/image registry/managed PostgreSQL topology.
- Closed nearby F-09.02 test drift caused by integration-scoped source-object deletion hardening.

Verification is not yet claimed. `S-09.03.01` remains `BLOCKED`: the Release Gate has not executed on a GitHub runner, required merge-check enforcement is unavailable/unverified for the current private-repository setup, and OQ-007 still blocks the environment-specific publish/deploy/rollback drill. No backup-restore or recovery-time success is claimed from repository code alone.

### Increment 14 — Audit, retention and deletion

- Added tenant-scoped durable security audit events with actor/resource/request correlation, bounded metadata and normalized-payload SHA-256 digests.
- Added PostgreSQL append-only enforcement that rejects audit-row updates while allowing explicit audit-retention deletion; actor UUID evidence is deliberately not a mutable user foreign key.
- Added `data_governance.manage` for Owner/Admin retention/deletion administration while organisation-wide governance/audit reads reuse `audit.read`.
- Added explicit per-organisation raw-event, derived-content and audit-event retention durations plus legal hold. Unset durations mean no automatic age-based purge; Brain does not invent a legal retention period.
- Added bounded raw retention and derived retention with reconstruction-suppressing tombstones. Derived tombstones preserve only raw-event ID plus minimal provider/object locator, not source content.
- Added integration-wide deletion gated on full revocation and typed source-object deletion with idempotency keys, stable target references, counts and completion digests.
- Closed the retained-raw deletion gap: a source-object deletion can still find and delete raw evidence after its canonical row was previously removed by derived retention.
- Added canonicalisation suppression so deleted/purged evidence cannot silently reappear through connector replay or reconciliation.
- Added orphan source-identity sanitation that clears unsupported identity evidence and returns the identity to `unresolved` state.
- Added pending/failed/stale-processing deletion recovery, bounded worker execution and PostgreSQL row-lock/`SKIP LOCKED` concurrency semantics.
- Added fail-closed durable audit coupling for ACL create/delete mutations; authorization-denial audit persistence remains best-effort so an audit-store problem cannot widen access.
- Added Alembic revision `20260908_0014`, service/route/worker/audit/retained-raw regression tests, operator documentation and realistic PostgreSQL/frontend UAT instructions.

Verification is not yet claimed. `S-09.02.01` remains `IN_REVIEW` until Ruff, Pytest, migration verification and the Delivery Verifier actually execute. PostgreSQL append-only-trigger/cascade/concurrency behavior, realistic deletion/replay behavior, frontend/manual acceptance and backup/PITR lifecycle remain separate `UAT_PENDING` evidence.

### Increment 13 — Production observability and SLOs

- Added correlated structured JSON logging with bounded request IDs, W3C/OpenTelemetry request + AI tracing, structured JSON logging with strict allowlisting and credential/token redaction, protected Prometheus metrics, route-template HTTP metrics, PostgreSQL readiness metrics, connector lifecycle telemetry, aggregate governed-AI status/latency/exact-cost telemetry, SLO/error-budget definitions, alert rules, incident runbook, tests and deployed UAT instructions.
- Tenant-configurable organisation/user/integration/provider/model values are deliberately excluded from Prometheus labels and remain available through correlated logs/traces/durable ledgers.

Verification is not yet claimed. `S-09.01.01` remains `IN_REVIEW` until Ruff, Pytest and the Delivery Verifier obtain an executable passing run. Deployed metrics/trace collection, alert firing and representative monthly SLO compliance remain separate `UAT_PENDING` evidence.

### Increment 12 — External API registry

- Added tenant-scoped external API service and credential-grant inventory with explicit owner, scopes, environment, status and optional expiry.
- Added dedicated `api.manage` administration permission while organisation-wide registry/history/usage reads reuse `audit.read`.
- Added AWS Secrets Manager storage for external API credentials; PostgreSQL persists only secret references and read APIs expose only `credential_present`.
- Added safe internal credential loading that refuses disabled, revoked, revoke-failed and time-expired grants before secret retrieval; no public credential-read endpoint exists.
- Added credential rotation without changing the stored reference or persisting old/new credential values.
- Added fail-closed `revoking`, `revoke_failed` and `revoked` transitions with retryable secret deletion and immutable lifecycle history.
- Added bounded expiry processing plus separate secret-cleanup retries so an expired grant remains unusable even when external secret deletion temporarily fails.
- Added trusted internal, idempotent API usage observations with PostgreSQL grant-row locking to avoid lost concurrent usage-count updates; normal clients cannot fabricate usage through a public write route.
- Added Alembic revision `20260907_0013`, security/lifecycle/worker/secret-store tests, operator documentation and realistic-data/frontend UAT instructions.

Verification is not yet claimed. The latest checked Backend CI job for this branch failed before runner startup with `runner_id=0` and no executed steps, so Ruff/Pytest/Delivery Verifier evidence does not exist and `S-06.03.01` remains `IN_REVIEW`.

### Increment 11 — Usage, cost and budgets

- Added historical provider/model rate cards and deterministic integer nano-USD cost accounting.
- Added explicit `calculated` versus `unknown` cost-resolution state; missing provider token counts or pricing are never silently treated as zero spend.
- Added usage aggregation by organisation, provider, model, user and existing Work Graph attribution node without guessing missing attribution.
- Added UTC calendar-month budgets for organisation/provider/model/user/project-track-work-item scopes with tenant-validated targets.
- Added deduplicated warning and 100% alerts plus a post-exhaustion hard-stop before provider secret lookup/execution.
- Added explicit incomplete-enforcement state when a budget period contains unknown-cost requests rather than pretending known spend equals the invoice.
- Added bounded cost reconciliation with PostgreSQL `FOR UPDATE SKIP LOCKED` for successful requests whose cost is missing or later becomes resolvable.
- Added Alembic revision `20260907_0012`, API routes, accounting/security tests, operator documentation and real-provider/frontend UAT instructions.

Increment 18 extends this accounting contract with cached-input usage/rates and migration `20260910_0016`. Verification is not yet claimed. `S-06.02.01` remains `BLOCKED` because S-06.01.01 lacks executable passing verification and the new cache-aware accounting tests/real-provider exact-cost smoke have not run.

### Increment 10 — Governed AI provider gateway

- Added tenant-scoped AI provider/model configuration with separate `ai.manage` administration and `ai.use` invocation permissions.
- Added secret-reference provider credentials, credential rotation, fail-closed revocation and no plaintext API-key persistence.
- Added production HTTPS/provider-host egress controls, redirect rejection and bounded provider response/error handling.
- Added a provider-neutral runtime contract with an isolated OpenAI-compatible chat-completions adapter.
- Added durable AI request metadata for organisation, user, provider, model, optional Work Graph attribution, status, latency, provider request ID and provider-returned token counts.
- Prompts, system text and model completions are not persisted in the AI request ledger by default.
- Added Alembic revision `20260907_0011`, gateway/adapter/route/security tests, documentation and real-provider/frontend UAT instructions.

Verification is not yet claimed because GitHub-hosted Actions cannot currently obtain a runner; `S-06.01.01` remains `IN_REVIEW` until Ruff, Pytest and the Delivery Verifier actually execute successfully.

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

Verification is not yet claimed: the project owner explicitly deferred the next local pytest and Render execution verification on 2026-09-10. `S-05.01.01` remains non-DONE until that verification actually runs successfully and is recorded.