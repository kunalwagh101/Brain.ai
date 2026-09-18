"use client";

import { useEffect, useRef, useState } from "react";

const PRESENCE_POLL_INTERVAL_MS = 3_000;
const TYPING_REFRESH_INTERVAL_MS = 3_000;

export type CollaborationPresenceUser = {
  user_id: string;
  display_name: string;
};

export type CollaborationPresenceState = {
  online_users: CollaborationPresenceUser[];
  typing_users: CollaborationPresenceUser[];
};

const EMPTY_STATE: CollaborationPresenceState = {
  online_users: [],
  typing_users: [],
};

export function useCollaborationPresence(
  endpoint: string | null,
  typingActive: boolean,
): CollaborationPresenceState {
  const [state, setState] = useState<CollaborationPresenceState>(EMPTY_STATE);
  const typingLeaseActive = useRef(false);

  useEffect(() => {
    if (!endpoint) {
      setState(EMPTY_STATE);
      return;
    }

    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    const clearTimer = () => {
      if (timer) clearTimeout(timer);
      timer = null;
    };

    const schedule = (delay = PRESENCE_POLL_INTERVAL_MS) => {
      clearTimer();
      if (!stopped) timer = setTimeout(() => void poll(), delay);
    };

    async function poll() {
      if (stopped) return;
      if (document.visibilityState !== "visible" || !navigator.onLine) {
        schedule();
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
        if (response.status === 403 || response.status === 404) {
          setState(EMPTY_STATE);
          schedule(5_000);
          return;
        }
        if (!response.ok) {
          schedule(5_000);
          return;
        }
        const next = await response.json() as CollaborationPresenceState;
        if (!Array.isArray(next.online_users) || !Array.isArray(next.typing_users)) {
          schedule(5_000);
          return;
        }
        setState(next);
        schedule();
      } catch {
        if (requestController.signal.aborted || stopped) return;
        schedule(5_000);
      }
    }

    const wake = () => {
      if (document.visibilityState === "visible" && navigator.onLine) {
        schedule(100);
      }
    };

    document.addEventListener("visibilitychange", wake);
    window.addEventListener("online", wake);
    schedule(50);

    return () => {
      stopped = true;
      clearTimer();
      controller?.abort();
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("online", wake);
    };
  }, [endpoint]);

  useEffect(() => {
    if (!endpoint) return;

    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    const clearTimer = () => {
      if (timer) clearTimeout(timer);
      timer = null;
    };

    const clearTyping = () => {
      clearTimer();
      if (!typingLeaseActive.current) return;
      typingLeaseActive.current = false;
      void fetch(`${endpoint}/typing`, {
        method: "DELETE",
        credentials: "same-origin",
        cache: "no-store",
        keepalive: true,
      }).catch(() => undefined);
    };

    const scheduleRefresh = () => {
      clearTimer();
      if (!stopped && typingActive) {
        timer = setTimeout(() => void refreshTyping(), TYPING_REFRESH_INTERVAL_MS);
      }
    };

    async function refreshTyping() {
      if (
        stopped
        || !typingActive
        || document.visibilityState !== "visible"
        || !navigator.onLine
      ) {
        clearTyping();
        return;
      }
      controller?.abort();
      const requestController = new AbortController();
      controller = requestController;
      try {
        const response = await fetch(`${endpoint}/typing`, {
          method: "PUT",
          credentials: "same-origin",
          cache: "no-store",
          signal: requestController.signal,
        });
        typingLeaseActive.current = response.ok;
      } catch {
        if (requestController.signal.aborted || stopped) return;
        typingLeaseActive.current = false;
      } finally {
        scheduleRefresh();
      }
    }

    const visibilityChanged = () => {
      if (document.visibilityState !== "visible" || !navigator.onLine) {
        clearTyping();
      } else if (typingActive) {
        void refreshTyping();
      }
    };

    const pageHide = () => clearTyping();
    document.addEventListener("visibilitychange", visibilityChanged);
    window.addEventListener("online", visibilityChanged);
    window.addEventListener("offline", visibilityChanged);
    window.addEventListener("pagehide", pageHide);

    if (typingActive && document.visibilityState === "visible" && navigator.onLine) {
      void refreshTyping();
    } else {
      clearTyping();
    }

    return () => {
      stopped = true;
      clearTimer();
      controller?.abort();
      clearTyping();
      document.removeEventListener("visibilitychange", visibilityChanged);
      window.removeEventListener("online", visibilityChanged);
      window.removeEventListener("offline", visibilityChanged);
      window.removeEventListener("pagehide", pageHide);
    };
  }, [endpoint, typingActive]);

  return state;
}
