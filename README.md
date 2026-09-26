# Brain

Brain is a company intelligence and AI-governance control plane. It connects to the tools a company already uses, structures authorised activity into a common work model, and gives teams evidence-backed visibility into projects, decisions, AI usage, APIs and blockers.

## Repository

- `app/` — existing Next.js 16 / React 19 frontend.
- `backend/` — FastAPI production API.
- `docs/ARCHITECTURE.md` — system boundary and architecture decisions.
- `PRODUCT_BACKLOG.md` — production MVP epics and acceptance outcomes.
- `BOARD.md` — current Scrum/Kanban delivery state.

## Backend stack

FastAPI, SQLAlchemy 2, PostgreSQL, Alembic and Pydantic Settings. The MVP remains a modular monolith until measured scaling or failure-isolation needs justify services.

## Run backend locally

Python 3.12+ is required.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

Or start PostgreSQL and the API together:

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`. Development OpenAPI docs are at `/docs`. Liveness is `/health/live`; readiness is `/health/ready` and fails with HTTP 503 if PostgreSQL is unavailable.

## Tests

```bash
cd backend
ruff check app tests migrations
pytest
```

## Production rules

- Set a strong `BRAIN_APP_SECRET`; the default is rejected in production.
- Set explicit `BRAIN_CORS_ORIGINS`; wildcard CORS is rejected in production.
- Keep provider/API secrets in a secrets manager, never plaintext database fields.
- Apply Alembic migrations before serving a new release.
- Permission checks must happen before retrieval or LLM access.

## Web workspace on Render

`npm run build` and `npm run start` use Next.js 16. The root is the authenticated Brain workspace: it redirects unauthenticated visitors to `/sign-in` and loads organisation-scoped data from FastAPI through the server session. `/demo` is a separate read-only example. If authentication settings are missing, `/` leads to `/setup` and Brain mutation routes return 503 instead of showing a sample user.

Configure `WORKOS_CLIENT_ID`, `WORKOS_API_KEY`, `WORKOS_COOKIE_PASSWORD` (32+ characters), `NEXT_PUBLIC_WORKOS_REDIRECT_URI=https://<frontend-host>/auth/callback`, and `BRAIN_API_BASE_URL=https://<backend-host>` on the **frontend Render service before building**. Set `BRAIN_WORKOS_CLIENT_ID` on the backend to the same WorkOS application; configure the JWT template claim and callback/login/logout URIs in `docs/WORKOS_FRONTEND_ACCEPTANCE.md`. Use separate backend service and PostgreSQL as documented in `render.yaml`. Restart after updating settings.

`npm run build:sites` and `npm run start:sites` preserve the separate vinext/Sites sample workflow. The production WorkOS path is verified with Next.js; vinext produced a server error for this authenticated root in local smoke tests. Official WorkOS credentials, a working backend, a real organisation membership and two-user browser testing are still required before calling the deployment operational.
