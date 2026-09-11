# Brain Render staging

This document is the deployment companion to `render.yaml`. It prepares a real staging environment for `S-05.01.01` and `S-05.02.01`; it is not evidence that either story passed.

## What the Blueprint creates

`render.yaml` defines:

- `brain-api-staging`: Docker web service in Render Singapore;
- `brain-staging-db`: Render Postgres in the same region;
- database wiring through Render's managed internal connection string;
- `/health/ready` HTTP readiness checks, including a real `SELECT 1` database check;
- Alembic migration to `head` before Uvicorn starts;
- automatic targeted S-05.01 retrieval verification against the real Render PostgreSQL/pgvector database before Uvicorn starts;
- production-mode Brain safety validation;
- `api.openai.com` as the only configured AI-provider egress host;
- generated Brain application/metrics secrets.

The backend accepts Render's standard `postgresql://`/`postgres://` connection URLs and normalises them to SQLAlchemy's installed `postgresql+psycopg://` driver.

## Staging verification image

Free Render web services do not provide Dashboard Shell, SSH or one-off jobs. The staging Blueprint therefore uses `backend/Dockerfile.staging` instead of depending on an unavailable interactive shell.

The staging image:

1. installs the backend development verification dependencies;
2. runs targeted Ruff checks for the S-05.01 retrieval slice during image build;
3. runs the targeted S-05.01 pytest files once against the portable SQLite fixture during image build;
4. retains the test files/runtime in the staging image so the same tests can run against managed PostgreSQL after deploy-time migrations.

The normal production `backend/Dockerfile` remains unchanged and does not include the dev/test runtime.

## Real PostgreSQL/pgvector gate

The free staging start command is deliberately ordered as:

```text
alembic upgrade head
BRAIN_TEST_DATABASE_URL="$BRAIN_DATABASE_URL" python -m pytest -q \
  tests/test_search.py \
  tests/test_search_evaluation.py \
  tests/test_search_contract.py
uvicorn ...
```

When `BRAIN_TEST_DATABASE_URL` is set, `backend/tests/conftest.py` creates a cryptographically unique temporary PostgreSQL schema, sets `search_path` to that schema plus `public`, creates the ORM test schema there, runs the tests through the PostgreSQL code paths, and drops the schema with `CASCADE` afterward. The staging application data in the normal schema is not used as test fixture data and is not deleted by this gate.

`alembic upgrade head` runs first so the database has the real pgvector extension and migration chain. If Ruff/build-time tests fail, the image build fails. If the PostgreSQL retrieval tests fail, the web process never starts and `/health/ready` cannot report healthy. A healthy deploy therefore proves only that these automated staging gates executed successfully; it does **not** by itself prove the full real-data/manual UAT requirements in `UAT/F-05.01.md`.

Because Free web services can restart/cold-start and do not provide a durable local filesystem, the targeted PostgreSQL tests may execute again when the service process restarts. Keep this gate bounded to the S-05.01 suite. Do not expand startup into the full repository test suite.

## Inputs that must remain outside Git

Fill these in the Render dashboard when the Blueprint asks for them:

- `BRAIN_CORS_ORIGINS`: exact HTTPS frontend origin(s), comma-separated; never `*`;
- `BRAIN_WORKOS_CLIENT_ID`: WorkOS client ID used by the staging frontend/API;
- `BRAIN_WORKOS_AUDIENCE`: expected JWT audience for the staging WorkOS token;
- `BRAIN_AWS_REGION`: region containing the staging Brain secrets;
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: staging-only AWS principal credentials.

Do not put the OpenAI API key in Render environment variables for normal Brain operation. `scripts/configure-ask-brain-openai.py` sends it once to Brain's owner/admin API and Brain stores it in AWS Secrets Manager.

The AWS principal should be restricted to the required Secrets Manager operations and Brain staging prefix. Do not reuse a broad personal/administrator AWS key.

## Free staging limitations

The checked-in Blueprint intentionally uses Render Free so the project owner can validate the system without committing to paid staging infrastructure. It is not a production topology. Free web services can cold-start after idle periods, and free Render Postgres is temporary and has no production backup guarantees. Performance results collected immediately after a cold start should not be mixed with warmed steady-state measurements.

Free web services currently do not support Dashboard Shell/SSH or one-off jobs, and Render's dedicated pre-deploy command is available only to paid web/private/worker services. For that reason this free staging path performs migrations and the bounded PostgreSQL retrieval gate in the Docker start command before Uvicorn. Keep staging at a single instance. A paid production topology should move migrations and acceptance jobs into dedicated release/pre-deploy execution.

## Deployment sequence

1. Connect the private `kunalwagh101/Brain.ai` repository to Render.
2. Create/sync the Blueprint from `render.yaml` on `increment-10-ai-provider-gateway`.
3. Supply the dashboard-only values above.
4. Confirm the database and web service are in Singapore and linked by the managed internal DB URL.
5. Inspect the build log and capture the targeted Ruff + SQLite pytest result from `Dockerfile.staging`.
6. Inspect the deploy/start log and capture the PostgreSQL S-05.01 pytest result after `alembic upgrade head`.
7. Wait for the service to report `/health/ready` as HTTP 200 with database `up`.
8. Confirm the deployed `RENDER_GIT_COMMIT` matches the branch SHA being accepted.
9. Create the isolated Brain staging organisation and WorkOS users/roles needed by the UAT plan.
10. Load representative staging evidence through the normal governed ingestion paths.
11. Complete the real-data permission/revocation/recall/latency checks in `UAT/F-05.01.md`.
12. Only after S-05.01 is accepted, continue `docs/ASK_BRAIN_STAGING.md` from the provider bootstrap onward.

## What must be recorded for acceptance

For every acceptance run record:

- deployed Git commit SHA;
- Render service name and deployment timestamp;
- database migration head;
- targeted build-time Ruff/SQLite pytest result;
- targeted runtime PostgreSQL/pgvector pytest result;
- real-data S-05.01 recall, leakage and latency measurements;
- WorkOS environment/organisation used, without tokens/secrets;
- Brain organisation UUID;
- OpenAI provider/model/rate-card IDs when S-05.02 begins;
- compatibility smoke request ID;
- total/cached/output token counts and exact nano-USD cost;
- RAG evaluation report path/hash or secure artifact reference;
- human citation reviewer/date;
- p50/p95/p99 and error rate;
- manual UAT tester/date and defect references.

Never copy customer source evidence, WorkOS tokens, AWS credentials, OpenAI keys, or full prompt/completion bodies into GitHub evidence blocks.

## Acceptance status

The project owner deferred S-05.01 execution on 2026-09-10 and asked to proceed into acceptance on 2026-09-11. The latest GitHub-hosted Backend CI, Delivery Verifier and Release Gate attempts failed before any workflow step executed, so they provide no test evidence. S-05.01 stays `IN_REVIEW` until the local and Render gates above actually execute successfully and the realistic permission/revocation/recall/latency UAT is recorded. Do not infer a PASS merely from repository implementation or a deploy that has not produced the required logs/evidence.
