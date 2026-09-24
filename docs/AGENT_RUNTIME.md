# Governed Agent Runtime

Story: `S-08.01.01` / feature `F-08.01`.

## Purpose

Brain agents may reason with approved AI models and tools, but the model is never the authority boundary. Every tool is code-controlled, every missing policy defaults to deny, high-risk actions require a durable human approval, and execution continues under the requesting user's current Brain permissions.

## Security model

The runtime separates four concerns:

1. **Planner** — an approved provider/model proposes either one tool call or a final response.
2. **Tool catalog** — Brain code defines every callable tool, its risk class, required permission and replay-safety property.
3. **Agent policy** — an administrator chooses a policy per tool for one agent definition.
4. **Human/current authorization** — the requesting user still needs the underlying Brain permission when a tool actually executes.

A prompt or model response cannot create a new tool, elevate a tool policy, bypass an ACL, bypass an AI budget, read a credential, or convert a high-risk action into a direct action.

## Policy modes

| Mode | Meaning |
|---|---|
| `read` | The agent may execute an approved read-only tool without a separate action approval. |
| `act` | The agent may execute a code-classified normal action directly. No built-in production tool currently uses this class. |
| `act_with_approval` | The agent may propose the action but execution pauses until the requester explicitly approves it. |
| `deny` | The tool cannot execute. Missing policy is also `deny`. |

Risk rules are enforced in code:

- read-only tools accept `read` or `deny`;
- ordinary action tools may accept `act`, `act_with_approval` or `deny`;
- high-risk action tools accept only `act_with_approval` or `deny`.

An administrator therefore cannot configure a high-risk action as direct `act`.

## Initial tool catalog

### `search.query`

Risk: `read`.

- Requires the requester's current `resource.read` permission.
- Calls the existing F-05.01 permission-aware search path.
- Uses keyword retrieval in the first runtime slice so the agent does not add another embedding-provider dependency.
- The planner receives at most five results with bounded excerpts.
- Search result content is ephemeral; the agent-run database records only result count and a result digest, not the retrieved customer content.

### `work_graph.create_work_item`

Risk: `high_risk_action`.

- Requires current `resource.write` permission.
- Policy must be `act_with_approval` or `deny`.
- The model can only propose a bounded `key` and `display_name`.
- No Work Graph mutation happens before approval.
- Execution uses the Work Graph's stable manual key, making retries idempotent/replay-safe.
- The mutation and its durable audit event commit together.

No generic shell, code execution, arbitrary HTTP, Slack-send, GitHub-write, secret-read or credential tool is exposed by this story.

## Agent definitions

Owner/Admin can create an agent definition that pins:

- one tenant-owned enabled AI provider configuration;
- one enabled model belonging to that provider;
- a maximum step count (`1..20`);
- explicit tool policies.

`agent.manage` is Owner/Admin-only. `agent.use` is available to Executive, Manager and Member; Guest does not receive agent access.

Disabling an agent prevents new runs. Progression must also treat the disabled definition as a kill switch before further model/tool execution; this is part of the runtime verification/UAT contract.

## Run privacy

The durable run does **not** store the objective text. It stores:

- SHA-256 of the normalized objective;
- objective character count;
- requester, organisation and definition IDs;
- state/timestamps;
- step count and bounded error code;
- SHA-256 of the final output, when completed.

The caller resubmits the same objective when advancing the run. Brain verifies its digest before any continuation. A different objective cannot hijack an existing run.

Final answer text is returned to the caller but is not persisted in the run ledger.

## Planning contract

The planner is invoked through F-06.01 `invoke_ai`, so existing provider lifecycle, credential isolation, AI usage records and F-06.02 hard-budget checks still apply.

The system prompt requires exactly one JSON object:

```json
{"action":"tool","tool":"search.query","arguments":{"query":"launch","limit":5},"reason":"Need current evidence"}
```

or:

```json
{"action":"final","answer":"..."}
```

The runtime parses the JSON and independently validates the tool, policy and arguments. Invalid JSON, an unknown tool, missing policy, invalid arguments or a denied policy fails closed.

## Approval lifecycle

For `act_with_approval`:

1. planner proposes a bounded tool call;
2. Brain stores the proposal arguments temporarily plus an arguments SHA-256;
3. run enters `waiting_approval`;
4. requester reviews the proposed action;
5. requester approves or rejects;
6. approval itself does **not** execute the mutation;
7. the next controlled `advance` executes the already-approved step once;
8. arguments/proposal text are cleared after success/failure/rejection/cancellation/expiry.

Approval expires after 24 hours. The maintenance worker actively clears expired approval arguments even when nobody returns to the UI.

Command:

```bash
cd backend
python -m app.agent_worker --once --batch-size 100
```

The worker is deliberately bounded. It also recovers stale planner state and only requeues stale action execution when the code-controlled tool is explicitly replay-safe; otherwise it fails closed.

## Concurrency

Public run mutation routes (`advance`, approval/rejection and cancel) use a PostgreSQL advisory lock derived from the run ID. A dedicated database connection holds the lock across planner/provider calls even when the normal request session commits.

This prevents two API replicas or a double-click from progressing the same run concurrently. SQLite unit tests bypass the PostgreSQL lock; real PostgreSQL concurrency remains UAT evidence.

## Audit

The existing append-only F-09.02 ledger records bounded events including:

- agent definition creation/status changes;
- run creation/completion/failure/cancellation;
- denied tool proposals;
- approval requested/approved/rejected/expired;
- tool success/failure;
- stale-state recovery.

Audit metadata contains IDs, tool name, policy, result/argument digests and bounded error codes. It does not contain the run objective, search results, final answer, provider credential or raw customer document/message content.

## API surface

Under `/api/v1/organizations/{organization_id}/agents`:

- `POST /definitions`
- `GET /definitions`
- `POST /definitions/{agent_id}/status`
- `POST /definitions/{agent_id}/runs`
- `GET /runs/{run_id}`
- `POST /runs/{run_id}/advance`
- `POST /runs/{run_id}/steps/{step_id}/approval`
- `POST /runs/{run_id}/cancel`

Run reads and mutations are requester-scoped. Another member in the same organisation cannot take over somebody else's run.

## Migration

Alembic revision `20260909_0015` creates:

- `agent_definitions`
- `agent_tool_policies`
- `agent_runs`
- `agent_steps`

`agent_models` is explicitly registered in `migrations/env.py` so schema drift checks include these tables.

## Current limitations

- The current production catalog intentionally contains only one read tool and one approval-required mutation.
- There is no generic browser/shell/code/tool-plugin executor.
- Planner output is not yet an Ask-Brain citation contract; F-05.02 remains responsible for evidence-backed RAG answer-quality acceptance.
- Agent-level cost roll-up is not a separate ledger dimension yet. Planner calls are still fully attributed through the underlying AI request records.
- Real PostgreSQL advisory-lock behavior, real provider behavior, budget exhaustion, permission changes during a run and frontend approval UX require deployed UAT.
- S-06.01.01 and S-09.02.01 are engineering-DONE. S-08.01.01 is also engineering-DONE under the repository DoD; real PostgreSQL concurrency, provider/budget/permission-loss and frontend approval checks remain `UAT_PENDING` before any PASSED/production-accepted claim.
