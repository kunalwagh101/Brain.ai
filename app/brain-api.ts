export type OrganizationRole = "owner" | "admin" | "executive" | "manager" | "member" | "guest";

export type BrainOrganization = {
  id: string;
  slug: string;
  name: string;
  role: OrganizationRole;
};

export type WorkspaceNavigationNode = {
  node_id: string;
  kind: "project" | "track";
  display_name: string | null;
  source_visibility: string;
  provider: string | null;
};

export type WorkspaceNavigation = {
  projects: WorkspaceNavigationNode[];
  tracks: WorkspaceNavigationNode[];
};

export type AIRuntimeOption = {
  provider_configuration_id: string;
  provider_key: string;
  provider_display_name: string;
  model_configuration_id: string;
  model_key: string;
  model_display_name: string;
  max_output_tokens: number | null;
};

export type AskBrainClaim = {
  text: string;
  citation_ids: string[];
};

export type AskBrainCitation = {
  evidence_id: string;
  document_id: string;
  canonical_event_id: string;
  source_provider: string;
  source_event_id: string | null;
  object_type: string;
  object_external_id: string;
  title: string;
  excerpt: string;
  occurred_at: string | null;
  provenance: Record<string, unknown>;
};

export type AskBrainResponse = {
  status: string;
  answer: string | null;
  claims: AskBrainClaim[];
  citations: AskBrainCitation[];
  uncertainty: string | null;
  ai_request_id: string | null;
  semantic_status: string;
};

export type ProjectProgressItem = {
  id: string;
  work_item_node_id: string;
  work_item_name: string;
  state: "not_started" | "in_progress" | "blocked" | "done";
  weight: number;
  note: string | null;
  updated_at: string;
};

export type ProjectMemory = {
  id: string;
  kind: "decision" | "blocker";
  state: string;
  summary: string;
  confidence: number;
  work_graph_node_id: string | null;
  canonical_event_id: string;
  search_document_id: string | null;
};

export type ProjectEvidence = {
  document_id: string;
  canonical_event_id: string;
  work_graph_node_id: string | null;
  source_provider: string;
  object_type: string;
  object_external_id: string;
  title: string;
  occurred_at: string | null;
  provenance: Record<string, unknown>;
};

export type ProjectStatus = {
  project_node_id: string;
  project_name: string;
  progress_percent: number | null;
  progress_basis: string;
  status: string;
  progress_items: ProjectProgressItem[];
  active_blockers: ProjectMemory[];
  confirmed_decisions: ProjectMemory[];
  candidate_memories: ProjectMemory[];
  evidence: ProjectEvidence[];
};

export type MetricProvenance = {
  metric_key: string;
  source_records: string;
  calculation: string;
  source_count: number;
  period_start: string | null;
  period_end: string | null;
  drilldown_path: string | null;
  complete: boolean;
};

export type ExecutiveOverview = {
  generated_at: string;
  period_start: string;
  period_end: string;
  visible_project_count: number;
  blocked_project_count: number;
  in_progress_project_count: number;
  done_project_count: number;
  not_started_project_count: number;
  unconfigured_project_count: number;
  active_blocker_count: number;
  confirmed_decision_count: number;
  portfolio: Array<{
    project_node_id: string;
    project_name: string;
    status: string;
    progress_percent: number | null;
    progress_basis: string;
    active_blocker_count: number;
    confirmed_decision_count: number;
    candidate_memory_count: number;
    evidence_count: number;
    provenance: MetricProvenance;
  }>;
  active_blockers: Array<{
    id: string;
    kind: "decision" | "blocker";
    state: string;
    summary: string;
    confidence: number;
    canonical_event_id: string;
    search_document_id: string | null;
    work_graph_node_id: string | null;
    project_node_ids: string[];
    project_names: string[];
    provenance: MetricProvenance;
  }>;
  confirmed_decisions: Array<{
    id: string;
    kind: "decision" | "blocker";
    state: string;
    summary: string;
    confidence: number;
    canonical_event_id: string;
    search_document_id: string | null;
    work_graph_node_id: string | null;
    project_node_ids: string[];
    project_names: string[];
    provenance: MetricProvenance;
  }>;
  ai_spend: {
    period_start: string;
    period_end: string;
    request_count: number;
    succeeded_count: number;
    failed_count: number;
    known_cost_requests: number;
    unknown_cost_requests: number;
    input_tokens: number;
    cached_input_tokens: number;
    output_tokens: number;
    known_spend_nano_usd: number;
    cost_complete: boolean;
    by_provider: Array<{
      provider_configuration_id: string | null;
      provider_key: string | null;
      request_count: number;
      succeeded_count: number;
      failed_count: number;
      known_cost_requests: number;
      unknown_cost_requests: number;
      input_tokens: number;
      cached_input_tokens: number;
      output_tokens: number;
      known_spend_nano_usd: number;
    }>;
    provenance: MetricProvenance;
  };
  api_usage: {
    period_start: string;
    period_end: string;
    observation_count: number;
    succeeded_count: number;
    failed_count: number;
    active_grant_count: number;
    known_spend_nano_usd: null;
    cost_status: string;
    by_service: Array<{
      service_id: string;
      service_key: string;
      display_name: string;
      provider_name: string;
      observation_count: number;
      succeeded_count: number;
      failed_count: number;
    }>;
    provenance: MetricProvenance;
    cost_provenance: MetricProvenance;
  };
  budget_warnings: Array<{
    budget_policy_id: string;
    scope_type: string;
    scope_target_id: string | null;
    known_spend_nano_usd: number;
    unknown_cost_requests: number;
    limit_nano_usd: number;
    warning_threshold_percent: number;
    percent_used: number;
    hard_limit: boolean;
    exhausted: boolean;
    enforcement_complete: boolean;
    warning_active: boolean;
    provenance: MetricProvenance;
  }>;
  risks: Array<{
    key: string;
    severity: string;
    message: string;
    project_node_id: string | null;
    budget_policy_id: string | null;
    provenance: MetricProvenance;
  }>;
  metric_provenance: MetricProvenance[];
};

export type AskBrainInput = {
  question: string;
  provider_configuration_id: string;
  model_configuration_id: string;
  search_mode?: "keyword" | "hybrid";
  search_limit?: number;
  max_output_tokens?: number;
  attribution_node_id?: string | null;
};

class BrainApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`Brain API request failed with HTTP ${status}`);
    this.name = "BrainApiError";
    this.status = status;
    this.detail = detail;
  }
}

function apiBaseUrl(): string {
  const configured = process.env.BRAIN_API_BASE_URL?.trim();
  if (!configured) throw new Error("BRAIN_API_BASE_URL is required for the production frontend");

  const parsed = new URL(configured);
  if (process.env.NODE_ENV === "production" && parsed.protocol !== "https:") {
    throw new Error("BRAIN_API_BASE_URL must use HTTPS in production");
  }
  return configured.replace(/\/$/, "");
}

async function brainApiFetch<T>(
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

export function listOrganizations(accessToken: string): Promise<BrainOrganization[]> {
  return brainApiFetch(accessToken, "/api/v1/organizations");
}

export function listWorkspaceNavigation(
  accessToken: string,
  organizationId: string,
): Promise<WorkspaceNavigation> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/workspace-navigation`,
  );
}

export function listRuntimeOptions(
  accessToken: string,
  organizationId: string,
): Promise<AIRuntimeOption[]> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/ai/runtime-options`,
  );
}

export function askBrain(
  accessToken: string,
  organizationId: string,
  input: AskBrainInput,
): Promise<AskBrainResponse> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/ask-brain`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listProjectStatuses(
  accessToken: string,
  organizationId: string,
): Promise<ProjectStatus[]> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/project-status?limit=100`,
  );
}

export function getExecutiveOverview(
  accessToken: string,
  organizationId: string,
): Promise<ExecutiveOverview> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/executive-overview`,
  );
}

export { BrainApiError };
