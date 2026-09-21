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

The current frontend still contains preview/sample data. It is intentionally not presented as live company evidence. The next slice replaces preview identity/state with real organisation and authentication flows.

## License

Brain.ai is open source under the Apache License 2.0.

You may use, modify, and distribute the software under the terms of the `LICENSE` file. The Apache 2.0 license also includes an explicit patent grant from contributors and requires preservation of applicable notices.
