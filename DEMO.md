# Increment 1 Demo

This demo is valid only after CI and the delivery verifier pass.

## Run

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
alembic upgrade head
pytest tests/test_auth.py tests/test_organizations.py -q
uvicorn app.main:app --reload
```

With a real WorkOS environment, set `BRAIN_WORKOS_CLIENT_ID` and optionally `BRAIN_WORKOS_AUDIENCE` / `BRAIN_WORKOS_ISSUER`, obtain a valid AuthKit access token, then call `GET /api/v1/auth/me` with `Authorization: Bearer <token>`.

## Expected evidence

- missing access token returns 401;
- a signed WorkOS-style JWT is accepted only with the configured issuer/audience and RS256 signature;
- an authenticated user creates an organisation and becomes its owner atomically;
- the owner can add an existing Brain user as a member;
- a user outside an organisation receives 404 when trying to read it;
- a non-owner member receives 403 when trying to add another member.
