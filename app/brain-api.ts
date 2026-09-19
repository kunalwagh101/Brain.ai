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

export type EvidenceSource = {
  id: string;
  organization_id: string;
  integration_connection_id: string;
  native_channel_id: string | null;
  kind: "document" | "transcript";
  title: string;
  filename: string;
  media_type: string;
  content_sha256: string;
  byte_size: number;
  source_visibility: "organization" | "restricted";
  chunk_count: number;
  extracted_char_count: number;
  created_by_user_id: string;
  occurred_at: string | null;
  status: "processing" | "active" | "failed" | "deleted";
  integration_status: "active" | "revoking" | "revoke_failed" | "revoked";
  retrieval_available: boolean;
  last_error_code: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  can_delete: boolean;
};

export type NativeChannel = {
  id: string;
  organization_id: string;
  work_graph_node_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  visibility: "organization" | "restricted";
  status: "active" | "archived";
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  member_count: number;
  can_post: boolean;
  can_manage_members: boolean;
  unread_count?: number;
  latest_message_id?: string | null;
  first_unread_message_id?: string | null;
};

export type NativeChannelMember = {
  user_id: string;
  email: string;
  display_name: string | null;
  role: OrganizationRole;
  access: "read" | "write";
  revoked_at: string | null;
};

export type NativeMention = {
  user_id: string;
  email: string;
  display_name: string | null;
};

export type NativeReaction = {
  reaction: string;
  count: number;
  reacted_by_me: boolean;
};

export type NativeAttachment = {
  source_id: string;
  title: string;
  filename: string;
  kind: "document" | "transcript";
  media_type: string;
  byte_size: number;
  status: "processing" | "active" | "failed" | "deleted";
  retrieval_available: boolean;
  source_visibility: "organization" | "restricted";
  native_channel_id: string | null;
};

export type NativeChannelUnread = {
  channel_id: string;
  unread_count: number;
  last_read_at: string | null;
  latest_message_id: string | null;
  first_unread_message_id: string | null;
};

export type NativeMessage = {
  id: string;
  organization_id: string;
  channel_id: string;
  thread_root_id: string | null;
  actor_kind: "user" | "agent";
  author_user_id: string | null;
  agent_run_id: string | null;
  actor_display_name: string;
  body: string;
  body_sha256: string;
  projection_status: "pending" | "ready" | "failed";
  canonical_event_id: string | null;
  message_sequence: number;
  created_at: string;
  reply_count: number;
  mentions: NativeMention[];
  reactions: NativeReaction[];
  attachments: NativeAttachment[];
  revision: number;
  edited_at: string | null;
  deleted_at: string | null;
  can_edit: boolean;
  can_delete: boolean;
};

export type NativeChannelCreateInput = {
  name: string;
  description?: string | null;
  visibility: "organization" | "restricted";
};

export type NativeMessagePin = {
  pin_id: string;
  pinned_at: string;
  pinned_by_user_id: string;
  pinned_by_display_name: string;
  message: NativeMessage;
};

export type NativeMessageSave = {
  save_id: string;
  saved_at: string;
  message: NativeMessage;
};

export type NativeMessageCreateInput = {
  body: string;
  attachment_source_ids: string[];
};

export type WorkspaceSearchResult = {
  document_id: string;
  canonical_event_id: string;
  source_provider: string;
  source_event_id: string | null;
  object_type: string;
  object_external_id: string;
  title: string;
  content: string;
  occurred_at: string | null;
  score: number;
  provenance: Record<string, unknown>;
};

export type WorkspaceSearchResponse = {
  query: string;
  mode: "keyword" | "hybrid";
  semantic_status: string;
  results: WorkspaceSearchResult[];
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

export function listEvidenceSources(
  accessToken: string,
  organizationId: string,
  limit = 200,
): Promise<EvidenceSource[]> {
  const boundedLimit = Math.min(Math.max(Math.trunc(limit), 1), 500);
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/evidence?limit=${boundedLimit}`,
  );
}

export function uploadEvidenceSource(
  accessToken: string,
  organizationId: string,
  body: Uint8Array,
  contentType: string,
  idempotencyKey: string,
): Promise<EvidenceSource> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/evidence/uploads`,
    {
      method: "POST",
      body,
      headers: {
        "Content-Type": contentType,
        "Idempotency-Key": idempotencyKey,
      },
    },
  );
}

export function deleteEvidenceSource(
  accessToken: string,
  organizationId: string,
  sourceId: string,
): Promise<EvidenceSource> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/evidence/${encodeURIComponent(sourceId)}`,
    { method: "DELETE" },
  );
}

export function listNativeChannels(
  accessToken: string,
  organizationId: string,
): Promise<NativeChannel[]> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-channels`,
  );
}

export function listNativeSavedMessages(
  accessToken: string,
  organizationId: string,
  limit = 100,
): Promise<NativeMessageSave[]> {
  const boundedLimit = Math.min(Math.max(Math.trunc(limit), 1), 200);
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/saved?limit=${boundedLimit}`,
  );
}

export function listNativePins(
  accessToken: string,
  organizationId: string,
  channelId: string,
  limit = 50,
): Promise<NativeMessagePin[]> {
  const boundedLimit = Math.min(Math.max(Math.trunc(limit), 1), 100);
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/pins?limit=${boundedLimit}`,
  );
}

export function listNativeMessages(
  accessToken: string,
  organizationId: string,
  channelId: string,
  limit = 100,
  beforeSequence?: number | null,
): Promise<NativeMessage[]> {
  const boundedLimit = Math.min(Math.max(Math.trunc(limit), 1), 200);
  const params = new URLSearchParams({ limit: String(boundedLimit) });
  if (beforeSequence !== undefined && beforeSequence !== null) {
    params.set("before_sequence", String(Math.max(1, Math.trunc(beforeSequence))));
  }
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages?${params.toString()}`,
  );
}

export function listNativeUnread(
  accessToken: string,
  organizationId: string,
): Promise<NativeChannelUnread[]> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels`,
  );
}

export function getNativeMessage(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
): Promise<NativeMessage> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages/${encodeURIComponent(messageId)}`,
  );
}

export function listNativeReplies(
  accessToken: string,
  organizationId: string,
  channelId: string,
  rootMessageId: string,
  limit = 100,
  beforeSequence?: number | null,
): Promise<NativeMessage[]> {
  const boundedLimit = Math.min(Math.max(Math.trunc(limit), 1), 200);
  const params = new URLSearchParams({ limit: String(boundedLimit) });
  if (beforeSequence !== undefined && beforeSequence !== null) {
    params.set("before_sequence", String(Math.max(1, Math.trunc(beforeSequence))));
  }
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages/${encodeURIComponent(rootMessageId)}/replies?${params.toString()}`,
  );
}

export function listNativeChannelMembers(
  accessToken: string,
  organizationId: string,
  channelId: string,
): Promise<NativeChannelMember[]> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-channels/${encodeURIComponent(channelId)}/members`,
  );
}

export function createNativeChannel(
  accessToken: string,
  organizationId: string,
  input: NativeChannelCreateInput,
): Promise<NativeChannel> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-channels`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function inviteNativeChannelMember(
  accessToken: string,
  organizationId: string,
  channelId: string,
  email: string,
  access: "read" | "write",
): Promise<NativeChannelMember> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-channels/${encodeURIComponent(channelId)}/members`,
    { method: "POST", body: JSON.stringify({ email, access }) },
  );
}

export function revokeNativeChannelMember(
  accessToken: string,
  organizationId: string,
  channelId: string,
  userId: string,
): Promise<void> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-channels/${encodeURIComponent(channelId)}/members/${encodeURIComponent(userId)}`,
    { method: "DELETE" },
  );
}

export function uploadNativeChannelAttachment(
  accessToken: string,
  organizationId: string,
  channelId: string,
  body: Uint8Array,
  contentType: string,
  idempotencyKey: string,
): Promise<NativeAttachment> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/attachments/uploads`,
    {
      method: "POST",
      body,
      headers: {
        "Content-Type": contentType,
        "Idempotency-Key": idempotencyKey,
      },
    },
  );
}

export function sendNativeMessage(
  accessToken: string,
  organizationId: string,
  channelId: string,
  input: NativeMessageCreateInput,
  idempotencyKey: string,
): Promise<NativeMessage> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages`,
    {
      method: "POST",
      body: JSON.stringify(input),
      headers: { "Idempotency-Key": idempotencyKey },
    },
  );
}

export function sendNativeReply(
  accessToken: string,
  organizationId: string,
  channelId: string,
  rootMessageId: string,
  input: NativeMessageCreateInput,
  idempotencyKey: string,
): Promise<NativeMessage> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages/${encodeURIComponent(rootMessageId)}/replies`,
    {
      method: "POST",
      body: JSON.stringify(input),
      headers: { "Idempotency-Key": idempotencyKey },
    },
  );
}

export function editNativeMessage(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
  body: string,
  expectedRevision: number,
): Promise<NativeMessage> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages/${encodeURIComponent(messageId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ body, expected_revision: expectedRevision }),
    },
  );
}

export function retractNativeMessage(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
  expectedRevision: number,
): Promise<NativeMessage> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages/${encodeURIComponent(messageId)}`,
    {
      method: "DELETE",
      body: JSON.stringify({ expected_revision: expectedRevision }),
    },
  );
}

export function setNativeSavedMessage(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
  active: boolean,
): Promise<NativeMessageSave | void> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages/${encodeURIComponent(messageId)}/saved`,
    { method: active ? "PUT" : "DELETE" },
  );
}

export function setNativePin(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
  active: boolean,
): Promise<NativeMessagePin | void> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages/${encodeURIComponent(messageId)}/pin`,
    { method: active ? "PUT" : "DELETE" },
  );
}

export function setNativeReaction(
  accessToken: string,
  organizationId: string,
  channelId: string,
  messageId: string,
  reaction: string,
  active: boolean,
): Promise<NativeReaction | void> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/messages/${encodeURIComponent(messageId)}/reaction`,
    {
      method: active ? "PUT" : "DELETE",
      body: JSON.stringify({ reaction }),
    },
  );
}

export function markNativeChannelRead(
  accessToken: string,
  organizationId: string,
  channelId: string,
  throughMessageId: string,
): Promise<NativeChannelUnread> {
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/native-conversation/channels/${encodeURIComponent(channelId)}/read`,
    {
      method: "POST",
      body: JSON.stringify({ through_message_id: throughMessageId }),
    },
  );
}

export function searchWorkspaceDocuments(
  accessToken: string,
  organizationId: string,
  query: string,
  limit = 12,
): Promise<WorkspaceSearchResponse> {
  const boundedLimit = Math.min(Math.max(Math.trunc(limit), 1), 12);
  const params = new URLSearchParams({
    q: query,
    mode: "keyword",
    limit: String(boundedLimit),
  });
  return brainApiFetch(
    accessToken,
    `/api/v1/organizations/${encodeURIComponent(organizationId)}/search?${params.toString()}`,
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
