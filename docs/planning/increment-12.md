# Increment 12 — External API Registry

Branch policy: this increment intentionally continues on `increment-10-ai-provider-gateway`; no new branch is created.

Story: S-06.03.01 — Inventory external API access without plaintext credentials.

## Goal

Give security/admin users a tenant-scoped inventory of external API access with explicit ownership, scopes, environment, lifecycle, expiry and usage metadata while keeping credential material exclusively in the configured secret store.

## Acceptance contract

1. A registered API service and credential grant belong to exactly one organisation; cross-tenant reads/mutations return no foreign fields.
2. PostgreSQL stores only a secret reference. API keys/tokens/client secrets are accepted only for transfer into the server-side secret store and are never returned by read APIs.
3. Every grant has an active Brain-member owner, explicit scopes, environment, status, optional expiry and creator.
4. Scope/environment/provider/service identifiers are normalized and bounded; an empty scope set is rejected.
5. Owner reassignment is allowed only to another active member in the same organisation and writes immutable before/after history.
6. Disable/re-enable is allowed only before revocation starts. Revocation fails closed: `revoking` and `revoke_failed` cannot be used or re-enabled; successful deletion ends in `revoked` with the secret reference cleared.
7. Due expiry moves an eligible grant to `expired` and writes one immutable expiry history event; replay is idempotent.
8. Credential rotation replaces the secret in the secret store, records `credential_rotated_at`, and writes audit history without storing old/new credential values.
9. Internal usage observation updates bounded usage metadata and appends an immutable usage event without accepting arbitrary plaintext request/response payloads.
10. Organisation-wide registry reads require the existing `audit.read`; mutations require a dedicated `api.manage` permission (Owner/Admin).
11. No feature claims production usage coverage until real calling systems are wired to the internal usage-observation contract and UAT proves it.

## Tasks

- T-06.03.01.a tenant-scoped API service/grant/history/usage schema and migration
- T-06.03.01.b server-side secret-store create/rotate/delete lifecycle
- T-06.03.01.c owner/scope/environment/status validation and fail-closed transitions
- T-06.03.01.d expiry reconciliation worker with idempotent audit history
- T-06.03.01.e permissioned registry/read/mutation API
- T-06.03.01.f internal usage-observation contract and visible usage metadata
- T-06.03.01.g tenant/security/idempotency/revocation/expiry tests
- T-06.03.01.h operator docs, rollback and real-data/frontend UAT

## Explicit non-goals

- Generic HTTP proxying through Brain
- Storing or displaying plaintext API credentials
- Guessing owners or scopes from traffic
- Network traffic discovery without an authorised integration
- Provider invoice reconciliation (F-06.02)
- Agent tool execution/approval policy (F-08.01)

## Verification work order — 2026-09-24

Mode: **CHECK** — implementation already exists; this pass verifies and closes engineering evidence only.

Role: **Senior full-stack engineer / systems architect**. Operating tier: **architect**.

Scope:
- verify the existing external API registry lifecycle, authorization, credential-reference and usage contracts;
- do not add a generic HTTP proxy, traffic discovery or plaintext credential persistence;
- keep real secret-store/calling-system/frontend acceptance as `UAT_PENDING`.

Files under review:
- `backend/app/api_registry.py`
- `backend/app/api_registry_credentials.py`
- `backend/app/api_registry_models.py`
- `backend/app/api_registry_worker.py`
- `backend/app/routes/api_registry.py`
- `backend/app/routes/api_registry_usage.py`
- `backend/migrations/versions/20260907_0013_api_registry.py`
- `backend/tests/test_api_registry.py`
- `backend/tests/test_api_registry_worker.py`
- `backend/tests/test_api_registry_usage_route.py`
- `backend/tests/test_secrets.py`
- `docs/API_REGISTRY.md`
- `UAT/F-06.03.md`

Required verification:
```bash
cd backend
ruff check app tests migrations
pytest -q tests/test_api_registry.py tests/test_api_registry_worker.py tests/test_api_registry_usage_route.py tests/test_secrets.py
pytest -q
cd ..
python scripts/verify_board.py
```

Release evidence must also exercise PostgreSQL migration upgrade/downgrade/forward recovery. A green automated run may support engineering `DONE`; it must not be presented as real credential/provider/frontend UAT.

## Engineering closure — 2026-09-24

Status: **DONE (engineering)**. Real secret-manager, real calling-system and frontend/manual validation remain **UAT_PENDING**.

Evidence baseline: commit `8be45dd4d96a87d9fa5a3cf9a385f8cd3ca6349f`; Backend CI `35930622742` passed Ruff + 385 backend tests; Delivery Verifier `35930622825` passed; Release Gate `35930622874` passed PostgreSQL migration recovery, backup/restore, frontend verification, production image build and readiness smoke. The closure Delivery Verifier re-runs the focused API-registry test command recorded in TRACEABILITY.md.
