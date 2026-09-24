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

**S-10.06.02 — Support participant-safe Brain-native direct messages without turning Brain into employee surveillance**  
As a user, I want private one-to-one conversations with explicit participants, so that sensitive collaboration has a bounded home in Brain without silently becoming employer-wide intelligence.  
Acceptance: only the two explicit participants can list/read a DM; Owner/Admin/Executive roles have no content override merely because of role; creation resolves an exact current same-organisation member and cannot accept arbitrary participant IDs; DM content is never projected into organisation-wide RawEvent/CanonicalEvent/Work Graph/SearchDocument or returned through organisation-wide Search/Ask Brain/Decision Memory/Project/Executive surfaces; normal DM sends do not create organisation-wide per-message/per-conversation audit records; browser mutations use authenticated same-origin BFF routes with no reusable bearer token; `private_message_days` is an explicit independent retention class where `NULL` means no automatic age purge, legal hold blocks purge, and retention-run accounting records only aggregate deletion counts; PostgreSQL tenant constraints and migration rollback/forward recovery are verified.  
Dependencies: S-10.01.01, OQ-008. Blocking risk: authenticated browser acceptance depends on S-10.04 WorkOS activation; repository implementation alone cannot satisfy DONE. Size: L. Indicator: zero private-message leakage and correct explicit-retention behavior. Value: E-10. Priority: P1.  
Tasks: T-10.06.02.a participant-scoped one-to-one schema/migrations; T-10.06.02.b tenant/participant-safe service and API; T-10.06.02.c company-intelligence exclusion and privacy regressions; T-10.06.02.d Slack-style DM navigation/panel; T-10.06.02.e same-origin WorkOS BFF contracts; T-10.06.02.f explicit private-message retention/legal-hold integration; T-10.06.02.g PostgreSQL/browser/accessibility UAT.

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

#### F-10.09 Activity & Notifications
**S-10.09.01 — Give each user one permission-aware Activity & Notifications inbox**  
As a Brain user, I want one personal attention queue for collaboration, agent, project and integration events, so that I can see what needs my attention and jump back to the exact authorised source without searching across the workspace.  
Acceptance: Given a current organisation member, when Activity is opened, then exact @mentions, thread replies, unread channel activity, agent approval requests, agent completion/failure events, visible project/blocker updates and authorised integration failures are returned with personal read/unread state; Given an item references channel, DM, project, blocker, agent run/step or integration state, when source permission or visibility is revoked, then the item disappears immediately and contributes nothing to unread count; Given a persisted item, when it is opened, then its link targets the exact source context rather than a generic page; Given mark-one or mark-all is used, then only the authenticated recipient's currently visible items are changed; Given notification preferences are updated, then only reviewed boolean categories are accepted and disabled categories are suppressed without deleting the underlying product object; Given any Activity API/UI response, then no copied DM/message body, provider secret, API credential, agent arguments/results or private evidence excerpt is exposed; Given the frontend mutates Activity, then it uses authenticated same-origin WorkOS BFF routes and no reusable bearer token is exposed to browser code; Given concurrent first reads create default preferences, then the unique per-organisation/user preference row remains idempotent and the request recovers safely from a uniqueness race; Given Alembic migration history, then the existing notification branches converge to one head before the Activity inbox extension is applied and upgrade/downgrade/forward recovery is testable.  
Dependencies: S-10.06.01, S-10.06.02, S-10.07.01, S-10.08.01, S-08.01.01, S-07.01.01. Blocking risk: repository implementation can reach IN_REVIEW, but DONE still requires executable backend/frontend/verifier evidence, PostgreSQL migration round-trip and authenticated S-10.04 WorkOS multi-user browser UAT. Size: L. Leading indicator: unread-to-source-open conversion and notification action completion. Business value: E-10. Priority: P1.  
Tasks: T-10.09.01.a reference-only notification/preference schema and migration convergence; T-10.09.01.b permission-rechecking materialisation for collaboration/agent/project/integration events; T-10.09.01.c read/unread and preference APIs with idempotency/concurrency safety; T-10.09.01.d exact deep-link contract and same-origin WorkOS BFF routes; T-10.09.01.e responsive accessible Activity dock/panel; T-10.09.01.f security/privacy/idempotency/migration/frontend tests; T-10.09.01.g docs/UAT/demo/rollback evidence.

#### F-10.10 Live workspace updates
**S-10.10.01 — Refresh active conversations and Activity without manual reload**  
As a Brain user, I want active channels, direct messages, unread badges and Activity to update automatically, so that collaboration feels live instead of requiring repeated manual refreshes.  
Acceptance: Given an authenticated visible workspace, when currently authorised channel/message/reaction/reply/DM/Activity state changes, then the browser detects the new authorised state within 5 seconds while the tab is visible and refreshes the server-rendered workspace without exposing a reusable backend token; Given the tab is hidden, offline or the live check fails, then checks back off to a bounded slower interval and recover automatically without a refresh storm; Given a restricted channel or DM is revoked, when the next live check runs, then the refreshed workspace removes the inaccessible source rather than keeping stale content; Given a selected channel reaction or reply-count changes, when the live revision changes, then the channel surface refreshes; Given a thread is open, when its permitted replies change, then the thread re-fetches through the existing same-origin conversation route without client bearer-token access; Given the live state endpoint is called, then it returns only an opaque revision and safe counters, never message bodies, DM text, credentials, agent arguments/results or private evidence excerpts; Given the same source state is polled repeatedly, then the opaque revision remains stable and no unnecessary router refresh is triggered; Given the current user loses organisation membership, then the same-origin live route fails closed and no cross-tenant or stale state is returned.  
Dependencies: S-10.06.01, S-10.06.02, S-10.09.01, S-10.04.01 server-session boundary. Blocking risk: final authenticated browser timing/security acceptance depends on official S-10.04 WorkOS activation, but repository implementation can reach IN_REVIEW without inventing a WebSocket infrastructure dependency. Size: M. Leading indicator: manual-refresh-free conversation update success and live refresh error rate. Business value: E-10. Priority: P1.  
Tasks: T-10.10.01.a stable permission-aware live revision over existing server APIs; T-10.10.01.b same-origin WorkOS live-state BFF; T-10.10.01.c adaptive visible/hidden/offline polling with bounded backoff; T-10.10.01.d channel/thread/DM/Activity refresh integration; T-10.10.01.e security/no-token/no-content-leak tests; T-10.10.01.f docs/UAT/demo and measured browser timing acceptance.

#### F-10.11 Workspace search and quick switcher
**S-10.11.01 — Find and jump to authorised work from one keyboard-first workspace search**  
As a Brain user, I want one fast search/switcher for channels, projects, people and searchable evidence, so that I can jump directly to the work I need without manually scanning the sidebar.  
Acceptance: Given a visible workspace, when the user presses Ctrl+K or Cmd+K, then an accessible search dialog opens and keyboard focus moves into the query; Given an empty query, then currently authorised channels, projects/tracks and participant-visible DM counterparts are offered from already-loaded workspace data without a network request; Given a query of at least 2 characters, then Brain performs a debounced same-origin search using the existing permission-aware Search API in keyword mode and renders only currently authorised results; Given a Brain-native message result, when opened, then navigation targets the exact authorised channel/message context; Given an external/evidence result without a dedicated exact workspace surface, then the result shows source/provenance and routes to the closest existing governed workspace surface rather than inventing access; Given a DM counterpart name matches, then the switcher may navigate to that DM conversation, but DM message bodies are never included in organisation-wide search results; Given restricted source access is revoked, then the next search returns no restricted result even if an earlier dialog state had shown it; Given an invalid/empty/oversized query, then the browser and BFF reject or suppress it without widening access; Given the browser performs search, then no reusable WorkOS/FastAPI bearer token is exposed to client code; Given loading, empty, error and no-results states, then the dialog remains keyboard-operable and screen-reader labelled.  
Dependencies: S-05.01.01 search contract, S-10.02.01 workspace navigation, S-10.06.01 native channels, S-10.06.02 participant-safe DMs, S-10.04.01 server-session boundary. Blocking risk: final authenticated browser acceptance depends on official S-10.04 WorkOS activation; existing S-05.01 executable acceptance is still outstanding, so repository implementation cannot be called DONE from source presence alone. Size: M. Leading indicator: successful search-to-open rate and median time-to-target. Business value: E-10. Priority: P1.  
Tasks: T-10.11.01.a typed existing-search client contract; T-10.11.01.b membership-validated same-origin search BFF; T-10.11.01.c keyboard-first command/search dialog; T-10.11.01.d exact Brain-message and local navigation links; T-10.11.01.e privacy/revocation/token/accessibility source contracts; T-10.11.01.f docs/UAT/demo and browser acceptance.

#### F-10.12 Message lifecycle
**S-10.12.01 — Let authors edit or retract their own Brain-channel messages without rewriting history**  
As a Brain channel participant, I want to correct or retract my own message, so that everyday collaboration is usable while Brain preserves trustworthy evidence and audit history.  
Acceptance: Given a current human-authored Brain message or thread reply, when its original author with current channel write access edits it, then the current conversation body, hash, character count, edited timestamp, mentions and searchable projection update atomically while an immutable prior revision is retained; Given two edits race, when the supplied expected revision is stale, then the later request fails with conflict instead of overwriting unseen changes; Given any non-author, owner/admin/executive, guest, revoked member or cross-tenant actor, when edit/retract is attempted, then the mutation fails closed without revealing whether hidden content exists; Given an agent-authored message, when a human attempts edit/retract, then the mutation is denied; Given the author retracts a message, then normal conversation reads return a tombstone with no body/hash/mentions/reactions, organisation-wide Search/Ask Brain no longer receives its current content, and the message no longer contributes to unread counts; Given a retracted thread root has existing replies, then the tombstone remains addressable so the existing reply history is not cascade-destroyed, but no new reply/reaction/edit may be added to the retracted message; Given an edit removes a mention, then that mention relationship no longer materialises or remains visible in Activity; Given an edit adds a valid authorised mention, then the existing mention/Activity pipeline can materialise it without duplicate rows; Given edit or retract succeeds, then a content-free security audit event records actor, message/channel IDs, revision transition and body hashes but never plaintext body; Given browser mutation, then it uses same-origin WorkOS BFF routes with bounded JSON and no reusable bearer token; Given migration rollback, then revision/lifecycle columns and tables can be removed without deleting the original raw/canonical evidence.  
Dependencies: S-10.06.01 conversation UX, S-10.09.01 Activity, S-10.10.01 live refresh, S-10.11.01 exact message navigation, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW, but DONE still requires executable backend/migration/frontend/verifier evidence plus authenticated WorkOS multi-user browser UAT. Size: L. Leading indicator: successful author correction/retraction rate with zero unauthorised mutation or stale-overwrite events. Business value: E-10. Priority: P1.  
Tasks: T-10.12.01.a lifecycle/revision schema and migration; T-10.12.01.b optimistic-concurrency edit/retract service; T-10.12.01.c Search/mention/Activity/unread consistency; T-10.12.01.d permission-aware API and same-origin BFF; T-10.12.01.e accessible edit/retract UI and live refresh; T-10.12.01.f security/concurrency/migration/frontend tests; T-10.12.01.g docs/UAT/demo/rollback evidence.

#### F-10.13 Governed channel attachments
**S-10.13.01 — Attach governed files to Brain channel messages without creating a second file store**  
As a Brain channel participant, I want to upload and attach governed documents/transcripts directly in a channel or thread, so that files shared during collaboration immediately enter Brain's permission-aware evidence, Search and Ask Brain workflow.  
Acceptance: Given a current channel writer, when a supported file <=10 MB is uploaded from the channel composer, then Brain reuses the existing evidence ingestion pipeline and creates exactly one governed EvidenceSource rather than a parallel attachment blob; Given an organisation-visible channel, when a file is uploaded, then the source is organisation-visible; Given a restricted channel, when a file is uploaded, then the source is channel-scoped and direct Evidence reads, Search and Work Graph access follow current channel membership, including later grant/revocation; Given an uploaded channel-scoped source, when a message/root/reply is sent with that source ID, then the relation is tenant/channel validated, deduplicated and returned as bounded attachment metadata; Given a user attaches an existing EvidenceSource, then only an active organisation-visible source or a source already scoped to that exact channel is accepted; Given a message has one or more attachments, then an empty text body is allowed, while a message with neither text nor attachments is rejected; Given a message is retracted, then normal conversation reads return no attachment cards, but the EvidenceSource remains governed/searchable according to its own evidence lifecycle until separately deleted; Given an EvidenceSource is deleted/revoked, then existing message attachment reads show an unavailable/deleted state without exposing removed content; Given a restricted member is added or removed after upload, then evidence metadata visibility and Work Graph/Search grants change with live channel access and no historical file content remains reachable through stale grants; Given the composer uploads files, then at most 5 supported files are accepted per message, each uses a bounded same-origin WorkOS multipart route and no reusable bearer token reaches browser code; Given a partial browser failure after evidence upload but before message send, then the uploaded source remains a valid governed channel file and the UI preserves its source ID for retry rather than silently re-uploading or losing data; Given migration rollback, then attachment relations/channel-scope metadata can be removed without deleting the underlying evidence sources.  
Dependencies: S-10.05.01 governed evidence/files, S-10.06.01 conversation UX, S-10.10.01 live refresh, S-10.12.01 message lifecycle, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW, but DONE still requires executable PostgreSQL/migration/backend/frontend/verifier evidence and authenticated WorkOS multi-user browser UAT. Size: L. Leading indicator: successful channel-file upload-to-message rate and attachment-to-search retrieval rate with zero restricted-file leakage. Business value: E-10. Priority: P1.  
Tasks: T-10.13.01.a evidence channel-scope + message-attachment schema/migration; T-10.13.01.b channel-aware evidence visibility and live grant propagation; T-10.13.01.c attachment upload/link/read services; T-10.13.01.d typed API and same-origin WorkOS BFF; T-10.13.01.e accessible composer/upload/attachment cards with retry-safe state; T-10.13.01.f tenant/revocation/deletion/partial-failure/security tests; T-10.13.01.g docs/UAT/demo/rollback evidence.

#### F-10.14 Ephemeral presence and typing
**S-10.14.01 — Show current online and typing state without creating employee activity history**  
As a Brain collaborator, I want to see when currently authorised teammates are online or actively typing in the channel/DM I am using, so that Brain conversations feel live and I can avoid talking over people or waiting blindly.  
Acceptance: Given a current active organisation member with native-chat access and a visible browser tab, when Brain sends a presence heartbeat, then a short-lived presence lease marks that user online for at most 75 seconds unless renewed; Given the tab becomes hidden/offline, then no new heartbeat is sent and the lease naturally expires without creating a durable last-seen record; Given a current channel reader, when presence is read for that channel, then only active organisation members who can currently read that exact channel are returned, and a restricted-channel revoke removes the user from the next response; Given a current participant opens a 1:1 Brain-native DM, when presence is read, then only the other currently authorised participant's online state may be returned and owner/admin role alone grants no private-DM presence visibility; Given a current channel writer or DM participant types non-empty text, then Brain creates/refreshes a typing lease that expires within 8 seconds unless renewed; Given typing stops, the input is cleared, a message is sent, the selected context changes, the tab hides or the component unmounts, then the client clears the typing lease best-effort and server expiry remains the correctness fallback; Given a typing-state read, then the current user is excluded and only users who still have current access to the exact channel/DM context are returned; Given typing requests repeat while text changes, then the browser throttles refreshes so it does not send one request per keystroke; Given any presence/typing API response or persistence row, then no message body, draft text, keystrokes, cursor position, exact last-seen history, IP address, user agent, secret, token or private evidence is stored or returned; Given expired leases exist, then reads ignore them, normal heartbeat/typing writes opportunistically purge them, and expired rows never count as online/typing; Given concurrent heartbeats/typing updates, then one unique lease per user/context is refreshed idempotently rather than duplicated; Given browser presence/typing mutation, then it uses bounded same-origin WorkOS BFF routes with current membership/context validation and no reusable bearer token in client code; Given migration rollback, then only ephemeral lease rows/tables are removed and no message, DM, evidence or audit data is changed.  
Dependencies: S-10.06.01 native channels, S-10.06.02 participant-only DMs, S-10.10.01 live collaboration baseline, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW; DONE still requires executable PostgreSQL/backend/frontend/verifier evidence plus authenticated two-user WorkOS timing/revocation UAT. Size: M. Leading indicator: authorised online/typing state appears/disappears within the lease target with zero unauthorised presence exposure and no per-keystroke request flood. Business value: E-10. Priority: P1.  
Tasks: T-10.14.01.a ephemeral presence/typing schema + migration; T-10.14.01.b permission-aware lease service for channel + DM contexts; T-10.14.01.c bounded API and same-origin WorkOS BFF; T-10.14.01.d visible-tab heartbeat + throttled typing client; T-10.14.01.e channel/DM online and typing UI; T-10.14.01.f expiry/concurrency/revocation/privacy/frontend tests; T-10.14.01.g docs/UAT/demo/rollback evidence.

#### F-10.15 Shared channel message pins
**S-10.15.01 — Pin important channel messages without duplicating message content**  
As a Brain channel participant, I want important messages and thread replies pinned at channel level, so that the team can reopen key context immediately without searching for it again.  
Acceptance: Given a current channel writer, when they pin a visible non-retracted channel message or thread reply, then Brain creates exactly one channel/message pin reference containing no copied message body, attachment bytes or evidence text; Given the same pin request repeats concurrently or is retried, then the operation is idempotent and the database still contains one pin; Given a current channel reader, when they list pins, then only pins for the exact channel they can currently read are returned and each item is materialised through the existing permission-aware message read model; Given a restricted-channel member is revoked, then the next pin-list/read request fails closed or returns no inaccessible pin content without waiting for pin cleanup; Given a non-writer, guest, revoked member, cross-tenant actor or user targeting another channel's message attempts pin/unpin, then the mutation fails closed without revealing hidden message existence; Given a message or thread reply is retracted, then any active pin to that message is removed in the same lifecycle transaction and it no longer appears in pinned results; Given an edited message remains pinned, then the pin continues to resolve to the current edited message while immutable message revision/evidence history remains unchanged; Given an agent-authored message is visible, then a current channel writer may pin/unpin it because pinning changes channel metadata rather than message authorship; Given pins are listed, then they are ordered newest-pin-first and the response includes pin metadata plus the existing safe message representation, with no second message-content store; Given a root message or reply is pinned, then the UI shows it in a channel Pins panel and can reopen the exact root/thread context using existing message/thread APIs; Given the selected channel's pin set changes, then the existing live workspace revision changes without hashing or exposing message plaintext; Given browser pin/list/unpin requests, then they use same-origin WorkOS BFF routes with bounded identifiers and no reusable backend token in client code; Given migration rollback, then only pin-reference rows/table are removed and no message, evidence, attachment, revision or audit content is deleted.  
Dependencies: S-10.06.01 native channels/threads, S-10.10.01 live refresh, S-10.12.01 message lifecycle, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW; DONE still requires executable PostgreSQL/backend/frontend/verifier evidence and authenticated WorkOS multi-user pin/revoke/retract UAT. Size: M. Leading indicator: pin-to-open success rate with zero inaccessible pin leakage and zero duplicate pin rows. Business value: E-10. Priority: P1.  
Tasks: T-10.15.01.a tenant-scoped pin schema/migration; T-10.15.01.b permission-aware pin/list/unpin service + lifecycle cleanup; T-10.15.01.c typed API and same-origin WorkOS BFF; T-10.15.01.d accessible channel Pins panel and message actions; T-10.15.01.e live invalidation; T-10.15.01.f tenant/revocation/retract/idempotency/frontend tests; T-10.15.01.g docs/UAT/demo/rollback evidence.

#### F-10.16 Personal saved messages
**S-10.16.01 — Save authorised channel messages for personal follow-up without creating a second content store**  
As a Brain user, I want to save important channel messages and thread replies for myself, so that I can return to work I personally need to follow up without changing shared channel state.  
Acceptance: Given a current channel reader, when they save a visible non-retracted root message or thread reply, then Brain creates exactly one private user/message reference containing no copied message body, attachment bytes or evidence text; Given the same save request repeats concurrently or is retried, then the operation is idempotent and the database still contains one user/message save row; Given a signed-in user, when they open Saved, then Brain returns only that user's saved references and materialises message content through the existing permission-aware message read model; Given another user, owner, admin, executive or auditor, when they request another user's saved list or save row, then Brain exposes nothing because saved state is personal metadata; Given a restricted-channel member loses access, then the next Saved read omits that message content without relying on stale client state; Given access is later restored and the message still exists, then the user's private saved reference may become visible again because the row stores only identity, not content; Given a message is retracted, then any saved reference to that message is removed in the same lifecycle transaction and the retracted message cannot remain in Saved; Given a message is edited, then the existing saved reference resolves to the current edited safe message representation without rewriting the saved row; Given an agent-authored message is visible, then the current reader may save/unsave it because saving is personal metadata rather than message authorship mutation; Given saved items are listed, then they are ordered newest-save-first and include only save metadata plus the existing safe message representation; Given a saved root or reply is opened, then Brain navigates to the existing exact channel/message or thread context; Given browser save/list/unsave requests, then they use same-origin WorkOS BFF routes with bounded identifiers and no reusable backend token in client code; Given migration rollback, then only private saved-reference rows are removed and no message, evidence, attachment, revision or audit content is deleted.  
Dependencies: S-10.06.01 native channels/threads, S-10.11.01 exact message navigation, S-10.12.01 message lifecycle, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW; DONE still requires executable PostgreSQL/backend/frontend/verifier evidence and authenticated WorkOS multi-user privacy/revoke/retract UAT. Size: M. Leading indicator: saved-to-open completion rate with zero cross-user or revoked-content leakage. Business value: E-10. Priority: P1.  
Tasks: T-10.16.01.a tenant/user/message scoped save schema/migration; T-10.16.01.b permission-aware save/list/unsave service + lifecycle cleanup; T-10.16.01.c typed API and same-origin WorkOS BFF; T-10.16.01.d accessible personal Saved panel and message actions; T-10.16.01.e privacy/revocation/idempotency/retract tests; T-10.16.01.f docs/UAT/demo/rollback evidence.

#### F-10.17 First-unread divider and jump-to-unread
**S-10.17.01 — Resume a channel at the exact first unread message**  
As a Brain collaborator, I want a clear first-unread divider and a Jump to unread action, so that I can resume a busy channel at the exact point new activity starts instead of rescanning conversation history.  
Acceptance: Given a visible channel has unread non-retracted messages from other actors after the authenticated user's monotonic read cursor, when unread summaries are loaded, then Brain returns the exact first unread message ID together with the existing unread count/latest-message cursor using bounded tenant-scoped queries; Given the first unread item is a root message already in the rendered window, when the channel opens, then exactly one accessible "New messages" divider renders immediately before that message and Jump to unread scrolls to that boundary; Given the first unread item is a thread reply or an older root outside the initial message window, when Jump to unread is used, then Brain re-fetches that exact message through the existing permission-aware same-origin message route, opens the owning thread when required, materialises the target without copying content to new storage, and scrolls to the divider; Given opening the channel advances the existing read cursor, when server refreshes occur, then the captured first-unread boundary for that open channel remains stable until the channel component is replaced, while the persisted read cursor remains monotonic; Given the first unread target is retracted after render, when current message state or a jump request observes the retraction, then the stale divider is removed and no retracted body is shown as unread; Given the current user authored a message, when unread boundaries are computed, then that message does not become their first unread item; Given restricted-channel access is revoked, when unread or exact-message reads are requested, then no unread boundary or hidden message content is returned; Given there are no unread messages, then no divider or Jump to unread action is rendered; Given browser jump/read requests execute, then they use authenticated same-origin WorkOS BFF routes and expose no reusable backend bearer token; Given the summary path is exercised across many visible channels, then the first-unread addition remains bounded and does not introduce per-channel N+1 database queries; Given this feature is rolled back, then removing the response/UI/BFF additions changes no persisted message/read/evidence state and requires no data migration.  
Dependencies: S-10.06.01 monotonic per-user unread state, S-10.10.01 live refresh, S-10.11.01 exact message navigation/read, S-10.12.01 retraction consistency, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW; DONE still requires executable backend/frontend/verifier evidence and authenticated WorkOS multi-user unread/thread/revocation UAT. Size: M. Leading indicator: jump-to-first-unread success rate with zero hidden/retracted target exposure and zero unread-summary N+1 queries. Business value: E-10. Priority: P1.  
Tasks: T-10.17.01.a bounded first-unread summary contract; T-10.17.01.b same-origin exact-message read BFF for jump recovery; T-10.17.01.c accessible channel/thread divider and Jump to unread UI; T-10.17.01.d security/revocation/retraction/query-boundary tests; T-10.17.01.e frontend contract tests; T-10.17.01.f docs/UAT/demo/rollback/traceability evidence.

#### F-10.18 Direct-message unread and resume
**S-10.18.01 — Resume participant-only DMs at the exact first unread message**  
As a Brain DM participant, I want per-conversation unread badges, a first-unread divider and Jump to unread, so that private conversations are as easy to resume as channels without exposing DM activity outside the participant pair.  
Acceptance: Given a current participant with a visible DM epoch, when the other participant sends messages after that user's monotonic DM read cursor, then the conversation list returns an exact unread count, latest visible message ID and first unread message ID while the current user's own messages do not count; Given a participant opens a DM with unread messages, when the panel renders, then exactly one accessible New messages divider appears before the first unread item and Jump to unread focuses/scrolls to it before the existing mark-read clears the persisted unread count; Given the first unread target is outside the initial message window, when Jump to unread is used, then Brain recovers the exact message through a participant-only same-origin route and never exposes it to a nonparticipant or privileged role; Given a participant marks through a message, then the cursor advances monotonically and a stale/older mark-read cannot move it backwards; Given a participant is revoked or later reactivated into a new visibility epoch, then unread state cannot resurrect messages from an earlier private epoch and the new cursor starts immediately before the new visible floor; Given the other participant is removed/downgraded, then history-only visibility for the still-authorised participant remains unchanged while the revoked participant receives no unread/list/read access; Given browser read/jump requests execute, then they use same-origin WorkOS BFF routes with bounded UUID/body validation and no reusable bearer token in client code; Given DM list unread summaries are loaded, then the additional unread calculation is bounded/set-based rather than one message query per conversation; Given rollback, then only DM read-cursor columns are removed and no private message content is deleted.  
Dependencies: S-10.06.02 participant-safe DMs, S-10.10.01 live refresh, S-10.17.01 unread UX pattern, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW; DONE still requires PostgreSQL migration round-trip, backend/frontend/verifier evidence and authenticated two-user WorkOS epoch/revocation UAT. Size: M. Leading indicator: DM unread-to-open conversion with zero cross-participant leakage and zero stale-epoch unread resurrection. Business value: E-10. Priority: P1.  
Tasks: T-10.18.01.a participant read-cursor schema/migration; T-10.18.01.b bounded DM unread summary + monotonic mark-read service; T-10.18.01.c exact participant-only message read/BFF; T-10.18.01.d accessible DM badge/divider/jump UI; T-10.18.01.e epoch/revocation/concurrency/security tests; T-10.18.01.f docs/UAT/demo/rollback/traceability evidence.

#### F-10.19 Conversation history pagination
**S-10.19.01 — Load older channel and DM history with stable sequence cursors**  
As a Brain collaborator, I want to load older messages without losing my current context, so that long-running channels and DMs remain usable beyond the initial server-rendered window.  
Acceptance: Given a visible native channel, when older root history is requested with a stable before-sequence cursor, then Brain returns the next bounded page newest-window-first without duplicates/gaps and without widening channel access; Given a visible DM, when older history is requested, then Brain returns only messages at or above the participant's current visibility floor and before the supplied sequence cursor; Given a cursor is malformed, out of range or belongs to another scope, then the request fails safely or returns an empty bounded page without exposing hidden identifiers/content; Given older pages are appended/prepended in the browser, then existing exact-message anchors, first-unread divider, open thread/DM context and composer state remain stable; Given no older history remains, then the UI removes/disables Load older and does not poll repeatedly; Given restricted-channel or DM access is revoked between pages, then the next page request fails closed and stale hidden content is removed on authoritative refresh; Given browser page requests execute, then they use same-origin authenticated routes with no reusable bearer token; Given page size is requested, then it is bounded server-side and query cost is index/sequence based without offset scans; Given rollback, then removing cursor parameters/UI changes requires no data migration.  
Dependencies: S-10.06.01 channels, S-10.06.02 DMs, S-10.11.01 exact message navigation, S-10.17.01/S-10.18.01 resume boundaries, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW; DONE requires backend/frontend/verifier evidence and authenticated long-history/revocation UAT. Size: M. Leading indicator: successful older-page load rate with zero duplicate/gap/access violations and bounded query latency. Business value: E-10. Priority: P1.  
Tasks: T-10.19.01.a sequence-cursor backend contracts for channel/DM history; T-10.19.01.b same-origin bounded BFF reads; T-10.19.01.c accessible Load older UX preserving current context; T-10.19.01.d cursor/revocation/duplicate-gap tests; T-10.19.01.e docs/UAT/demo/traceability evidence.

#### F-10.20 Direct-message lifecycle
**S-10.20.01 — Let a DM author safely edit or retract their own private message**  
As a Brain DM participant, I want to correct or retract my own direct message, so that private conversations can recover from mistakes without giving organisation roles access to private content or silently rewriting history.  
Acceptance: Given a current participant and author of a visible DM message, when they edit with the expected revision, then the current private body/hash/length/edited timestamp update atomically and an append-only private revision snapshot preserves the prior body for the same participant-only retention class; Given a stale expected revision races with another edit, then the stale mutation fails with conflict and does not overwrite the accepted version; Given a non-author, owner/admin/executive nonparticipant, revoked participant or cross-tenant actor attempts edit/retract, then the mutation fails closed without revealing hidden DM existence; Given the author retracts a visible DM, then participant reads return a body-free tombstone, the message no longer contributes to unread state, and no organisation-wide Search/Ask Brain/Work Graph/audit content is created; Given a participant is reactivated into a later visibility epoch, then old hidden messages/revisions remain hidden and cannot be edited/retracted from the new epoch; Given private-message retention runs, then current/revision plaintext follows the existing private_message_days/legal-hold policy without copying content into organisation-wide audit; Given browser mutations execute, then they use same-origin WorkOS routes with bounded JSON, expected-revision validation and no reusable bearer token; Given rollback, then lifecycle columns/private revision rows can be removed only with an explicit maintenance warning because retraction semantics would be lost, while no organisation-wide evidence is created or deleted.  
Dependencies: S-10.06.02 participant-safe DMs, S-10.18.01 DM unread state, S-10.19.01 history pagination, S-09.02.01 private-message retention, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW; DONE requires PostgreSQL migration/rollback, concurrency/privacy/retention tests, frontend/verifier evidence and authenticated WorkOS multi-user UAT. Size: L. Leading indicator: unauthorised DM lifecycle mutation = 0, stale overwrite = 0, retracted body exposure = 0. Business value: E-10. Priority: P1.  
Tasks: T-10.20.01.a DM revision/lifecycle schema + migration; T-10.20.01.b author/epoch-safe edit/retract transaction service; T-10.20.01.c unread + retention consistency; T-10.20.01.d API/BFF/UI lifecycle controls; T-10.20.01.e privacy/concurrency/retention/rollback tests; T-10.20.01.f docs/UAT/demo/traceability evidence.

#### F-10.21 Thread history pagination
**S-10.21.01 — Load older replies inside long-running threads with stable sequence cursors**  
As a Brain collaborator, I want older thread replies to load without losing my place, so that busy discussions remain usable beyond the initial reply window.  
Acceptance: Given an authorised thread root, when replies are requested with a positive before-sequence cursor, then only replies under that exact root with `message_sequence < before_sequence` are returned in chronological order with bounded page size and no OFFSET scan; Given channel/root access is hidden or revoked, then paging fails closed without leaking reply IDs/content; Given a root is retracted but existing replies remain permitted by S-10.12, then those historical replies remain pageable while new reply mutation stays disabled; Given older replies are loaded, then the thread panel merges by ID/sequence without duplicate/gap creation and keeps composer, attachments, unread boundary and focused reply state stable; Given live refresh runs after older pages were loaded, then recent reply refresh merges instead of discarding historical pages; Given history is exhausted, then Load older replies disappears; Given browser paging runs, then it uses the existing same-origin WorkOS reply route and no reusable bearer token; rollback changes no persisted state.  
Dependencies: S-10.06.01 threads, S-10.19.01 sequence pagination, S-10.10.01 live refresh, S-10.04.01 server-session boundary. Blocking risk: repository implementation can reach IN_REVIEW; DONE requires backend/frontend/verifier execution plus authenticated long-thread/revocation UAT. Size: M. Leading indicator: older-thread-page success with zero duplicate/gap/access violations. Business value: E-10. Priority: P1.  
Tasks: T-10.21.01.a before_sequence reply contract; T-10.21.01.b bounded BFF GET; T-10.21.01.c merge-safe Load older replies UX; T-10.21.01.d revocation/cursor/refresh tests; T-10.21.01.e UAT/demo/traceability.

#### F-10.22 Thread unread and resume
**S-10.22.01 — Track unread state independently for each thread and resume at its first unread reply**  
As a Brain collaborator, I want each followed/opened thread to remember what I have read, so that channel-level read state does not hide unread replies inside active threads.  
Acceptance: Given a user opens or participates in a visible thread, then Brain maintains a monotonic per-user/root read cursor without copying reply content; Given other actors add non-retracted replies after that cursor, then the root exposes an exact thread unread count and first unread reply ID while the current user's own replies do not count; Given the thread opens, then exactly one accessible New replies divider and Jump to unread target the first unread reply and marking read cannot move backwards; Given channel access is revoked or the root is retracted, then thread unread state returns no inaccessible content and no stale badge survives authoritative refresh; Given many roots render, unread summaries are set-based/bounded rather than one query per root; browser read/jump uses same-origin WorkOS routes; rollback removes only per-thread read-state rows.  
Dependencies: S-10.17.01 channel resume, S-10.21.01 thread pagination, S-10.12.01 lifecycle, S-10.04.01. Blocking risk: repository implementation can reach IN_REVIEW; DONE requires PostgreSQL migration round-trip, executable tests/verifier and authenticated multi-user thread UAT. Size: M. Leading indicator: thread unread-to-open conversion with zero stale/revoked leakage. Business value: E-10. Priority: P1.  
Tasks: T-10.22.01.a thread read-state schema/migration; T-10.22.01.b set-based unread summary + monotonic mark-read; T-10.22.01.c divider/jump UI; T-10.22.01.d revocation/retraction/concurrency tests; T-10.22.01.e UAT/demo/traceability.

#### F-10.23 Participant-private DM reactions
**S-10.23.01 — React to participant-only DMs without creating employer-visible activity**  
As a DM participant, I want lightweight reactions on private messages, so that acknowledgement does not require another message or weaken DM privacy.  
Acceptance: Given a current participant and visible non-retracted DM message in the current visibility epoch, when they add one allow-listed reaction, then exactly one participant/message/reaction row exists and aggregate counts are correct; Given the same add/remove retries concurrently, then operations are idempotent; Given a nonparticipant, revoked participant, privileged nonparticipant, cross-tenant actor or old visibility epoch targets the message, then the request fails closed without revealing existence; Given a message is retracted or private retention deletes it, then reaction rows disappear by cascade and no reaction remains in unread/latest calculations; Given responses render reactions, then only current participants receive aggregate counts plus reacted-by-me state and no participant list is exposed; Given normal DM reaction changes occur, then no RawEvent/CanonicalEvent/Search/Work Graph/organisation-wide SecurityAuditEvent record is created; browser mutation uses bounded same-origin WorkOS PUT/DELETE with no bearer token; rollback removes only private reaction rows.  
Dependencies: S-10.06.02 participant-safe DMs, S-10.20.01 DM lifecycle, OQ-008, S-10.04.01. Blocking risk: repository implementation can reach IN_REVIEW; DONE requires PostgreSQL migration, privacy/idempotency tests, frontend/verifier execution and authenticated two-user UAT. Size: M. Leading indicator: DM reaction success with zero cross-participant metadata leakage. Business value: E-10. Priority: P1.  
Tasks: T-10.23.01.a private reaction schema/migration; T-10.23.01.b participant/epoch-safe add/remove/aggregate service; T-10.23.01.c API/BFF/UI; T-10.23.01.d privacy/idempotency/retract/retention tests; T-10.23.01.e UAT/demo/traceability.

#### F-10.24 Workspace teams
**S-10.24.01 — Organise the workspace into real Teams without changing channel access**  
As a Brain user, I want shared Teams such as Sales, Frontend, Backend, AI or Full-stack, so that the workspace matches the company structure instead of showing one flat channel list.  
Acceptance: Given a current organisation member, when Teams are listed, then active team metadata is organisation-scoped, contains no message/DM/evidence content and does not imply access to any channel; Given a current role with native-chat write permission, when a valid unique team name/optional description is submitted, then exactly one active Team is created with a stable ID/slug, creator, revision and audit event; Given the team creator or Owner/Admin, when name/description is changed with the expected revision, then the update is atomic and stale revisions fail with conflict; Given an authorised manager archives or restores an eligible Team, then lifecycle state/timestamps/revision update atomically and the action never deletes channels, messages, evidence, DMs or grants; Given any non-manager, guest, cross-tenant user or removed member attempts a mutation, then it fails closed without widening access; Given team metadata is rendered, then the sidebar shows Teams as real navigation containers and keeps existing visible channels available in an explicit unassigned area until S-10.25 assigns them; Given browser mutations execute, then they use bounded same-origin WorkOS routes with no reusable backend token; Given migration rollback, then only Team metadata is removed and existing collaboration content remains untouched.  
Dependencies: S-10.02.01 workspace shell, S-10.04.01 server-session boundary, S-10.06.01 channel authority, OQ-009/OQ-010 engineering-safe boundaries. Blocking risk: repository implementation can reach IN_REVIEW; DONE requires PostgreSQL migration round-trip, backend/frontend/verifier execution and authenticated role/tenant browser UAT. Size: M. Leading indicator: successful team create/edit/archive rate with zero channel-permission changes. Business value: E-10. Priority: P1.  
Tasks: T-10.24.01.a team schema/migration; T-10.24.01.b permission-aware lifecycle service; T-10.24.01.c API/BFF/UI/sidebar; T-10.24.01.d authz/concurrency/rollback tests; T-10.24.01.e UAT/demo/traceability.

#### F-10.25 Team channel groups
**S-10.25.01 — Create channel groups inside Teams and move channels without changing ACLs**  
As a Brain collaborator, I want subfolders/channel groups inside Teams, so that large teams can organise many chats like Slack/Discord without turning navigation structure into a security boundary.  
Acceptance: Given an active Team, when an authorised team manager creates or edits a valid unique group, then exactly one organisation/team-scoped group with optimistic revision is stored; Given a visible channel manager assigns or moves a channel to an active Team/group, then only navigation references change and the channel visibility, NativeChannelMembership rows, ResourceGrants, evidence grants, unread state and Search access remain unchanged; Given a group belongs to another Team/organisation, is archived or the actor cannot manage the channel/target Team, then assignment fails closed; Given a group is archived, then its currently visible channels remain reachable under the parent Team's ungrouped section rather than disappearing or changing permissions; Given a restricted channel is hidden from the current user, then Teams/groups never reveal that channel ID/name through counts, membership or assignment reads; Given the workspace renders, then channels appear under Team → Group hierarchy while unassigned channels remain visible in a fallback section; DMs remain in the separate participant-private section under OQ-010; Given browser mutations execute, then same-origin WorkOS routes validate bounded IDs/names and expose no bearer token; Given rollback, then group and channel-navigation references can be removed without deleting channel/message/evidence content.  
Dependencies: S-10.24.01 Teams, S-10.06.01 channel ACL, OQ-009/OQ-010. Blocking risk: repository implementation can reach IN_REVIEW; DONE requires PostgreSQL migration round-trip, move/revocation/tenant tests, frontend/verifier execution and authenticated hierarchy UAT. Size: L. Leading indicator: team/group navigation completion with zero ACL/grant deltas. Business value: E-10. Priority: P1.  
Tasks: T-10.25.01.a group + channel-navigation schema/migration; T-10.25.01.b group lifecycle and safe assignment service; T-10.25.01.c typed API/BFF; T-10.25.01.d nested sidebar + management UX; T-10.25.01.e ACL-invariance/tenant/archive tests; T-10.25.01.f UAT/demo/traceability.

#### F-10.26 Channel administration
**S-10.26.01 — Manage channel identity, lifecycle and restricted member access from the workspace**  
As a channel manager, I want to maintain channel settings and member access without database/API work, so that Brain channels stay usable as the company changes.  
Acceptance: Given the channel creator or Owner/Admin, when name/description is edited with expected revision, then channel identity updates atomically, slug uniqueness is enforced, the current Work Graph track label/navigation metadata is updated, historical message/canonical evidence is not rewritten, and stale revisions fail with conflict; Given an authorised manager archives a channel, then it becomes read-only and leaves the default active sidebar while existing authorised history/evidence remains permission-filtered and recoverable; Given an authorised manager restores it, then posting follows the existing channel ACL again; Given a restricted-channel manager changes an existing member between read/write, then the membership and current ResourceGrant/evidence grant access are updated consistently without revoking the member; Given visibility is requested to change between organisation/restricted, then S-10.26 rejects it because safe visibility conversion is not part of this story; Given non-manager/revoked/cross-tenant actors attempt settings/member-access mutations, then they fail closed; Given archived channels exist, then authorised managers have an explicit Archived channels surface to restore them without making archived channels part of the normal active list; Given browser mutations execute, then bounded same-origin WorkOS routes use no browser bearer token; Given rollback, then the settings revision column can be removed without deleting channels/content and archive/name state remains representable by existing fields.  
Dependencies: S-10.25.01 hierarchy, S-10.06.01 restricted members, S-10.12.01 immutable message history, S-10.04.01. Blocking risk: repository implementation can reach IN_REVIEW; DONE requires migration/backend/frontend/verifier execution plus authenticated creator/Admin/member archive/permission UAT. Size: L. Leading indicator: channel-admin workflow success with zero stale overwrite, permission widening or content loss. Business value: E-10. Priority: P1.  
Tasks: T-10.26.01.a settings revision migration; T-10.26.01.b lifecycle/rename + Work Graph consistency; T-10.26.01.c restricted member read/write update consistency; T-10.26.01.d same-origin BFF/settings/archived UI; T-10.26.01.e concurrency/authz/grant-invariance tests; T-10.26.01.f UAT/demo/traceability.

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
| Slack/Discord-style company workspace | S-10.02.01, S-10.03.01, S-10.06.01, S-10.24.01, S-10.25.01 |
| Human communication | S-10.01.01, S-10.06.01, S-10.06.02, S-10.14.01, S-10.15.01, S-10.16.01, S-10.24.01, S-10.25.01, S-10.26.01 |
| Participant-only private collaboration | S-10.06.02, S-10.14.01, S-10.18.01, S-10.19.01, S-10.20.01, S-10.23.01 |
| Tenant/channel-scoped message threads | S-10.06.01 |
| Exact-member mentions without identity guessing | S-10.06.01 |
| Idempotent per-user message reactions | S-10.06.01 |
| Per-user monotonic unread state | S-10.06.01, S-10.17.01, S-10.18.01, S-10.22.01 |
| First-unread divider and exact jump-to-unread | S-10.17.01, S-10.18.01, S-10.22.01 |
| Stable older-message pagination for channels and DMs | S-10.19.01, S-10.21.01 |
| Independent per-thread unread/resume | S-10.22.01 |
| Participant-private DM reactions | S-10.23.01 |
| Author-owned DM edit/retract lifecycle | S-10.20.01 |
| Restricted-channel notification/content privacy | S-10.06.01 |
| Visibly attributed agent messages | S-10.01.01, S-10.06.01 |
| Focused responsive Slack/Discord-style channel surface | S-10.02.01, S-10.06.01 |
| AI tracks/agents | S-08.01.01, S-10.01.01, S-10.07.01 |
| Permission-aware company memory | S-01.03.01, S-05.01.01 |
| RAG/search | S-05.01.01, S-05.02.01, S-10.13.01 |
| Citations / no unsupported claims | S-05.02.01, S-10.03.01 |
| Data provenance | S-03.01.01, S-03.02.01, S-10.05.01, S-10.13.01 |
| Identity resolution | S-03.03.01 |
| Security/auth/authz | S-01.02.01, S-01.03.01, S-09.02.01, S-10.04.01, S-10.06.01, S-10.06.02, S-10.09.01, S-10.11.01, S-10.12.01, S-10.13.01, S-10.14.01, S-10.15.01, S-10.16.01, S-10.17.01, S-10.18.01, S-10.19.01, S-10.20.01, S-10.21.01, S-10.22.01, S-10.23.01, S-10.24.01, S-10.25.01, S-10.26.01 |
| Validation/data integrity/idempotency | S-03.01.01, S-03.02.01, S-10.06.01, S-10.06.02, S-10.09.01, S-10.12.01, S-10.13.01, S-10.14.01, S-10.15.01, S-10.16.01, S-10.17.01, S-10.18.01, S-10.19.01, S-10.20.01, S-10.21.01, S-10.22.01, S-10.23.01, S-10.24.01, S-10.25.01, S-10.26.01 |
| Observability | S-09.01.01 |
| Migrations/rollback/backup | S-09.03.01, S-10.06.01, S-10.06.02, S-10.09.01, S-10.12.01, S-10.13.01, S-10.14.01, S-10.15.01, S-10.16.01, S-10.18.01, S-10.20.01, S-10.22.01, S-10.23.01, S-10.24.01, S-10.25.01, S-10.26.01 |
| Latency/cost benchmarks | S-09.04.01 |
| Accessibility | S-07.01.01, S-07.02.01, S-10.02.01, S-10.03.01, S-10.05.01, S-10.06.01, S-10.06.02, S-10.09.01, S-10.11.01, S-10.12.01, S-10.13.01, S-10.14.01, S-10.15.01, S-10.16.01, S-10.17.01, S-10.18.01, S-10.19.01, S-10.20.01, S-10.21.01, S-10.22.01, S-10.23.01, S-10.24.01, S-10.25.01, S-10.26.01 |
| Workspace administration and governance UI | S-10.08.01 |
| Personal Activity & Notifications inbox | S-10.09.01 |
| @mentions and thread-reply notifications | S-10.06.01, S-10.09.01 |
| Unread channel activity in one attention queue | S-10.06.01, S-10.09.01 |
| Agent approval/completion/failure notifications | S-08.01.01, S-10.07.01, S-10.09.01 |
| Project and blocker update notifications | S-07.01.01, S-04.02.01, S-10.09.01 |
| Integration failure notifications | S-02.01.01, S-10.08.01, S-10.09.01 |
| Notification read/unread state and preferences | S-10.09.01 |
| Notification deep links to exact source context | S-10.09.01 |
| Automatic live workspace refresh | S-10.10.01 |
| Live channel, thread, DM and Activity updates without browser bearer tokens | S-10.06.01, S-10.06.02, S-10.09.01, S-10.10.01 |
| Keyboard-first workspace search and quick switcher | S-10.11.01 |
| Author-owned channel message edit/retract lifecycle | S-10.12.01 |
| Governed channel file attachments | S-10.05.01, S-10.13.01 |
| Ephemeral online presence and typing indicators | S-10.14.01 |
| Shared channel message pins | S-10.15.01 |
| Personal saved channel messages | S-10.16.01 |
| Restricted attachment access follows live channel membership | S-10.01.01, S-10.13.01 |
| File-only channel messages with bounded attachment count | S-10.06.01, S-10.13.01 |
| Immutable message revision history with optimistic concurrency | S-10.12.01 |
| Retracted content removed from current Search/Activity/unread surfaces | S-10.09.01, S-10.12.01 |
| Permission-aware message/evidence search from the workspace | S-05.01.01, S-10.11.01 |
| DM participant navigation without organisation-wide DM-content search | S-10.06.02, S-10.11.01 |
| CI and lie-detector verifier | S-09.03.01 |
| Agile/Scrum/Kanban artifacts | S-09.03.01 |

| Workspace → Teams → channel groups → channels hierarchy | S-10.24.01, S-10.25.01 |
| Channel settings/archive/member-access administration | S-10.26.01 |

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
- Organisation-wide Brain-native DM-content search: prohibited by the resolved participant-only DM privacy boundary; only visible counterpart metadata may be used for local navigation.
- Admin/moderator editing or hard-deleting another user's Brain-native channel message: not part of S-10.12; moderation policy requires an explicit new story and evidence-retention decision.
- Admin/moderator override, edit-time windows, hard-delete/eDiscovery for Brain-native DMs, and editing/retracting agent-authored channel messages remain outside S-10.20; each needs separate authority/retention rules.
- Arbitrary image/video/audio attachments and OCR/media previews: S-10.13 reuses the currently supported governed evidence types; unsupported binary/media ingestion needs an explicit storage/scanning/preview story.
- Brain-native DM attachments: participant-private storage/search rules differ from organisation/channel evidence and are not silently included in S-10.13.
- Unread history analytics and push notifications remain outside S-10.17/S-10.18/S-10.22; external delivery still needs a separate product/privacy contract.
- Group DMs, DM attachments, message forwarding and organisation-wide DM discovery remain outside S-10.18–S-10.23 unless separately specified; participant-only privacy remains authoritative.
