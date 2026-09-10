# Brain Render staging

This document is the deployment companion to `render.yaml`. It prepares a real staging environment for `S-05.01.01` and `S-05.02.01`; it is not evidence that either story passed.

## What the Blueprint creates

`render.yaml` defines:

- `brain-api-staging`: Docker web service in Render Singapore;
- `brain-staging-db`: Render Postgres in the same region;
- database wiring through Render's managed internal connection string;
- `/health/ready` HTTP readiness checks, including a real `SELECT 1` database check;
- Alembic migration to `head` before Uvicorn starts;
- production-mode Brain safety validation;
- `api.openai.com` as the only configured AI-provider egress host;
- generated Brain application/metrics secrets.

The backend accepts Render's standard `postgresql://`/`postgres://` connection URLs and normalises them to SQLAlchemy's installed `postgresql+psycopg://` driver.

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

Because Render's dedicated pre-deploy command is not available on free web services, this staging Blueprint runs `alembic upgrade head` in the Docker start command before Uvicorn. Keep staging at a single instance. A paid production topology should move migrations to a dedicated pre-deploy/release step.

## Deployment sequence

1. Connect the private `kunalwagh101/Brain.ai` repository to Render.
2. Create/sync the Blueprint from `render.yaml` on `increment-10-ai-provider-gateway`.
3. Supply the dashboard-only values above.
4. Confirm the database and web service are in Singapore and linked by the managed internal DB URL.
5. Wait for the service to report `/health/ready` as HTTP 200 with database `up`.
6. Confirm the deployed commit SHA matches the branch SHA being accepted.
7. Create the isolated Brain staging organisation and WorkOS users/roles needed by the UAT plan.
8. Load representative staging evidence through the normal governed ingestion paths.
9. Run `docs/ASK_BRAIN_STAGING.md` from the provider bootstrap onward.

## What must be recorded for acceptance

For every acceptance run record:

- deployed Git commit SHA;
- Render service name and deployment timestamp;
- database migration revision (`20260910_0016` or later);
- WorkOS environment/organisation used, without tokens/secrets;
- Brain organisation UUID;
- OpenAI provider/model/rate-card IDs;
- compatibility smoke request ID;
- total/cached/output token counts and exact nano-USD cost;
- RAG evaluation report path/hash or secure artifact reference;
- human citation reviewer/date;
- p50/p95/p99 and error rate;
- manual UAT tester/date and defect references.

Never copy customer source evidence, WorkOS tokens, AWS credentials, OpenAI keys, or full prompt/completion bodies into GitHub evidence blocks.

## Deliberately deferred S-05.01.01 verification

On 2026-09-10 the project owner explicitly deferred running the S-05.01.01 pytest suite locally and on Render. Leave S-05.01.01 `IN_REVIEW` until those commands are actually run and their passing output is captured. Do not infer a PASS from a successful deployment alone.
