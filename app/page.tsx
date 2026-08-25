import { PreviewActions } from "./preview-actions";

const activity = [
  { source: "GitHub", tone: "violet", title: "Authentication middleware merged", detail: "PR #184 · brain-api · 12 checks passed", time: "18 min" },
  { source: "Linear", tone: "blue", title: "Tenant isolation moved to review", detail: "BRN-42 · Assigned to Security", time: "41 min" },
  { source: "Slack", tone: "green", title: "Onboarding copy approved", detail: "#product-launch · Decision captured", time: "1 hr" },
];

const tracks = [
  { name: "Secure shell", progress: 84, meta: "7 of 9 checks", status: "In review" },
  { name: "Connector framework", progress: 32, meta: "3 of 11 tasks", status: "Building" },
  { name: "Evidence graph", progress: 12, meta: "Discovery", status: "Planned" },
];

export default function Home() {
  return (
    <main className="appShell">
      <a className="skipLink" href="#workspace-main">Skip to workspace</a>

      <aside className="sidebar" aria-label="Brain workspace navigation">
        <div className="brandRow">
          <span className="brandMark" aria-hidden="true">B</span>
          <div><strong>Brain</strong><span>Control plane</span></div>
        </div>

        <div className="workspacePicker">
          <span className="workspaceAvatar" aria-hidden="true">OX</span>
          <div><strong>OffsetX</strong><span>Product workspace</span></div>
          <span className="pickerChevron" aria-hidden="true">⌄</span>
        </div>

        <nav className="sideNav">
          <p>Workspace</p>
          <a className="active" href="#overview"><span aria-hidden="true">⌂</span>Overview</a>
          <a href="#project-room"><span aria-hidden="true">▣</span>Project room</a>
          <a href="#ai-control"><span aria-hidden="true">✦</span>AI control</a>
          <p>Governance</p>
          <a href="#sources"><span aria-hidden="true">⇄</span>Sources</a>
          <a href="#access"><span aria-hidden="true">◇</span>Access</a>
          <a href="#audit"><span aria-hidden="true">≡</span>Audit log</a>
        </nav>

        <div className="sidebarFooter">
          <span className="ownerDot" aria-hidden="true">KW</span>
          <div><strong>Workspace owner</strong><span>Private preview</span></div>
        </div>
      </aside>

      <section className="workspace" id="workspace-main">
        <header className="topbar">
          <div><p className="crumb">OffsetX / Product workspace</p><h1>Good evening, Kunal.</h1></div>
          <PreviewActions />
        </header>

        <div className="previewNotice" role="note">
          <span className="pulseDot" aria-hidden="true" />
          <strong>Interactive product preview</strong>
          <span>Sample workspace data · No external source or AI provider is connected.</span>
        </div>

        <section className="overview" id="overview" aria-labelledby="overview-title">
          <div className="sectionHeading">
            <div><p className="eyebrow">Executive overview</p><h2 id="overview-title">What moved today</h2></div>
            <span className="timeStamp">Updated 6:08 PM</span>
          </div>

          <div className="metricGrid">
            <article className="metricCard featured">
              <div className="metricTop"><span>Delivery confidence</span><span className="trend">↑ 6%</span></div>
              <strong>78</strong><small>/100</small>
              <div className="metricBar"><span style={{ width: "78%" }} /></div>
              <p>Two review gates are waiting on external evidence.</p>
            </article>
            <article className="metricCard">
              <div className="metricTop"><span>Active tracks</span><span className="miniIcon violet">▣</span></div>
              <strong>3</strong><p>1 building · 1 in review · 1 planned</p>
            </article>
            <article className="metricCard">
              <div className="metricTop"><span>Open blockers</span><span className="miniIcon amber">!</span></div>
              <strong>2</strong><p>WorkOS staging and PostgreSQL CI</p>
            </article>
            <article className="metricCard">
              <div className="metricTop"><span>AI spend today</span><span className="miniIcon green">₹</span></div>
              <strong>₹0</strong><p>Governed execution is not enabled yet.</p>
            </article>
          </div>
        </section>

        <div className="contentGrid">
          <section className="panel" id="project-room" aria-labelledby="tracks-title">
            <div className="panelHeader">
              <div><p className="eyebrow">Project room</p><h2 id="tracks-title">Delivery tracks</h2></div>
              <button className="textButton">View board →</button>
            </div>
            <div className="trackList">
              {tracks.map((track) => (
                <article className="track" key={track.name}>
                  <div className="trackMain">
                    <span className="trackIcon" aria-hidden="true">{track.name.slice(0, 1)}</span>
                    <div><strong>{track.name}</strong><span>{track.meta}</span></div>
                  </div>
                  <div className="trackProgress" aria-label={`${track.progress}% complete`}><span style={{ width: `${track.progress}%` }} /></div>
                  <span className={`status ${track.status.toLowerCase().replace(" ", "-")}`}>{track.status}</span>
                </article>
              ))}
            </div>
          </section>

          <section className="panel" id="audit" aria-labelledby="activity-title">
            <div className="panelHeader">
              <div><p className="eyebrow">Evidence stream</p><h2 id="activity-title">Recent activity</h2></div>
              <button className="filterButton">All sources ⌄</button>
            </div>
            <div className="activityList">
              {activity.map((item) => (
                <article className="activityItem" key={item.title}>
                  <span className={`sourceIcon ${item.tone}`} aria-hidden="true">{item.source.slice(0, 1)}</span>
                  <div><strong>{item.title}</strong><span>{item.detail}</span><small>{item.source}</small></div>
                  <time>{item.time}</time>
                </article>
              ))}
            </div>
          </section>
        </div>

        <section className="foundationCard" id="ai-control" aria-labelledby="foundation-title">
          <div className="foundationCopy">
            <span className="foundationIcon" aria-hidden="true">✦</span>
            <div>
              <p className="eyebrow">Current live boundary</p>
              <h2 id="foundation-title">Secure foundation before AI</h2>
              <p>Authentication, tenant isolation, scoped roles and audit evidence are built first. Connectors and AI runs stay locked until their permission path is proven.</p>
            </div>
          </div>
          <div className="gateList" id="access">
            <span><b className="check">✓</b> Tenant model</span>
            <span><b className="check">✓</b> Role boundaries</span>
            <span><b className="waiting">···</b> External review</span>
          </div>
        </section>

        <footer id="sources">
          <span>Brain preview · Increment 1</span>
          <span>Slack · GitHub · Linear · AI connectors are roadmap items</span>
        </footer>
      </section>
    </main>
  );
}
