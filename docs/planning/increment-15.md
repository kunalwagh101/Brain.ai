# Increment 15 — safe deployment, rollback, backup and restore

Story: `S-09.03.01` / `F-09.03`.

Branch rule: continue on `increment-10-ai-provider-gateway`; no new feature branch is created.

## Goal

Make every release candidate prove its tests, delivery state, migration reversibility mechanics, production-mode startup and disposable PostgreSQL restore before an environment-specific production deployment can be approved.

## Dependency state

The Phase 3 delivery verifier exists and is engineering-DONE. The story is buildable.

Two external/environment controls remain unresolved:

1. OQ-007 has not selected the production runtime/image registry/managed PostgreSQL topology.
2. GitHub's API reports repository rulesets unavailable for this private repository on the current GitHub plan; the connected integration also cannot inspect branch protection. Therefore the new Release Gate cannot yet be truthfully claimed as a required merge blocker.

## Acceptance refinement

### AC1 — one release gate validates code and delivery truth
Given a release-bound change, when Release Gate executes, then Ruff, backend Pytest and `scripts/verify_board.py` must all pass in the same workflow before later release checks run.

### AC2 — migrations prove rollback mechanics and forward recovery
Given disposable PostgreSQL 17 + pgvector, when the migration exercise runs, then `upgrade head`, `alembic check`, `downgrade base`, `upgrade head` and the final `alembic check` must all pass.

This proves migration mechanics on disposable data. It does not assert that every destructive downgrade is safe against production data.

### AC3 — backup is verifiable
Given the disposable migrated database, when backup runs, then a PostgreSQL custom-format archive is created, `pg_restore --list` can parse it and a SHA-256 sidecar is written.

### AC4 — restore proves recovered data
Given a pre-backup sentinel, when the database is mutated and restored from that archive, then the original sentinel value must be recovered. A backup command exiting zero without restored-data verification is insufficient.

### AC5 — restore is fail-safe
Given the restore script, when destructive confirmation is absent, the script refuses before archive or database mutation. A missing/invalid checksum or unreadable archive also refuses restoration.

### AC6 — production image starts under production safety validation
Given the built OCI image and disposable PostgreSQL, when the image starts with `BRAIN_ENVIRONMENT=production`, valid non-secret CI configuration and no external-provider dependency, then `/health/ready` becomes healthy.

### AC7 — release identity is immutable and inspectable
Given all release checks passed, when the workflow completes, then a manifest records commit SHA, image ID, Alembic head(s) and verification timestamp. Production promotion must later use an immutable registry digest, never `latest`.

### AC8 — migration rollback policy is data-aware
Given a migration that drops data on downgrade, when production rollback is considered, then the runbook prefers previous compatible application image / forward recovery or verified restore rather than automatically running a destructive downgrade.

### AC9 — failing release checks are technically merge-blocking
Given a pull request to the protected release path, when Release Gate fails, then GitHub prevents merge. This AC remains externally blocked until required-check enforcement is configured and verified.

### AC10 — environment deployment and rollback are exercised
Given the selected production runtime from OQ-007, when a non-production deployment drill runs, then the exact verified image is deployed, readiness gates traffic, the previous image digest is captured, rollback redeploys that digest, and observed recovery time is recorded.

## Tasks

- `T-09.03.01.a` Add provider-neutral Release Gate.
- `T-09.03.01.b` Exercise Alembic upgrade/downgrade/forward recovery on PostgreSQL+pgvector.
- `T-09.03.01.c` Add guarded PostgreSQL backup and restore scripts.
- `T-09.03.01.d` Exercise restored-data verification in disposable CI.
- `T-09.03.01.e` Build and smoke production-mode OCI image/readiness.
- `T-09.03.01.f` Produce non-secret release manifest.
- `T-09.03.01.g` Document deployment/migration/rollback/restore runbook.
- `T-09.03.01.h` Add release-contract regression tests.
- `T-09.03.01.i` Select/configure production runtime, registry, managed PostgreSQL and required GitHub release check.
- `T-09.03.01.j` Run deployment rollback + production-like backup/restore UAT and record RTO/RPO evidence.

## Security rules

- No production credentials in workflows, images, manifests or checked-in backup files.
- Release Gate database credentials are disposable CI-only values.
- The CI logical backup is deleted before artifact upload.
- Production restore requires explicit destructive confirmation and an integrity-checked archive.
- Production deployment uses immutable image digest.
- Database migrations execute as a one-shot release task, not from every API replica at startup.
- A failed migration blocks application rollout.
- A failed readiness check blocks/halts traffic promotion.
- A written convention is not accepted as equivalent to technical merge enforcement.

## Current status

Implementation is staged, but engineering-DONE is prohibited until the Release Gate actually executes successfully and AC9/AC10 have environment evidence. The story should remain non-DONE while GitHub runner/merge-enforcement and production-runtime selection are unresolved.
