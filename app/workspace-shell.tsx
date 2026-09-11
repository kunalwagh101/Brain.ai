import type {
  BrainOrganization,
  ExecutiveOverview,
  ProjectStatus,
  WorkspaceNavigation,
} from "./brain-api";
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

export function WorkspaceShell({
  organization,
  navigation,
  projects,
  overview,
  signedInName,
}: {
  organization: BrainOrganization;
  navigation: WorkspaceNavigation;
  projects: ProjectStatus[];
  overview: ExecutiveOverview | null;
  signedInName: string;
}) {
  const projectById = new Map(projects.map((project) => [project.project_node_id, project]));
  const blockers = projects.flatMap((project) => project.active_blockers);
  const decisions = projects.flatMap((project) => project.confirmed_decisions);

  return (
    <main className={styles.shell}>
      <a className={styles.skipLink} href="#brain-workspace-main">Skip to workspace</a>

      <aside className={styles.workspaceRail} aria-label="Workspace shortcuts">
        <div className={styles.brandMark} aria-label="Brain">B</div>
        <nav className={styles.railNav} aria-label="Primary workspace shortcuts">
          <a className={styles.railActive} href="#home" aria-label="Home">⌂</a>
          <a href="#projects" aria-label="Projects">▣</a>
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
          <button type="button" aria-label="Workspace menu" disabled>⌄</button>
        </header>

        <div className={styles.searchBox} aria-label="Search shortcut">
          <span aria-hidden="true">⌕</span>
          <span>Search Brain</span>
          <kbd>⌘K</kbd>
        </div>

        <nav className={styles.navGroups}>
          <section>
            <div className={styles.groupTitle}><span>Workspace</span></div>
            <a className={styles.navActive} href="#home"><span>⌂</span> Home</a>
            <a href="#memory"><span>◇</span> Decisions & blockers</a>
            <a href="#files"><span>▤</span> Files & evidence</a>
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Tracks</span><small>{navigation.tracks.length}</small>
            </div>
            {navigation.tracks.length ? navigation.tracks.map((track) => (
              <a href={`#track-${track.node_id}`} key={track.node_id}>
                <span>#</span> {track.display_name ?? "Untitled track"}
              </a>
            )) : <p className={styles.emptyNav}>No visible tracks</p>}
          </section>

          <section>
            <div className={styles.groupTitle}>
              <span>Projects</span><small>{navigation.projects.length}</small>
            </div>
            {navigation.projects.length ? navigation.projects.map((project) => {
              const status = projectById.get(project.node_id);
              return (
                <a href={`#project-${project.node_id}`} key={project.node_id}>
                  <span className={styles.projectDot} data-status={status?.status ?? "unconfigured"} />
                  {project.display_name ?? "Untitled project"}
                </a>
              );
            }) : <p className={styles.emptyNav}>No visible projects</p>}
          </section>

          <section>
            <div className={styles.groupTitle}><span>Intelligence</span></div>
            <a href="#projects"><span>▣</span> Project Command Centre</a>
            {overview ? <a href="#company-pulse"><span>◉</span> Company pulse</a> : null}
            <span className={styles.comingSoon}><span>✦</span> Ask Brain <small>next</small></span>
          </section>
        </nav>

        <footer className={styles.userCard}>
          <span>{initials(signedInName)}</span>
          <div><strong>{signedInName}</strong><small>Signed in</small></div>
        </footer>
      </aside>

      <section className={styles.mainSurface} id="brain-workspace-main">
        <header className={styles.topbar}>
          <div>
            <p>{organization.name} / workspace</p>
            <h1 id="home">Home</h1>
          </div>
          <span className={styles.liveBadge}>Permission-aware live data</span>
        </header>

        <section className={styles.welcomeCard}>
          <div>
            <p className={styles.eyebrow}>Brain workspace</p>
            <h2>Everything your role can see, in one operating surface.</h2>
            <p>
              Tracks and projects below come from the tenant-scoped Work Graph. Hidden resources are
              filtered by the backend before their names reach this page.
            </p>
          </div>
          <div className={styles.summaryPills}>
            <span><b>{navigation.tracks.length}</b> tracks</span>
            <span><b>{navigation.projects.length}</b> projects</span>
            <span><b>{blockers.length}</b> blockers</span>
          </div>
        </section>

        {overview ? (
          <section className={styles.metricGrid} id="company-pulse" aria-label="Company pulse">
            <article><span>Visible projects</span><strong>{overview.visible_project_count}</strong><small>{overview.in_progress_project_count} in progress</small></article>
            <article><span>Confirmed blockers</span><strong>{overview.active_blocker_count}</strong><small>Human-confirmed only</small></article>
            <article><span>Confirmed decisions</span><strong>{overview.confirmed_decision_count}</strong><small>Evidence-backed</small></article>
            <article><span>Budget warnings</span><strong>{overview.budget_warnings.filter((item) => item.warning_active).length}</strong><small>Visible scopes only</small></article>
          </section>
        ) : (
          <section className={styles.roleNotice} role="status">
            <strong>Company-wide pulse is role-gated.</strong>
            <span>Your workspace remains available; Brain does not widen executive/audit access for this role.</span>
          </section>
        )}

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
              {blockers.length ? blockers.slice(0, 6).map((item) => (
                <article key={item.id}><span className={styles.blockerIcon}>!</span><div><strong>{item.summary}</strong><small>Confirmed blocker</small></div></article>
              )) : <p className={styles.emptyState}>No confirmed blockers in visible projects.</p>}
            </div>
            <div>
              <h3>Decisions</h3>
              {decisions.length ? decisions.slice(0, 6).map((item) => (
                <article key={item.id}><span className={styles.decisionIcon}>✓</span><div><strong>{item.summary}</strong><small>Confirmed decision</small></div></article>
              )) : <p className={styles.emptyState}>No confirmed decisions in visible projects.</p>}
            </div>
          </div>
        </section>

        <section className={styles.panel} id="files" aria-labelledby="files-heading">
          <header className={styles.panelHeader}>
            <div><p className={styles.eyebrow}>Files & evidence</p><h2 id="files-heading">Evidence workspace</h2></div>
            <span className={styles.nextBadge}>S-10.05</span>
          </header>
          <p className={styles.emptyState}>
            Governed upload, browsing and provenance UI is a separate P0 story. This shell does not fake
            file data before that route is wired.
          </p>
        </section>
      </section>

      <aside className={styles.contextRail} aria-label="Workspace context">
        <section>
          <p className={styles.eyebrow}>Context</p>
          <h2>What Brain knows</h2>
          <dl>
            <div><dt>Visible tracks</dt><dd>{navigation.tracks.length}</dd></div>
            <div><dt>Visible projects</dt><dd>{navigation.projects.length}</dd></div>
            <div><dt>Confirmed blockers</dt><dd>{blockers.length}</dd></div>
            <div><dt>Confirmed decisions</dt><dd>{decisions.length}</dd></div>
          </dl>
        </section>
        <section>
          <p className={styles.eyebrow}>Ask Brain</p>
          <h2>Evidence-backed answers</h2>
          <p>
            The Ask Brain composer will be connected through the same-origin WorkOS BFF in S-10.03/S-10.04.
            It is intentionally not wired to a dead or insecure endpoint here.
          </p>
        </section>
      </aside>
    </main>
  );
}
