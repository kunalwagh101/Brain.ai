import type { AdminCenter } from "./admin-center-api";
import { AdminCenterPanel } from "./admin-center-panel";
import type { AgentWorkspace } from "./agent-workspace-api";
import { AgentWorkspacePanel } from "./agent-workspace-panel";
import type {
  AIRuntimeOption,
  BrainOrganization,
  EvidenceSource,
  ExecutiveOverview,
  NativeChannel,
  NativeChannelGroup,
  NativeChannelMember,
  NativeMessage,
  NativeMessagePin,
  NativeMessageSave,
  NativeTeam,
  ProjectMemory,
  ProjectStatus,
  WorkspaceNavigation,
} from "./brain-api";
import { AskBrainPanel } from "./ask-brain-panel";
import type { ActivitySummary } from "./activity-api";
import { ActivityPanel } from "./activity-panel";
import type { DirectConversation, DirectMessage } from "./direct-message-api";
import { DirectMessagePanel } from "./direct-message-panel";
import { EvidenceWorkspace } from "./evidence-workspace";
import { NativeChannelCreate } from "./native-channel-create";
import { NativeChannelGroupManager } from "./native-channel-group-manager";
import { ArchivedChannelManager } from "./native-channel-settings";
import { NativeChatPanel } from "./native-chat-panel";
import { NativeTeamManager } from "./native-team-manager";
import { MobileWorkspaceNavigation } from "./mobile-workspace-navigation";
import { SavedMessagesPanel } from "./saved-messages-panel";
import { WorkspaceSearch } from "./workspace-search";
import { WorkspaceHeading, WorkspaceNavLink, WorkspaceScreen, WorkspaceViewProvider } from "./workspace-view";
import styles from "./workspace-shell.module.css";

function projectProgress(project: ProjectStatus): string {
  return project.progress_percent === null
    ? "Not configured"
    : `${project.progress_percent.toFixed(0)}%`;
}

function projectStatusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

function initials(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "B";
}

function uniqueMemory(items: ProjectMemory[]): ProjectMemory[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function formatKnownSpend(nanoUsd: number): string {
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(nanoUsd / 1_000_000_000);
}

function MemoryProvenance({ item }: { item: ProjectMemory }) {
  return (
    <details className={styles.provenanceDetails}>
      <summary>Evidence</summary>
      <dl>
        <div><dt>Canonical event</dt><dd>{item.canonical_event_id}</dd></div>
        {item.search_document_id ? (
          <div><dt>Search document</dt><dd>{item.search_document_id}</dd></div>
        ) : null}
        {item.work_graph_node_id ? (
          <div><dt>Work Graph node</dt><dd>{item.work_graph_node_id}</dd></div>
        ) : null}
        <div><dt>Confidence</dt><dd>{Math.round(item.confidence * 100)}%</dd></div>
      </dl>
    </details>
  );
}

export function WorkspaceShell({
  organization,
  organizations,
  navigation,
  projects,
  evidenceSources,
  nativeChannels,
  nativeTeams,
  nativeChannelGroups,
  archivedNativeChannels,
  selectedNativeChannel,
  nativeMessages,
  nativeHistoryBeforeSequence,
  nativeHasOlderHistory,
  nativePins,
  savedMessages,
  requestedNativeMessage,
  selectedNativeMembers,
  invalidRequestedChannel,
  directConversations,
  selectedDirectConversation,
  directMessages,
  invalidRequestedDirectMessage,
  overview,
  runtimes,
  agentWorkspace,
  adminCenter,
  activity,
  activityMutationBase,
  signedInName,
  askBrainEndpoint,
  evidenceMutationBase,
  canUploadEvidence,
  nativeChatMutationBase,
  nativeTeamMutationBase,
  nativeSavedMutationBase,
  nativeMessageEndpoint,
  nativeMemberEndpoint,
  nativeConversationEndpoint,
  channelPresenceEndpoint,
  canCreateNativeChannel,
  directMessageCreateEndpoint,
  directMessageSendEndpoint,
  directMessageConversationEndpoint,
  directMessagePresenceEndpoint,
  agentMutationBase,
  workspaceSearchEndpoint,
  demoMode = false,
  temporarySession = false,
  signOutAction,
}: {
  organization: BrainOrganization;
  organizations: BrainOrganization[];
  navigation: WorkspaceNavigation;
  projects: ProjectStatus[];
  evidenceSources: EvidenceSource[];
  nativeChannels: NativeChannel[];
  nativeTeams: NativeTeam[];
  nativeChannelGroups: NativeChannelGroup[];
  archivedNativeChannels: NativeChannel[];
  selectedNativeChannel: NativeChannel | null;
  nativeMessages: NativeMessage[];
  nativeHistoryBeforeSequence: number | null;
  nativeHasOlderHistory: boolean;
  nativePins: NativeMessagePin[];
  savedMessages: NativeMessageSave[];
  requestedNativeMessage: NativeMessage | null;
  selectedNativeMembers: NativeChannelMember[];
  invalidRequestedChannel: boolean;
  directConversations: DirectConversation[];
  selectedDirectConversation: DirectConversation | null;
  directMessages: DirectMessage[];
  invalidRequestedDirectMessage: boolean;
  overview: ExecutiveOverview | null;
  runtimes: AIRuntimeOption[];
  agentWorkspace: AgentWorkspace;
  adminCenter: AdminCenter | null;
  activity: ActivitySummary;
  activityMutationBase: string | null;
  signedInName: string;
  askBrainEndpoint: string | null;
  evidenceMutationBase: string | null;
  canUploadEvidence: boolean;
  nativeChatMutationBase: string | null;
  nativeTeamMutationBase: string | null;
  nativeSavedMutationBase: string | null;
  nativeMessageEndpoint: string | null;
  nativeMemberEndpoint: string | null;
  nativeConversationEndpoint: string | null;
  channelPresenceEndpoint: string | null;
  canCreateNativeChannel: boolean;
  directMessageCreateEndpoint: string | null;
  directMessageSendEndpoint: string | null;
  directMessageConversationEndpoint: string | null;
  directMessagePresenceEndpoint: string | null;
  agentMutationBase: string | null;
  workspaceSearchEndpoint: string | null;
  demoMode?: boolean;
  temporarySession?: boolean;
  signOutAction?: (formData: FormData) => Promise<void>;
}) {
  const projectById = new Map(projects.map((project) => [project.project_node_id, project]));
  const blockers = uniqueMemory(projects.flatMap((project) => project.active_blockers));
  const decisions = uniqueMemory(projects.flatMap((project) => project.confirmed_decisions));
  const warningCount = overview?.budget_warnings.filter((item) => item.warning_active).length ?? 0;
  const activeTeams = nativeTeams.filter((team) => team.status === "active");
  const activeTeamIds = new Set(activeTeams.map((team) => team.id));
  const activeGroups = nativeChannelGroups.filter((group) => group.status === "active");
  const activeGroupsByTeam = new Map<string, NativeChannelGroup[]>();
  for (const group of activeGroups) {
    const items = activeGroupsByTeam.get(group.team_id) ?? [];
    items.push(group);
    activeGroupsByTeam.set(group.team_id, items);
  }
  const globalUnassignedChannels = nativeChannels.filter(
    (channel) => !channel.team_id || !activeTeamIds.has(channel.team_id),
  );
  return (
    <WorkspaceViewProvider>
    <main className={styles.shell}>
      <a className={styles.skipLink} href="#brain-workspace-main">Skip to workspace</a>

      <aside className={styles.workspaceRail} aria-label="Workspace shortcuts">
        <div className={styles.brandMark} aria-label="Brain">B</div>
        <nav className={styles.railNav} aria-label="Primary workspace shortcuts">
          <WorkspaceNavLink view="home" href="#home" label="Home">⌂</WorkspaceNavLink>
          <WorkspaceNavLink view="activity" href="#activity-center" label={`Activity, ${activity.unread_count} unread`}>◉</WorkspaceNavLink>
          <WorkspaceNavLink view="channels" href="#native-chat" label="Brain channels">#</WorkspaceNavLink>
          <WorkspaceNavLink view="direct-messages" href="#direct-messages" label="Direct messages">↔</WorkspaceNavLink>
          <WorkspaceNavLink view="saved" href="#saved-messages" label="Saved messages">☆</WorkspaceNavLink>
          <WorkspaceNavLink view="projects" href="#projects" label="Projects">▣</WorkspaceNavLink>
          <WorkspaceNavLink view="agents" href="#agent-workspace" label="Agent runs and approvals">⌘</WorkspaceNavLink>
          <WorkspaceNavLink view="ask" href="#ask-brain" label="Ask Brain">✦</WorkspaceNavLink>
          <WorkspaceNavLink view="files" href="#files" label="Files and evidence">▤</WorkspaceNavLink>
          {adminCenter ? <WorkspaceNavLink view="admin" href="#admin-center" label="Admin and governance">⚙</WorkspaceNavLink> : null}
        </nav>
        <div className={styles.railAvatar} title={signedInName}>{initials(signedInName)}</div>
      </aside>

      <aside className={styles.navigation} aria-label="Brain workspace navigation">
        <header className={styles.workspaceHeader}>
          <div className={styles.workspaceIdentity}>
            <span>{initials(organization.name)}</span>
            <div>
              <strong>{organization.name}</strong>
              <small>{organization.role}</small>
            </div>
          </div>
          <details className={styles.workspaceMenu}>
            <summary aria-label="Switch organisation">⌄</summary>
            <div>
              {organizations.map((item) => (
                item.id === organization.id ? (
                  <span className={styles.currentWorkspace} key={item.id}>
                    <b>{item.name}</b><small>{item.role} · current</small>
                  </span>
                ) : (
                  <a href={`?organizationId=${encodeURIComponent(item.id)}`} key={item.id}>
                    <b>{item.name}</b><small>{item.role}</small>
                  </a>
                )
              ))}
            </div>
          </details>
        </header>

        <WorkspaceSearch
          organizationId={organization.id}
          endpoint={workspaceSearchEndpoint}
          channels={nativeChannels}
          projects={navigation.projects}
          tracks={navigation.tracks}
          directConversations={directConversations}
        />

        <nav className={styles.navGroups}>
          <section>
            <div className={styles.groupTitle}><span>Workspace</span></div>
            <WorkspaceNavLink view="home" href="#home"><span>⌂</span> Home</WorkspaceNavLink>
            <WorkspaceNavLink view="activity" href="#activity-center"><span>◉</span> Activity {activity.unread_count ? <small>{activity.unread_count}</small> : null}</WorkspaceNavLink>
            <WorkspaceNavLink view="saved" href="#saved-messages">
              <span>☆</span> Saved
              {savedMessages.length ? <small>{savedMessages.length}</small> : null}
            </WorkspaceNavLink>
            <WorkspaceNavLink view="agents" href="#agent-workspace"><span>⌘</span> Agent runs</WorkspaceNavLink>
            <WorkspaceNavLink view="memory" href="#memory"><span>◇</span> Decisions & blockers</WorkspaceNavLink>
            <WorkspaceNavLink view="files" href="#files"><span>▤</span> Files & evidence</WorkspaceNavLink>
            {adminCenter ? <WorkspaceNavLink view="admin" href="#admin-center"><span>⚙</span> Admin & governance</WorkspaceNavLink> : null}
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Teams</span><small>{activeTeams.length}</small>
            </div>
            {activeTeams.length ? activeTeams.map((team) => {
              const groups = activeGroupsByTeam.get(team.id) ?? [];
              const activeGroupIds = new Set(groups.map((group) => group.id));
              const teamChannels = nativeChannels.filter(
                (channel) => channel.team_id === team.id,
              );
              const ungrouped = teamChannels.filter(
                (channel) => !channel.channel_group_id
                  || !activeGroupIds.has(channel.channel_group_id),
              );
              return (
                <div className={styles.teamTree} key={team.id}>
                  <div className={styles.teamNavRow}>
                    <span aria-hidden="true">▦</span>
                    <span>
                      <strong>{team.name}</strong>
                      {team.description ? <small>{team.description}</small> : null}
                    </span>
                  </div>
                  {groups.map((group) => {
                    const groupChannels = teamChannels.filter(
                      (channel) => channel.channel_group_id === group.id,
                    );
                    return (
                      <div className={styles.channelGroupTree} key={group.id}>
                        <div className={styles.channelGroupTitle}>
                          <span>⌄</span><strong>{group.name}</strong>
                        </div>
                        {groupChannels.map((channel) => (
                          <WorkspaceNavLink
                            view="channels"
                            activeWhen={selectedNativeChannel?.id === channel.id}
                            className={styles.nestedChannel}
                            href={`?organizationId=${encodeURIComponent(organization.id)}&channelId=${encodeURIComponent(channel.id)}#native-chat`}
                            key={channel.id}
                          >
                            <span>{channel.visibility === "restricted" ? "▣" : "#"}</span>
                            <span className={styles.channelName}>{channel.name}</span>
                            {channel.unread_count ? (
                              <span className={styles.unreadBadge} aria-label={`${channel.unread_count} unread`}>
                                {channel.unread_count > 99 ? "99+" : channel.unread_count}
                              </span>
                            ) : null}
                          </WorkspaceNavLink>
                        ))}
                      </div>
                    );
                  })}
                  {ungrouped.length ? (
                    <div className={styles.channelGroupTree}>
                      <div className={styles.channelGroupTitle}>
                        <span>⌄</span><strong>Ungrouped</strong>
                      </div>
                      {ungrouped.map((channel) => (
                        <WorkspaceNavLink
                          view="channels"
                          activeWhen={selectedNativeChannel?.id === channel.id}
                          className={styles.nestedChannel}
                          href={`?organizationId=${encodeURIComponent(organization.id)}&channelId=${encodeURIComponent(channel.id)}#native-chat`}
                          key={channel.id}
                        >
                          <span>{channel.visibility === "restricted" ? "▣" : "#"}</span>
                          <span className={styles.channelName}>{channel.name}</span>
                          {channel.unread_count ? (
                            <span className={styles.unreadBadge} aria-label={`${channel.unread_count} unread`}>
                              {channel.unread_count > 99 ? "99+" : channel.unread_count}
                            </span>
                          ) : null}
                        </WorkspaceNavLink>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            }) : <p className={styles.emptyNav}>No Teams yet</p>}
            <NativeTeamManager teams={nativeTeams} endpoint={nativeTeamMutationBase} />
            <NativeChannelGroupManager
              teams={nativeTeams}
              groups={nativeChannelGroups}
              channels={nativeChannels}
              endpoint={nativeTeamMutationBase}
            />
            <ArchivedChannelManager
              channels={archivedNativeChannels}
              mutationBase={nativeChatMutationBase}
            />
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Unassigned channels</span><small>{globalUnassignedChannels.length}</small>
            </div>
            {globalUnassignedChannels.length ? globalUnassignedChannels.map((channel) => (
              <WorkspaceNavLink
                view="channels"
                activeWhen={selectedNativeChannel?.id === channel.id}
                href={`?organizationId=${encodeURIComponent(organization.id)}&channelId=${encodeURIComponent(channel.id)}#native-chat`}
                key={channel.id}
              >
                <span>{channel.visibility === "restricted" ? "▣" : "#"}</span>
                <span className={styles.channelName}>{channel.name}</span>
                {channel.unread_count ? (
                  <span className={styles.unreadBadge} aria-label={`${channel.unread_count} unread`}>
                    {channel.unread_count > 99 ? "99+" : channel.unread_count}
                  </span>
                ) : null}
              </WorkspaceNavLink>
            )) : <p className={styles.emptyNav}>No unassigned visible channels</p>}
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Direct messages</span><small>{directConversations.length}</small>
            </div>
            {directConversations.length ? directConversations.map((conversation) => (
              <WorkspaceNavLink
                view="direct-messages"
                activeWhen={selectedDirectConversation?.id === conversation.id}
                href={`?organizationId=${encodeURIComponent(organization.id)}&dmId=${encodeURIComponent(conversation.id)}#direct-messages`}
                key={conversation.id}
              >
                <span>●</span>
                <span className={styles.channelName}>{conversation.other_display_name}</span>
                {conversation.unread_count ? (
                  <span className={styles.unreadBadge} aria-label={`${conversation.unread_count} unread`}>
                    {conversation.unread_count > 99 ? "99+" : conversation.unread_count}
                  </span>
                ) : null}
              </WorkspaceNavLink>
            )) : <p className={styles.emptyNav}>No direct messages</p>}
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Connected tracks</span><small>{navigation.tracks.length}</small>
            </div>
            {navigation.tracks.length ? navigation.tracks.map((track) => (
              <a href={`#track-${encodeURIComponent(track.node_id)}`} key={track.node_id}>
                <span>#</span> {track.display_name ?? "Untitled track"}
              </a>
            )) : <p className={styles.emptyNav}>No visible connected tracks</p>}
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Projects</span><small>{navigation.projects.length}</small>
            </div>
            {navigation.projects.length ? navigation.projects.map((project) => {
              const projectStatus = projectById.get(project.node_id);
              return (
                <a href={`#project-${encodeURIComponent(project.node_id)}`} key={project.node_id}>
                  <span className={styles.projectDot} data-status={projectStatus?.status ?? "unconfigured"} />
                  {project.display_name ?? "Untitled project"}
                </a>
              );
            }) : <p className={styles.emptyNav}>No visible projects</p>}
          </section>

          <section>
            <div className={styles.groupTitle}><span>Intelligence</span></div>
            <WorkspaceNavLink view="ask" href="#ask-brain"><span>✦</span> Ask Brain</WorkspaceNavLink>
            <a href="#projects"><span>▣</span> Project Command Centre</a>
            {overview ? <a href="#company-pulse"><span>◉</span> Company pulse</a> : null}
          </section>
        </nav>

        <footer className={styles.userCard}>
          <span>{initials(signedInName)}</span>
          <div><strong>{signedInName}</strong><small>{demoMode ? "Sample profile" : temporarySession ? "Temporary test account" : "Signed in"}</small></div>
          {signOutAction ? (
            <form action={signOutAction}>
              <button className={styles.signOutButton} type="submit">Sign out</button>
            </form>
          ) : null}
        </footer>
      </aside>

      <section className={styles.mainSurface} id="brain-workspace-main">
        <header className={styles.topbar}>
          <div>
            <p>{organization.name} / Brain</p>
            <WorkspaceHeading channel={selectedNativeChannel?.name ?? null} direct={selectedDirectConversation?.other_display_name ?? null} />
          </div>
          <div className={styles.topbarActions}>
            <MobileWorkspaceNavigation className={styles.mobileNavigation}>
              <summary>Browse workspace</summary>
              <nav aria-label="Mobile workspace navigation">
                <a href="#home">Home</a>
                <a href="#activity-center">Activity {activity.unread_count ? `(${activity.unread_count})` : ""}</a>
                <a href="#saved-messages">Saved</a>
                <a href="#projects">Projects</a>
                <a href="#ask-brain">Ask Brain</a>
                <a href="#agent-workspace">Agent runs</a>
                <a href="#memory">Decisions & blockers</a>
                <a href="#files">Files & evidence</a>
                {adminCenter ? <a href="#admin-center">Admin & governance</a> : null}
                <strong>Channels</strong>
                {nativeChannels.map((channel) => (
                  <a key={channel.id} href={`?organizationId=${encodeURIComponent(organization.id)}&channelId=${encodeURIComponent(channel.id)}#native-chat`}># {channel.name}</a>
                ))}
                <strong>Direct messages</strong>
                {directConversations.map((conversation) => (
                  <a key={conversation.id} href={`?organizationId=${encodeURIComponent(organization.id)}&dmId=${encodeURIComponent(conversation.id)}#direct-messages`}>{conversation.other_display_name}</a>
                ))}
              </nav>
            </MobileWorkspaceNavigation>
            <form className={styles.mobileOrgForm} method="get">
              <label htmlFor="mobile-organization">Organisation</label>
              <select id="mobile-organization" name="organizationId" defaultValue={organization.id}>
                {organizations.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
              <button type="submit">Switch</button>
            </form>
            <span className={styles.liveBadge}>{demoMode ? "Read-only example" : temporarySession ? "Temporary test workspace · Real data" : "Permission-aware live data"}</span>
          </div>
        </header>

        <WorkspaceScreen view="activity">
        <section className={styles.panel} id="activity-center" aria-label="Activity and notifications">
          <ActivityPanel activity={activity} organizationId={organization.id} mutationBase={activityMutationBase} />
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="saved">
        <section className={styles.panel} id="saved-messages" aria-label="Personal saved messages">
          <SavedMessagesPanel
            organizationId={organization.id}
            items={savedMessages}
            channels={nativeChannels}
            mutationBase={nativeSavedMutationBase}
          />
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="channels">
        <section className={styles.panel} id="native-chat" aria-label="Brain native channels">
          {canCreateNativeChannel ? (
            <NativeChannelCreate organizationId={organization.id} endpoint={nativeChatMutationBase} />
          ) : null}
          {invalidRequestedChannel ? (
            <div className={styles.roleNotice} role="alert">
              <strong>Channel unavailable.</strong>
              <span>The requested channel is not in your current permission-filtered channel list.</span>
            </div>
          ) : selectedNativeChannel ? (
            <NativeChatPanel
              channel={selectedNativeChannel}
              key={selectedNativeChannel.id}
              messages={nativeMessages}
              initialHistoryBeforeSequence={nativeHistoryBeforeSequence}
              initialHasOlderHistory={nativeHasOlderHistory}
              pins={nativePins}
              savedMessageIds={savedMessages
                .filter((item) => item.message.channel_id === selectedNativeChannel.id)
                .map((item) => item.message.id)}
              requestedMessage={requestedNativeMessage}
              members={selectedNativeMembers}
              mutationEndpoint={nativeMessageEndpoint}
              memberEndpoint={nativeMemberEndpoint}
              conversationEndpoint={nativeConversationEndpoint}
              presenceEndpoint={channelPresenceEndpoint}
            />
          ) : (
            <div className={styles.emptyState}>
              {canCreateNativeChannel
                ? "No Brain channels exist yet. Create the first one above when the authenticated mutation route is active."
                : "No Brain channels are currently visible to this account."}
            </div>
          )}
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="direct-messages">
        <section className={styles.panel} id="direct-messages" aria-label="Participant-only direct messages">
          {invalidRequestedDirectMessage ? (
            <div className={styles.roleNotice} role="alert">
              <strong>Direct conversation unavailable.</strong>
              <span>The requested conversation is not in your participant-scoped DM list.</span>
            </div>
          ) : null}
          <DirectMessagePanel
            key={selectedDirectConversation?.id ?? "no-direct-conversation"}
            organizationId={organization.id}
            conversations={directConversations}
            selectedConversation={selectedDirectConversation}
            messages={directMessages}
            createEndpoint={directMessageCreateEndpoint}
            messageEndpoint={directMessageSendEndpoint}
            conversationEndpoint={directMessageConversationEndpoint}
            presenceEndpoint={directMessagePresenceEndpoint}
          />
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="home">
        <section className={styles.welcomeCard}>
          <div>
            <p className={styles.eyebrow}>Brain workspace</p>
            <h2>Everything your role can see, in one operating surface.</h2>
            <p>
              Catch up on conversations, find your projects, and see the evidence behind decisions.
              Direct messages stay between their participants.
            </p>
          </div>
          <div className={styles.summaryPills}>
            <span><b>{nativeChannels.length}</b> Brain channels</span>
            <span><b>{navigation.projects.length}</b> projects</span>
            <span><b>{blockers.length}</b> blockers</span>
          </div>
        </section>

        {overview ? (
          <section className={styles.metricGrid} id="company-pulse" aria-label="Company pulse">
            <article>
              <span>Visible projects</span>
              <strong>{overview.visible_project_count}</strong>
              <small>{overview.in_progress_project_count} in progress</small>
            </article>
            <article>
              <span>Confirmed blockers</span>
              <strong>{overview.active_blocker_count}</strong>
              <small>Human-confirmed only</small>
            </article>
            <article>
              <span>Known AI spend</span>
              <strong>{formatKnownSpend(overview.ai_spend.known_spend_nano_usd)}</strong>
              <small>{overview.ai_spend.cost_complete ? "Complete for period" : "Incomplete · unknown costs remain"}</small>
            </article>
            <article>
              <span>Budget warnings</span>
              <strong>{warningCount}</strong>
              <small>Visible scopes only</small>
            </article>
          </section>
        ) : (
          <section className={styles.roleNotice} role="status">
            <strong>Company-wide pulse is role-gated.</strong>
            <span>Your workspace remains available; Brain does not widen executive/audit access for this role.</span>
          </section>
        )}
        </WorkspaceScreen>

        <WorkspaceScreen view="tracks">
        <section className={styles.panel} id="tracks" aria-labelledby="tracks-heading">
          <header className={styles.panelHeader}>
            <div><p className={styles.eyebrow}>Connected evidence tracks</p><h2 id="tracks-heading">Visible tracks</h2></div>
            <span>{navigation.tracks.length}</span>
          </header>
          <div className={styles.trackList}>
            {navigation.tracks.length ? navigation.tracks.map((track) => (
              <article id={`track-${track.node_id}`} key={track.node_id}>
                <span className={styles.trackMark}>#</span>
                <div>
                  <strong>{track.display_name ?? "Untitled track"}</strong>
                  <small>{track.provider ? `${track.provider} source` : "Brain track"} · {track.source_visibility}</small>
                </div>
              </article>
            )) : <p className={styles.emptyState}>No connected tracks are currently visible to this account.</p>}
          </div>
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="projects">
        <section className={styles.panel} id="projects" aria-labelledby="projects-heading">
          <header className={styles.panelHeader}>
            <div><p className={styles.eyebrow}>Project Command Centre</p><h2 id="projects-heading">Visible projects</h2></div>
            <span>{projects.length}</span>
          </header>
          <div className={styles.projectList}>
            {projects.length ? projects.map((project) => (
              <article id={`project-${project.project_node_id}`} key={project.project_node_id}>
                <div className={styles.projectIdentity}>
                  <span>{initials(project.project_name)}</span>
                  <div>
                    <strong>{project.project_name}</strong>
                    <small>{project.progress_percent === null
                      ? "Progress not configured"
                      : `${project.progress_items.length} visible structured work items`}</small>
                  </div>
                </div>
                <div className={styles.projectMeta}>
                  <strong>{projectProgress(project)}</strong>
                  <small>{project.active_blockers.length} blocker(s)</small>
                </div>
                <span className={styles.statusChip} data-status={project.status}>{projectStatusLabel(project.status)}</span>
                <details className={styles.projectDetails}>
                  <summary>Structured work & evidence</summary>
                  <div className={styles.projectDetailsGrid}>
                    <section>
                      <h3>Structured work</h3>
                      {project.progress_items.length ? (
                        <ul>
                          {project.progress_items.map((item) => (
                            <li key={item.id}>
                              <span>{item.work_item_name}</span>
                              <small>{item.state} · weight {item.weight}</small>
                            </li>
                          ))}
                        </ul>
                      ) : <p>No configured structured work is visible.</p>}
                    </section>
                    <section>
                      <h3>Evidence</h3>
                      {project.evidence.length ? (
                        <ul>
                          {project.evidence.map((item) => (
                            <li key={item.document_id}>
                              <span>{item.title}</span>
                              <small>{item.source_provider} · {item.object_type}</small>
                              <code>{item.canonical_event_id}</code>
                            </li>
                          ))}
                        </ul>
                      ) : <p>No visible evidence is linked to this project.</p>}
                    </section>
                  </div>
                </details>
              </article>
            )) : <p className={styles.emptyState}>No projects are currently visible to this account.</p>}
          </div>
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="agents">
        <section className={styles.panel} id="agent-workspace" aria-label="Agent runs and approvals">
          <AgentWorkspacePanel
            workspace={agentWorkspace}
            projects={projects}
            channels={nativeChannels}
            mutationBase={agentMutationBase}
          />
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="admin">
        {adminCenter ? (
          <section className={styles.panel} id="admin-center" aria-label="Admin and governance">
            {demoMode ? (
              <fieldset className={styles.readOnlyAdmin} disabled aria-label="Sample administration, read only">
                <AdminCenterPanel admin={adminCenter} />
              </fieldset>
            ) : <AdminCenterPanel admin={adminCenter} />}
          </section>
        ) : (
          <section className={styles.roleNotice} role="status">
            <strong>Admin is unavailable for this account.</strong>
            <span>Return to Home or choose a workspace you can access.</span>
          </section>
        )}
        </WorkspaceScreen>

        <WorkspaceScreen view="memory">
        <section className={styles.panel} id="memory" aria-labelledby="memory-heading">
          <header className={styles.panelHeader}>
            <div><p className={styles.eyebrow}>Organisational memory</p><h2 id="memory-heading">Confirmed decisions & blockers</h2></div>
          </header>
          <div className={styles.memoryGrid}>
            <div>
              <h3>Blockers</h3>
              {blockers.length ? blockers.map((item) => (
                <article key={item.id}>
                  <span className={styles.blockerIcon}>!</span>
                  <div>
                    <strong>{item.summary}</strong>
                    <small>Confirmed blocker</small>
                    <MemoryProvenance item={item} />
                  </div>
                </article>
              )) : <p className={styles.emptyState}>No confirmed blockers in visible projects.</p>}
            </div>
            <div>
              <h3>Decisions</h3>
              {decisions.length ? decisions.map((item) => (
                <article key={item.id}>
                  <span className={styles.decisionIcon}>✓</span>
                  <div>
                    <strong>{item.summary}</strong>
                    <small>Confirmed decision</small>
                    <MemoryProvenance item={item} />
                  </div>
                </article>
              )) : <p className={styles.emptyState}>No confirmed decisions in visible projects.</p>}
            </div>
          </div>
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="ask">
        <section className={styles.panel} id="ask-brain" aria-label="Ask Brain">
          {askBrainEndpoint ? (
            <div className={styles.embeddedIntelligence}>
              <AskBrainPanel endpoint={askBrainEndpoint} runtimes={runtimes} />
            </div>
          ) : (
            <>
              <header className={styles.panelHeader}>
                <div>
                  <p className={styles.eyebrow}>Ask Brain</p>
                  <h2>Evidence-backed answers</h2>
                </div>
              </header>
              <p className={styles.emptyState}>
                {demoMode
                  ? "Answers are unavailable in this read-only example. Use a connected Brain workspace to ask a question."
                  : "Ask Brain is unavailable for this account right now. Contact your workspace admin if you need access."}
              </p>
            </>
          )}
        </section>
        </WorkspaceScreen>

        <WorkspaceScreen view="files">
        <section className={styles.panel} id="files" aria-label="Files and evidence">
          <EvidenceWorkspace
            sources={evidenceSources}
            mutationBase={evidenceMutationBase}
            canUpload={canUploadEvidence}
          />
        </section>
        </WorkspaceScreen>
      </section>

    </main>
    </WorkspaceViewProvider>
  );
}
