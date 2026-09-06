# Brain Delivery Board

Method: Scrum + Kanban hybrid. Two-week increments. WIP limit: IN_PROGRESS <= 2. Chat is not state.

Format: `STATUS | STORY_ID | FEATURE | NOTE`

DONE | S-01.01.01 | F-01.01 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.02.01 | F-01.02 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-01.03.01 | F-01.03 | Engineering evidence in TRACEABILITY.md; UAT remains pending in UAT.md
DONE | S-02.01.01 | F-02.01 | Engineering evidence in TRACEABILITY.md; real-data/frontend UAT remains pending
DONE | S-02.02.01 | F-02.02 | Engineering evidence in TRACEABILITY.md; real Slack + frontend UAT remains pending
DONE | S-02.03.01 | F-02.03 | Engineering evidence in TRACEABILITY.md; real GitHub + frontend UAT remains pending
BACKLOG | S-02.04.01 | F-02.04 | OQ-004 selects first provider
DONE | S-03.01.01 | F-03.01 | Engineering evidence in TRACEABILITY.md; realistic raw-data inspection UAT remains pending
DONE | S-03.02.01 | F-03.02 | Engineering evidence in TRACEABILITY.md; Slack/GitHub real-data + frontend UAT remains pending
DONE | S-03.03.01 | F-03.03 | Engineering evidence in TRACEABILITY.md; real provider identity + frontend/manual UAT remains pending
BACKLOG | S-04.01.01 | F-04.01 | Identity resolution dependency is engineering-DONE; eligible for refinement
BACKLOG | S-04.02.01 | F-04.02 | Depends on work graph + retrieval evaluation
BACKLOG | S-05.01.01 | F-05.01 | Depends on RBAC + canonical evidence
BACKLOG | S-05.02.01 | F-05.02 | OQ-005 before provider contract is frozen
BACKLOG | S-06.01.01 | F-06.01 | Depends on RBAC
BACKLOG | S-06.02.01 | F-06.02 | Depends on AI provider registry/gateway
BACKLOG | S-06.03.01 | F-06.03 | Depends on RBAC + integration secret-reference model
BACKLOG | S-07.01.01 | F-07.01 | Depends on work graph + decision/blocker memory
BACKLOG | S-07.02.01 | F-07.02 | Depends on project status + usage/cost
BACKLOG | S-08.01.01 | F-08.01 | Depends on AI gateway + audit/retention
BACKLOG | S-09.01.01 | F-09.01 | Foundation exists; acceptance evidence incomplete
BACKLOG | S-09.02.01 | F-09.02 | OQ-006 retention defaults unresolved
BACKLOG | S-09.03.01 | F-09.03 | Phase 3 verifier is merged and green; full production deployment story remains
BACKLOG | S-09.04.01 | F-09.04 | Benchmarks attach to implemented vertical slices
DEFERRED | S-10.01.01 | F-10.01 | Revisit after E-01 through E-05 prove external-tool wedge

## Sprint planning

Increment 6 goal: **every Slack/GitHub source actor can be represented as a tenant-scoped source identity without pretending it is a Brain user; only verified exact evidence may auto-resolve, while Owner/Admin manual resolve/reassign/unresolve actions are tenant-safe, reversible and immutably audited.**

Vertical slice: source-identity/history schema -> canonical actor observation -> exact verified-email resolver -> unresolved/conflict states -> Owner/Admin identity-management API -> canonical resolved-user reference -> reconciliation for existing canonical events -> tests/migration/docs/UAT.

## Increment 6 review

- Added tenant-scoped source identities that are explicitly separate from WorkOS authentication identities.
- Canonical Slack/GitHub person actors now create/reuse one source identity per organisation/provider/external ID while preserving the original source actor fields.
- Added one append-only source-identity observation per canonical event; replay remains idempotent.
- Automatic resolution is intentionally narrow: only a provider-verified exact email may link to an active member of the same Brain organisation.
- Missing/unverified evidence stays `UNRESOLVED`; conflicting verified evidence moves the source identity to `REVIEW_REQUIRED` and clears unsafe attribution.
- No name-only, username-similarity, domain-only, cross-tenant or LLM identity guessing is used.
- Added Owner/Admin `identity.manage` routes for listing, history, manual resolve/reassign/unresolve and reconciliation of existing canonical events.
- Manual resolution targets must be active members of the same organisation; every material change writes immutable previous/new-user history.
- Canonical events gain optional `source_identity_id` and `resolved_user_id` without rewriting source-provider actor evidence.
- UTC normalization prevents SQLite/PostgreSQL timezone representation differences from corrupting first/last-seen comparisons.
- Alembic revision `20260906_0007` adds source identity, observation and resolution-history storage plus canonical linkage with downgrade support.
- Backend CI passed lint and 82 tests on GitHub Actions run `34038863067`.
- Delivery Verifier passed on run `34038863068` before engineering-DONE was claimed.
- F-03.03 remains `UAT_PENDING`; real-provider identity evidence and frontend/manual acceptance are not claimed by engineering tests.

## Increment 5 review

- Added schema-versioned canonical events with one canonical row per raw event and immutable raw-event provenance.
- Slack and GitHub now map into the same actor/action/object/source/permissions/provenance contract.
- Unsupported or malformed mappings are quarantined; raw source evidence remains intact instead of being silently discarded.
- GitHub uses a verified GitHub App installation flow rather than PATs or arbitrary client-supplied installation IDs.
- Brain-signed expiring state binds the initiating Brain organisation/user; a second signed selection token binds the verified GitHub installation/account choice.
- A selected installation is re-fetched and verified as belonging to the configured GitHub App before it is connected.
- The generic integration endpoint rejects `provider=github`, preventing bypass of the verified GitHub App flow.
- GitHub App private key, OAuth client secret and webhook secret are loaded by secret reference; installation access tokens are short-lived and are not persisted.
- Webhooks validate `X-Hub-Signature-256` against the exact raw body before parsing; `X-GitHub-Delivery` provides retry-safe idempotency.
- Private/internal repository evidence carries `github:repository:<id>` source ACL provenance for the later retrieval-authorisation layer.
- GitHub backfill walks repository metadata, commits, pull requests, issues and deployments using a signed, connection-bound, replay-safe cursor.
- Alembic revision `20260906_0006` adds provider metadata and canonical event storage with downgrade support.
- Backend CI passed lint and 73 tests on GitHub Actions run `34037248953`.
- Delivery Verifier passed on run `34037248958` before engineering-DONE was claimed; the final DONE-state gate also passed before merge.
- F-02.03 and F-03.02 remain `UAT_PENDING`; they are not called passed/accepted until real GitHub/Slack data and frontend/manual UAT are recorded.

## Session-open self-audit

- Nine stories are engineering-DONE; user acceptance remains independently tracked in UAT.md.
- Current WIP count: 0.
- F-03.03 is engineering-DONE only; real-provider/manual UAT remains pending.
- WorkOS authentication identities remain separate from Slack/GitHub source identities.
- Automatic source-identity linking requires provider-verified exact evidence inside the same organisation; incomplete evidence remains unresolved.
- No fuzzy name/username/domain/LLM guessing is allowed for automatic identity resolution.
- S-04.01.01 Work Graph is now dependency-unlocked and is the next product story eligible for refinement.
