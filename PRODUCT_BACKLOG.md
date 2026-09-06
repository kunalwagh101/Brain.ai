# Brain Product Backlog

Priority: P0 = required for production MVP, P1 = next, P2 = later.

| ID | Epic | Priority | Acceptance outcome |
|---|---|---:|---|
| BRN-001 | Backend foundation | P0 | FastAPI service boots, probes expose app/DB health, CI tests the backend. |
| BRN-002 | Organisations and identity | P0 | Users belong to explicit organisations through memberships; no cross-tenant reads/writes. |
| BRN-003 | Authentication | P0 | Real identity provider/session validation; protected routes reject unauthenticated users. |
| BRN-004 | RBAC and resource permissions | P0 | Roles and resource ACLs are enforced server-side and covered by negative tests. |
| BRN-005 | Integration framework | P0 | OAuth connections have scoped credentials, health, sync cursor and revocation state. |
| BRN-006 | Slack connector | P0 | Authorised channels/messages/users ingest idempotently with source permissions preserved. |
| BRN-007 | GitHub connector | P0 | Repos/PRs/issues/commits/deployments ingest via signed webhooks and backfill. |
| BRN-008 | Canonical event platform | P0 | External events map into versioned Brain events with provenance and deduplication. |
| BRN-009 | Work graph | P0 | People/projects/tracks/work items/decisions/evidence can be linked and traversed. |
| BRN-010 | Search and knowledge | P0 | Permission-filtered keyword + semantic retrieval returns source evidence. |
| BRN-011 | Ask Brain | P0 | Answers cite authorised evidence; unsupported claims are not presented as fact. |
| BRN-012 | AI provider registry | P0 | OpenAI/Anthropic/xAI models and provider connections are centrally represented. |
| BRN-013 | AI usage and cost | P0 | Usage is attributed to organisation/team/project/user/model where evidence exists. |
| BRN-014 | Executive/project dashboards | P0 | Leaders see evidence-backed project state, blockers, incidents and AI usage. |
| BRN-015 | Audit and retention | P0 | Sensitive mutations produce immutable audit records; retention/deletion rules are enforceable. |
| BRN-016 | Alerts and budgets | P1 | Cost/risk/failure thresholds create deduplicated alerts. |
| BRN-017 | Agent runtime | P1 | Agents run with allowlisted tools, least privilege and approval gates. |
| BRN-018 | Native tracks/chat | P2 | Brain-native team communication uses the same work graph and permission model. |
