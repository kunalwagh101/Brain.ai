# WorkOS / frontend acceptance — Brain production path

Status: **IMPLEMENTATION_STAGED / PACKAGE_INSTALL_BLOCKED / UAT_PENDING**

This document defines the only accepted production authentication/frontend path for Brain. The existing `app/chatgpt-auth.ts` integration is a preview-host helper and is **not** an accepted production authentication mechanism.

## Security boundary

Production browser authentication must use the official WorkOS AuthKit Next.js SDK. Do not replace it with hand-written OAuth, custom PKCE/state handling, copied bearer tokens, localStorage access tokens or manually fabricated package-lock entries.

Accepted flow:

`browser -> WorkOS AuthKit encrypted session cookie -> Next.js server component/BFF -> server-held WorkOS access token -> FastAPI Authorization: Bearer -> Brain permission checks`

The browser must not receive the reusable Brain/WorkOS bearer token for ordinary API use.

`app/brain-api.ts` and the feature-specific server API clients are the server-side FastAPI boundary. Production clients use `cache: no-store`, require an explicit server-held bearer token, refuse non-HTTPS Brain API URLs in production and never place the token in a URL.

## Current official SDK contract

Reviewed again against the current WorkOS AuthKit Next.js documentation on 2026-09-16. Brain pins Next.js `16.2.6`, so the accepted integration is:

- reviewed `@workos-inc/authkit-nextjs` **4.x** line until a separate major-version review is approved;
- root `proxy.ts` using `authkitProxy()`;
- proxy matcher covering `/`, `/api/brain/:path*`, `/sign-in` and `/auth/callback` so every server route using `withAuth()` executes behind AuthKit;
- `app/auth/callback/route.ts` using `handleAuth()`;
- `app/sign-in/route.ts` using `getSignInUrl()`;
- `AuthKitProvider` from `@workos-inc/authkit-nextjs/components`;
- server `withAuth()` / `withAuth({ ensureSignedIn: true })`;
- server `signOut()` for logout;
- official `@workos-inc/authkit-nextjs` plus `@workos-inc/node`.

Do not use the older Next.js <=15 `middleware.ts` path for this repository.

## Official package installation

Run:

```bash
bash scripts/install-workos-authkit.sh
```

The reviewed installer asks npm for:

```bash
npm install '@workos-inc/authkit-nextjs@^4' @workos-inc/node
```

The installer refuses to consider the install complete unless `package.json` and `package-lock.json` contain genuine package entries with an exact resolved version, registry `resolved` URL and `integrity` hash. It also rejects an AuthKit result outside the reviewed 4.x line.

Do **not** hand-edit versions, tarball URLs, transitive packages or integrity hashes if the registry is unavailable. The controlled execution environment used for this implementation has not produced a genuine WorkOS package install, so the active branch intentionally contains no fabricated WorkOS dependency metadata.

## Reviewed source activation

Once the official packages are installed and environment values are supplied, run:

```bash
bash scripts/activate-workos-authkit.sh
```

The activation script fails closed before changing the live frontend unless all of the following are true:

1. both official WorkOS packages are declared and integrity-pinned;
2. AuthKit resolves to the reviewed 4.x line;
3. all required environment variables exist without printing their values;
4. `WORKOS_COOKIE_PASSWORD` is at least 32 characters;
5. `NEXT_PUBLIC_WORKOS_REDIRECT_URI` is an HTTP(S) URL pointing exactly to `/auth/callback` with no query string, embedded URL credentials or fragment;
6. production redirect and Brain API URLs use HTTPS;
7. the reviewed proxy template still covers `/`, `/api/brain/:path*`, `/sign-in` and `/auth/callback`;
8. callback/sign-in templates still use the reviewed official SDK helpers;
9. target auth/root/BFF paths contain no uncommitted changes.

Only then does activation copy the reviewed templates under `docs/workos-activation/` and run frontend lint, build and all `tests/*.test.mjs` contracts.

A successful activation build is **not** production UAT.

## WorkOS dashboard configuration

The WorkOS dashboard must match the repository contract:

- Redirect URI: exact value of `NEXT_PUBLIC_WORKOS_REDIRECT_URI` ending in `/auth/callback`;
- Initiate Login URI: Brain frontend `/sign-in` route;
- Default Logout URI: reviewed Brain signed-out destination;
- application/client ID must match the backend trusted client configuration.

Mismatched redirect/login/logout configuration is an acceptance failure; do not compensate by weakening callback or token validation.

## Frontend environment

Server/private:

```text
WORKOS_CLIENT_ID=client_...
WORKOS_API_KEY=sk_...
WORKOS_COOKIE_PASSWORD=<strong random value, at least 32 characters>
BRAIN_API_BASE_URL=https://<brain-api-staging-or-production-host>
```

Browser-safe redirect configuration:

```text
NEXT_PUBLIC_WORKOS_REDIRECT_URI=https://<frontend-host>/auth/callback
```

The backend separately requires the same trusted WorkOS application client ID:

```text
BRAIN_WORKOS_CLIENT_ID=client_...
```

For normal AuthKit session tokens, leave `BRAIN_WORKOS_AUDIENCE` unset unless a deliberate custom audience is configured. If a WorkOS custom auth domain changes the JWT issuer, set `BRAIN_WORKOS_ISSUER` to that exact trusted issuer rather than weakening issuer validation.

## Required Brain JWT Template claim

Brain links stable WorkOS subject `sub` to its internal user and requires an explicit subject-email claim. Configure the WorkOS AuthKit JWT Template with:

```json
{
  "urn:brain:user_email": {{ user.email }}
}
```

The backend rejects a token without a usable `urn:brain:user_email`. The optional WorkOS `act` impersonation/delegation context is never treated as the subject's email.

## Production root behavior

Before official package installation/activation, `app/page.tsx` remains the explicitly labelled product preview. This prevents a sample page from being misrepresented as the authenticated product.

After activation, the reviewed root template:

- uses `withAuth({ ensureSignedIn: true })`;
- obtains the access token only on the server;
- derives the signed-in display name from the WorkOS user;
- passes only the server token into `ProductionWorkspace`;
- accepts optional organisation/channel/DM selections, but `ProductionWorkspace` validates them against server-returned permission-visible data before loading protected content;
- enables same-origin Ask Brain, Evidence, native-channel, DM, Agent Workspace and Admin Center mutation routes only through server BFFs;
- injects a WorkOS `signOut()` server action into the workspace shell.

`ProductionWorkspace` is role-aware: normal Members/Managers are allowed into Brain, while Executive/Company Pulse and Admin Center data are separately permission-gated. FastAPI remains authoritative for every read/mutation regardless of frontend presentation.

## AuthKit proxy and BFF invariant

Every route under `/api/brain/...` that calls `withAuth()` must be matched by root `proxy.ts`.

The reviewed matcher is intentionally narrow:

```text
/
/api/brain/:path*
/sign-in
/auth/callback
```

Do not replace it with a broad catch-all that intercepts Next.js static/image assets. Do not remove `/api/brain/:path*`; doing so can break the trusted AuthKit session-header path used by server BFF routes.

Source contracts:

```bash
node --test tests/workos-authkit-contract.test.mjs
node --test tests/workos-installer-contract.test.mjs
```

These tests are source contracts only; they do not substitute for a real session/browser UAT.

## Same-origin BFF rules

The activated Brain BFF set includes reviewed routes for:

- Ask Brain;
- evidence upload/delete;
- native-channel create/messages/threads/reactions/read state/member management;
- Brain-native DMs;
- Agent Workspace run/start/advance/approval/cancel;
- Admin Center governance actions.

Each reviewed BFF route must:

1. execute behind the AuthKit proxy;
2. call official `withAuth()` server-side;
3. reject missing user/access-token state with a bounded response;
4. validate current Brain organisation membership before forwarding;
5. enforce its exact content-type/body-size/field/UUID/action contract before protected backend mutation/provider invocation;
6. call FastAPI only with the server-held access token;
7. use `Cache-Control: no-store` where the route returns protected data;
8. return only bounded safe status/messages rather than raw backend/provider/secret-store details;
9. never serialize the access/refresh token, internal AuthKit headers, WorkOS API key, cookie password, Brain provider secrets or secret references.

Feature-specific BFFs may add stricter rules such as same-origin/CSRF checks, multipart streaming limits, idempotency-key validation and role prechecks; those are defense in depth and never replace FastAPI authorization.

## Ask Brain BFF

Activated route:

`POST /api/brain/organizations/{organizationId}/ask-brain`

The reviewed route/helper validates the exact Ask Brain input, current Brain membership and server-held token before forwarding. `app/ask-brain-panel.tsx` calls only the same-origin endpoint with `credentials: "same-origin"`; it has no access-token prop and creates no Authorization header.

## Governed evidence BFF

Activated routes:

- `POST /api/brain/organizations/{organizationId}/evidence/uploads`
- `DELETE /api/brain/organizations/{organizationId}/evidence/{sourceId}`

The evidence upload route preserves the backend 10 MB file contract, uses a bounded multipart stream read, validates an idempotency key and must not trust Content-Length as its only size boundary. Delete validates the source ID and current membership before forwarding. The browser never receives the backend bearer token.

## Native collaboration / DM BFF

Native-channel mutations, thread/reaction/read-state/member changes and Brain-native DM create/send requests are all same-origin BFF operations.

DM privacy is separate from company-wide evidence: WorkOS authentication establishes the user; the Brain backend still enforces explicit participant-only DM authorization, including lifecycle revocation after membership/role changes. AuthKit role or Owner/Admin status must never be treated as a DM-content override.

## Agent Workspace BFF

Agent mutations use the server-held authenticated identity and Brain organisation membership. The browser cannot supply arbitrary provider/model/tool authority. High-risk approvals and workspace context are revalidated by the backend at action time.

## Admin Center BFF

Admin mutations use one reviewed same-origin route:

`POST /api/brain/organizations/{organizationId}/admin-center/actions`

It requires WorkOS server auth, same-origin/CSRF checks, bounded JSON, exact discriminated actions and current Brain Owner/Admin membership. Secret-bearing actions allow only transient bounded credential input; stored values are never returned by Admin Center and must not be persisted to browser storage.

## Current live frontend implementation

Repo-side implementation now includes:

- permission-aware workspace navigation and Slack/Discord-style workspace shell;
- server-composed projects, decisions/blockers, Company Pulse and Ask Brain;
- governed Files & Evidence workspace;
- Brain-native channels/messages plus thread/reaction/mention/unread UX;
- participant-safe Brain-native DMs;
- governed Developer & Agent Workspace;
- Owner/Admin Admin Center with member/integration/AI/API governance;
- reviewed same-origin BFF templates for all mutation surfaces above;
- `tests/workspace-contract.test.mjs`, `tests/workos-authkit-contract.test.mjs`, `tests/workos-installer-contract.test.mjs` plus feature-specific source contracts;
- `scripts/install-workos-authkit.sh` and `scripts/activate-workos-authkit.sh` package/activation gates;
- feature-specific UAT contracts under `UAT/`.

No source-presence statement above is a PASS claim.

## Authentication UAT

Exercise at least:

1. unauthenticated browser;
2. Owner/Admin/Executive in Org A;
3. Member/Manager in Org A without `audit.read`;
4. user in Org B only;
5. user who can access Org A but not one restricted Work Graph project/evidence/channel;
6. user belonging to two Brain organisations;
7. two valid DM participants plus a nonparticipant privileged role;
8. sign-out and expired/revoked-session case where practical.

Pass only if:

- unauthenticated protected root requires AuthKit instead of loading company data;
- callback establishes a valid encrypted session and leaves no token in the URL;
- FastAPI accepts the real AuthKit token with matching trusted client/issuer/expiry/signature and `urn:brain:user_email`;
- wrong-client, wrong-issuer, expired, malformed and missing-email-claim tokens fail closed;
- Org B cannot select/query Org A;
- manipulated organisation/resource/channel/DM IDs disclose no unavailable target fields/content;
- restricted projects/evidence/channels remain absent from unauthorised navigation, counts, intelligence and citations;
- normal Member/Manager can use the workspace even when Executive Overview is unavailable;
- nonparticipant Owner/Admin/Executive cannot read a DM merely because of role;
- logout/session expiry removes access and requires authentication again;
- no WorkOS access/refresh token, API key, cookie password, internal session header, AWS/OpenAI/API credential or secret reference appears in HTML, client JS configuration, browser storage, URLs or user-visible errors.

## Product UAT after authentication

Once authentication passes, exercise:

1. S-10.02 workspace organisation/project/track navigation and responsive/accessibility behavior;
2. S-05.01 permission-aware retrieval/revocation;
3. S-02.04 meeting/document upload, retrieval and delete/revoke behavior;
4. S-10.05 governed Files & Evidence workspace;
5. S-10.03 Ask Brain answer + insufficient-evidence + citations + bounded provider-error states;
6. S-10.06.01 native channels, threads, mentions, reactions, unread/read state and revocation behavior;
7. S-10.06.02 participant-only DMs, role/membership revocation, visibility epochs and Search/Ask Brain negative sentinel;
8. S-10.07 governed agent runs, context revocation, high-risk approval, tool policy and structured artifacts;
9. S-10.08 Owner/Admin governance, transient credential entry/rotation and browser-network secret inspection;
10. Decision/Blocker human-review behavior;
11. Project Command Centre deterministic progress/evidence drill-down;
12. Executive Overview deterministic metrics/cost/budget/API state;
13. keyboard navigation, visible focus, screen-reader labels, loading/empty/error states and responsive layout.

The frontend must not show an employee productivity/worth/performance score or turn message/commit/token/API activity into an employee ranking.

## Acceptance record

Record without secrets:

- frontend commit SHA:
- backend commit SHA:
- `package-lock.json` SHA:
- `@workos-inc/authkit-nextjs` exact version:
- `@workos-inc/node` exact version:
- source-contract tests: PENDING
- frontend lint/build/tests result: PENDING
- WorkOS application/client ID suffix only:
- dashboard Redirect URI exact-match reviewed: PENDING
- Initiate Login URI reviewed: PENDING
- default Logout URI reviewed: PENDING
- JWT Template reviewed: PENDING
- callback/sign-in/session UAT: PENDING
- real access-token -> FastAPI UAT: PENDING
- organisation/resource permission negative UAT: PENDING
- BFF proxy/`withAuth()` coverage UAT: PENDING
- Ask Brain BFF/browser UAT: PENDING
- governed evidence UAT: PENDING
- native channel/conversation UAT: PENDING
- DM multi-user privacy UAT: PENDING
- Agent Workspace UAT: PENDING
- Admin Center/credential-network inspection UAT: PENDING
- Project Command Centre browser UAT: PENDING
- Executive Overview browser UAT: PENDING
- sign-out/session-expiry UAT: PENDING
- browser-secret inspection: PENDING
- accessibility/responsive UAT: PENDING
- final frontend acceptance: **PENDING**

No frontend story or dependent feature may be marked production PASSED solely because these files exist.
