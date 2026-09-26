# Increment 43 — Integrated workspace experience

Mode: **TASK**. Role: senior frontend engineer. Branch: `increment-10-ai-provider-gateway`. The product owner reviewed the stories and directed implementation on 2026-09-26. Board WIP cap: 2; currently 0 in progress because the implemented slices are in review.

## Product goal and scope truth

A member lands in a focused, conversation-first Brain workspace, can move from attention to the exact authorised work, and understands why an intelligence result is trustworthy. Operators can act without guessing the scope or consequence of an agent/admin change. This increment integrates existing capabilities; it neither rebuilds the collaboration backend nor invents sample production data.

The branch contains the prior redesign commits `b3e3ce2` and `f72248c` plus this integration pass. The existing read-only demo at `/demo` is evidence of composition and visual direction, not authenticated UAT. The root remains sample mode until official WorkOS activation under S-10.04.01. The already-built `ProductionWorkspace` composes the same `WorkspaceShell` with live server data when activated.

## Screen map and feature ownership

| Destination | First thing a user sees / next action | Existing feature authority | Redesign story |
| --- | --- | --- | --- |
| Home / workspace browser | Organisation, role, focused entry points, visible Teams/channels/projects | F-10.02, F-10.24–.26 | S-10.27.01 |
| Channels / threads / DMs | Conversation identity, unread anchor, message list, composer and contextual thread | F-10.06, F-10.12–.23 | S-10.27.02 |
| Activity / Saved / Search | Actionable event or result → exact authorised source | F-10.09, F-10.11, F-10.15–.18 | S-10.27.03 |
| Projects / Tracks / decisions | Structured progress, confirmed state, source and drill-down | F-10.03, E-04, E-07 | S-10.27.04 |
| Files / Ask Brain | Evidence provenance; answer with citations or explicit no-answer | F-10.03, F-10.05, E-05 | S-10.27.04 |
| Agents / Admin | Run/approval status and management actions by current role | F-10.07, F-10.08 | S-10.27.05 |
| Real authenticated product | Multi-role, responsive, keyboard, permission and revocation acceptance | F-10.04 and all above | S-10.27.06 |

## Layout decision and design system

Direction chosen from earlier visual explorations: a quiet working canvas with a fixed identity rail, one contextual workspace browser and one active work surface. The optional thread appears adjacent to its parent conversation. At narrow widths the browser opens with **Browse workspace** and closes after selecting a destination. Activity and Saved are destinations, not endless overlays. Admin is visible only when the server supplies its permitted read model.

The implementation uses the existing tokens in `docs/workspace-redesign.md`: navy `#222d40` for stable location, off-white `#f8f9f6` for long reading, teal `#236a69` for action, warm `#e1b890` sparingly for identity. Current CSS uses Inter with native sans-serif fallbacks, 14 px body copy with 1.5 line-height, 11–12 px utility labels, and a responsive 21–29 px view title. In S-10.27.01 review, audit the older duplicate CSS rules and check contrast/readability at actual viewport widths before freezing those values. Shared typography, hierarchy, spacing, border, focus, loading/empty/error states and reduced motion should read as one system. Desktop shell: 62 px identity rail + 256 px contextual sidebar + flexible content, with thread only when relevant. No new colour treatment should outrank unread position, action state or source evidence.

## Sequence, handoffs and status

| Pull order | Story | State now | Pull when | Handoff / evidence |
| --- | --- | --- | --- | --- |
| 1 | S-10.27.01 | IN_REVIEW | Existing local work; verify instead of reimplementing | Actual route/source map, responsive and keyboard screenshots, relevant tests |
| 2 | S-10.27.02 | IN_REVIEW | Local thread/DM UX integrated | Channel/DM/thread state matrix, two-user acceptance |
| 3 | S-10.27.03 | IN_REVIEW | Local Search/Activity/Saved flows integrated | Exact-link, revoked-result, keyboard and DM privacy checks |
| 4 | S-10.27.04 | IN_REVIEW | Project/memory/evidence/Ask Brain screens integrated | Real provenance/unknown-cost/no-answer reconciliation |
| 5 | S-10.27.05 | IN_REVIEW | Agent/Admin screens integrated | Approval, error, secret-safe Admin and Member checks |
| 6 | S-10.27.06 | BLOCKED | Slices reviewed + external WorkOS activation | UAT/F-10.27.md, exact tested SHA, release/rollback note |

The earlier S-10.27.01 prototype was committed before this formal readiness record; this is recorded process drift, not retroactive Ready compliance. S-10.27.02–.05 are in review because the existing feature components are integrated and local checks run, while real user journeys, permission revocation and external services still need UAT. The external browser gate remains distinct.

## Implementation checkpoint — 2026-09-26

The branch now uses the chosen shell for both sample and `ProductionWorkspace`. This pass fixed sample/live identity wording; native mobile disclosure close and focus return; denied Admin recovery; clear project work/status with sample progress and blocker counts reconciled; channel thread focus return; safe Search result lifetime bound to query and organisation endpoint; legible agent form, approval and DM unread states; and unavailable-action copy that tells users what they can do. The core BFF and backend ACL contracts were not changed.

Local `npm run build` and `node --test tests/*.test.mjs` passed on the implementation working tree (142 tests, 141 passed, 1 intentional unauthenticated skip). Focused lint on newly changed shell/search/demo/agent files passed. Repository-wide lint still reports 10 React effect errors and 2 warnings in existing collaboration/presence components; `npx tsc --noEmit` still lacks Cloudflare Worker ambient types (`Fetcher`, `D1Database`, `cloudflare:workers`). `python scripts/verify_board.py` finds the mappings but cannot execute historical DONE evidence because `pytest` is not installed in this workspace. No authenticated WorkOS/browser test, independent code review or release gate was run at this checkpoint. These are explicit outstanding checks, not accepted exceptions.

## Work orders

### S-10.27.01 — shell and design foundation (verify existing implementation)

**Goal:** one active destination, retained hash links, clear permission-aware navigation, responsive/keyboard usage and a visibly read-only sample.

**Files under review:** `app/workspace-shell.tsx`, `app/workspace-shell.module.css`, `app/workspace-view.tsx`, `app/workspace-view-routes.ts`, `app/production-workspace.tsx`, `app/demo/page.tsx`, `app/globals.css`, `tests/workspace-view-routes.test.mjs`, `tests/rendered-html.test.mjs`, `tests/workspace-contract.test.mjs`.

**Check:** `npm run build && node --test tests/workspace-view-routes.test.mjs tests/rendered-html.test.mjs tests/workspace-contract.test.mjs`. Browser: keyboard focus, compact browser, deep-link refresh, normal/executive role, restricted-resource absence. Fix concrete defects; keep S-10.02.01 and S-10.04.01 gates visible.

### S-10.27.02 — conversation and DM quality

**Goal:** turn the existing backend-complete messaging functions into a predictable daily workflow, including unread, thread, archived, restricted and failed actions.

**Files under review:** `app/native-chat-panel.tsx`, `app/native-chat-panel.module.css`, `app/direct-message-panel.tsx`, `app/direct-message-panel.module.css`, `app/workspace-shell.tsx`, `tests/direct-message-contract.test.mjs`, `tests/first-unread-contract.test.mjs`, `tests/thread-unread-contract.test.mjs`.

**Check:** relevant `node --test` files, existing backend restricted-channel/DM permission tests, two-user keyboard/mobile browser scenarios. Do not modify ACL, message retention, read-cursor semantics or evidence projection for decoration.

### S-10.27.03 — attention to exact context

**Goal:** make an Activity, Saved or Search click land at the right authorised object with a safe recovery path for unavailable results.

**Files under review:** `app/activity-panel.tsx`, `app/saved-messages-panel.tsx`, `app/workspace-search.tsx`, `app/workspace-view-routes.ts`, `tests/activity-contract.test.mjs`, `tests/saved-messages-contract.test.mjs`, `tests/workspace-search-contract.test.mjs`.

**Check:** exact-result and revocation regressions, keyboard open/close/focus, no DM-text search leak. Search authorization and indexing remain server-owned.

### S-10.27.04 — intelligence and provenance

**Goal:** make project status, confirmed memory, evidence and Ask Brain clear, source-linked and honest about uncertainty.

**Files under review:** `app/workspace-shell.tsx`, `app/evidence-workspace.tsx`, `app/ask-brain-panel.tsx`, `app/production-workspace.tsx`, `tests/workspace-contract.test.mjs`, `UAT/F-10.03.md`.

**Check:** introduce focused evidence/unknown-state tests where missing; reconcile live project/evidence/memory/AI cost and citations against permitted records; test normal versus executive and revoked access. Do not infer progress, cost, employee productivity or unsupported claims.

### S-10.27.05 — governed operator work

**Goal:** show agent scope, approval and outcome and make Admin workflows legible without weakening role or secret controls.

**Files under review:** `app/agent-workspace-panel.tsx`, `app/agent-workspace-panel.module.css`, `app/admin-center-panel.tsx`, `app/production-workspace.tsx`, `tests/agent-workspace-contract.test.mjs`, `tests/admin-center-contract.test.mjs`.

**Check:** existing frontend contracts plus owner/admin/member browser paths; real provider and secret-store checks remain under F-10.08. No browser bearer or reusable secret.

### S-10.27.06 — integrated acceptance

**Goal:** finish a reproducible release record for the selected branch.

**Checks:** `npm run build`, `node --test tests/*.test.mjs`, `python scripts/verify_board.py`, targeted backend auth/permissions tests when backend changes or their gates are in scope, and all scenarios in `UAT/F-10.27.md`. Capture tester/date, exact SHA and desktop/tablet/mobile screenshots. Fix and rerun affected checks. If official WorkOS cannot run, remain BLOCKED and record why; do not present sample mode as a production pass.

## Boundaries, failure and rollback

- Production data, roles, current organisation membership, ACL and mutations remain owned by backend and same-origin BFF. The browser must never use a reusable backend bearer token.
- This UI increment requires no schema change, migration or data backfill. Rollback can revert frontend commits while keeping existing backend collaboration/evidence data. Review hash compatibility and WorkOS activation separately before reverting a published branch.
- Explicit failure states: loading; empty but permitted; inaccessible or revoked; stale/deleted deep link; expired session; provider failure; mutation conflict; unknown cost; no cited answer. Each has a safe next step. Never fabricate a success or expose raw upstream error detail.
- Success signals: first destination and result-to-source completion, unread-to-reply completion, citation inspection, accessible keyboard journey and zero restricted-content leaks. Measure against real sessions only; no benchmark is claimed from sample data.

## Completion boundary

`IN_REVIEW` requires changed code plus relevant automated checks, build, updated board/traceability and review of role/failure states. `DONE` requires the repository's Definition of Done, CI and resolvable evidence block. Feature acceptance requires real-data and authenticated manual UAT in `UAT/F-10.27.md`; engineering Done and feature acceptance remain separate. This file is a work order for review, not a release claim.
