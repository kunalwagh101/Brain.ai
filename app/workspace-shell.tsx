import type {
  AIRuntimeOption,
  BrainOrganization,
  EvidenceSource,
  ExecutiveOverview,
  NativeChannel,
  NativeMessage,
  ProjectMemory,
  ProjectStatus,
  WorkspaceNavigation,
} from "./brain-api";
import { AskBrainPanel } from "./ask-brain-panel";
import { EvidenceWorkspace } from "./evidence-workspace";
import { NativeChannelCreate } from "./native-channel-create";
import { NativeChatPanel } from "./native-chat-panel";
import styles from "./workspace-shell.module.css";

function projectProgress(project: ProjectStatus): string {
  return project.progress_percent === null
    ? "Not configured"
    : `${project.progress_percent.toFixed(0)}%`;
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
  selectedNativeChannel,
  nativeMessages,
  invalidRequestedChannel,
  overview,
  runtimes,
  signedInName,
  askBrainEndpoint,
  evidenceMutationBase,
  canUploadEvidence,
  nativeChatMutationBase,
  nativeMessageEndpoint,
  canCreateNativeChannel,
  signOutAction,
}: {
  organization: BrainOrganization;
  organizations: BrainOrganization[];
  navigation: WorkspaceNavigation;
  projects: ProjectStatus[];
  evidenceSources: EvidenceSource[];
  nativeChannels: NativeChannel[];
  selectedNativeChannel: NativeChannel | null;
  nativeMessages: NativeMessage[];
  invalidRequestedChannel: boolean;
  overview: ExecutiveOverview | null;
  runtimes: AIRuntimeOption[];
  signedInName: string;
  askBrainEndpoint: string | null;
  evidenceMutationBase: string | null;
  canUploadEvidence: boolean;
  nativeChatMutationBase: string | null;
  nativeMessageEndpoint: string | null;
  canCreateNativeChannel: boolean;
  signOutAction?: (formData: FormData) => Promise<void>;
}) {
  const projectById = new Map(projects.map((project) => [project.project_node_id, project]));
  const blockers = uniqueMemory(projects.flatMap((project) => project.active_blockers));
  const decisions = uniqueMemory(projects.flatMap((project) => project.confirmed_decisions));
  const warningCount = overview?.budget_warnings.filter((item) => item.warning_active).length ?? 0;

  return (
    <main className={styles.shell}>
      <a className={styles.skipLink} href="#brain-workspace-main">Skip to workspace</a>

      <aside className={styles.workspaceRail} aria-label="Workspace shortcuts">
        <div className={styles.brandMark} aria-label="Brain">B</div>
        <nav className={styles.railNav} aria-label="Primary workspace shortcuts">
          <a className={styles.railActive} href="#home" aria-label="Home">⌂</a>
          <a href="#native-chat" aria-label="Brain channels">#</a>
          <a href="#projects" aria-label="Projects">▣</a>
          <a href="#ask-brain" aria-label="Ask Brain">✦</a>
          <a href="#memory" aria-label="Decisions and blockers">◇</a>
          <a href="#files" aria-label="Files and evidence">▤</a>
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

        <a className={styles.searchBox} href="#ask-brain" aria-label="Open Ask Brain">
          <span aria-hidden="true">✦</span>
          <span>Ask Brain</span>
          <kbd>⌘K</kbd>
        </a>

        <nav className={styles.navGroups}>
          <section>
            <div className={styles.groupTitle}><span>Workspace</span></div>
            <a className={styles.navActive} href="#home"><span>⌂</span> Home</a>
            <a href="#memory"><span>◇</span> Decisions & blockers</a>
            <a href="#files"><span>▤</span> Files & evidence</a>
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Brain channels</span><small>{nativeChannels.length}</small>
            </div>
            {nativeChannels.length ? nativeChannels.map((channel) => (
              <a
                href={`?organizationId=${encodeURIComponent(organization.id)}&channelId=${encodeURIComponent(channel.id)}#native-chat`}
                key={channel.id}
                aria-current={selectedNativeChannel?.id === channel.id ? "page" : undefined}
              >
                <span>{channel.visibility === "restricted" ? "▣" : "#"}</span>
                {channel.name}
              </a>
            )) : <p className={styles.emptyNav}>No visible Brain channels</p>}
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Connected tracks</span><small>{navigation.tracks.length}</small>
            </div>
            {navigation.tracks.length ? navigation.tracks.map((track) => (
              <a href={`#track-${track.node_id}`} key={track.node_id}>
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
                <a href={`#project-${project.node_id}`} key={project.node_id}>
                  <span className={styles.projectDot} data-status={projectStatus?.status ?? "unconfigured"} />
                  {project.display_name ?? "Untitled project"}
                </a>
              );
            }) : <p className={styles.emptyNav}>No visible projects</p>}
          </section>

          <section>
            <div className={styles.groupTitle}><span>Intelligence</span></div>
            <a href="#ask-brain"><span>✦</span> Ask Brain</a>
            <a href="#projects"><span>▣</span> Project Command Centre</a>
            {overview ? <a href="#company-pulse"><span>◉</span> Company pulse</a> : null}
          </section>
        </nav>

        <footer className={styles.userCard}>
          <span>{initials(signedInName)}</span>
          <div><strong>{signedInName}</strong><small>Signed in</small></div>
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
            <p>{organization.name} / workspace</p>
            <h1 id="home">Home</h1>
          </div>
          <div className={styles.topbarActions}>
            <form className={styles.mobileOrgForm} method="get">
              <label htmlFor="mobile-organization">Organisation</label>
              <select id="mobile-organization" name="organizationId" defaultValue={organization.id}>
                {organizations.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
              <button type="submit">Switch</button>
            </form>
            <span className={styles.liveBadge}>Permission-aware live data</span>
          </div>
        </header>

        <section className={styles.welcomeCard}>
          <div>
            <p className={styles.eyebrow}>Brain workspace</p>
            <h2>Everything your role can see, in one operating surface.</h2>
            <p>
              Native Brain channels, connected tracks and projects share the same tenant and evidence
              boundaries. Restricted names and messages are filtered by the backend before this page renders.
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
              messages={nativeMessages}
              mutationEndpoint={nativeMessageEndpoint}
            />
          ) : (
            <div className={styles.emptyState}>
              {canCreateNativeChannel
                ? "No Brain channels exist yet. Create the first one above when the authenticated mutation route is active."
                : "No Brain channels are currently visible to this account."}
            </div>
          )}
        </section>

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
                  <div><strong>{project.project_name}</strong><small>{project.progress_basis}</small></div>
                </div>
                <div className={styles.projectMeta}>
                  <strong>{projectProgress(project)}</strong>
                  <small>{project.active_blockers.length} blocker(s)</small>
                </div>
                <span className={styles.statusChip} data-status={project.status}>{project.status}</span>
                <details className={styles.projectDetails}>
                  <summary>Structured work & evidence</summary>
                  <div className={styles.projectDetailsGrid}>
                    <section>
                      <h3>Structured work</h3>
                      {project.progress_items.length ? (
                        <ul>
                          {project.progress_items.slice(0, 8).map((item) => (
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
                          {project.evidence.slice(0, 8).map((item) => (
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

        <section className={styles.panel} id="memory" aria-labelledby="memory-heading">
          <header className={styles.panelHeader}>
            <div><p className={styles.eyebrow}>Organisational memory</p><h2 id="memory-heading">Confirmed decisions & blockers</h2></div>
          </header>
          <div className={styles.memoryGrid}>
            <div>
              <h3>Blockers</h3>
              {blockers.length ? blockers.slice(0, 8).map((item) => (
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
              {decisions.length ? decisions.slice(0, 8).map((item) => (
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
                <span className={styles.nextBadge}>S-10.04</span>
              </header>
              <p className={styles.emptyState}>
                The live Ask Brain surface is ready for governed runtimes, but the browser mutation stays
                disabled until the official WorkOS same-origin BFF is installed. Brain will not expose a
                reusable backend bearer token to make this button work early.
              </p>
            </>
          )}
        </section>

        <section className={styles.panel} id="files" aria-label="Files and evidence">
          <EvidenceWorkspace
            sources={evidenceSources}
            mutationBase={evidenceMutationBase}
            canUpload={canUploadEvidence}
          />
        </section>
      </section>

      <aside className={styles.contextRail} aria-label="Workspace context">
        <section>
          <p className={styles.eyebrow}>Context</p>
          <h2>What Brain knows</h2>
          <dl>
            <div><dt>Brain channels</dt><dd>{nativeChannels.length}</dd></div>
            <div><dt>Connected tracks</dt><dd>{navigation.tracks.length}</dd></div>
            <div><dt>Visible projects</dt><dd>{navigation.projects.length}</dd></div>
            <div><dt>Evidence sources</dt><dd>{evidenceSources.length}</dd></div>
            <div><dt>Confirmed blockers</dt><dd>{blockers.length}</dd></div>
            <div><dt>Confirmed decisions</dt><dd>{decisions.length}</dd></div>
          </dl>
        </section>
        <section>
          <p className={styles.eyebrow}>Native chat</p>
          <h2>{nativeChatMutationBase ? "Secure BFF connected" : "Secure BFF pending"}</h2>
          <p>
            {nativeChatMutationBase
              ? "Human messages use the authenticated same-origin server path; agent identity remains server-controlled."
              : "Visible channels can be composed server-side, but channel/message mutations stay disabled until AuthKit/BFF activation."}
          </p>
        </section>
        <section>
          <p className={styles.eyebrow}>Ask Brain</p>
          <h2>{askBrainEndpoint ? "Secure BFF connected" : "Secure BFF pending"}</h2>
          <p>
            {askBrainEndpoint
              ? `${runtimes.length} governed runtime(s) are available through the same-origin server path.`
              : "The UI does not send WorkOS or Brain access tokens to browser code. AuthKit/BFF activation remains the S-10.04 gate."}
          </p>
        </section>
        <section>
          <p className={styles.eyebrow}>Evidence</p>
          <h2>{evidenceMutationBase ? "Governed mutations connected" : "Permission-aware read model"}</h2>
          <p>
            {evidenceMutationBase
              ? "Upload and deletion use the authenticated same-origin server path; source lifecycle remains authoritative in FastAPI."
              : "Visible evidence metadata is server-rendered. Upload/delete stays disabled until the authenticated WorkOS BFF is active."}
          </p>
        </section>
      </aside>
    </main>
  );
}
