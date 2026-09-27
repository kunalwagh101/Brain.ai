"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import styles from "./live-workspace-refresh.module.css";

const VISIBLE_INTERVAL_MS = 4_000;
const HIDDEN_INTERVAL_MS = 30_000;
const OFFLINE_INTERVAL_MS = 10_000;
const MAX_ERROR_BACKOFF_MS = 30_000;

type LiveState = {
  revision: string;
  unread_count: number;
};

export function LiveWorkspaceRefresh({
  endpoint,
  initialRevision,
}: {
  endpoint: string;
  initialRevision: string;
}) {
  const router = useRouter();
  const revision = useRef(initialRevision);
  const [status, setStatus] = useState<"live" | "reconnecting">("live");

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;
    let failures = 0;
    revision.current = initialRevision;

    const clearTimer = () => {
      if (timer) clearTimeout(timer);
      timer = null;
    };

    const baseInterval = () =>
      document.visibilityState === "visible" ? VISIBLE_INTERVAL_MS : HIDDEN_INTERVAL_MS;

    const schedule = (delay: number) => {
      clearTimer();
      if (!stopped) timer = setTimeout(() => void check(), delay);
    };

    async function check() {
      if (stopped) return;
      if (!navigator.onLine) {
        setStatus("reconnecting");
        schedule(OFFLINE_INTERVAL_MS);
        return;
      }

      controller?.abort();
      const requestController = new AbortController();
      controller = requestController;
      try {
        const response = await fetch(endpoint, {
          credentials: "same-origin",
          cache: "no-store",
          headers: { Accept: "application/json" },
          signal: requestController.signal,
        });
        if (!response.ok) throw new Error(`live_state_${response.status}`);
        const next = await response.json() as LiveState;
        if (!/^[a-f0-9]{64}$/.test(next.revision)) throw new Error("live_revision_invalid");

        failures = 0;
        setStatus("live");
        if (next.revision !== revision.current) {
          revision.current = next.revision;
          router.refresh();
        }
        schedule(baseInterval());
      } catch (error) {
        if (requestController.signal.aborted || stopped) return;
        failures += 1;
        setStatus("reconnecting");
        const delay = Math.min(
          VISIBLE_INTERVAL_MS * 2 ** Math.min(failures, 3),
          MAX_ERROR_BACKOFF_MS,
        );
        schedule(Math.max(delay, baseInterval()));
      }
    }

    const wake = () => {
      if (document.visibilityState === "visible" && navigator.onLine) {
        failures = 0;
        schedule(250);
      }
    };

    document.addEventListener("visibilitychange", wake);
    window.addEventListener("online", wake);
    window.addEventListener("offline", wake);
    schedule(VISIBLE_INTERVAL_MS);

    return () => {
      stopped = true;
      clearTimer();
      controller?.abort();
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("online", wake);
      window.removeEventListener("offline", wake);
    };
  }, [endpoint, initialRevision, router]);

  return (
    <div className={styles.status} data-state={status} aria-live="polite" aria-atomic="true">
      <span aria-hidden="true" />
      {status === "live" ? "Live" : "Reconnecting"}
    </div>
  );
}
