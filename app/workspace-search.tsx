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
import { resultsForQuery } from "./workspace-search-state";
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
  const [remote, setRemote] = useState<{ query: string; items: WorkspaceSearchPayload["items"] } | null>(null);
  const [state, setState] = useState<{ query: string; status: "idle" | "loading" | "error" }>({ query: "", status: "idle" });
  const searchKey = `${endpoint ?? ""}::${query.trim()}`;
  const visibleRemote = resultsForQuery(remote, searchKey);
  const visibleState = state.query === searchKey ? state.status : "loading";

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
    setRemote(null);
    setState({ query: "", status: "idle" });
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
    if (!endpoint || normalized.length < 2) return;

    const controller = new AbortController();
    const requestKey = `${endpoint}::${normalized}`;
    const timer = window.setTimeout(() => {
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
          if (controller.signal.aborted) return;
          setRemote({ query: requestKey, items: payload.items });
          setState({ query: requestKey, status: "idle" });
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setRemote(null);
            setState({ query: requestKey, status: "error" });
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
            onChange={(event) => {
              setQuery(event.target.value);
              setRemote(null);
              const nextQuery = event.target.value.trim();
              setState({
                query: `${endpoint ?? ""}::${nextQuery}`,
                status: endpoint && nextQuery.length >= 2 ? "loading" : "idle",
              });
            }}
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

          {query.trim().length >= 2 && endpoint ? (
            <section aria-labelledby="workspace-search-content">
              <h3 id="workspace-search-content">Messages & evidence</h3>
              {visibleState === "loading" ? <p role="status">Searching authorised work…</p> : null}
              {visibleState === "error" ? (
                <p role="alert">Search could not be loaded safely. Try again.</p>
              ) : null}
              {visibleState === "idle" && visibleRemote?.length ? visibleRemote.map((item) => (
                <a href={item.href} key={item.id} onClick={close}>
                  <strong>{item.title}</strong>
                  <span>{item.excerpt || "No text preview available."}</span>
                  <small>{item.source} · {item.object_type}</small>
                </a>
              )) : null}
              {visibleState === "idle" && visibleRemote !== null && !visibleRemote.length && !filteredLocal.length ? (
                <p role="status">No authorised results found.</p>
              ) : null}
            </section>
          ) : (
            <p className={styles.hint}>
              {endpoint
                ? "Type 2 or more characters to search authorised messages and evidence."
                : "Jump to a visible place above. Message and evidence search needs a connected workspace."}
            </p>
          )}
        </div>
      </dialog>
    </>
  );
}
