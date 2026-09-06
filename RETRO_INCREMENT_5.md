# Increment 5 Retrospective — GitHub + Canonical Events

## What went well

- Adding GitHub as the second provider forced the canonical event contract to prove it was provider-neutral rather than Slack-shaped.
- The existing raw-event layer gave canonicalisation a recoverable source of truth: mapping failures can quarantine instead of losing evidence.
- Security review caught the dangerous assumption that a GitHub callback `installation_id` could be trusted; the final flow verifies the user-visible installation and revalidates it as the configured GitHub App.
- The existing integration/RBAC abstractions were reused instead of creating a parallel GitHub security model.
- Tests cover exact-body signatures, signed state/cursors, replay/idempotency, source ACL propagation and the generic-integration bypass attempt.

## What changed during implementation

- GitHub issue filtering moved out of the low-level API client because `/issues` includes pull requests; filtering there would have made page-size completion logic incorrect.
- SQLAlchemy's reserved `metadata` attribute required the Python model field to be named `event_metadata` while preserving the database column name `metadata`.
- GitHub connections intentionally have no per-installation secret reference because installation access tokens are short-lived and generated from the App credentials when needed.
- Canonicalisation remains synchronous with ingestion for this increment. A queue/worker is not added until throughput/failure-isolation requirements justify it.

## Defects caught before engineering-DONE

- SQLAlchemy reserved-name collision.
- FastAPI dependency parameter ordering/import formatting issues.
- GitHub issue/pull-request pagination correctness.
- Unsafe generic GitHub connection bypass.
- Lint line-length/import-order failures caught by CI.

## What was deliberately not claimed

- No GitHub or canonical feature is called user-accepted. Real provider/data and frontend UAT are still pending.
- GitHub source ACL markers are provenance, not yet a complete user-to-repository authorisation system; S-03.03.01 identity resolution and later permission-aware retrieval complete that chain.
- No production throughput/scaling claim is made from the unit/integration suite.

## Estimate correction

The difficult part was not converting JSON fields. GitHub App installation identity, token lifetime, repository visibility and pagination semantics required more engineering attention than the mapping layer. Future connector estimates should budget explicitly for provider security semantics and retry/pagination edge cases.

## Next dependency-unlocked work

S-03.03.01 Identity Resolution is now the correct next story. It should deterministically connect Slack/GitHub source identities to Brain users where evidence is strong, leave ambiguous identities unresolved, and make every merge/reassignment reversible and auditable. The Work Graph remains blocked until that identity layer exists.
