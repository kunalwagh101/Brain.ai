# Brain Engineering Demo

A demo section is valid only after its named CI evidence exists. A successful engineering demo does not replace real-data/manual UAT.

## Increment 1 — secure organisation boundary

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
alembic upgrade head
pytest tests/test_auth.py tests/test_organizations.py -q
uvicorn app.main:app --reload
```

With a configured WorkOS environment, a valid user can call `/api/v1/auth/me`, create an organisation and exercise the tenant-safe membership APIs.

## Increment 4 — Slack + raw evidence

Automated evidence command:

```bash
cd backend
pytest -q
```

Expected engineering evidence:

- Slack OAuth state is signed/tamper-evident and expires;
- required Slack scopes exclude direct-message scopes;
- DMs cannot be authorised;
- invalid signatures are rejected before storage;
- authorised signed events persist exact raw bytes and checksum;
- retrying the same event ID does not create another row;
- unauthorised channels are ignored;
- private source ACL membership is stored/updated;
- backfill cursor resumes and replay is deduplicated;
- oversized raw payload is rejected.

For actual feature acceptance, run the real provider and frontend steps in `UAT/F-02.02.md` and `UAT/F-03.01.md`.
