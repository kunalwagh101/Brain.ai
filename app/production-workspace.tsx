import { getAdminCenter } from "./admin-center-api";
import { getAgentWorkspace } from "./agent-workspace-api";
import {
  getExecutiveOverview,
  listEvidenceSources,
  listNativeChannelMembers,
  listNativeChannels,
  listNativeMessages,
  listNativeUnread,
  listOrganizations,
  listProjectStatuses,
  listRuntimeOptions,
  listWorkspaceNavigation,
} from "./brain-api";
import { WorkspaceShell } from "./workspace-shell";

const ADMIN_ROLES = new Set(["owner", "admin"]);
const EXECUTIVE_ROLES = new Set(["owner", "admin", "executive"]);
const AI_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const AGENT_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const EVIDENCE_WRITE_ROLES = new Set(["owner", "admin", "manager", "member"]);
const CHAT_WRITE_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);

export async function ProductionWorkspace({
  accessToken,
  signedInName,
  requestedOrganizationId,
  requestedChannelId,
  enableAskBrainBff = false,
  enableEvidenceBff = false,
  enableNativeChatBff = false,
  enableAgentWorkspaceBff = false,
  signOutAction,
}: {
  accessToken: string;
  signedInName: string;
  requestedOrganizationId?: string | null;
  requestedChannelId?: string | null;
  enableAskBrainBff?: boolean;
  enableEvidenceBff?: boolean;
  enableNativeChatBff?: boolean;
  enableAgentWorkspaceBff?: boolean;
  signOutAction?: (formData: FormData) => Promise<void>;
}) {
  const organizations = await listOrganizations(accessToken);
  if (!organizations.length) {
    return (
      <main role="status">
        <h1>No organisation membership</h1>
        <p>Your authenticated identity is not currently a member of a Brain organisation.</p>
      </main>
    );
  }

  const organization = requestedOrganizationId
    ? organizations.find((item) => item.id === requestedOrganizationId)
    : organizations[0];

  if (!organization) {
    return (
      <main role="alert">
        <h1>Organisation unavailable</h1>
        <p>The requested organisation is not in your current authenticated membership list.</p>
      </main>
    );
  }

  const [
    navigation,
    projects,
    evidenceSources,
    channelRows,
    unreadRows,
    overview,
    runtimes,
    agentWorkspace,
    adminCenter,
  ] = await Promise.all([
    listWorkspaceNavigation(accessToken, organization.id),
    listProjectStatuses(accessToken, organization.id),
    listEvidenceSources(accessToken, organization.id),
    listNativeChannels(accessToken, organization.id),
    listNativeUnread(accessToken, organization.id),
    EXECUTIVE_ROLES.has(organization.role)
      ? getExecutiveOverview(accessToken, organization.id)
      : Promise.resolve(null),
    AI_ROLES.has(organization.role)
      ? listRuntimeOptions(accessToken, organization.id)
      : Promise.resolve([]),
    AGENT_ROLES.has(organization.role)
      ? getAgentWorkspace(accessToken, organization.id)
      : Promise.resolve({ agents: [], runs: [] }),
    ADMIN_ROLES.has(organization.role)
      ? getAdminCenter(accessToken, organization.id)
      : Promise.resolve(null),
  ]);
  const unreadByChannel = new Map(unreadRows.map((item) => [item.channel_id, item]));
  const nativeChannels = channelRows.map((channel) => ({
    ...channel,
    unread_count: unreadByChannel.get(channel.id)?.unread_count ?? 0,
    latest_message_id: unreadByChannel.get(channel.id)?.latest_message_id ?? null,
  }));

  const selectedChannel = requestedChannelId
    ? nativeChannels.find((item) => item.id === requestedChannelId) ?? null
    : nativeChannels[0] ?? null;
  const invalidRequestedChannel = Boolean(requestedChannelId && !selectedChannel);
  const [nativeMessages, selectedNativeMembers] = selectedChannel
    ? await Promise.all([
        listNativeMessages(accessToken, organization.id, selectedChannel.id),
        selectedChannel.can_manage_members
          ? listNativeChannelMembers(accessToken, organization.id, selectedChannel.id)
          : Promise.resolve([]),
      ])
    : [[], []];

  const askBrainEndpoint = enableAskBrainBff && AI_ROLES.has(organization.role)
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/ask-brain`
    : null;
  const canUploadEvidence = EVIDENCE_WRITE_ROLES.has(organization.role);
  const evidenceMutationBase = enableEvidenceBff && canUploadEvidence
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/evidence`
    : null;
  const canCreateNativeChannel = CHAT_WRITE_ROLES.has(organization.role);
  const nativeChatMutationBase = enableNativeChatBff && canCreateNativeChannel
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/native-channels`
    : null;
  const nativeMessageEndpoint = selectedChannel && nativeChatMutationBase && selectedChannel.can_post
    ? `${nativeChatMutationBase}/${encodeURIComponent(selectedChannel.id)}/messages`
    : null;
  const nativeMemberEndpoint = selectedChannel && nativeChatMutationBase && selectedChannel.can_manage_members
    ? `${nativeChatMutationBase}/${encodeURIComponent(selectedChannel.id)}/members`
    : null;
  const nativeConversationEndpoint = selectedChannel && enableNativeChatBff
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/native-channels/${encodeURIComponent(selectedChannel.id)}`
    : null;
  const agentMutationBase = enableAgentWorkspaceBff && AGENT_ROLES.has(organization.role)
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/agent-workspace`
    : null;

  return (
    <WorkspaceShell
      organization={organization}
      organizations={organizations}
      navigation={navigation}
      projects={projects}
      evidenceSources={evidenceSources}
      nativeChannels={nativeChannels}
      selectedNativeChannel={selectedChannel}
      nativeMessages={nativeMessages}
      selectedNativeMembers={selectedNativeMembers}
      invalidRequestedChannel={invalidRequestedChannel}
      overview={overview}
      runtimes={runtimes}
      agentWorkspace={agentWorkspace}
      adminCenter={adminCenter}
      signedInName={signedInName}
      askBrainEndpoint={askBrainEndpoint}
      evidenceMutationBase={evidenceMutationBase}
      canUploadEvidence={canUploadEvidence}
      nativeChatMutationBase={nativeChatMutationBase}
      nativeMessageEndpoint={nativeMessageEndpoint}
      nativeMemberEndpoint={nativeMemberEndpoint}
      nativeConversationEndpoint={nativeConversationEndpoint}
      canCreateNativeChannel={canCreateNativeChannel}
      agentMutationBase={agentMutationBase}
      signOutAction={signOutAction}
    />
  );
}
