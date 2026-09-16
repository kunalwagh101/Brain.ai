import { BrainApiError } from "./brain-api";

export type AgentWorkspaceToolPolicy = {
  tool_name: string;
  policy: "read" | "act" | "act_with_approval" | "deny";
  risk: string;
  replay_safe: boolean;
  approval_required: boolean;
};

export type AgentWorkspaceAgent = {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  max_steps: number;
  provider_key: string;
  provider_display_name: string;
  model_key: string;
  model_display_name: string;
  tool_policies: AgentWorkspaceToolPolicy[];
};

export type AgentWorkspaceStep = {
  id: string;
  sequence: number;
  tool_name: string;
  policy: "read" | "act" | "act_with_approval" | "deny";
  status: string;
  arguments: Record<string, unknown>;
  arguments_sha256: string;
  proposal_reason: string | null;
  result_sha256: string | null;
  approval_expires_at: string | null;
  approved_at: string | null;
  completed_at: string | null;
  error_code: string | null;
};

export type AgentWorkspaceRun = {
  id: string;
  agent_definition_id: string;
  agent_name: string;
  provider_key: string;
  provider_display_name: string;
  model_key: string;
  model_display_name: string;
  status: string;
  objective_sha256: string;
  objective_char_count: number;
  step_count: number;
  final_output_sha256: string | null;
  last_error_code: string | null;
  context: {
    available: boolean;
    project: {
      node_id: string;
      name: string;
      provider: string | null;
      repository_id: string | null;
    } | null;
    channel: {
      channel_id: string;
      name: string;
      visibility: string;
    } | null;
  };
  artifacts: Array<{
    kind: string;
    label: string;
    reference_id: string;
    metadata: Record<string, unknown>;
  }>;
  steps: AgentWorkspaceStep[];
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  cancelled_at: string | null;
};

export type AgentWorkspace = {
  agents: AgentWorkspaceAgent[];
  runs: AgentWorkspaceRun[];
};

export type AgentWorkspaceRunInput = {
  agent_definition_id: string;
  objective: string;
  project_node_id?: string | null;
  native_channel_id?: string | null;
};

function apiBaseUrl(): string {
  const configured = process.env.BRAIN_API_BASE_URL?.trim();
  if (!configured) throw new Error("BRAIN_API_BASE_URL is required for the production frontend");
  const parsed = new URL(configured);
  if (process.env.NODE_ENV === "production" && parsed.protocol !== "https:") {
    throw new Error("BRAIN_API_BASE_URL must use HTTPS in production");
  }
  return configured.replace(/\/$/, "");
}

async function agentApiFetch<T>(
  accessToken: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  if (!accessToken.trim()) throw new Error("A server-side WorkOS access token is required");
  if (!path.startsWith("/api/v1/")) throw new Error("Brain API path must be under /api/v1/");
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
      Authorization: `Bearer ${accessToken}`,
    },
  });
  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = { error: "non_json_error_response" };
    }
    throw new BrainApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getAgentWorkspace(
  accessToken: string,
  organizationId: string,
  limit = 30,
): Promise<AgentWorkspace> {
  const bounded = Math.min(Math.max(Math.trunc(limit), 1), 100);
  return agentApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/agent-workspace?limit=${bounded}`,
  );
}

export function getAgentWorkspaceRun(
  accessToken: string,
  organizationId: string,
  runId: string,
): Promise<AgentWorkspaceRun> {
  return agentApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/agent-workspace/runs/${encodeURIComponent(runId)}`,
  );
}

export function createAgentWorkspaceRun(
  accessToken: string,
  organizationId: string,
  input: AgentWorkspaceRunInput,
): Promise<AgentWorkspaceRun> {
  return agentApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/agent-workspace/runs`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function advanceAgentWorkspaceRun(
  accessToken: string,
  organizationId: string,
  runId: string,
  objective: string,
): Promise<unknown> {
  return agentApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/agents/runs/${encodeURIComponent(runId)}/advance`,
    { method: "POST", body: JSON.stringify({ objective }) },
  );
}

export function decideAgentWorkspaceStep(
  accessToken: string,
  organizationId: string,
  runId: string,
  stepId: string,
  approve: boolean,
  reason: string | null,
): Promise<unknown> {
  return agentApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/agents/runs/${encodeURIComponent(runId)}/steps/${encodeURIComponent(stepId)}/approval`,
    { method: "POST", body: JSON.stringify({ approve, reason }) },
  );
}

export function cancelAgentWorkspaceRun(
  accessToken: string,
  organizationId: string,
  runId: string,
): Promise<unknown> {
  return agentApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/agents/runs/${encodeURIComponent(runId)}/cancel`,
    { method: "POST" },
  );
}
