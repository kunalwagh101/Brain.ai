import type { ActivitySummary } from "../activity-api";
import type { AdminCenter } from "../admin-center-api";
import type { AgentWorkspace } from "../agent-workspace-api";
import type {
  BrainOrganization, EvidenceSource, ExecutiveOverview, NativeChannel,
  NativeMessage, NativeTeam, ProjectStatus, WorkspaceNavigation,
} from "../brain-api";
import type { DirectConversation, DirectMessage } from "../direct-message-api";
import { WorkspaceShell } from "../workspace-shell";

// A sample read model passed through the very same components as the authenticated
// workspace. No mutation endpoint or credential is provided to the browser.
const stamp = "2026-09-26T10:00:00.000Z";
const organization: BrainOrganization = { id: "sample-brain", slug: "sample-brain", name: "Northstar Studio", role: "owner" };
const team: NativeTeam = {
  id: "product", organization_id: organization.id, name: "Product", slug: "product",
  description: "Design and delivery", status: "active", revision: 1,
  created_by_user_id: "ada", created_at: stamp, updated_at: stamp, archived_at: null, can_manage: false,
};
const channels: NativeChannel[] = [
  { id: "general", name: "general", team_id: "product", channel_group_id: "planning", unread_count: 2, description: "Everyone in the studio", visibility: "organization" as const },
  { id: "design", name: "design-review", team_id: "product", channel_group_id: "planning", unread_count: 1, description: "Feedback and design decisions", visibility: "organization" as const },
  { id: "launch", name: "launch-plan", team_id: "product", channel_group_id: null, unread_count: 0, description: "Release coordination", visibility: "restricted" as const },
].map((item) => ({
  organization_id: organization.id, work_graph_node_id: null, slug: item.name,
  status: "active", created_by_user_id: "ada", created_at: stamp, updated_at: stamp,
  archived_at: null, settings_revision: 1, member_count: 8, can_post: false,
  can_manage: false, can_manage_members: false, ...item,
}));
const navigation: WorkspaceNavigation = {
  projects: [
    { node_id: "mobile-app", kind: "project", display_name: "Mobile experience", source_visibility: "organization", provider: "Brain" },
    { node_id: "launch", kind: "project", display_name: "Autumn launch", source_visibility: "organization", provider: "Brain" },
  ],
  tracks: [{ node_id: "customer-voice", kind: "track", display_name: "Customer voice", source_visibility: "organization", provider: "Drive" }],
};
const projects: ProjectStatus[] = [
  {
    project_node_id: "mobile-app", project_name: "Mobile experience", progress_percent: 66.67,
    progress_basis: "visible_configured_work_items", status: "blocked",
    progress_items: [
      { id: "prototype", work_item_node_id: "prototype", work_item_name: "Navigation prototype", state: "done", weight: 2, note: null, updated_at: stamp },
      { id: "accessibility", work_item_node_id: "accessibility", work_item_name: "Accessibility review", state: "in_progress", weight: 1, note: null, updated_at: stamp },
    ],
    active_blockers: [{ id: "b1", kind: "blocker", state: "confirmed", summary: "Waiting on research participant recruitment", confidence: 1, work_graph_node_id: "mobile-app", canonical_event_id: "event-b1", search_document_id: "doc-b1" }],
    confirmed_decisions: [{ id: "d1", kind: "decision", state: "confirmed", summary: "Keep the primary navigation task focused", confidence: 1, work_graph_node_id: "mobile-app", canonical_event_id: "event-d1", search_document_id: "doc-d1" }],
    candidate_memories: [],
    evidence: [{ document_id: "doc-d1", canonical_event_id: "event-d1", work_graph_node_id: "mobile-app", source_provider: "Drive", object_type: "document", object_external_id: "research", title: "Navigation research notes", occurred_at: stamp, provenance: {} }],
  },
  { project_node_id: "launch", project_name: "Autumn launch", progress_percent: null, progress_basis: "unconfigured", status: "unconfigured", progress_items: [], active_blockers: [], confirmed_decisions: [], candidate_memories: [], evidence: [] },
];
const provenance = { metric_key: "sample", source_records: "Sample read model", calculation: "Sample only", source_count: 2, period_start: stamp, period_end: stamp, drilldown_path: null, complete: true };
const overview: ExecutiveOverview = {
  generated_at: stamp, period_start: stamp, period_end: stamp, visible_project_count: 2,
  blocked_project_count: 1, in_progress_project_count: 0, done_project_count: 0,
  not_started_project_count: 0, unconfigured_project_count: 1, active_blocker_count: 1,
  confirmed_decision_count: 1, portfolio: [], active_blockers: [], confirmed_decisions: [],
  ai_spend: {
    period_start: stamp, period_end: stamp, request_count: 0, succeeded_count: 0, failed_count: 0,
    known_cost_requests: 0, unknown_cost_requests: 0, input_tokens: 0, cached_input_tokens: 0,
    output_tokens: 0, known_spend_nano_usd: 0, cost_complete: true, by_provider: [], provenance,
  },
  api_usage: {
    period_start: stamp, period_end: stamp, observation_count: 0, succeeded_count: 0,
    failed_count: 0, active_grant_count: 0, known_spend_nano_usd: null,
    cost_status: "sample", by_service: [], provenance, cost_provenance: provenance,
  },
  budget_warnings: [], risks: [], metric_provenance: [provenance],
};
const message = (id: string, channelId: string, name: string, body: string, sequence: number): NativeMessage => ({
  id, organization_id: organization.id, channel_id: channelId, thread_root_id: null,
  actor_kind: "user", author_user_id: name === "Ada Chen" ? "ada" : "morgan", agent_run_id: null,
  actor_display_name: name, body, body_sha256: "sample", projection_status: "ready",
  canonical_event_id: `event-${id}`, message_sequence: sequence, created_at: stamp,
  reply_count: 0, thread_unread_count: 0, thread_latest_reply_id: null,
  thread_first_unread_reply_id: null, mentions: [], reactions: [], attachments: [],
  revision: 1, edited_at: null, deleted_at: null, can_edit: false, can_delete: false,
});
const messages: NativeMessage[] = [
  message("m1", "general", "Ada Chen", "Welcome to the project room. The research summary is linked under Files & evidence.", 1),
  message("m2", "general", "Morgan Lee", "I’ve reviewed the first navigation prototype. The simpler path is easier to understand.", 2),
  message("m3", "design", "Morgan Lee", "The accessibility review is underway. Please leave feedback in this channel.", 1),
  message("m4", "launch", "Ada Chen", "Launch planning starts here. Access to this channel is restricted.", 1),
];
const conversations: DirectConversation[] = [
  { id: "dm-morgan", organization_id: organization.id, other_user_id: "morgan", other_display_name: "Morgan Lee", other_email: "morgan@example.test", can_send: false, unread_count: 1, latest_message_id: "dm1", first_unread_message_id: "dm1", created_at: stamp, updated_at: stamp },
];
const directMessages: DirectMessage[] = [
  { id: "dm1", organization_id: organization.id, conversation_id: "dm-morgan", author_user_id: "morgan", author_display_name: "Morgan Lee", is_mine: false, body: "Can we review the navigation together this afternoon?", body_sha256: "sample", sequence: 1, revision: 1, edited_at: null, deleted_at: null, can_edit: false, can_delete: false, reactions: [], created_at: stamp },
];
const activity: ActivitySummary = {
  unread_count: 3,
  items: [
    { id: "a1", kind: "mention", actor_display_name: "Morgan Lee", label: "Mentioned you in #design-review", context_label: "Product / Planning", href: "?channelId=design#native-chat", read: false, created_at: stamp },
    { id: "a2", kind: "direct_message", actor_display_name: "Morgan Lee", label: "Sent you a direct message", context_label: "Direct messages", href: "?dmId=dm-morgan#direct-messages", read: false, created_at: stamp },
    { id: "a3", kind: "blocker_update", actor_display_name: null, label: "Research recruitment needs attention", context_label: "Mobile experience", href: "#project-mobile-app", read: false, created_at: stamp },
    { id: "a4", kind: "project_update", actor_display_name: "Ada Chen", label: "Navigation prototype completed", context_label: "Mobile experience", href: "#project-mobile-app", read: true, created_at: stamp },
  ],
};
const sources: EvidenceSource[] = [{
  id: "source-1", organization_id: organization.id, integration_connection_id: "drive-sample",
  native_channel_id: null, kind: "document", title: "Navigation research notes", filename: "research.pdf",
  media_type: "application/pdf", content_sha256: "sample", byte_size: 24192,
  source_visibility: "organization", chunk_count: 8, extracted_char_count: 5320,
  created_by_user_id: "ada", occurred_at: stamp, status: "active", integration_status: "active",
  retrieval_available: true, last_error_code: null, created_at: stamp, updated_at: stamp,
  deleted_at: null, can_delete: false,
}];
const agentWorkspace: AgentWorkspace = {
  agents: [{ id: "agent-1", name: "Research assistant", description: "Summarises linked evidence with approval gates", enabled: true, max_steps: 4, provider_key: "sample", provider_display_name: "Sample provider", model_key: "sample", model_display_name: "Sample model", tool_policies: [{ tool_name: "search_evidence", policy: "read", risk: "low", replay_safe: true, approval_required: false }] }],
  runs: [],
};
const adminCenter: AdminCenter = {
  organization_id: organization.id, organization_name: organization.name, organization_slug: organization.slug,
  viewer_role: "owner", members: [
    { membership_id: "owner", user_id: "ada", email: "ada@example.test", display_name: "Ada Chen", role: "owner", joined_at: stamp },
    { membership_id: "member", user_id: "morgan", email: "morgan@example.test", display_name: "Morgan Lee", role: "member", joined_at: stamp },
  ],
  integrations: [{ id: "drive-sample", provider: "google_drive", display_name: "Team Drive", status: "active", health: "healthy", scopes: ["read"], last_synced_at: stamp, last_error_code: null, created_at: stamp, revoked_at: null }],
  ai_providers: [], api_services: [],
  summary: { member_count: 2, integration_count: 1, unhealthy_integration_count: 0, ai_provider_count: 0, enabled_ai_model_count: 0, api_service_count: 0, active_api_grant_count: 0, expiring_api_grant_count: 0 },
};

export default async function Demo({ searchParams }: { searchParams: Promise<{ channelId?: string; dmId?: string }> }) {
  const requested = await searchParams;
  const channel = channels.find((item) => item.id === requested.channelId) ?? channels[0];
  const conversation = conversations.find((item) => item.id === requested.dmId) ?? conversations[0];
  const invalidChannel = !!requested.channelId && !channels.some((item) => item.id === requested.channelId);
  const invalidDm = !!requested.dmId && !conversations.some((item) => item.id === requested.dmId);
  return (
    <>
      <div role="note" style={{ position: "relative", zIndex: 50, background: "#dcebe4", color: "#1d514b", padding: "9px 20px", textAlign: "center", fontSize: 13 }}>
        <strong>Interactive sample workspace</strong> · Example data · Read only · No account or backend connected
      </div>
      <WorkspaceShell
        demoMode
        organization={organization} organizations={[organization]} navigation={navigation}
        projects={projects} evidenceSources={sources} nativeChannels={channels} nativeTeams={[team]}
        nativeChannelGroups={[{ id: "planning", organization_id: organization.id, team_id: team.id, name: "Planning", slug: "planning", status: "active", revision: 1, created_by_user_id: "ada", created_at: stamp, updated_at: stamp, archived_at: null, can_manage: false }]}
        archivedNativeChannels={[]} selectedNativeChannel={channel}
        nativeMessages={messages.filter((item) => item.channel_id === channel.id)}
        nativeHistoryBeforeSequence={1} nativeHasOlderHistory={false} nativePins={[]}
        savedMessages={[{ save_id: "saved-1", saved_at: stamp, message: messages[1] }]}
        requestedNativeMessage={null} selectedNativeMembers={[]}
        invalidRequestedChannel={invalidChannel} directConversations={conversations}
        selectedDirectConversation={invalidDm ? null : conversation} directMessages={invalidDm ? [] : directMessages}
        invalidRequestedDirectMessage={invalidDm} overview={overview} runtimes={[]}
        agentWorkspace={agentWorkspace} adminCenter={adminCenter} activity={activity}
        activityMutationBase={null} signedInName="Ada Chen" askBrainEndpoint={null}
        evidenceMutationBase={null} canUploadEvidence={false} nativeChatMutationBase={null}
        nativeTeamMutationBase={null} nativeSavedMutationBase={null} nativeMessageEndpoint={null}
        nativeMemberEndpoint={null} nativeConversationEndpoint={null} channelPresenceEndpoint={null}
        canCreateNativeChannel={false} directMessageCreateEndpoint={null} directMessageSendEndpoint={null}
        directMessageConversationEndpoint={null} directMessagePresenceEndpoint={null}
        agentMutationBase={null} workspaceSearchEndpoint={null}
      />
    </>
  );
}
