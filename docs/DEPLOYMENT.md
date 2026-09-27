# Brain deployment, rollback, backup and restore

Story: `S-09.03.01` / `F-09.03`.

This document defines the release contract that is independent of the final cloud runtime. The cloud/runtime adapter is intentionally not guessed; see `OPEN_QUESTIONS.md` OQ-007.

## Release invariant

A production release is eligible only when all of the following refer to the same commit:

1. Ruff passes.
2. Backend Pytest passes.
3. `scripts/verify_board.py` passes.
4. Alembic upgrades to `head` on disposable PostgreSQL + pgvector.
5. The disposable database can downgrade to `base` and upgrade to `head` again.
6. `alembic check` reports no ORM/migration drift after forward recovery.
7. A custom-format PostgreSQL backup is created and archive-validated.
8. A destructive change is made to the disposable database, the backup is restored, and a pre-backup sentinel value is recovered.
9. The backend OCI image builds successfully.
10. That image starts with production safety validation enabled and `/health/ready` becomes healthy against PostgreSQL.
11. A release manifest records the commit SHA, local OCI image ID, migration head(s), and verification timestamp.

`.github/workflows/release-gate.yml` implements this gate. The disposable backup is deleted before artifact upload; only the non-secret release manifest is uploaded.

## Required GitHub merge control

The `Release Gate / verify-release` check must be a required check before merging release-bound changes to `main`.

At the time this story was staged, the repository API reported that repository rulesets are unavailable for this private repository on the current GitHub plan, and the connected GitHub integration cannot inspect branch protection. Therefore the repository must **not** claim that failing checks are technically merge-blocking until this is configured and verified in GitHub.

Possible resolutions:

- enable a GitHub plan/private-repository control that supports required checks, or
- make the repository public only if that is independently acceptable (not recommended merely to gain rulesets), or
- use another protected release branch/environment control that can enforce the same gate.

Do not replace an unavailable required-check control with a written convention and call it equivalent.

## Release artifact rules

- Production deploys use an immutable image digest (`registry/repository@sha256:...`), not a mutable tag such as `latest`.
- The deployed image must correspond to a commit whose Release Gate passed.
- Production credentials are injected by the runtime/secret manager. They are never baked into the image or release manifest.
- The final registry/runtime is OQ-007. Until it is selected, this repository does not contain cloud-specific push/deploy credentials or commands.

## Migration strategy

Brain uses Alembic. The release gate exercises the complete migration chain on a disposable database, but that does **not** mean `alembic downgrade` is always the preferred production rollback.

Production schema changes should follow expand/contract rules:

1. **Expand:** add backward-compatible columns/tables/indexes first.
2. Deploy application code that can operate with the expanded schema.
3. Backfill/reconcile separately when needed.
4. **Contract:** remove old schema only in a later release after old application versions no longer require it.

Before every production migration:

1. record the currently deployed image digest and Alembic revision;
2. verify the managed backup/PITR state;
3. create a logical pre-deploy backup when required by the change/runbook;
4. run `alembic upgrade head` as a one-shot release task, never concurrently from every web replica;
5. deploy the application only after the migration task succeeds;
6. verify `/health/live`, `/health/ready`, error rate, and key workflow smoke checks.

### Rollback decision

Prefer **application rollback with the forward-compatible schema** when possible. Redeploy the previous immutable image digest and leave the expanded database schema in place.

Use an Alembic downgrade in production only when the specific migration has been reviewed as data-safe. A downgrade that drops tables/columns is destructive even if the SQL technically works.

For example, revision `20260908_0014` creates governance/audit/retention tables. Its downgrade removes those tables. If production data has been written, the safe recovery path is normally a forward fix or restoration from the verified pre-deploy backup, not casually executing the destructive downgrade.

## PostgreSQL backup

`scripts/postgres-backup.sh` creates a custom-format archive using standard PostgreSQL environment variables:

```bash
PGHOST=db.example.internal \
PGPORT=5432 \
PGDATABASE=brain \
PGUSER=brain_backup \
PGPASSWORD='from-secret-store' \
BACKUP_FILE=/secure/brain-$(date -u +%Y%m%dT%H%M%SZ).dump \
bash scripts/postgres-backup.sh
```

The script:

- uses `umask 077`;
- does not print `PGPASSWORD`;
- uses `pg_dump --format=custom --no-owner --no-acl`;
- validates the archive with `pg_restore --list`;
- writes a SHA-256 sidecar;
- chmods the archive/checksum to owner-only.

Logical backups are not a substitute for managed PostgreSQL snapshots/PITR. OQ-007 must select the managed database and production backup/PITR policy.

## PostgreSQL restore

Restore is deliberately destructive and requires an explicit confirmation token:

```bash
PGHOST=disposable-db.example.internal \
PGPORT=5432 \
PGDATABASE=brain_restore_test \
PGUSER=brain_restore \
PGPASSWORD='from-secret-store' \
RESTORE_FILE=/secure/brain-20260908T120000Z.dump \
BRAIN_RESTORE_CONFIRM=I_UNDERSTAND_THIS_REPLACES_DATABASE \
bash scripts/postgres-restore.sh
```

The restore script refuses to run when:

- the confirmation token is absent/wrong;
- the archive is unreadable;
- the SHA-256 sidecar is missing or invalid;
- `pg_restore --list` cannot parse the archive.

It restores using `--clean --if-exists --exit-on-error` and therefore must never be pointed at production casually.

## Restore exercise

The Release Gate uses a disposable `pgvector/pgvector:0.8.6-pg17` database and proves recovery rather than merely proving that `pg_dump` exits zero:

1. migrate to current schema;
2. insert a sentinel `verified-before-backup` row;
3. create and validate a custom-format backup;
4. mutate the sentinel to `corrupted-after-backup`;
5. restore the backup destructively;
6. assert the sentinel is again `verified-before-backup`.

A real production readiness exercise must additionally restore a real encrypted non-production backup/snapshot into an isolated environment and run application integrity checks. It must never copy sensitive customer production data into an uncontrolled developer environment.

## Deployment sequence once OQ-007 is resolved

The environment-specific adapter must implement this order:

1. require a passing Release Gate for the exact commit;
2. build/publish or promote the exact verified OCI image and resolve its immutable digest;
3. capture the currently deployed image digest and database revision;
4. verify backup/PITR and execute any required pre-deploy logical backup;
5. run migrations once;
6. deploy the new image using rolling/canary semantics supported by the selected runtime;
7. require readiness before sending normal traffic;
8. smoke critical authenticated workflows;
9. observe SLO/error metrics for the release window;
10. record deployed commit/image/migration identifiers;
11. on failure, stop rollout and use the rollback decision above.

## Rollback drill

The production UAT for this story must prove at least:

- previous immutable image digest is known;
- a bad application release can be replaced by that image without permission/secrets changes;
- schema remains compatible with the previous image or a reviewed recovery procedure exists;
- a disposable restore from a verified backup succeeds;
- restored database reaches the expected Alembic revision and the API becomes ready;
- the exercise has timestamps, operator, RTO observation, defects, and final result.

## What is not yet claimed

Repository code alone does not prove:

- that GitHub currently prevents merging when Release Gate fails;
- that the final production image registry/runtime is configured;
- that production PostgreSQL snapshots/PITR are configured;
- that a production-like backup restore has actually been exercised;
- that rollback RTO/RPO targets have been met.

Those are required environment/UAT evidence before `S-09.03.01` can be called DONE/PASSED under Brain's delivery contract.
