import { getActivity } from "./activity-api";
import { ActivityDock } from "./activity-dock";
import { getAdminCenter } from "./admin-center-api";
import { getAgentWorkspace } from "./agent-workspace-api";
import {
  BrainApiError,
  getExecutiveOverview,
  getNativeMessage,
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
import { listDirectConversations, listDirectMessages } from "./direct-message-api";
import { computeLiveRevision } from "./live-updates-api";
import { LiveWorkspaceRefresh } from "./live-workspace-refresh";
import { WorkspaceShell } from "./workspace-shell";

const ADMIN_ROLES = new Set(["owner", "admin"]);
const EXECUTIVE_ROLES = new Set(["owner", "admin", "executive"]);
const AI_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const AGENT_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const EVIDENCE_WRITE_ROLES = new Set(["owner", "admin", "manager", "member"]);
const CHAT_WRITE_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);
const DM_ROLES = CHAT_WRITE_ROLES;

export async function ProductionWorkspace({
  accessToken,
  signedInName,
  requestedOrganizationId,
  requestedChannelId,
  requestedDirectMessageId,
  requestedMessageId,
  enableAskBrainBff = false,
  enableEvidenceBff = false,
  enableNativeChatBff = false,
  enableDirectMessageBff = false,
  enableActivityBff = false,
  enableAgentWorkspaceBff = false,
  enableLiveUpdatesBff = false,
  enableWorkspaceSearchBff = false,
  signOutAction,
}: {
  accessToken: string;
  signedInName: string;
  requestedOrganizationId?: string | null;
  requestedChannelId?: string | null;
  requestedDirectMessageId?: string | null;
  requestedMessageId?: string | null;
  enableAskBrainBff?: boolean;
  enableEvidenceBff?: boolean;
  enableNativeChatBff?: boolean;
  enableDirectMessageBff?: boolean;
  enableActivityBff?: boolean;
  enableAgentWorkspaceBff?: boolean;
  enableLiveUpdatesBff?: boolean;
  enableWorkspaceSearchBff?: boolean;
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
    activity,
    overview,
    runtimes,
    agentWorkspace,
    adminCenter,
    directConversations,
  ] = await Promise.all([
    listWorkspaceNavigation(accessToken, organization.id),
    listProjectStatuses(accessToken, organization.id),
    listEvidenceSources(accessToken, organization.id),
    listNativeChannels(accessToken, organization.id),
    listNativeUnread(accessToken, organization.id),
    getActivity(accessToken, organization.id),
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
    DM_ROLES.has(organization.role)
      ? listDirectConversations(accessToken, organization.id)
      : Promise.resolve([]),
  ]);
  const unreadByChannel = new Map(unreadRows.map((item) => [item.channel_id, item]));
  const nativeChannels = channelRows.map((channel) => ({
    ...channel,
    unread_count: unreadByChannel.get(channel.id)?.unread_count ?? 0,
    latest_message_id: unreadByChannel.get(channel.id)?.latest_message_id ?? null,
  }));

  const selectedDirectConversation = requestedDirectMessageId
    ? directConversations.find((item) => item.id === requestedDirectMessageId) ?? null
    : null;
  const invalidRequestedDirectMessage = Boolean(
    requestedDirectMessageId && !selectedDirectConversation,
  );

  const selectedChannel = requestedDirectMessageId
    ? null
    : requestedChannelId
      ? nativeChannels.find((item) => item.id === requestedChannelId) ?? null
      : nativeChannels[0] ?? null;
  const invalidRequestedChannel = Boolean(
    !requestedDirectMessageId && requestedChannelId && !selectedChannel,
  );
  const [nativeMessageRows, selectedNativeMembers] = selectedChannel
    ? await Promise.all([
        listNativeMessages(accessToken, organization.id, selectedChannel.id),
        selectedChannel.can_manage_members
          ? listNativeChannelMembers(accessToken, organization.id, selectedChannel.id)
          : Promise.resolve([]),
      ])
    : [[], []];

  let requestedNativeMessage = null;
  let nativeMessages = nativeMessageRows;
  if (selectedChannel && requestedMessageId) {
    try {
      requestedNativeMessage = await getNativeMessage(
        accessToken,
        organization.id,
        selectedChannel.id,
        requestedMessageId,
      );
    } catch (error) {
      if (!(error instanceof BrainApiError) || ![404, 422].includes(error.status)) {
        throw error;
      }
    }

    if (requestedNativeMessage) {
      const rootId = requestedNativeMessage.thread_root_id ?? requestedNativeMessage.id;
      let rootMessage = nativeMessageRows.find((message) => message.id === rootId) ?? null;
      if (!rootMessage) {
        try {
          rootMessage = await getNativeMessage(
            accessToken,
            organization.id,
            selectedChannel.id,
            rootId,
          );
        } catch (error) {
          if (!(error instanceof BrainApiError) || ![404, 422].includes(error.status)) {
            throw error;
          }
        }
      }
      if (rootMessage && !nativeMessageRows.some((message) => message.id === rootMessage.id)) {
        nativeMessages = [rootMessage, ...nativeMessageRows];
      }
    }
  }

  const directMessages = selectedDirectConversation
    ? await listDirectMessages(accessToken, organization.id, selectedDirectConversation.id)
    : [];

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
  const directMessageCreateEndpoint = enableDirectMessageBff && DM_ROLES.has(organization.role)
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/direct-messages`
    : null;
  const directMessageSendEndpoint = (
    selectedDirectConversation
    && selectedDirectConversation.can_send
    && directMessageCreateEndpoint
  )
    ? `${directMessageCreateEndpoint}/${encodeURIComponent(selectedDirectConversation.id)}/messages`
    : null;
  const activityMutationBase = enableActivityBff
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/activity`
    : null;
  const agentMutationBase = enableAgentWorkspaceBff && AGENT_ROLES.has(organization.role)
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/agent-workspace`
    : null;
  const liveRevision = await computeLiveRevision({
    activity,
    channels: channelRows,
    unread: unreadRows,
    selectedChannelMessages: nativeMessages,
    directConversations,
    directMessages,
  });
  const liveParams = new URLSearchParams();
  if (selectedChannel) liveParams.set("channelId", selectedChannel.id);
  if (selectedDirectConversation) liveParams.set("dmId", selectedDirectConversation.id);
  const liveQuery = liveParams.toString();
  const liveUpdatesEndpoint = enableLiveUpdatesBff
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/live${liveQuery ? `?${liveQuery}` : ""}`
    : null;
  const workspaceSearchEndpoint = enableWorkspaceSearchBff
    ? `/api/brain/organizations/${encodeURIComponent(organization.id)}/search`
    : null;

  return (
    <>
      <ActivityDock
        activity={activity}
        organizationId={organization.id}
        mutationBase={activityMutationBase}
      />
      {liveUpdatesEndpoint ? (
        <LiveWorkspaceRefresh
          endpoint={liveUpdatesEndpoint}
          initialRevision={liveRevision}
        />
      ) : null}
      <WorkspaceShell
        organization={organization}
        organizations={organizations}
        navigation={navigation}
        projects={projects}
        evidenceSources={evidenceSources}
        nativeChannels={nativeChannels}
        selectedNativeChannel={selectedChannel}
        nativeMessages={nativeMessages}
        requestedNativeMessage={requestedNativeMessage}
        selectedNativeMembers={selectedNativeMembers}
        invalidRequestedChannel={invalidRequestedChannel}
        directConversations={directConversations}
        selectedDirectConversation={selectedDirectConversation}
        directMessages={directMessages}
        invalidRequestedDirectMessage={invalidRequestedDirectMessage}
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
        directMessageCreateEndpoint={directMessageCreateEndpoint}
        directMessageSendEndpoint={directMessageSendEndpoint}
        agentMutationBase={agentMutationBase}
        workspaceSearchEndpoint={workspaceSearchEndpoint}
        signOutAction={signOutAction}
      />
    </>
  );
}
