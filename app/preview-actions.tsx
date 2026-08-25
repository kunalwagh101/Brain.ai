"use client";

import { useMemo, useState } from "react";

type Panel = "search" | "invite" | "brief" | null;

const searchableItems = [
  { title: "Authentication middleware merged", group: "GitHub evidence" },
  { title: "Tenant isolation", group: "Secure shell" },
  { title: "Connector framework", group: "Delivery track" },
  { title: "Evidence graph", group: "Delivery track" },
  { title: "WorkOS staging", group: "Open blocker" },
  { title: "PostgreSQL CI", group: "Open blocker" },
];

export function PreviewActions() {
  const [panel, setPanel] = useState<Panel>(null);
  const [query, setQuery] = useState("");

  const searchResults = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return searchableItems.slice(0, 3);
    return searchableItems.filter((item) => `${item.title} ${item.group}`.toLowerCase().includes(normalized));
  }, [query]);

  const openPanel = (nextPanel: Exclude<Panel, null>) => {
    setPanel((current) => (current === nextPanel ? null : nextPanel));
    if (nextPanel !== "search") setQuery("");
  };

  return (
    <div className="topActionsWrap">
      <div className="topActions">
        <button
          className="iconButton"
          aria-label="Search sample workspace"
          aria-expanded={panel === "search"}
          onClick={() => openPanel("search")}
        >
          ⌕
        </button>
        <button
          className="secondaryButton"
          aria-expanded={panel === "invite"}
          onClick={() => openPanel("invite")}
        >
          Invite people
        </button>
        <button
          className="primaryButton"
          aria-expanded={panel === "brief"}
          onClick={() => openPanel("brief")}
        >
          Run daily brief
        </button>
      </div>

      {panel ? (
        <section className="actionPopover" aria-live="polite" aria-label="Preview action result">
          <button className="popoverClose" aria-label="Close preview panel" onClick={() => setPanel(null)}>×</button>

          {panel === "search" ? (
            <>
              <p className="eyebrow">Workspace search</p>
              <label htmlFor="workspace-search">Search the sample evidence</label>
              <input
                id="workspace-search"
                autoFocus
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Try ‘tenant’ or ‘blocker’"
              />
              <div className="searchResults">
                {searchResults.length ? searchResults.map((item) => (
                  <button key={item.title} onClick={() => setPanel(null)}>
                    <strong>{item.title}</strong><span>{item.group}</span>
                  </button>
                )) : <p>No sample evidence matches that search.</p>}
              </div>
            </>
          ) : null}

          {panel === "invite" ? (
            <>
              <p className="eyebrow">Permission boundary</p>
              <h2>Invitations are safely disabled</h2>
              <p>This preview will not send an email or add a member. Production invitations unlock after WorkOS and role assignment are connected.</p>
              <span className="safeBadge">No action was sent</span>
            </>
          ) : null}

          {panel === "brief" ? (
            <>
              <p className="eyebrow">Sample daily brief</p>
              <h2>Three signals need attention</h2>
              <ul className="briefList">
                <li><b>Decision:</b> approve the tenant-isolation review gate.</li>
                <li><b>Blocker:</b> provide WorkOS staging credentials.</li>
                <li><b>Momentum:</b> authentication middleware passed 12 checks.</li>
              </ul>
              <p className="sampleFootnote">Prepared from the sample cards on this page; no AI request was made.</p>
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
