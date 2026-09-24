"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  NativeChannel,
  WorkspaceNavigationNode,
} from "./brain-api";
import type { DirectConversation } from "./direct-message-api";
import styles from "./workspace-search.module.css";

type WorkspaceSearchPayload = {
  query: string;
  items: Array<{
    id: string;
    title: string;
    excerpt: string;
    source: string;
    object_type: string;
    href: string;
    occurred_at: string | null;
  }>;
};

type LocalItem = {
  id: string;
  label: string;
  detail: string;
  kind: "channel" | "project" | "track" | "dm";
  href: string;
};

function normalize(value: string): string {
  return value.trim().toLocaleLowerCase();
}

export function WorkspaceSearch({
  organizationId,
  endpoint,
  channels,
  projects,
  tracks,
  directConversations,
}: {
  organizationId: string;
  endpoint: string | null;
  channels: NativeChannel[];
  projects: WorkspaceNavigationNode[];
  tracks: WorkspaceNavigationNode[];
  directConversations: DirectConversation[];
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [remote, setRemote] = useState<WorkspaceSearchPayload["items"]>([]);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");

  const localItems = useMemo<LocalItem[]>(() => [
    ...channels.map((channel) => ({
      id: `channel:${channel.id}`,
      label: `# ${channel.name}`,
      detail: channel.visibility === "restricted" ? "Restricted Brain channel" : "Brain channel",
      kind: "channel" as const,
      href: `?organizationId=${encodeURIComponent(organizationId)}&channelId=${encodeURIComponent(channel.id)}#native-chat`,
    })),
    ...projects.map((project) => ({
      id: `project:${project.node_id}`,
      label: project.display_name ?? "Untitled project",
      detail: "Project",
      kind: "project" as const,
      href: `#project-${encodeURIComponent(project.node_id)}`,
    })),
    ...tracks.map((track) => ({
      id: `track:${track.node_id}`,
      label: track.display_name ?? "Untitled track",
      detail: "Connected track",
      kind: "track" as const,
      href: `#track-${encodeURIComponent(track.node_id)}`,
    })),
    ...directConversations.map((conversation) => ({
      id: `dm:${conversation.id}`,
      label: conversation.other_display_name,
      detail: `Direct message · ${conversation.other_email}`,
      kind: "dm" as const,
      href: `?organizationId=${encodeURIComponent(organizationId)}&dmId=${encodeURIComponent(conversation.id)}#direct-messages`,
    })),
  ], [channels, directConversations, organizationId, projects, tracks]);

  const filteredLocal = useMemo(() => {
    const needle = normalize(query);
    if (!needle) return localItems.slice(0, 12);
    return localItems
      .filter((item) => normalize(`${item.label} ${item.detail}`).includes(needle))
      .slice(0, 8);
  }, [localItems, query]);

  const open = useCallback(() => {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) return;
    dialog.showModal();
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const close = useCallback(() => {
    dialogRef.current?.close();
    setQuery("");
    setRemote([]);
    setState("idle");
  }, []);

  useEffect(() => {
    function keydown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLocaleLowerCase() === "k") {
        event.preventDefault();
        open();
      }
    }
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [open]);

  useEffect(() => {
    const normalized = query.trim();
    if (!endpoint || normalized.length < 2) {
      setRemote([]);
      setState("idle");
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setState("loading");
      const url = new URL(endpoint, window.location.origin);
      url.searchParams.set("q", normalized);
      void fetch(url, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      })
        .then(async (response) => {
          if (!response.ok) throw new Error(`workspace_search_${response.status}`);
          return response.json() as Promise<WorkspaceSearchPayload>;
        })
        .then((payload) => {
          setRemote(payload.items);
          setState("idle");
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setRemote([]);
            setState("error");
          }
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [endpoint, query]);

  return (
    <>
      <button className={styles.trigger} onClick={open} type="button">
        <span aria-hidden="true">⌕</span>
        <span>Search Brain</span>
        <kbd>Ctrl/⌘ K</kbd>
      </button>

      <dialog
        aria-labelledby="workspace-search-title"
        className={styles.dialog}
        onCancel={(event) => {
          event.preventDefault();
          close();
        }}
        ref={dialogRef}
      >
        <header>
          <div>
            <p>Quick switcher</p>
            <h2 id="workspace-search-title">Find work in Brain</h2>
          </div>
          <button aria-label="Close search" onClick={close} type="button">×</button>
        </header>

        <label className={styles.searchField}>
          <span className={styles.srOnly}>Search visible Brain work</span>
          <span aria-hidden="true">⌕</span>
          <input
            autoComplete="off"
            maxLength={120}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Channels, projects, people, messages…"
            ref={inputRef}
            type="search"
            value={query}
          />
        </label>

        <div className={styles.results}>
          {filteredLocal.length ? (
            <section aria-labelledby="workspace-search-jump">
              <h3 id="workspace-search-jump">Jump to</h3>
              {filteredLocal.map((item) => (
                <a href={item.href} key={item.id} onClick={close}>
                  <strong>{item.label}</strong>
                  <span>{item.detail}</span>
                </a>
              ))}
            </section>
          ) : null}

          {query.trim().length >= 2 ? (
            <section aria-labelledby="workspace-search-content">
              <h3 id="workspace-search-content">Messages & evidence</h3>
              {state === "loading" ? <p role="status">Searching authorised work…</p> : null}
              {state === "error" ? (
                <p role="alert">Search could not be loaded safely. Try again.</p>
              ) : null}
              {state === "idle" && remote.length ? remote.map((item) => (
                <a href={item.href} key={item.id} onClick={close}>
                  <strong>{item.title}</strong>
                  <span>{item.excerpt || "No text preview available."}</span>
                  <small>{item.source} · {item.object_type}</small>
                </a>
              )) : null}
              {state === "idle" && !remote.length && !filteredLocal.length ? (
                <p role="status">No authorised results found.</p>
              ) : null}
            </section>
          ) : (
            <p className={styles.hint}>Type 2 or more characters to search authorised messages and evidence.</p>
          )}
        </div>
      </dialog>
    </>
  );
}
