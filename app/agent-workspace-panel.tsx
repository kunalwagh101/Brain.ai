"use client";

import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { NativeChannel, ProjectStatus } from "./brain-api";
import type {
  AgentWorkspace,
  AgentWorkspaceRun,
  AgentWorkspaceStep,
} from "./agent-workspace-api";
import styles from "./agent-workspace-panel.module.css";

function statusLabel(value: string): string {
  return value.replaceAll("_", " ");
}

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function safeError(status: number): string {
  if (status === 400 || status === 422) return "The agent request was not accepted. Check the selected context and objective.";
  if (status === 401) return "Your authenticated session has expired.";
  if (status === 403) return "Your current role cannot use this agent action.";
  if (status === 404) return "The agent run or workspace context is no longer available to your account.";
  if (status === 409) return "The run changed before this action could be applied. Refresh and try again.";
  if (status === 429) return "Agent actions are temporarily rate limited.";
  if (status === 503) return "The governed agent runtime is temporarily unavailable.";
  return "The agent action failed safely.";
}

function activeRun(run: AgentWorkspaceRun): boolean {
  return !["completed", "failed", "cancelled", "step_limit"].includes(run.status);
}

function StepCard({
  run,
  step,
  mutationBase,
  onWorking,
  onError,
}: {
  run: AgentWorkspaceRun;
  step: AgentWorkspaceStep;
  mutationBase: string | null;
  onWorking: (value: boolean) => void;
  onError: (value: string | null) => void;
}) {
  const router = useRouter();

  async function decide(approve: boolean) {
    if (!mutationBase) return;
    onWorking(true);
    onError(null);
    try {
      const response = await fetch(
        `${mutationBase}/runs/${encodeURIComponent(run.id)}/steps/${encodeURIComponent(step.id)}/approval`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approve,
            reason: approve ? "Approved from Brain agent workspace" : "Rejected from Brain agent workspace",
          }),
        },
      );
      if (!response.ok) {
        onError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      onError("The approval action could not reach the secure Brain route.");
    } finally {
      onWorking(false);
    }
  }

  return (
    <article className={styles.step} data-status={step.status}>
      <header>
        <div>
          <span className={styles.sequence}>Step {step.sequence}</span>
          <strong>{step.tool_name}</strong>
        </div>
        <div className={styles.stepBadges}>
          <span>{statusLabel(step.policy)}</span>
          <span data-status={step.status}>{statusLabel(step.status)}</span>
        </div>
      </header>
      {step.proposal_reason ? <p>{step.proposal_reason}</p> : null}
      <details>
        <summary>Proposed arguments</summary>
        <pre>{JSON.stringify(step.arguments, null, 2)}</pre>
        <small>Arguments SHA-256: {step.arguments_sha256}</small>
      </details>
      {step.status === "waiting_approval" ? (
        <div className={styles.approvalActions}>
          <strong>Human approval required before this tool can execute.</strong>
          <div>
            <button disabled={!mutationBase} onClick={() => void decide(false)} type="button">Reject</button>
            <button className={styles.primaryButton} disabled={!mutationBase} onClick={() => void decide(true)} type="button">Approve</button>
          </div>
        </div>
      ) : null}
      {step.result_sha256 ? <small>Result SHA-256: {step.result_sha256}</small> : null}
      {step.error_code ? <small className={styles.errorText}>Error: {step.error_code}</small> : null}
    </article>
  );
}

export function AgentWorkspacePanel({
  workspace,
  projects,
  channels,
  mutationBase,
}: {
  workspace: AgentWorkspace;
  projects: ProjectStatus[];
  channels: NativeChannel[];
  mutationBase: string | null;
}) {
  const router = useRouter();
  const [agentId, setAgentId] = useState(workspace.agents[0]?.id ?? "");
  const [projectId, setProjectId] = useState(projects[0]?.project_node_id ?? "");
  const [channelId, setChannelId] = useState("");
  const [objective, setObjective] = useState("");
  const [resumeObjectives, setResumeObjectives] = useState<Record<string, string>>({});
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedAgent = useMemo(
    () => workspace.agents.find((item) => item.id === agentId) ?? null,
    [workspace.agents, agentId],
  );

  async function startRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!mutationBase || !agentId || (!projectId && !channelId) || !objective.trim()) return;
    setWorking(true);
    setError(null);
    setNotice(null);
    const normalizedObjective = objective.trim();
    try {
      const createdResponse = await fetch(`${mutationBase}/runs`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_definition_id: agentId,
          objective: normalizedObjective,
          project_node_id: projectId || null,
          native_channel_id: channelId || null,
        }),
      });
      if (!createdResponse.ok) {
        setError(safeError(createdResponse.status));
        return;
      }
      const created = (await createdResponse.json()) as AgentWorkspaceRun;
      const advanceResponse = await fetch(
        `${mutationBase}/runs/${encodeURIComponent(created.id)}/advance`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ objective: normalizedObjective }),
        },
      );
      if (!advanceResponse.ok) {
        setNotice("The governed run was created, but its first planning step did not advance. Open the run and retry with the same objective.");
      } else {
        setObjective("");
        setNotice("Agent run started. Review any proposed high-risk action before approving it.");
      }
      router.refresh();
    } catch {
      setError("The agent workspace could not reach the secure Brain route.");
    } finally {
      setWorking(false);
    }
  }

  async function advance(run: AgentWorkspaceRun) {
    if (!mutationBase) return;
    const value = (resumeObjectives[run.id] ?? "").trim();
    if (!value) {
      setError("Re-enter the original objective before continuing. Brain intentionally does not store objective plaintext.");
      return;
    }
    setWorking(true);
    setError(null);
    try {
      const response = await fetch(`${mutationBase}/runs/${encodeURIComponent(run.id)}/advance`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective: value }),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setError("The run could not reach the secure Brain route.");
    } finally {
      setWorking(false);
    }
  }

  async function cancel(run: AgentWorkspaceRun) {
    if (!mutationBase) return;
    setWorking(true);
    setError(null);
    try {
      const response = await fetch(`${mutationBase}/runs/${encodeURIComponent(run.id)}/cancel`, {
        method: "POST",
        credentials: "same-origin",
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setError("The cancellation could not reach the secure Brain route.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className={styles.workspace} aria-labelledby="agent-workspace-heading">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Developer & agent workspace</p>
          <h2 id="agent-workspace-heading">Governed engineering work</h2>
          <p>Agents work only through approved Brain tools. This surface does not expose a generic terminal, repository credential, or browser-side shell.</p>
        </div>
        <div className={styles.summary}>
          <span><b>{workspace.agents.length}</b> approved agents</span>
          <span><b>{workspace.runs.length}</b> your recent runs</span>
        </div>
      </header>

      {mutationBase ? (
        <form className={styles.launcher} onSubmit={startRun}>
          <div className={styles.formGrid}>
            <label>
              Agent
              <select value={agentId} onChange={(event) => setAgentId(event.target.value)} required>
                {workspace.agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>{agent.name} · {agent.model_display_name}</option>
                ))}
              </select>
            </label>
            <label>
              Project context
              <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
                <option value="">No project</option>
                {projects.map((project) => (
                  <option key={project.project_node_id} value={project.project_node_id}>{project.project_name}</option>
                ))}
              </select>
            </label>
            <label>
              Channel context
              <select value={channelId} onChange={(event) => setChannelId(event.target.value)}>
                <option value="">No channel</option>
                {channels.map((channel) => (
                  <option key={channel.id} value={channel.id}># {channel.name}</option>
                ))}
              </select>
            </label>
          </div>
          {selectedAgent ? (
            <div className={styles.agentContract}>
              <div>
                <strong>{selectedAgent.provider_display_name} · {selectedAgent.model_display_name}</strong>
                <small>Maximum {selectedAgent.max_steps} governed step(s)</small>
              </div>
              <div className={styles.policyList}>
                {selectedAgent.tool_policies.map((policy) => (
                  <span key={policy.tool_name} data-approval={policy.approval_required || undefined}>
                    {policy.tool_name} · {statusLabel(policy.policy)}{policy.approval_required ? " · approval" : ""}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          <label className={styles.objectiveLabel}>
            Objective
            <textarea
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              maxLength={20_000}
              rows={4}
              placeholder="Describe the engineering task or investigation. This is not a shell command."
              required
            />
          </label>
          <div className={styles.launchActions}>
            <small>Objective plaintext is used for the live run but is not stored by the core agent runtime.</small>
            <button
              className={styles.primaryButton}
              disabled={working || !agentId || (!projectId && !channelId) || !objective.trim()}
              type="submit"
            >
              {working ? "Starting…" : "Start governed run"}
            </button>
          </div>
        </form>
      ) : (
        <div className={styles.notice} role="status">
          The agent workspace read model is available, but mutations remain disabled until the authenticated WorkOS same-origin BFF is active.
        </div>
      )}

      {notice ? <div className={styles.notice} role="status">{notice}</div> : null}
      {error ? <div className={styles.error} role="alert">{error}</div> : null}

      <div className={styles.runList}>
        {workspace.runs.length ? workspace.runs.map((run) => (
          <article className={styles.runCard} key={run.id}>
            <header className={styles.runHeader}>
              <div>
                <p className={styles.eyebrow}>{run.agent_name}</p>
                <h3>{run.context.project?.name ?? (run.context.channel ? `# ${run.context.channel.name}` : "Context no longer available")}</h3>
                <small>{run.provider_display_name} · {run.model_display_name} · {formatTime(run.created_at)}</small>
              </div>
              <span className={styles.runStatus} data-status={run.status}>{statusLabel(run.status)}</span>
            </header>

            <div className={styles.contextGrid}>
              <div><span>Project</span><strong>{run.context.project?.name ?? "—"}</strong><small>{run.context.project?.provider ?? "No visible project context"}</small></div>
              <div><span>Channel</span><strong>{run.context.channel ? `# ${run.context.channel.name}` : "—"}</strong><small>{run.context.channel?.visibility ?? "No visible channel context"}</small></div>
              <div><span>Objective</span><strong>{run.objective_char_count.toLocaleString()} chars</strong><small>SHA-256 {run.objective_sha256.slice(0, 12)}…</small></div>
            </div>

            {run.artifacts.length ? (
              <section className={styles.artifacts}>
                <h4>Produced artifacts</h4>
                {run.artifacts.map((artifact) => (
                  <div key={`${artifact.kind}:${artifact.reference_id}`}>
                    <span>{artifact.kind}</span><strong>{artifact.label}</strong><code>{artifact.reference_id}</code>
                  </div>
                ))}
              </section>
            ) : null}

            <section className={styles.timeline}>
              <h4>Run timeline</h4>
              {run.steps.length ? run.steps.map((step) => (
                <StepCard
                  key={step.id}
                  run={run}
                  step={step}
                  mutationBase={mutationBase}
                  onWorking={setWorking}
                  onError={setError}
                />
              )) : <p>No agent step has been planned yet.</p>}
            </section>

            {run.status === "ready" && mutationBase ? (
              <div className={styles.resumeBox}>
                <label>
                  Re-enter objective to continue
                  <textarea
                    rows={2}
                    value={resumeObjectives[run.id] ?? ""}
                    onChange={(event) => setResumeObjectives((current) => ({ ...current, [run.id]: event.target.value }))}
                    placeholder="Brain does not persist the objective plaintext; paste it again to continue this run."
                  />
                </label>
                <button disabled={working} onClick={() => void advance(run)} type="button">Run next governed step</button>
              </div>
            ) : null}

            {activeRun(run) && mutationBase ? (
              <footer className={styles.runFooter}>
                <button disabled={working} onClick={() => void cancel(run)} type="button">Cancel run</button>
                <code>{run.id}</code>
              </footer>
            ) : (
              <footer className={styles.runFooter}><code>{run.id}</code></footer>
            )}
          </article>
        )) : (
          <div className={styles.empty}>
            <strong>No governed agent runs yet.</strong>
            <span>Choose an approved agent and bind it to a visible project or Brain channel.</span>
          </div>
        )}
      </div>
    </section>
  );
}
