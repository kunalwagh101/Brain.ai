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

## Increment 5 — GitHub + canonical events

Automated evidence command:

```bash
cd backend
pytest -q
```

Expected engineering evidence:

- GitHub webhook HMAC verification is exact-body and tamper-sensitive;
- install state and installation-selection tokens are signed and expiring;
- GitHub cannot be connected through the generic credential endpoint;
- a signed private-repository delivery is persisted/canonicalised exactly once;
- private repository ACL provenance reaches the canonical event;
- backfill cursor is signed, connection-bound, resumable and replay-safe;
- Slack and GitHub both produce the same schema-versioned canonical dimensions;
- unsupported mappings quarantine the raw event without losing source evidence;
- migration/model uniqueness keeps one canonical event per raw event.

GitHub Actions run `34037248953` passed lint and 73 tests. For actual feature acceptance, run `UAT/F-02.03.md` and `UAT/F-03.02.md` with a real GitHub App, realistic Slack/GitHub data and the production frontend.

## Increment 6 — identity resolution

Automated evidence command:

```bash
cd backend
pytest -q
```

Expected engineering evidence:

- repeated Slack/GitHub provider actors reuse the same tenant-scoped source identity;
- canonical retry does not duplicate source identity observations;
- WorkOS authentication identities are not overloaded as source identities;
- unverified email never auto-resolves;
- provider-verified exact email can resolve only an active same-organisation member;
- a matching user in another organisation is not linked;
- Owner/Admin can manually resolve, reassign and unresolve with immutable before/after history;
- normal Members cannot use identity-management endpoints;
- canonical source actor fields remain intact while optional `resolved_user_id` changes;
- existing canonical events can be reconciled into the identity layer;
- timezone normalization keeps first/last-seen ordering portable across database implementations.

GitHub Actions run `34038863067` passed lint and 82 tests. Delivery Verifier run `34038863068` passed before engineering-DONE. For actual acceptance, run `UAT/F-03.03.md` using realistic provider identities and the production admin workflow.

## Increment 7 — typed Work Graph

Automated evidence command:

```bash
cd backend
pytest -q
```

Expected engineering evidence:

- canonical Slack/GitHub evidence projects into typed graph nodes without duplicating on replay;
- source identities and Brain users remain distinct person nodes connected only by the current reversible `resolves_to` relationship;
- GitHub repository evidence produces projects/work items and Slack channel evidence produces tracks;
- every relationship exposes source, explicit verified/inferred state, confidence and provenance;
- unsupported manual person-identity assertions and cross-tenant graph edges are rejected;
- traversal is tenant-scoped and depth-bounded;
- private Slack access is recalculated from current channel membership, so historical ACL provenance cannot keep revoked access alive;
- restricted GitHub evidence requires an explicit resource grant and is not bypassed by Owner/Admin role;
- reconciliation is bounded and idempotent;
- migration `20260906_0008` can be rolled back without deleting the raw/canonical evidence needed to rebuild the graph.

GitHub Actions run `34043847195` passed lint and 89 tests on implementation commit `a97d724416191ec8515f5ed90888321343013cda`. Delivery Verifier run `34043847222` also passed before the DONE-state documentation update. For actual acceptance, run `UAT/F-04.01.md` with realistic Slack/GitHub evidence and the production frontend/manual workflow.
