import type {
  AIRuntimeOption,
  BrainOrganization,
  ExecutiveOverview,
  ProjectStatus,
} from "./brain-api";

function dollarsFromNanoUsd(value: number): string {
  const dollars = value / 1_000_000_000;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: dollars < 1 ? 4 : 2,
  }).format(dollars);
}

function progressLabel(project: ProjectStatus): string {
  return project.progress_percent === null
    ? "Not configured"
    : `${project.progress_percent.toFixed(0)}%`;
}

export function LiveWorkspace({
  organization,
  overview,
  projects,
  runtimes,
  signedInName,
}: {
  organization: BrainOrganization;
  overview: ExecutiveOverview;
  projects: ProjectStatus[];
  runtimes: AIRuntimeOption[];
  signedInName: string;
}) {
  return (
    <main className="appShell">
      <a className="skipLink" href="#workspace-main">Skip to workspace</a>

      <aside className="sidebar" aria-label="Brain workspace navigation">
        <div className="brandRow">
          <span className="brandMark" aria-hidden="true">B</span>
          <div><strong>Brain</strong><span>Company control plane</span></div>
        </div>

        <div className="workspacePicker">
          <span className="workspaceAvatar" aria-hidden="true">
            {organization.name.slice(0, 2).toUpperCase()}
          </span>
          <div><strong>{organization.name}</strong><span>{organization.role}</span></div>
        </div>

        <nav className="sideNav">
          <p>Workspace</p>
          <a className="active" href="#overview"><span aria-hidden="true">⌂</span>Overview</a>
          <a href="#projects"><span aria-hidden="true">▣</span>Projects</a>
          <a href="#memory"><span aria-hidden="true">◇</span>Decisions & blockers</a>
          <p>Governance</p>
          <a href="#ai"><span aria-hidden="true">✦</span>AI usage</a>
          <a href="#provenance"><span aria-hidden="true">≡</span>Provenance</a>
        </nav>

        <div className="sidebarFooter">
          <span className="ownerDot" aria-hidden="true">
            {signedInName.slice(0, 2).toUpperCase()}
          </span>
          <div><strong>{signedInName}</strong><span>Authenticated with WorkOS</span></div>
        </div>
      </aside>

      <section className="workspace" id="workspace-main">
        <header className="topbar">
          <div>
            <p className="crumb">{organization.name} / Executive workspace</p>
            <h1>Company pulse</h1>
          </div>
          <div className="topActions" aria-label="Live workspace status">
            <span className="safeBadge">Live permission-aware data</span>
          </div>
        </header>

        <section className="overview" id="overview" aria-labelledby="overview-title">
          <div className="sectionHeading">
            <div><p className="eyebrow">Executive overview</p><h2 id="overview-title">Current organisation state</h2></div>
            <time className="timeStamp">{new Date(overview.generated_at).toLocaleString()}</time>
          </div>

          <div className="metricGrid">
            <article className="metricCard featured">
              <div className="metricTop"><span>Visible projects</span><span className="trend">Permission filtered</span></div>
              <strong>{overview.visible_project_count}</strong>
              <p>{overview.in_progress_project_count} in progress · {overview.blocked_project_count} blocked</p>
            </article>
            <article className="metricCard">
              <div className="metricTop"><span>Confirmed blockers</span><span className="miniIcon amber">!</span></div>
              <strong>{overview.active_blocker_count}</strong>
              <p>Human-confirmed facts only.</p>
            </article>
            <article className="metricCard">
              <div className="metricTop"><span>Confirmed decisions</span><span className="miniIcon violet">✓</span></div>
              <strong>{overview.confirmed_decision_count}</strong>
              <p>Evidence-backed and permission-aware.</p>
            </article>
            <article className="metricCard" id="ai">
              <div className="metricTop"><span>Known AI spend</span><span className="miniIcon green">$</span></div>
              <strong>{dollarsFromNanoUsd(overview.ai_spend.known_spend_nano_usd)}</strong>
              <p>
                {overview.ai_spend.cost_complete
                  ? "All successful requests have calculated cost."
                  : `${overview.ai_spend.unknown_cost_requests} successful request(s) still have unknown cost.`}
              </p>
            </article>
          </div>
        </section>

        <div className="contentGrid">
          <section className="panel" id="projects" aria-labelledby="projects-title">
            <div className="panelHeader">
              <div><p className="eyebrow">Project Command Centre</p><h2 id="projects-title">Projects</h2></div>
              <span className="timeStamp">{projects.length} visible</span>
            </div>
            <div className="trackList">
              {projects.length ? projects.map((project) => (
                <article className="track" key={project.project_node_id}>
                  <div className="trackMain">
                    <span className="trackIcon" aria-hidden="true">{project.project_name.slice(0, 1).toUpperCase()}</span>
                    <div>
                      <strong>{project.project_name}</strong>
                      <span>{project.progress_basis}</span>
                    </div>
                  </div>
                  <div>
                    <strong>{progressLabel(project)}</strong>
                    <span className="timeStamp"> · {project.active_blockers.length} blocker(s)</span>
                  </div>
                  <span className="status planned">{project.status}</span>
                </article>
              )) : <p>No projects are currently visible to this account.</p>}
            </div>
          </section>

          <section className="panel" id="memory" aria-labelledby="memory-title">
            <div className="panelHeader">
              <div><p className="eyebrow">Decision memory</p><h2 id="memory-title">Current facts</h2></div>
            </div>
            <div className="activityList">
              {overview.active_blockers.slice(0, 5).map((item) => (
                <article className="activityItem" key={item.id}>
                  <span className="sourceIcon amber" aria-hidden="true">!</span>
                  <div><strong>{item.summary}</strong><span>{item.project_names.join(", ") || "Unlinked"}</span><small>Confirmed blocker</small></div>
                </article>
              ))}
              {overview.confirmed_decisions.slice(0, 5).map((item) => (
                <article className="activityItem" key={item.id}>
                  <span className="sourceIcon green" aria-hidden="true">✓</span>
                  <div><strong>{item.summary}</strong><span>{item.project_names.join(", ") || "Unlinked"}</span><small>Confirmed decision</small></div>
                </article>
              ))}
              {!overview.active_blockers.length && !overview.confirmed_decisions.length ? (
                <p>No confirmed decision or blocker facts are currently visible.</p>
              ) : null}
            </div>
          </section>
        </div>

        <section className="foundationCard" id="provenance" aria-labelledby="governance-title">
          <div className="foundationCopy">
            <span className="foundationIcon" aria-hidden="true">✦</span>
            <div>
              <p className="eyebrow">Governed AI & API</p>
              <h2 id="governance-title">No invented cost or productivity scoring</h2>
              <p>
                {runtimes.length} enabled AI runtime option(s). External API monetary cost is {overview.api_usage.cost_status};
                activity is not converted into employee worth or productivity scores.
              </p>
            </div>
          </div>
          <div className="gateList">
            <span><b className="check">✓</b> Permission-filtered portfolio</span>
            <span><b className="check">✓</b> Human-confirmed memory</span>
            <span><b className={overview.ai_spend.cost_complete ? "check" : "waiting"}>{overview.ai_spend.cost_complete ? "✓" : "···"}</b> AI cost completeness</span>
          </div>
        </section>
      </section>
    </main>
  );
}
