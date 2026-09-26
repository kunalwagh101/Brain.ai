"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { viewForWorkspaceHash, type WorkspaceView } from "./workspace-view-routes";

const WorkspaceViewContext = createContext<WorkspaceView>("home");

export function WorkspaceViewProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<WorkspaceView>("home");
  const previousHash = useRef<string | null>(null);

  useEffect(() => {
    const sync = () => {
      const hash = window.location.hash;
      const changed = previousHash.current !== null && previousHash.current !== hash;
      previousHash.current = hash;
      setView(viewForWorkspaceHash(hash));
      document.querySelectorAll<HTMLDetailsElement>("details[data-brain-mobile-nav]").forEach((details) => { details.open = false; });
      // A deep link can target a section that was hidden when the browser first
      // attempted to scroll. Reveal the screen before retrying the scroll.
      window.requestAnimationFrame(() => {
        const id = hash.slice(1);
        let decoded = id;
        try { decoded = decodeURIComponent(id); } catch { /* Ignore malformed fragments. */ }
        if (decoded) document.getElementById(decoded)?.scrollIntoView({ block: "start" });
        if (changed) document.querySelector<HTMLElement>("#brain-workspace-main h1")?.focus({ preventScroll: true });
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
  return <h1 id="home" tabIndex={-1}>{labels[view]}</h1>;
}
