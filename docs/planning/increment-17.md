# Increment 17 — Governed agent runtime

Story: `S-08.01.01` / feature `F-08.01`.

Branch rule: continue on `increment-10-ai-provider-gateway`; no new branch is created.

## Goal

Allow Brain to move from AI reasoning to carefully constrained action without allowing model output to become an authority boundary.

## Dependency state

The implementation is buildable on the staged F-06.01 AI gateway and F-09.02 audit/governance contracts, but both dependencies still lack executable passing verification because GitHub Actions cannot provision a runner. S-08.01.01 therefore remains `BLOCKED` from engineering-DONE even while its implementation is staged.

## Acceptance refinement

### AC1 — default deny

Given an agent definition with no policy for a tool, when the planner proposes that tool, then the runtime denies the proposal before tool execution and writes durable denial evidence.

### AC2 — policy/risk compatibility

Given a code-controlled tool risk class, when an administrator configures policy, then incompatible modes are rejected. A high-risk action cannot be configured as direct `act`.

### AC3 — current human permissions remain authoritative

Given a configured tool, when it executes, then the requesting user's current Brain permission/ACL is evaluated. Agent configuration cannot grant access the human does not have.

### AC4 — high-risk mutation requires durable approval

Given a high-risk action proposal, when planning reaches that proposal, then no mutation occurs and the run enters `waiting_approval`. Only an explicit requester approval may move the step to `approved`.

### AC5 — approval is separate from execution

Given an approved step, when the approval endpoint returns, then the mutation still has not executed. The next serialized runtime advance executes the already-approved bounded arguments.

### AC6 — approval/retry cannot duplicate a mutation

Given retry/double-click/concurrent requests, when the same approved replay-safe mutation is processed, then the resulting domain effect is idempotent and the run cannot progress concurrently across API replicas.

### AC7 — rejection/cancel/expiry remove pending action payload

Given a pending action, when it is rejected, cancelled or expires, then the action cannot execute and temporary arguments/proposal text are cleared.

### AC8 — model output is untrusted input

Given invalid JSON, an unknown tool, invented arguments or a denied tool, when planner output is parsed, then Brain fails closed and does not execute arbitrary code/HTTP/tool access.

### AC9 — existing AI governance still applies

Given an agent planner call, when it invokes the model, then it uses the F-06.01 governed provider/model contract and F-06.02 hard-budget path. Provider revocation, disabled models, missing credentials and exhausted hard budgets prevent planning.

### AC10 — durable evidence without unnecessary content copying

Given an agent run, when steps occur, then durable records/audit include identities, states, tool/policy, timestamps and digests while the run objective, search result content and final response are not persisted in the agent ledger.

### AC11 — admin disable is a kill switch

Given an agent definition is disabled after a proposal or approval, when the run attempts further progression, then no additional planner call or tool mutation executes.

### AC12 — maintenance recovers abandoned state safely

Given expired approval/stale planning/stale execution, when the bounded maintenance worker runs, then expired arguments are cleared, stale planning is recoverable, replay-safe execution may be retried, and non-replay-safe execution fails closed.

## Initial production tool catalog

- `search.query` — read-only, permission-aware search, policy `read`/`deny`.
- `work_graph.create_work_item` — high-risk action, policy `act_with_approval`/`deny`.

No arbitrary shell, code executor, generic HTTP caller, Slack-send, GitHub-write or credential tool is introduced in this increment.

## Tasks

- `T-08.01.01.a` Add agent definitions/tool policies/run/step schema and migration.
- `T-08.01.01.b` Add code-controlled tool catalog and policy/risk validation.
- `T-08.01.01.c` Add governed planner loop through F-06.01.
- `T-08.01.01.d` Add approval/reject/cancel/expiry lifecycle.
- `T-08.01.01.e` Add requester/current-permission enforcement and durable audit evidence.
- `T-08.01.01.f` Add cross-replica run serialization and bounded recovery worker.
- `T-08.01.01.g` Add adversarial service/route/policy/maintenance tests.
- `T-08.01.01.h` Add operator docs and realistic backend/frontend UAT.
- `T-08.01.01.i` Obtain executable Ruff/Pytest/migration/Delivery Verifier evidence after the Actions runner issue is resolved.

## Current status

Implementation is staged, but `BLOCKED` from DONE while S-06.01.01 and S-09.02.01 remain unverified and this increment has no executable test/migration evidence. Real provider, PostgreSQL concurrency, permissions/budget changes during a run and frontend approval UX remain `UAT_PENDING`.
