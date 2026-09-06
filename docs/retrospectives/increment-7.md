# Increment 7 Retrospective — Work Graph

Date: 2026-09-06
Story: S-04.01.01 / F-04.01

## What shipped

- PostgreSQL typed Work Graph nodes/edges for people, projects, tracks, work items and canonical evidence.
- Deterministic Slack/GitHub projection wired into canonicalisation.
- Reversible source-identity to Brain-user resolution edges.
- Manual project/track/work-item nodes and constrained manual organisational edges.
- Bounded tenant-scoped traversal and reconciliation for historical canonical events.
- Explicit `VERIFIED` vs `INFERRED` relationship state with confidence and provenance.
- Alembic revision `20260906_0008` with downgrade support.

## What went well

- Reused PostgreSQL/SQLAlchemy instead of adding Neo4j before graph-query needs justify it.
- Kept raw/canonical evidence as the source of truth, making graph reconstruction possible after rollback.
- CI exposed an outdated model-registry assertion before DONE and the contract was updated rather than weakening the new schema.
- Security review caught two ACL hazards before closure: historical private-Slack ACL accumulation and a broader Owner/Admin bypass than Brain's existing resource ACL contract.
- Both were fixed with regression tests rather than documentation-only warnings.
- Reconciliation was bounded so a repair operation does not load an organisation's whole canonical history into memory.

## What caused rework

- Initial lint failures were avoidable and caused extra CI loops. Future large patches should run Ruff-equivalent formatting checks before first push when the execution environment is available.
- The first graph visibility implementation mixed provenance ACL snapshots with current authorization state. Source provenance and live authorization must be treated as separate concepts from the start.
- The graph initially assumed Owner/Admin could read restricted evidence. Existing security semantics proved stricter: restricted-resource access requires explicit grants. New subsystems must inherit the established permission contract rather than introducing role-specific exceptions.

## Rules carried forward

1. No graph database until measured traversal/query requirements make PostgreSQL insufficient.
2. Raw/canonical evidence remains authoritative; graph rows are a rebuildable projection.
3. `VERIFIED` can come only from deterministic source logic or an authorised explicit manual assertion.
4. LLM/model output may create only clearly `INFERRED` candidates until a later workflow verifies them.
5. Permission checks use current source/resource authorization, never historical evidence ACLs as current entitlement.
6. New intelligence features must reuse the existing ACL boundary; they cannot create a broader parallel permission system.
7. Real-data and frontend acceptance remain `UAT_PENDING` until the user executes the recorded UAT script.

## Next dependency

F-04.02 Decision and Blocker Memory depends on this graph plus permission-aware retrieval/evaluation. Do not make extracted decisions/blockers verified facts merely because the Work Graph can store relationships.
