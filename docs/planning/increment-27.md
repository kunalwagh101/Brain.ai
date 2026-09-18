# Increment 27 — Workspace Search & Quick Switcher

Story: `S-10.11.01`

Status: `IN_PROGRESS`

## Sprint goal

Give Brain one keyboard-first way to jump to authorised channels, projects, tracks, DM counterparts and searchable company evidence without creating another search engine or weakening privacy.

## Vertical slice

Ctrl+K / Cmd+K opens an accessible dialog. With no query, it filters already-loaded visible navigation. With >=2 characters, it adds debounced keyword results from the existing permission-aware Search API through a same-origin WorkOS BFF. Brain-native message results deep-link to the exact channel/message. DM conversation names are locally searchable only for existing participants; DM bodies remain outside organisation-wide search.

## Architecture

- local navigation search: channels, projects, tracks and participant-visible DM counterparts already rendered in the workspace;
- remote search: existing `GET /api/v1/organizations/{id}/search?mode=keyword&limit=12`;
- browser -> same-origin BFF -> server WorkOS token -> FastAPI Search -> current authorization predicate;
- no new database table, index, embedding provider, cache or search service.

## Rejected alternatives

- New Algolia/Elasticsearch/Typesense index: duplicate source of truth and new ACL synchronisation problem without evidence the PostgreSQL SearchDocument baseline is insufficient.
- Hybrid/embedding search in the command palette: adds provider latency/availability to a navigation interaction. Keep keyword deterministic first.
- Organisation-wide DM-content search: explicitly violates the resolved participant-only DM privacy boundary.
- Client-side direct FastAPI search: would require browser bearer-token handling.

## Acceptance truth

Repository implementation can reach `IN_REVIEW`. Final DONE requires executable frontend/search/verifier checks and authenticated WorkOS browser UAT proving keyboard behaviour, exact native-message navigation, live revocation filtering, restricted-source isolation and zero DM-content leakage.
