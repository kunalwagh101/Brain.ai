# Definition of Ready

A story may enter `READY` only when all conditions below are true. `IN_PROGRESS` may be entered only from a Ready-compliant story and only when the board WIP limit permits it.

- Acceptance criteria are written as observable, machine-testable Given/When/Then outcomes.
- Upstream backlog dependencies are engineering-DONE or named external dependencies with a usable contract.
- Required source data, schemas, API contracts and state transitions are known.
- No open question can materially change the story's shape, security boundary, persistence contract or external interface.
- Tenant isolation, authentication/authorization and sensitive-data handling are explicit.
- Failure, retry, idempotency and rollback expectations are explicit where state changes.
- Required migration/data backfill strategy is known.
- Success metric and leading indicator are named.
- Out-of-scope items are explicit; nothing is silently removed from scope.
- Tasks are small engineering steps and the story remains an independently shippable vertical slice.

## Increment 8 readiness record — S-05.01.01

Decision: `READY` then pulled to `IN_PROGRESS` on 2026-09-07.

Dependencies: S-01.03.01 RBAC/resource ACL = engineering-DONE; S-03.02.01 canonical event model = engineering-DONE; S-04.01.01 Work Graph authorization semantics = engineering-DONE and reused.

Data/contracts known: `CanonicalEvent`, immutable `RawEvent`, `IntegrationConnection`, `SlackChannelAuthorization`, `SourceIdentity`, `ResourceGrant`, and Work Graph evidence nodes provide the source/provenance/access inputs.

Open questions: OQ-005 is about the later RAG generation provider and does not change this retrieval storage/API shape. Embeddings use an operator-configured provider-neutral HTTP contract, so no provider business rule is invented here.

Security boundary: organisation membership is checked first; current source/resource authorization is applied inside the search candidate predicate before result content is selected; role alone cannot bypass restricted-resource access.

Rollback: search projection and embeddings are derived/rebuildable. Migration downgrade removes only derived retrieval tables/indexes; raw/canonical evidence remains intact.

Leading indicators: unauthorised retrieval failures = 0; synthetic retrieval evaluation >=90% recall target; real-provider recall and p95 latency recorded in UAT before production acceptance.
