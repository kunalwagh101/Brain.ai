# Brain Product Backlog

## Method

Brain uses a **Scrum + Kanban hybrid**: two-week fixed-scope MVP increments, with a machine-checked Kanban board and WIP limit of 2. Scrum gives us a reviewable vertical increment; Kanban prevents parallel unfinished work.

## Product outcome

Brain is the intelligence layer for an AI-native company: it connects authorised company tools, reconstructs organisational work from evidence, governs AI/API usage, and lets humans and AI agents operate from the same permission-aware context.

## Success criteria

- Zero cross-tenant or unauthorised retrieval in security tests.
- >=99.9% accepted connector events persisted or durably queued.
- <0.1% duplicate canonical events after idempotency.
- >=98% citation correctness on the evaluation set before Ask Brain is called production-ready.
- >=90% source-retrieval recall on the evaluation set.
- p95 structured API latency <500 ms excluding external providers; search p95 <1.5 s; AI-answer p95 target <10 s.
- 100% AI/API usage records have provider/model/timestamp; attribution fields are nullable only when source evidence cannot establish them.

## Epics

| ID | Business outcome | Owner | Value hypothesis |
|---|---|---|---|
| E-01 | Secure multi-tenant company foundation | Platform | Trustworthy isolation is required before any company data is connected. |
| E-02 | Connect existing company systems | Integrations | Adoption is easier when Brain works above tools companies already use. |
| E-03 | Convert activity into trustworthy company evidence | Data Platform | Normalised provenance makes cross-tool reasoning possible. |
| E-04 | Reconstruct work and organisational context | Intelligence | Linking people, projects, decisions and artifacts makes Brain more than search. |
| E-05 | Permission-aware search and Ask Brain | AI | Evidence-backed answers reduce time spent finding context. |
| E-06 | AI and API governance | AI Platform | Central usage, budgets and access reduce cost and security risk. |
| E-07 | Executive and project command centre | Product | Leaders need evidence-backed visibility into progress, blockers and spend. |
| E-08 | Agent execution with approval controls | AI Platform | Agents create value only when tool access is constrained and auditable. |
| E-09 | Production reliability, security and operations | Platform/Security | Real active users require measurable reliability, rollback and observability. |
| E-10 | Brain workspace and native collaboration | Product | A Slack/Discord-style operating surface makes the intelligence layer usable by the whole company while preserving Brain's permission and evidence model. |

## Features and stories

### E-01 Secure multi-tenant company foundation

#### F-01.01 Organisation and identity
**Capability:** organisations, users, memberships and external identities.

**S-01.01.01 — Create and read organisation membership**  
As an organisation owner, I want users to belong to an explicit organisation with a role, so that company data has an enforceable ownership boundary.  
Acceptance: Given a valid authenticated owner, when a membership is created, then it is persisted for exactly one organisation; Given a user from Org A, when Org B is requested, then the API returns 404/403 and no Org B fields.  
Dependencies: foundation merged; blocking risk: authentication contract. Size: M. Leading indicator: tenant-boundary test pass rate. Business value: E-01.  
Tasks: T-01.01.01.a API schemas/routes; T-01.01.01.b transaction/service path; T-01.01.01.c positive/negative tests; T-01.01.01.d docs.

#### F-01.02 Authentication
**S-01.02.01 — Verify real user identity**  
As a company user, I want secure sign-in, so that Brain can attribute every protected action to a verified identity.  
Acceptance: Given no valid session/token, protected routes return 401; Given a valid configured provider identity, the backend resolves one Brain user without trusting client-supplied email/role.  
Dependencies: S-01.01.01. Risk: provider choice in OQ-001. Size: M. Indicator: authenticated-route coverage. Value: E-01.  
Tasks: T-01.02.01.a provider adapter; T-01.02.01.b session/token validation; T-01.02.01.c tests; T-01.02.01.d threat notes.

#### F-01.03 RBAC and resource ACL
**S-01.03.01 — Enforce tenant and role permissions server-side**  
As an organisation admin, I want roles and resource permissions enforced before data access, so that users and AI cannot see unauthorised company data.  
Acceptance: Given each role, when a protected mutation/read is attempted, then the policy matrix is enforced; Given an unauthorised resource, retrieval rejects before any LLM/tool call.  
Dependencies: S-01.02.01. Risk: private-message policy OQ-002. Size: L. Indicator: permission-leakage failures = 0. Value: E-01.  
Tasks: T-01.03.01.a policy matrix; T-01.03.01.b dependency layer; T-01.03.01.c negative tests; T-01.03.01.d audit hooks.

### E-02 Connect existing company systems

#### F-02.01 Integration framework
**S-02.01.01 — Manage scoped integration connections**  
As an admin, I want to connect/revoke external systems with visible scopes and health, so that Brain has controlled access and can recover from revocation.  
Acceptance: connection stores no plaintext secret; revocation prevents future sync; health and sync cursor are persisted.  
Dependencies: S-01.03.01. Risk: secrets-manager provider OQ-003. Size: L. Indicator: connector setup success. Value: E-02.  
Tasks: T-02.01.01.a schema; T-02.01.01.b credential-reference contract; T-02.01.01.c lifecycle endpoints; T-02.01.01.d tests.

#### F-02.02 Slack
**S-02.02.01 — Ingest authorised Slack activity idempotently**  
As a team member, I want authorised Slack channels/messages/threads represented in Brain, so that communication becomes searchable company evidence.  
Acceptance: verified webhook/backfill input produces one raw event and at most one canonical event; source permissions are retained; replay produces no duplicate canonical record.  
Dependencies: S-02.01.01, S-03.01.01. Risk: DM policy OQ-002. Size: L. Indicator: ingestion success/duplicate rate. Value: E-02.  
Tasks: T-02.02.01.a OAuth/scopes; T-02.02.01.b signature verification; T-02.02.01.c webhook/backfill; T-02.02.01.d permission mapping/tests.

#### F-02.03 GitHub
**S-02.03.01 — Ingest authorised GitHub engineering activity**  
As an engineering leader, I want repos, PRs, issues, commits and deployments represented in Brain, so that product progress is grounded in engineering evidence.  
Acceptance: signed webhook accepted exactly once; backfill resumes from cursor; repository visibility/organisation ownership is preserved.  
Dependencies: S-02.01.01, S-03.01.01. Size: L. Indicator: event coverage and lag. Value: E-02.  
Tasks: T-02.03.01.a GitHub App contract; T-02.03.01.b webhook; T-02.03.01.c backfill; T-02.03.01.d tests.

#### F-02.04 Meeting/document sources
**S-02.04.01 — Ingest files/transcripts through a generic evidence adapter**  
As a team, I want authorised meeting transcripts and documents represented with provenance, so that decisions outside chat/code are not lost.  
Acceptance: file/transcript source is immutable-addressed, permission-labelled and chunkable; deleted/revoked source becomes unavailable to retrieval.  
Dependencies: S-02.01.01, S-03.01.01. Risk: first provider OQ-004. Size: M. Indicator: source coverage. Value: E-02.

### E-03 Trustworthy company evidence

#### F-03.01 Raw ingestion and idempotency
**S-03.01.01 — Persist raw source events before enrichment**  
As an operator, I want external events durably captured with source identifiers and idempotency keys, so that retries, audits and reprocessing are safe.  
Acceptance: duplicate delivery is detected; malformed payload is rejected/quarantined; accepted raw payload has source, received_at, organisation, version and checksum/reference.  
Dependencies: S-01.03.01. Size: L. Indicator: accepted-event durability. Value: E-03.

#### F-03.02 Canonical event model
**S-03.02.01 — Normalise heterogeneous events into a versioned schema**  
As the intelligence layer, I want Slack/GitHub/AI events in one canonical event contract, so that downstream systems reason consistently.  
Acceptance: canonical event contains actor/action/object/source/timestamp/org/permissions/provenance; schema version is explicit; unsupported input never silently drops fields.  
Dependencies: S-03.01.01. Size: L. Indicator: canonicalisation success. Value: E-03.

#### F-03.03 Identity resolution
**S-03.03.01 — Link external identities without unsafe guessing**  
As an admin, I want Slack/GitHub/AI identities linked to Brain users with evidence, so that activity attribution is trustworthy.  
Acceptance: Given a source identity with an exact provider ID, when it is observed again in the same organisation, then the same source identity is reused; Given a source identity with a provider-verified email that exactly matches one active member in the same organisation, when resolution runs, then it auto-resolves with deterministic evidence; Given an unverified, missing or ambiguous identity, when resolution runs, then it remains unresolved and no Brain user is guessed; Given an Owner/Admin manually resolves, reassigns or unresolves an identity, then the target user must be an active member of that organisation and an immutable before/after history record is written.  
Dependencies: S-01.01.01, S-01.03.01, S-03.02.01. Blocking risk: provider events frequently lack verified email, so unresolved/manual is a valid production state rather than a reason to guess. Size: M. Indicator: verified attribution rate and false-link count = 0 in the evaluation set. Value: E-03.  
Rules: source identities are tenant-scoped; WorkOS authentication identities remain separate; no name-only, username-similarity, email-domain-only, cross-tenant or LLM auto-linking; canonical source observations are append-only evidence; all manual changes are reversible and audited.  
Tasks: T-03.03.01.a source-identity + immutable resolution-history schema/migration; T-03.03.01.b idempotent canonical-actor observation and verified-email deterministic resolver; T-03.03.01.c Owner/Admin list/resolve/reassign/unresolve/reconcile API with tenant checks; T-03.03.01.d canonical-event resolved-user linkage without rewriting source actor evidence; T-03.03.01.e positive/negative/concurrency/idempotency tests; T-03.03.01.f migration rollback, UAT, security and operator docs.

### E-04 Work graph and organisational memory

#### F-04.01 Work graph
**S-04.01.01 — Link people, projects, tracks, work items and evidence**  
As a project lead, I want related work across tools connected, so that Brain can explain what happened and why.  
Acceptance: graph edges have type/source/confidence/provenance; unsupported inferred links are distinguishable from verified links; traversal is tenant-filtered.  
Dependencies: S-03.02.01, S-03.03.01. Size: L. Indicator: evaluation link precision. Value: E-04.

#### F-04.02 Decision and blocker memory
**S-04.02.01 — Extract candidate decisions/blockers with evidence**  
As a project lead, I want important decisions and blockers surfaced with citations, so that critical context does not disappear in chat/meetings.  
Acceptance: extraction never converts an unsupported inference into confirmed fact; candidate includes evidence/confidence/state; human correction is stored.  
Dependencies: S-04.01.01, S-05.01.01. Size: L. Indicator: >=90% precision target on eval set before production claim. Value: E-04.

### E-05 Search and Ask Brain

#### F-05.01 Permission-aware retrieval
**S-05.01.01 — Search authorised evidence only**  
As a user, I want keyword and semantic search across permitted company evidence, so that I can find context without leaking restricted data.  
Acceptance: permission filter executes before result content is returned; revoked content disappears; each result contains source provenance.  
Dependencies: S-01.03.01, S-03.02.01. Size: L. Indicator: retrieval recall and zero leakage. Value: E-05.

#### F-05.02 Ask Brain
**S-05.02.01 — Answer company questions with evidence-backed RAG**  
As a user, I want natural-language answers about company work, so that I can understand status/decisions quickly.  
Acceptance: factual claims cite retrieved authorised evidence; insufficient evidence produces an explicit uncertainty/no-answer response; eval gates citation correctness >=98% and retrieval recall >=90%.  
Dependencies: S-05.01.01. Risk: model/provider policy OQ-005. Size: L. Indicator: answer success/citation correctness. Value: E-05.

### E-06 AI and API governance

#### F-06.01 AI provider registry and gateway
**S-06.01.01 — Route governed AI requests through a provider-neutral contract**  
As an admin, I want approved AI providers/models centrally represented, so that usage and policy are consistent.  
Acceptance: request records provider/model/org/user/project when known; provider failure is surfaced; no secret is logged.  
Dependencies: S-01.03.01. Size: L. Indicator: governed AI request share. Value: E-06.

#### F-06.02 Usage, cost and budgets
**S-06.02.01 — Attribute AI/API usage and enforce budgets**  
As a leader, I want spend by provider/model/team/project and budget alerts, so that AI costs are visible and controllable.  
Acceptance: cost calculation is deterministic from source rates/config; unknown attribution stays unknown; threshold alerts deduplicate.  
Dependencies: S-06.01.01. Size: M. Indicator: attributable spend %. Value: E-06.

#### F-06.03 API registry
**S-06.03.01 — Inventory external API access without plaintext credentials**  
As a security admin, I want API grants, owners, scopes and usage visible, so that over-privileged or stale access can be found.  
Acceptance: registry stores secret references only; grant has owner/scope/environment/status; revoke/expire transitions are audited.  
Dependencies: S-01.03.01, S-02.01.01. Size: M. Indicator: governed credentials %. Value: E-06.

### E-07 Command centre

#### F-07.01 Project status
**S-07.01.01 — Show evidence-backed project progress and blockers**  
As a leader, I want project status grounded in milestones/tasks/PRs/decisions, so that progress is not an invented AI score.  
Acceptance: status exposes underlying evidence; percentage is calculated only from configured structured work; AI may explain but not fabricate the number.  
Dependencies: S-04.01.01, S-04.02.01. Size: M. Indicator: dashboard evidence coverage. Value: E-07.

#### F-07.02 Executive overview
**S-07.02.01 — Show organisation pulse across projects, risk and AI spend**  
As an executive, I want one permission-aware company overview, so that I can see what needs attention.  
Acceptance: every displayed metric has deterministic source/query; no employee-worth/productivity score; restricted project data respects ACL.  
Dependencies: S-07.01.01, S-06.02.01. Size: M. Indicator: weekly active leaders. Value: E-07.

### E-08 Agent execution

#### F-08.01 Agent runtime
**S-08.01.01 — Execute agents with explicit tools and approval gates**  
As a user, I want AI agents to perform approved work, so that Brain can move from understanding to action safely.  
Acceptance: tool access defaults deny; read/act/act-with-approval/deny policy is enforced; tool calls and approvals are audited; high-risk mutation cannot bypass approval.  
Dependencies: S-06.01.01, S-09.02.01. Size: L. Indicator: successful governed agent runs. Value: E-08.

### E-09 Production reliability, security and operations

#### F-09.01 Observability and SLOs
**S-09.01.01 — Trace requests, connector jobs and AI calls**  
As an operator, I want request IDs, traces, metrics and actionable failures, so that incidents can be diagnosed.  
Acceptance: request/organisation/integration/model latency/error/cost metadata is emitted without secrets; health/readiness distinguish process from dependency health.  
Dependencies: foundation. Size: M. Indicator: diagnosable incident %. Value: E-09.

#### F-09.02 Audit, retention and deletion
**S-09.02.01 — Maintain immutable sensitive-action audit evidence and enforce retention**  
As a security/compliance admin, I want sensitive actions auditable and customer data deletable under policy, so that Brain can be operated responsibly.  
Acceptance: security-relevant mutation produces audit event; retention job is deterministic/idempotent; deletion removes/revokes derived retrieval material and records completion evidence.  
Dependencies: S-01.03.01. Risk: retention defaults OQ-006. Size: L. Indicator: audit coverage %. Value: E-09.

#### F-09.03 Deployment, rollback, backup and restore
**S-09.03.01 — Deploy safely with verified rollback and restore**  
As an operator, I want CI/CD, migrations, backups and rollback tested, so that production failures do not become data loss.  
Acceptance: CI blocks failing tests/verifier; migration has rollback/forward-recovery note; backup restore is exercised against a disposable environment.  
Dependencies: Phase 3 verifier. Size: M. Indicator: recovery exercise success. Value: E-09.

#### F-09.04 Performance and cost budgets
**S-09.04.01 — Enforce measurable latency/cost budgets**  
As a product owner, I want load and cost thresholds measured, so that scale claims are evidence-based.  
Acceptance: benchmark captures p50/p95 and test load; regressions over agreed budget fail/review; AI cost per evaluated task is reported.  
Dependencies: relevant vertical slice. Size: M. Indicator: budget pass rate. Value: E-09.

### E-10 Brain workspace and native collaboration

The frontend is a first-class product surface. A Slack/Discord-style information architecture is required for the MVP even though Brain does **not** need to clone every Slack feature before launch. Native messaging and private collaboration remain separate capabilities with their own backend/security acceptance gates.

#### F-10.01 Native tracks/chat
**S-10.01.01 — Communicate in Brain tracks using the same work graph and permissions**  
As a team member, I want Brain-native project channels with humans and agents, so that work can happen where intelligence already lives.  
Acceptance: channel/message persistence is tenant-scoped; messages inherit channel/track ACL; agent participation is explicit; message/event enters the canonical evidence path; revoked channel access removes future read access without deleting immutable audit evidence.  
Dependencies: E-01 through E-05. Size: L. Indicator: active native tracks. Value: E-10. Priority: P1.

#### F-10.02 Workspace shell and navigation
**S-10.02.01 — Operate Brain through a Slack/Discord-style permission-aware workspace**  
As a company user, I want one workspace with organisation switching, team/track/project navigation and intelligence surfaces, so that Brain feels like the place where company work is understood rather than a collection of disconnected dashboards.  
Acceptance: authenticated root experience is the live workspace rather than the sample preview; organisation membership and role come from the server session; the left navigation exposes only currently authorised projects/tracks/resources; project/track labels come from real Brain data rather than hard-coded demo teams; restricted resource names/counts do not leak; desktop layout supports workspace rail + navigation sidebar + main work surface + contextual intelligence region; empty/loading/error states are usable; keyboard navigation, focus states and responsive behaviour pass frontend UAT.  
Dependencies: S-01.02.01, S-01.03.01, S-04.01.01. Size: L. Indicator: successful authenticated workspace load and navigation coverage. Value: E-10. Priority: P0.  
Tasks: T-10.02.01.a permission-aware workspace navigation read contract; T-10.02.01.b workspace rail/sidebar/main/context shell; T-10.02.01.c real project/track navigation; T-10.02.01.d responsive/accessibility states; T-10.02.01.e frontend tests/UAT.

#### F-10.03 Live intelligence surfaces
**S-10.03.01 — Use Ask Brain, projects, decisions/blockers and company pulse inside the workspace**  
As a user, I want Brain intelligence embedded beside the work it describes, so that I do not have to jump between standalone dashboards.  
Acceptance: Ask Brain, Project Command Centre, Decision/Blocker Memory and Executive Overview render live backend data with role/permission filtering; Ask Brain citations open provenance; non-executive users are not blocked from the whole workspace merely because Executive Overview is unavailable; no fixture/sample metric is rendered in authenticated production mode; provider/API failures have bounded retry/error states without widening access.  
Dependencies: S-05.02.01, S-04.02.01, S-07.01.01, S-07.02.01. Size: L. Indicator: live intelligence surface completion rate. Value: E-10. Priority: P0.

#### F-10.04 Production frontend authentication and BFF
**S-10.04.01 — Connect the Next.js workspace to Brain through official WorkOS AuthKit server sessions**  
As a company user, I want production sign-in and a secure same-origin frontend, so that browser code never handles reusable Brain/API credentials directly.  
Acceptance: official WorkOS AuthKit Next.js 16 integration supplies the authenticated server session; server-side access token is used for FastAPI calls; the browser talks to same-origin BFF routes for mutations such as Ask Brain; no client-supplied role/email/token is trusted; logout/session expiry is handled; production root cannot silently fall back to ChatGPT preview headers or sample credentials.  
Dependencies: S-01.02.01, official WorkOS package installation and real lockfile. Size: M. Indicator: authenticated-browser UAT pass rate. Value: E-10. Priority: P0.

#### F-10.05 Evidence and files experience
**S-10.05.01 — Upload, browse and inspect governed documents/transcripts from the workspace**  
As a team member, I want documents and meeting transcripts available in the workspace with provenance and permissions, so that non-chat context can be used without leaving Brain.  
Acceptance: authorised user can upload supported S-02.04 sources, see processing/active/failed/deleted state, inspect source metadata/provenance and use resulting evidence in Search/Ask Brain; restricted uploads remain invisible to unauthorised users; deletion/revocation state is reflected without stale UI content.  
Dependencies: S-02.04.01, S-05.01.01. Size: M. Indicator: successful governed upload-to-retrieval flow. Value: E-10. Priority: P0.

#### F-10.06 Conversation UX
**S-10.06.01 — Make Brain channels feel like Slack/Discord with safe conversation affordances**  
As a team member, I want focused channels with threads, mentions, reactions and unread state, so that Brain is practical for daily team communication without weakening its permission model.  
Acceptance: Given a permitted root message, when a permitted writer replies, then the reply is stored under exactly that root and is returned only inside the same tenant and channel; Given an exact @email for a current readable organisation/channel member, when a message or reply is created, then the mention is stored once, while unknown or unauthorised addresses create no mention; Given a permitted message, when a permitted writer adds or removes an allowed reaction, then one per-user reaction is stored idempotently and aggregate counts remain correct; Given channel messages created by other actors after a user's monotonic read cursor, when channels are listed, then only that user receives the correct unread count; Given access to a restricted channel is revoked, when unread, thread, reaction or mention endpoints are requested, then they return no channel or message content; Given an agent-authored message, when the channel renders, then the agent identity is visibly distinct; Given a channel is selected, when the workspace renders, then the channel conversation is the primary work surface with keyboard-visible controls, responsive layout, thread context, reaction controls and unread badges.  
Dependencies: S-10.01.01. Blocking risk: executable/backend and authenticated-browser acceptance depend on the existing CI runner and S-10.04 WorkOS activation; repository implementation alone cannot satisfy DONE. Size: L. Leading indicator: active channel participation and unread-to-read conversion. Business value: E-10. Priority: P1.  
Tasks: T-10.06.01.a conversation schema/migration; T-10.06.01.b tenant-safe thread/mention/reaction/read services; T-10.06.01.c permission-aware APIs and same-origin BFF contracts; T-10.06.01.d focused Slack/Discord-style channel UI; T-10.06.01.e security/idempotency/accessibility tests; T-10.06.01.f docs/UAT/demo/rollback.

**S-10.06.02 — Support permission-safe direct messages without turning Brain into employee surveillance**  
As a user, I want private direct conversations with explicit participants, so that sensitive collaboration has a bounded home in Brain.  
Acceptance: DM membership is explicit; non-participants including executives cannot read content merely because of role; search/Ask Brain inclusion follows the approved OQ-002 private-message policy; no unrestricted employer/private-message capture; deletion/retention behaviour is explicit and audited.  
Dependencies: S-10.01.01, OQ-002. Size: L. Indicator: zero private-message leakage. Value: E-10. Priority: P1.

#### F-10.07 Developer and agent workspace
**S-10.07.01 — Run governed engineering/agent work from project and channel context**  
As an engineer, I want repo context, agent runs, approvals and resulting patches/PR references visible inside the project workspace, so that coding agents participate in the same company context without receiving an unrestricted shell.  
Acceptance: UI exposes only tools/actions authorised by S-08.01; high-risk actions visibly require approval; repo/project context is permission-aware; agent/model identity and action state are explicit; no arbitrary browser-side credential access or hidden generic shell is introduced.  
Dependencies: S-08.01.01, S-02.03.01, S-10.02.01. Size: L. Indicator: governed agent task completion rate. Value: E-10. Priority: P1.

#### F-10.08 Workspace administration
**S-10.08.01 — Manage integrations, members, permissions and AI/API governance from the workspace**  
As an owner/admin, I want setup and governance surfaces inside Brain, so that the product can be operated without direct API calls or database work.  
Acceptance: role-gated UI covers membership visibility, Slack/GitHub/evidence integration state, resource grants where supported, approved AI runtimes, budget/API-governance status and revocation flows; secrets are never displayed; unavailable capabilities fail closed rather than presenting fake controls.  
Dependencies: E-01, E-02, E-06. Size: L. Indicator: admin workflow completion rate. Value: E-10. Priority: P1.

## Requirements -> Backlog coverage

| Requirement | Backlog IDs |
|---|---|
| FastAPI backend | S-01.01.01, S-09.01.01 |
| Production-grade active-user MVP | E-09, S-09.03.01, S-09.04.01, S-10.02.01, S-10.04.01 |
| Existing Slack users | S-02.02.01 |
| GitHub/code progress | S-02.03.01, S-07.01.01, S-10.07.01 |
| Meetings/video/document evidence | S-02.04.01, S-10.05.01 |
| ChatGPT/OpenAI, Claude, Grok/xAI and other AI | S-06.01.01, S-06.02.01 |
| Intake/channel/structure data | S-03.01.01, S-03.02.01, S-10.02.01 |
| Understand company activity | S-04.01.01, S-04.02.01 |
| Boss/company overview | S-07.02.01, S-10.03.01 |
| Project progress | S-07.01.01, S-10.03.01 |
| AI/API access visibility | S-06.03.01, S-10.08.01 |
| AI/API usage/cost visibility | S-06.02.01, S-10.03.01 |
| Slack/Discord-style company workspace | S-10.02.01, S-10.03.01 |
| Human communication | S-10.01.01, S-10.06.01, S-10.06.02 |
| Tenant/channel-scoped message threads | S-10.06.01 |
| Exact-member mentions without identity guessing | S-10.06.01 |
| Idempotent per-user message reactions | S-10.06.01 |
| Per-user monotonic unread state | S-10.06.01 |
| Restricted-channel notification/content privacy | S-10.06.01 |
| Visibly attributed agent messages | S-10.01.01, S-10.06.01 |
| Focused responsive Slack/Discord-style channel surface | S-10.02.01, S-10.06.01 |
| AI tracks/agents | S-08.01.01, S-10.01.01, S-10.07.01 |
| Permission-aware company memory | S-01.03.01, S-05.01.01 |
| RAG/search | S-05.01.01, S-05.02.01 |
| Citations / no unsupported claims | S-05.02.01, S-10.03.01 |
| Data provenance | S-03.01.01, S-03.02.01, S-10.05.01 |
| Identity resolution | S-03.03.01 |
| Security/auth/authz | S-01.02.01, S-01.03.01, S-09.02.01, S-10.04.01 |
| Validation/data integrity/idempotency | S-03.01.01, S-03.02.01 |
| Observability | S-09.01.01 |
| Migrations/rollback/backup | S-09.03.01 |
| Latency/cost benchmarks | S-09.04.01 |
| Accessibility | S-07.01.01, S-07.02.01, S-10.02.01, S-10.03.01, S-10.05.01 |
| CI and lie-detector verifier | S-09.03.01 |
| Agile/Scrum/Kanban artifacts | S-09.03.01 |

Orphan requirements: **0**.

## Out of scope for production MVP

- Native video calling/recording: use connectors first; revisit after native tracks prove adoption.
- Replacing Jira/Linear/CRM/email: Brain consumes their evidence rather than cloning them; workspace surfaces may expose governed links/status/actions without recreating those products wholesale.
- Custom foundation-model training/fine-tuning: no evidence it beats RAG/rules for MVP.
- Kubernetes/microservices: modular monolith until measured scaling/failure-isolation needs justify split.
- Graph database: PostgreSQL relationship tables first; add specialised graph storage only after measured query limits.
- Secret storage in Brain DB: prohibited; secrets manager/reference model only.
- Secret employee surveillance or unrestricted private-message capture: prohibited by product/security boundary.
- Employee productivity/worth scoring: explicitly rejected; project/system evidence only.