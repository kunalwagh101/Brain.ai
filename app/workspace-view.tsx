"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { viewForWorkspaceHash, type WorkspaceView } from "./workspace-view-routes";

const WorkspaceViewContext = createContext<WorkspaceView>("home");

export function WorkspaceViewProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<WorkspaceView>("home");

  useEffect(() => {
    const sync = () => {
      setView(viewForWorkspaceHash(window.location.hash));
      document.querySelectorAll<HTMLDetailsElement>("details[data-brain-mobile-nav]").forEach((details) => { details.open = false; });
      // A deep link can target a section that was hidden when the browser first
      // attempted to scroll. Reveal the screen before retrying the scroll.
      window.requestAnimationFrame(() => {
        const id = window.location.hash.slice(1);
        let decoded = id;
        try { decoded = decodeURIComponent(id); } catch { /* Ignore malformed fragments. */ }
        if (decoded) document.getElementById(decoded)?.scrollIntoView({ block: "start" });
      });
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  return <WorkspaceViewContext.Provider value={view}>{children}</WorkspaceViewContext.Provider>;
}

export function WorkspaceScreen({ view, children }: { view: WorkspaceView; children: ReactNode }) {
  const active = useContext(WorkspaceViewContext) === view;
  return <div className="brain-workspace-screen" hidden={!active}>{children}</div>;
}

export function WorkspaceNavLink({ view, href, children, className, label, activeWhen = true }: {
  view: WorkspaceView;
  href: string;
  children: ReactNode;
  className?: string;
  label?: string;
  activeWhen?: boolean;
}) {
  const active = useContext(WorkspaceViewContext) === view && activeWhen;
  return <a href={href} className={className} aria-label={label} aria-current={active ? "page" : undefined}>{children}</a>;
}

export function WorkspaceHeading({ channel, direct }: { channel: string | null; direct: string | null }) {
  const view = useContext(WorkspaceViewContext);
  const labels: Record<WorkspaceView, string> = {
    home: "Home", activity: "Activity", channels: channel ? `# ${channel}` : "Channels",
    "direct-messages": direct ?? "Direct messages", saved: "Saved for later",
    tracks: "Connected tracks", projects: "Projects", agents: "Developer & agents",
    admin: "Admin & governance", memory: "Decisions & blockers", ask: "Ask Brain",
    files: "Files & evidence",
  };
  return <h1 id="home">{labels[view]}</h1>;
}
