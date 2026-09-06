# Engineering Demo

This file demonstrates repository-verified engineering behavior. It is **not** the real-data/manual user acceptance record; feature acceptance lives in `UAT.md` and `docs/acceptance/`.

## Increment 3 — integration framework

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
alembic upgrade head
pytest tests/test_integrations.py tests/test_secrets.py -q
pytest -q
uvicorn app.main:app --reload
```

Expected automated evidence:

- Owner/Admin connection creation is allowed; Member creation is denied.
- Cross-tenant integration listing returns tenant-safe 404.
- API responses never contain credential payloads or `secret_ref`.
- Duplicate organisation/provider/account creation is rejected before a second secret write.
- Successful revoke clears the database secret reference and makes the connection non-syncable.
- Secret deletion failure returns 503 but still leaves the connection non-syncable.
- Sync success persists health, cursor and timestamp only for ACTIVE connections.
- AWS adapter tests use a fake client and verify create/get/delete calls without real AWS credentials.

Real AWS/provider credentials must be tested later using `docs/acceptance/F-02.01.md`; do not paste credentials into commands committed to the repository.

## Increment 1 — authentication and organisation boundary

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
alembic upgrade head
pytest tests/test_auth.py tests/test_organizations.py -q
uvicorn app.main:app --reload
```

With a real WorkOS environment, set `BRAIN_WORKOS_CLIENT_ID` and optionally `BRAIN_WORKOS_AUDIENCE` / `BRAIN_WORKOS_ISSUER`, obtain a valid AuthKit access token, then call `GET /api/v1/auth/me` with `Authorization: Bearer <token>`.

Expected engineering evidence:

- missing access token returns 401;
- a signed WorkOS-style JWT is accepted only with configured issuer/audience and RS256 signature;
- an authenticated user creates an organisation and becomes its owner atomically;
- the owner can add an existing Brain user as a member;
- a user outside an organisation receives 404 when trying to read it;
- a non-owner member receives 403 when trying to add another member.
