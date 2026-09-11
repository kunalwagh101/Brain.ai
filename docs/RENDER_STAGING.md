# Brain Render staging

This document is the deployment companion to `render.yaml`. It prepares the real staging environment for Brain's ordered backend acceptance chain; it is not evidence that any story passed until the logged checks actually execute successfully.

## What the Blueprint creates

`render.yaml` defines:

- `brain-api-staging`: Docker web service in Render Singapore;
- `brain-staging-db`: Render Postgres in the same region;
- database wiring through Render's managed internal connection string;
- `/health/ready` HTTP readiness checks, including a real `SELECT 1` database check;
- Alembic migration to `head` before Uvicorn starts;
- an ordered backend acceptance chain against the real Render PostgreSQL/pgvector database before Uvicorn starts;
- production-mode Brain safety validation;
- `api.openai.com` as the only configured AI-provider egress host;
- generated Brain application/metrics secrets.

The backend accepts Render's standard `postgresql://`/`postgres://` connection URLs and normalises them to SQLAlchemy's installed `postgresql+psycopg://` driver.

## Staging verification image

Free Render web services do not provide Dashboard Shell, SSH or one-off jobs. The staging Blueprint therefore uses `backend/Dockerfile.staging` instead of depending on an unavailable interactive shell.

The staging image:

1. installs the backend development verification dependencies;
2. runs `tests/test_acceptance_chain.py` to lock the dependency order/fail-closed runner contract;
3. runs Ruff over `app`, `tests` and `migrations`;
4. runs the ordered backend acceptance chain once against the portable SQLite fixture;
5. retains the tests/runtime so the same ordered chain can run against managed PostgreSQL after migrations.

The normal production `backend/Dockerfile` remains unchanged and does not include the dev/test runtime.

## Ordered backend acceptance chain

`backend/run_acceptance_chain.py` executes in this order and stops at the first failing stage:

1. **S-05.01.01 — Authentication + Permission-Aware Retrieval**
   - WorkOS JWT application/email binding;
   - organisation/RBAC boundaries;
   - search tenant/resource filtering;
   - retrieval evaluation/provenance contracts.
2. **S-02.04.01 — Meeting/Document Evidence**
   - governed ingestion, ACL/provenance and lifecycle contracts.
3. **S-05.02.01 — Ask Brain + governed AI/cost dependencies**
   - AI gateway/adapter/routes;
   - cached/exact cost and usage accounting;
   - runtime discovery;
   - Ask Brain grounding, citation, strict-output, generic-evidence and evaluation contracts.
4. **S-04.02.01 — Decision & Blocker Memory**
   - extraction/review/idempotency/generic-evidence/precision instrumentation.
5. **S-07.01.01 — Project Command Centre**
   - deterministic structured progress, permission-aware project evidence and routes.
6. **S-07.02.01 — Executive Overview**
   - portfolio/memory/accounting/budget-privacy/API-usage contracts.

A backend stage PASS is executable backend evidence only. The runner writes `uat_claimed=false` and cannot by itself mark a story production `DONE/PASSED`.

## Real PostgreSQL/pgvector gate

The free staging start command is deliberately ordered as:

```text
alembic upgrade head
BRAIN_TEST_DATABASE_URL="$BRAIN_DATABASE_URL" \
  python run_acceptance_chain.py \
    --require-postgres \
    --report /tmp/brain-acceptance-postgres.json
uvicorn ...
```

When `BRAIN_TEST_DATABASE_URL` is set, `backend/tests/conftest.py`:

- refuses a non-PostgreSQL test URL;
- creates a random temporary PostgreSQL schema;
- sets `search_path` to the temporary schema plus `public`;
- verifies the `vector` extension exists;
- verifies the temporary schema is actually active;
- creates the ORM test tables in that temporary schema;
- runs the test stages through PostgreSQL code paths;
- drops only that temporary schema afterward.

The staging application's normal schema is not the acceptance fixture and is not deleted by this gate.

`alembic upgrade head` runs first so the database has the real migration chain and pgvector extension. If the build-time contract/Ruff/portable chain fails, the image build fails. If the PostgreSQL chain fails, Uvicorn never starts and `/health/ready` cannot report healthy.

A healthy deploy therefore proves only that the automated backend chain passed on that exact deployed commit. It does **not** replace the real-data, provider, human-review, browser or accessibility UAT required by the feature-specific UAT documents.

Because Free web services can restart/cold-start and do not provide a durable local filesystem, this bounded chain may execute again when the process restarts. Keep the chain focused on the acceptance-critical backend contracts rather than expanding startup into every repository test.

## Inputs that must remain outside Git

Fill these in the Render dashboard when the Blueprint asks for them:

- `BRAIN_CORS_ORIGINS`: exact HTTPS frontend origin(s), comma-separated; never `*`;
- `BRAIN_WORKOS_CLIENT_ID`: WorkOS application client ID used by frontend and FastAPI;
- `BRAIN_AWS_REGION`: region containing the staging Brain secrets;
- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`: staging-only AWS principal credentials.

For normal WorkOS AuthKit session tokens, **do not configure `BRAIN_WORKOS_AUDIENCE`**. Brain validates the signed token's `client_id` against `BRAIN_WORKOS_CLIENT_ID`. Configure `BRAIN_WORKOS_AUDIENCE` only if you intentionally introduce an additional custom `aud` claim and want Brain to require it as a second application-binding check.

If the WorkOS environment uses a custom auth domain/issuer, configure the exact trusted `BRAIN_WORKOS_ISSUER`; do not disable issuer validation.

### Required WorkOS JWT Template

The FastAPI identity boundary requires this AuthKit JWT Template claim:

```json
{
  "urn:brain:user_email": {{ user.email }}
}
```

`sub` remains the stable WorkOS identity key. Brain deliberately does not use the optional `act` claim as the signed-in user's email because `act` can represent actor/delegation context.

Do not put the OpenAI API key in Render environment variables for normal Brain operation. `scripts/configure-ask-brain-openai.py` sends it once to Brain's owner/admin API and Brain stores it in AWS Secrets Manager.

The AWS principal should be restricted to the required Secrets Manager operations and Brain staging prefix. Do not reuse a broad personal/administrator AWS key.

## Free staging limitations

The checked-in Blueprint intentionally uses Render Free so the project owner can validate the system without committing to paid staging infrastructure. It is not a production topology. Free web services can cold-start after idle periods, and free Render Postgres is temporary and has no production backup guarantees. Performance results collected immediately after a cold start should not be mixed with warmed steady-state measurements.

Free web services currently do not support Dashboard Shell/SSH or one-off jobs, and Render's dedicated pre-deploy command is not part of this free path. For that reason this staging path performs migrations and the bounded PostgreSQL acceptance chain in the Docker start command before Uvicorn. Keep staging at a single instance. A paid production topology should move migrations and acceptance jobs into dedicated release/pre-deploy execution.

## Deployment sequence

1. Connect the private `kunalwagh101/Brain.ai` repository to Render.
2. Create/sync the Blueprint from `render.yaml` on `increment-10-ai-provider-gateway`.
3. Supply the dashboard-only values above.
4. Confirm the database and web service are in Singapore and linked by the managed internal DB URL.
5. Inspect the image build log and capture:
   - acceptance-runner contract result;
   - Ruff result;
   - portable ordered-chain stage results.
6. Inspect the deploy/start log and capture the PostgreSQL ordered-chain result after `alembic upgrade head`.
7. If any stage fails, fix that stage and do not interpret skipped downstream stages as passing.
8. Wait for `/health/ready` HTTP 200 with database `up` only after the chain passes.
9. Confirm the deployed `RENDER_GIT_COMMIT` equals the branch SHA being accepted.
10. Create the isolated Brain staging organisation and WorkOS users/roles needed by UAT.
11. Configure the required WorkOS JWT Template and production frontend AuthKit path in `docs/WORKOS_FRONTEND_ACCEPTANCE.md`.
12. Load representative staging evidence through normal governed ingestion paths.
13. Execute the feature-specific real acceptance gates in dependency order:
    - S-05.01 real permission/revocation/recall/latency UAT;
    - S-02.04 file/transcript ingest/delete/revoke UAT;
    - Ask Brain real OpenAI compatibility, exact cost, labelled retrieval/RAG evaluation, human citation review and performance;
    - Decision/Blocker representative precision + human review UAT;
    - Project Command Centre deterministic progress/resource-permission UAT;
    - Executive Overview accounting/budget/API/permission UAT;
    - official WorkOS authenticated frontend/manual/accessibility UAT.

## What must be recorded for acceptance

Record without secrets:

- deployed Git commit SHA;
- Render service name and deployment timestamp;
- database migration head;
- build-time runner-contract/Ruff/portable-chain results;
- runtime PostgreSQL/pgvector chain stage results;
- first failing story if a chain stops;
- real-data S-05.01 recall, leakage and latency measurements;
- WorkOS environment/organisation used, without tokens/secrets;
- Brain organisation UUID;
- OpenAI provider/model/rate-card IDs when Ask Brain begins;
- compatibility smoke request ID;
- total/cached/output token counts and exact nano-USD cost;
- RAG evaluation report path/hash or secure artifact reference;
- human citation reviewer/date;
- p50/p95/p99 and error rate;
- Decision/Blocker representative precision result;
- project/executive permission-revocation UAT result;
- frontend/manual/accessibility tester/date and defect references.

Never copy customer source evidence, WorkOS tokens, WorkOS API keys, AWS credentials, OpenAI keys, AuthKit encrypted session headers, or full prompt/completion bodies into GitHub evidence blocks.

## Acceptance status

The project owner asked to proceed into acceptance on 2026-09-11. GitHub-hosted Backend CI, Delivery Verifier and Release Gate have repeatedly failed before any workflow step executed; raw job metadata shows `runner_id=0`, empty runner names and empty step lists, so those runs provide no code-test verdict.

The Render path above is now the independent executable acceptance route. Until it actually runs successfully, the current stories retain their existing `IN_REVIEW`/`BLOCKED` states. No story is marked `DONE/PASSED` merely because the acceptance harness exists.
