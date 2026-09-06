# Brain Architecture

## Product boundary

Brain is an organisational intelligence and AI-governance control plane. The first product connects to existing company systems, normalises authorised activity into a common event model, and makes that evidence searchable and queryable. Native chat/tracks come after the control plane is useful on its own.

## Current architecture

- **Frontend:** existing Next.js 16 + React 19 application.
- **Backend:** FastAPI modular monolith under `backend/`.
- **Primary database:** PostgreSQL.
- **Vector search:** pgvector when knowledge ingestion begins; not installed before it is needed.
- **Queue/cache:** Redis is not part of Increment 1. Add a durable queue when connector ingestion starts; do not use Redis as the source of truth.
- **Object storage:** add S3-compatible storage when files/transcripts are ingested.

## Backend modules, in build order

1. identity and organisations
2. permissions and tenant enforcement
3. integration registry and OAuth connection model
4. raw event capture and idempotent ingestion
5. canonical event model
6. work graph and evidence links
7. search/RAG with permission filtering before retrieval
8. AI gateway, usage and budgets
9. agent runtime with explicit tool permissions and approvals

## Tenant invariant

Every customer-owned domain record must carry an `organization_id` or be reachable only through an organisation-owned parent. Tenant filtering is a server-side requirement. The frontend is never trusted to enforce tenant boundaries.

## Security invariants

- no plaintext third-party secrets in the application database
- no wildcard CORS in production
- webhook signatures must be verified before processing
- permission checks happen before data reaches an LLM
- every sensitive mutation must become an audit event
- agent tools default to deny and least privilege
- raw source provenance is retained so AI claims can cite evidence

## Why a modular monolith

The MVP needs strong transactional boundaries and fast iteration more than independently scaled services. FastAPI modules can be split later only where measured load, failure isolation or team ownership makes the split valuable.

## Increment 1

The repository now has the backend runtime, PostgreSQL connection layer, core organisation/user/membership schema, Alembic migration, liveness/readiness probes, request IDs, basic security headers, tests and CI. Authentication and CRUD are intentionally not faked; they are the next production slice.
