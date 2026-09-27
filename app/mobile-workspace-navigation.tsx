"use client";

import type { ReactNode } from "react";

/** Native disclosure keeps its keyboard semantics even before hydration. */
export function MobileWorkspaceNavigation({ className, children }: { className: string; children: ReactNode }) {
  return (
    <details className={className} data-brain-mobile-nav onClick={(event) => {
      if (!(event.target instanceof Element) || !event.target.closest("a")) return;
      event.currentTarget.open = false;
      window.requestAnimationFrame(() => {
        document.querySelector<HTMLElement>("#brain-workspace-main h1")?.focus({ preventScroll: true });
      });
    }}>
      {children}
    </details>
  );
}
