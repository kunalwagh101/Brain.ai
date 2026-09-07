# Decision and Blocker Memory

Feature: `F-04.02` / Story: `S-04.02.01`

## Purpose

Decision and Blocker Memory turns explicit statements in authorised company evidence into reviewable organisational memory. Machine extraction never makes a statement true merely because it detected a phrase: every machine-created record starts in `candidate` state and retains its evidence/provenance.

## Data flow

1. Slack/GitHub input is persisted as raw evidence and canonicalised.
2. The Work Graph links canonical evidence to people/projects/tracks/work items.
3. Permission-Aware Retrieval creates the whitelisted `SearchDocument` projection.
4. The decision-memory extractor reads only that whitelisted projection; it does not parse arbitrary raw JSON.
5. Explicit decision/blocker statements become idempotent `DecisionMemoryCandidate` rows.
6. Reads reuse the live search authorisation boundary before candidate content/provenance is returned.
7. Human review changes candidate state/summary and appends an immutable `DecisionMemoryReview` record.

Raw/canonical evidence remains authoritative. Search and decision-memory tables are derived/rebuildable layers; human review history is retained while the candidate exists.

## Security invariants

- Every candidate is tenant-scoped.
- User-facing reads are constrained by the same live search authorisation query used for evidence retrieval.
- Public Slack still requires a current explicit channel authorisation.
- Private Slack requires current channel authorisation and current resolved membership.
- Private/internal GitHub evidence requires the current explicit repository/work-graph grant; Owner/Admin is not an ACL bypass.
- Revoked integrations and deleted search documents disappear from memory reads immediately without deleting historical candidate/review rows.
- Cross-tenant candidate access returns no candidate content.
- No employee score, sentiment score or hidden performance judgement is extracted.

## Candidate states

- `candidate`: machine/manual candidate not yet accepted as fact.
- `confirmed`: a human accepted the candidate as supported organisational memory.
- `rejected`: a human rejected it.
- `resolved`: a confirmed blocker is no longer blocking.
- `superseded`: an unreviewed machine candidate disappeared when the same evidence was re-extracted; hidden from normal reads but retained for audit.

Decisions cannot transition to `resolved`. `resolve` is blocker-only.

## Extractor v1

Current method: `deterministic`  
Current version: `explicit-markers-v1`

The extractor intentionally recognises only high-precision markers such as:

- `Decision: ...`
- `We decided to ...`
- `The decision is ...`
- `We agreed to ...`
- `Blocker: ...`
- `... is blocked by ...`
- `Blocked because ...`
- `Cannot proceed until ...`
- `We're waiting on ...`

This is a real deterministic production path, not a mock model. Its limitation is deliberate: it optimises precision before recall. A future model-backed extractor may implement the same candidate contract after provider/data-policy evaluation, but model output must still start as `candidate`.

## Idempotency and extractor upgrades

Each candidate fingerprint is SHA-256 over the candidate kind plus normalised extracted statement. The database uniquely constrains organisation + canonical event + kind + fingerprint.

`decision_memory_extractions` records the extractor version, source-content SHA-256, candidate count and processing time. Documents with zero candidates are therefore still marked processed. When the extractor version or source projection changes, reconciliation can reprocess it. Unreviewed machine candidates no longer emitted become `superseded`; human-reviewed state is not silently overwritten.

## API

All paths are below the configured API prefix.

- `GET /organizations/{organization_id}/memory`
  - list currently authorised candidates; optional `kind`, `state`, `limit`.
- `GET /organizations/{organization_id}/memory/{candidate_id}`
  - read one currently authorised candidate.
- `POST /organizations/{organization_id}/memory/{candidate_id}/review`
  - `confirm`, `reject`, `edit`, `resolve`, or `reopen` with mandatory reason.
- `GET /organizations/{organization_id}/memory/{candidate_id}/reviews`
  - immutable review history after current candidate authorisation succeeds.
- `POST /organizations/{organization_id}/memory/reconcile`
  - bounded historical extraction/reconciliation.

Responses include canonical/search/work-graph evidence identifiers, source provider/event, occurred time, bounded evidence excerpt and provenance.

## Worker

The memory worker is one-shot and bounded so deployment can schedule it with the production job runner:

```bash
cd backend
python -m app.decision_memory_worker --once --batch-size 100
```

Run the search projection worker before/alongside this worker so new canonical evidence has a `SearchDocument` before memory extraction.

## Migration and rollback

Revision: `20260907_0010`

Upgrade creates:

- `decision_memory_candidates`
- `decision_memory_extractions`
- `decision_memory_reviews`

Downgrade drops only those derived memory/review tables. It does not delete raw events, canonical events, search documents or Work Graph evidence, so machine candidates can be rebuilt after re-upgrade. Before a production downgrade, export human review history if it must survive the downgrade because the review table itself is removed.

## Verification and acceptance

Engineering tests must cover:

- explicit extraction and no automatic confirmation;
- idempotency and zero-candidate extraction ledger;
- current Slack/GitHub authorisation and revocation;
- tenant isolation;
- integration revocation/source deletion;
- human transition rules and immutable before/after history;
- extractor reprocessing/supersession;
- synthetic precision instrumentation.

Synthetic fixtures prove contract/plumbing only. `F-04.02` must not be called production-accepted until a representative labelled company-evidence evaluation reaches at least 90% precision for the agreed candidate definition and real backend/frontend UAT is recorded.
