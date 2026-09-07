# Increment 9 — Decision and Blocker Memory

Story: `S-04.02.01` / Feature: `F-04.02`

## Goal

Turn authorised company evidence into reviewable decision/blocker candidates without ever presenting an unsupported inference as confirmed fact.

## Dependency state

- `S-04.01.01` Work Graph: engineering-DONE.
- `S-05.01.01` Permission-Aware Retrieval: IN_REVIEW; implementation exists but GitHub-hosted runners are currently not starting, so no passing verification evidence is claimed.
- This increment may be implemented on top of the retrieval contract, but it cannot be engineering-DONE until its dependency and its own verification gates are satisfied.

## Acceptance criteria

1. Candidate records are tenant-scoped and linked to immutable canonical evidence plus the derived search/work-graph evidence identifiers used to enforce current access.
2. A candidate has an explicit kind (`decision` or `blocker`), confidence in `[0,1]`, extraction method/version, and state. Machine extraction creates `candidate`, never `confirmed`.
3. Candidate content is returned only after current source authorization succeeds. Revoked/deleted evidence disappears from memory reads without rewriting historical audit records.
4. Deterministic extraction is idempotent: replay/reconciliation cannot duplicate the same candidate for the same evidence and normalized statement.
5. Human review supports confirm, reject, edit, resolve and reopen transitions with actor, reason and immutable before/after history.
6. Cross-tenant reads/mutations and attempts to review an inaccessible candidate fail closed.
7. Evidence/provenance is returned with every visible candidate, including canonical event, source provider/event and occurred time.
8. Extraction failures never mutate the source canonical/raw evidence and never convert malformed output into a confirmed record.
9. Evaluation reports candidate precision separately for decisions and blockers. Production claim requires >=90% precision on the agreed representative evaluation set; synthetic fixtures may validate plumbing but are not a real-model quality claim.
10. Migration downgrade removes only derived decision/blocker state and history; raw/canonical/search/work-graph evidence remains available for rebuild.

## Extraction strategy

The first production-safe extractor is deterministic and conservative. It emits only explicit linguistic markers such as `we decided`, `decision:`, `blocked by`, `blocker:`, `waiting on`, and closely bounded equivalents. It deliberately prefers precision over recall. A later model-backed extractor can implement the same provider-neutral candidate contract after the AI provider policy is resolved and evaluated; model output still remains `candidate` until human confirmation.

The extractor reads from the existing `SearchDocument` projection rather than reparsing arbitrary raw JSON. This reuses the source-content whitelist and keeps extraction downstream of the retrieval boundary.

## State model

- `candidate`: machine/manual candidate not yet confirmed.
- `confirmed`: human accepted as a valid decision/blocker.
- `rejected`: human marked unsupported/not useful.
- `resolved`: confirmed blocker is no longer blocking; decisions may not transition to resolved.

Allowed transitions:

- candidate -> confirmed | rejected
- confirmed -> rejected
- confirmed blocker -> resolved
- rejected -> candidate (reopen)
- resolved blocker -> confirmed (reopen)
- edit keeps the current state and appends history.

## Tasks

- T-04.02.01.a derived candidate + immutable review-history schema/migration.
- T-04.02.01.b conservative idempotent extractor over search documents.
- T-04.02.01.c current-permission-aware query/read service.
- T-04.02.01.d human review/edit/resolve/reopen API with tenant and visibility checks.
- T-04.02.01.e reconciliation worker/path for historical evidence.
- T-04.02.01.f security, transition, idempotency, revocation and evaluation tests.
- T-04.02.01.g operator/UAT/rollback documentation and traceability.

## Explicit non-goals

- No automatic promotion from inference to confirmed fact.
- No employee scoring, sentiment scoring or hidden performance judgement.
- No new LLM provider choice; OQ-005 remains unresolved.
- No broad free-form entity extraction in this story.
- No frontend acceptance claim while the current frontend remains sample/preview state.
