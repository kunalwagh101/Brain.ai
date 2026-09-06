# Increment 6 Retrospective — Identity Resolution

## What went well

- Keeping WorkOS authentication identities separate from Slack/GitHub source identities prevented one table from mixing login authority with uncertain work-attribution evidence.
- The canonical event layer gave identity resolution a stable provider-neutral actor boundary instead of adding Slack- and GitHub-specific user models.
- The resolver is deterministic and fail-closed: uncertainty remains unresolved rather than becoming a plausible-looking but unsafe attribution.
- Tenant checks and manual administration reuse the existing organisation membership and RBAC model.
- Canonical source actor evidence remains immutable while resolved Brain-user attribution can change reversibly.

## What changed during implementation

- Source-identity observation was wired directly into canonicalisation so new events enter the identity layer automatically; a reconciliation endpoint covers existing canonical events.
- One observation is unique per canonical event, which keeps replay idempotent while preserving repeated observations across different events.
- Conflicting provider-verified email evidence clears the current resolution and moves the identity to `REVIEW_REQUIRED` instead of silently choosing one value.
- Timestamp comparisons now normalize to UTC because SQLite can return timezone-aware columns as naive datetimes during tests while PostgreSQL preserves timezone semantics.

## Defects caught before engineering-DONE

- The initial identity-list endpoint used an unnecessary SQLAlchemy Select truthiness expression; it was simplified before the final test run.
- CI caught three lint issues in the new acceptance tests before any DONE claim.
- The first full behavioral run caught an offset-naive/offset-aware timestamp comparison after 81 tests had passed; the resolver boundary now normalizes timestamps explicitly.

## What was deliberately not claimed

- Provider-verified email availability is not assumed for every Slack/GitHub event or account. Missing verified evidence is expected to remain unresolved.
- No fuzzy or model-based identity inference has been introduced to inflate attribution coverage.
- No production attribution-rate claim is made from unit/integration tests.
- F-03.03 is not user-accepted until real-provider and frontend/manual UAT is recorded.

## Estimate correction

The core matching rule is small; the real engineering work is preserving provenance, tenant isolation, reversibility and conflict behavior. Future identity/provider features should budget for evidence quality and correction workflows rather than assuming identity is a simple email join.

## Next dependency-unlocked work

S-04.01.01 Work Graph is now eligible for refinement. It can safely link people, projects, tracks, work items and evidence using source identity/resolved-user references without inventing person attribution.
