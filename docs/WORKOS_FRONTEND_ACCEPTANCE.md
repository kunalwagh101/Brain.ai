# WorkOS / frontend acceptance — Brain production path

Status: **IMPLEMENTATION_STAGED / PACKAGE_INSTALL_BLOCKED / UAT_PENDING**

This document defines the only accepted production authentication/frontend path for Brain. The existing `app/chatgpt-auth.ts` integration is a preview-host helper and is **not** an accepted production authentication mechanism.

## Security boundary

Production browser authentication must use the official WorkOS AuthKit Next.js SDK. Do not replace it with hand-written OAuth, custom PKCE/state handling, copied bearer tokens, localStorage access tokens or manually fabricated package-lock entries.

Accepted flow:

`browser -> WorkOS AuthKit encrypted session cookie -> Next.js server component/BFF -> server-held WorkOS access token -> FastAPI Authorization: Bearer -> Brain permission checks`

The browser must not receive the reusable Brain/WorkOS bearer token for ordinary API use.

`app/brain-api.ts` is the server-side FastAPI client boundary. It uses `cache: no-store`, requires an explicit bearer token, refuses non-HTTPS Brain API URLs in production and never places the token in a URL.

## Current official SDK contract

Reviewed against the current WorkOS AuthKit Next.js documentation on 2026-09-11. Brain pins Next.js `16.2.6`, so the accepted integration is:

- root `proxy.ts` using `authkitProxy()`;
- `app/auth/callback/route.ts` using `handleAuth()`;
- `app/sign-in/route.ts` using `getSignInUrl()`;
- `AuthKitProvider` from `@workos-inc/authkit-nextjs/components`;
- server `withAuth()` / `withAuth({ ensureSignedIn: true })`;
- server `signOut()` for logout;
- official `@workos-inc/authkit-nextjs` plus its `@workos-inc/node` peer dependency.

Do not use the older Next.js <=15 `middleware.ts` path for this repository.

## Official package installation

Run:

```bash
bash scripts/install-workos-authkit.sh
```

The script performs the normal npm installation:

```bash
npm install @workos-inc/authkit-nextjs @workos-inc/node
```

and refuses to consider the install complete unless `package.json` and `package-lock.json` contain real package entries with `version`, registry `resolved` URL and `integrity` hash.

Do **not** hand-edit versions, tarball URLs, transitive packages or integrity hashes if the registry is unavailable. The current controlled execution environment cannot resolve the npm registry, so the active branch intentionally does not contain fabricated WorkOS dependencies.

## Reviewed source activation

Once the official packages are installed and environment values are supplied, run:

```bash
bash scripts/activate-workos-authkit.sh
```

The activation script:

1. verifies both official WorkOS packages are declared and integrity-pinned;
2. validates required environment variables without printing their values;
3. refuses uncommitted changes in the target auth/root/BFF paths;
4. copies only the reviewed templates under `docs/workos-activation/`;
5. activates root `proxy.ts`, callback, sign-in, AuthKit provider layout, protected root workspace and Ask Brain BFF;
6. runs frontend lint, build and all `tests/*.test.mjs` contracts.

A successful activation build is **not** production UAT.

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
- accepts an optional `organizationId` query selection, but `ProductionWorkspace` validates it against the server-returned Brain membership list before loading data;
- enables the Ask Brain BFF only after that membership resolution;
- injects a WorkOS `signOut()` server action into the workspace shell.

`ProductionWorkspace` is role-aware: normal Members/Managers are allowed into Brain, while Executive/Company Pulse data is loaded only for Owner/Admin/Executive roles. Frontend role presentation never overrides FastAPI authorization.

## Same-origin Ask Brain BFF

Activated route:

`POST /api/brain/organizations/{organizationId}/ask-brain`

The reviewed route/template must:

1. call official `withAuth()` server-side;
2. return a bounded `401` if no user/access token exists;
3. require JSON and enforce a bounded body size before parsing;
4. pass the organisation ID through `handleAskBrainBff()`;
5. have `handleAskBrainBff()` verify the ID exists in the current server-returned Brain membership list;
6. enforce the exact Ask Brain request-field allowlist and UUID/range bounds;
7. call FastAPI only with the server-held access token;
8. return only the Ask Brain response or bounded status/message;
9. never serialize the access/refresh token, encrypted session headers, WorkOS API key, Brain provider secrets or raw upstream error detail.

`app/ask-brain-panel.tsx` calls only this same-origin endpoint with `credentials: "same-origin"`; it has no access-token prop and creates no Authorization header.

## Current live frontend implementation

Repo-side implementation now includes:

- `backend/app/routes/workspace_navigation.py` — permission-filtered project/track navigation;
- `app/brain-api.ts` — typed server-side Brain API boundary;
- `app/brain-bff.ts` — exact Ask Brain validation + membership check;
- `app/production-workspace.tsx` — authenticated organisation/role composition;
- `app/workspace-shell.tsx` — Slack/Discord-style workspace rail/sidebar/main/context layout with real organisation switching;
- `app/workspace-shell.module.css` — desktop/tablet/mobile workspace behavior;
- `app/ask-brain-panel.tsx` — same-origin citation/provenance Ask Brain surface;
- `tests/workspace-contract.test.mjs` — browser-boundary/source contracts;
- `docs/workos-activation/*` — reviewed production activation templates;
- `scripts/install-workos-authkit.sh` and `scripts/activate-workos-authkit.sh` — package/activation gates;
- `UAT/F-10.02.md`, `UAT/F-10.03.md`, `UAT/F-10.04.md` — feature acceptance contracts.

No source-presence statement above is a PASS claim.

## Authentication UAT

Exercise at least:

1. unauthenticated browser;
2. Owner/Admin/Executive in Org A;
3. Member/Manager in Org A without `audit.read`;
4. user in Org B only;
5. user who can access Org A but not one restricted Work Graph project/evidence source;
6. user belonging to two Brain organisations;
7. sign-out and expired/revoked-session case where practical.

Pass only if:

- unauthenticated protected root requires AuthKit instead of loading company data;
- callback establishes a valid encrypted session and leaves no token in the URL;
- FastAPI accepts the real AuthKit token with matching trusted client/issuer/expiry/signature and `urn:brain:user_email`;
- wrong-client, wrong-issuer, expired, malformed and missing-email-claim tokens fail closed;
- Org B cannot select/query Org A;
- a manipulated `organizationId` outside current memberships returns the unavailable boundary without target fields;
- restricted projects/evidence remain absent from navigation, counts, intelligence and citations;
- normal Member/Manager can use the workspace even when Executive Overview is unavailable;
- logout/session expiry removes access and requires authentication again;
- no WorkOS access/refresh token, API key, cookie password, internal session header, AWS/OpenAI key or secret reference appears in HTML, client JS configuration, browser storage, URLs or user-visible errors.

## Product UAT after authentication

Once authentication passes, exercise:

1. S-10.02 workspace organisation/project/track navigation and responsive/accessibility behavior;
2. S-05.01 permission-aware retrieval/revocation;
3. S-02.04 meeting/document upload, retrieval and delete/revoke behavior;
4. S-10.03 Ask Brain answer + insufficient-evidence + citation + bounded provider-error states;
5. Decision/Blocker candidate -> human confirm/edit/reject/resolve/reopen behavior;
6. Project Command Centre deterministic progress and evidence drill-down;
7. Executive Overview project counts, confirmed blockers/decisions, exact/incomplete AI cost, budget warnings and API `not_modeled` monetary-cost state;
8. keyboard navigation, visible focus, screen-reader labels, loading/empty/error states and responsive layout.

The frontend must not show an employee productivity/worth/performance score or turn message/commit/token/API activity into an employee ranking.

## Acceptance record

Record without secrets:

- frontend commit SHA:
- backend commit SHA:
- `package-lock.json` SHA:
- `@workos-inc/authkit-nextjs` version:
- `@workos-inc/node` version:
- frontend lint/build/tests result: PENDING
- WorkOS application/client ID suffix only:
- JWT Template reviewed: PENDING
- callback/sign-in/session UAT: PENDING
- real access-token -> FastAPI UAT: PENDING
- organisation switch/cross-tenant/resource-permission UAT: PENDING
- Ask Brain BFF/browser UAT: PENDING
- Project Command Centre browser UAT: PENDING
- Executive Overview browser UAT: PENDING
- sign-out/session-expiry UAT: PENDING
- browser-secret inspection: PENDING
- accessibility/responsive UAT: PENDING
- final frontend acceptance: **PENDING**

No frontend story or dependent feature may be marked production PASSED solely because these files exist.
