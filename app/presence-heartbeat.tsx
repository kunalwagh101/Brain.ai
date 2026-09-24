"use client";

import { useEffect } from "react";

const HEARTBEAT_INTERVAL_MS = 30_000;

export function PresenceHeartbeat({ endpoint }: { endpoint: string }) {
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    const clearTimer = () => {
      if (timer) clearTimeout(timer);
      timer = null;
    };

    const schedule = () => {
      clearTimer();
      if (!stopped && document.visibilityState === "visible" && navigator.onLine) {
        timer = setTimeout(() => void heartbeat(), HEARTBEAT_INTERVAL_MS);
      }
    };

    async function heartbeat() {
      if (
        stopped
        || document.visibilityState !== "visible"
        || !navigator.onLine
      ) {
        return;
      }
      controller?.abort();
      const requestController = new AbortController();
      controller = requestController;
      try {
        await fetch(endpoint, {
          method: "POST",
          credentials: "same-origin",
          cache: "no-store",
          signal: requestController.signal,
        });
      } catch {
        if (requestController.signal.aborted || stopped) return;
      } finally {
        schedule();
      }
    }

    const wake = () => {
      clearTimer();
      if (document.visibilityState === "visible" && navigator.onLine) {
        void heartbeat();
      }
    };

    document.addEventListener("visibilitychange", wake);
    window.addEventListener("online", wake);
    window.addEventListener("offline", wake);
    if (document.visibilityState === "visible" && navigator.onLine) {
      void heartbeat();
    }

    return () => {
      stopped = true;
      clearTimer();
      controller?.abort();
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("online", wake);
      window.removeEventListener("offline", wake);
    };
  }, [endpoint]);

  return null;
}
