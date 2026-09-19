"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { DirectConversation, DirectMessage } from "./direct-message-api";
import styles from "./direct-message-panel.module.css";
import { useCollaborationPresence } from "./use-collaboration-presence";

function timeLabel(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function safeError(status: number): string {
  if (status === 401) return "Your session has expired. Sign in again.";
  if (status === 403) return "Direct messaging is not available for this account.";
  if (status === 404) return "That member or conversation is not available.";
  if (status === 409) return "That direct conversation cannot accept this message right now.";
  if (status === 413) return "The request is too large.";
  return "The direct-message action could not be completed.";
}

export function DirectMessagePanel({
  organizationId,
  conversations,
  selectedConversation,
  messages,
  createEndpoint,
  messageEndpoint,
  conversationEndpoint,
  presenceEndpoint,
}: {
  organizationId: string;
  conversations: DirectConversation[];
  selectedConversation: DirectConversation | null;
  messages: DirectMessage[];
  createEndpoint: string | null;
  messageEndpoint: string | null;
  conversationEndpoint: string | null;
  presenceEndpoint: string | null;
}) {
  const router = useRouter();
  const [targetEmail, setTargetEmail] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [composerFocused, setComposerFocused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleMessages, setVisibleMessages] = useState(messages);
  const [historyBeforeSequence, setHistoryBeforeSequence] = useState(
    messages[0]?.sequence ?? null,
  );
  const [hasOlderHistory, setHasOlderHistory] = useState(messages.length >= 200);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [firstUnreadMessageId, setFirstUnreadMessageId] = useState(
    selectedConversation?.first_unread_message_id ?? null,
  );

  useEffect(() => {
    setVisibleMessages((current) => {
      const merged = new Map(current.map((message) => [message.id, message]));
      for (const message of messages) merged.set(message.id, message);
      return [...merged.values()].sort((left, right) => left.sequence - right.sequence);
    });
  }, [messages]);

  useEffect(() => {
    if (
      !selectedConversation
      || !conversationEndpoint
      || !selectedConversation.latest_message_id
      || !selectedConversation.unread_count
    ) return;
    const controller = new AbortController();
    void fetch(`${conversationEndpoint}/read`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        through_message_id: selectedConversation.latest_message_id,
      }),
      signal: controller.signal,
    }).then((response) => {
      if (response.ok) router.refresh();
    }).catch(() => undefined);
    return () => controller.abort();
  }, [
    conversationEndpoint,
    router,
    selectedConversation?.id,
    selectedConversation?.latest_message_id,
    selectedConversation?.unread_count,
  ]);

  const presence = useCollaborationPresence(
    presenceEndpoint,
    Boolean(
      selectedConversation?.can_send
      && composerFocused
      && body.trim()
    ),
  );
  const otherOnline = presence.online_users.length > 0;
  const typingName = presence.typing_users[0]?.display_name ?? null;

  async function createConversation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!createEndpoint || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(createEndpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_email: targetEmail.trim().toLowerCase() }),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      const created = (await response.json()) as DirectConversation;
      window.location.assign(
        `?organizationId=${encodeURIComponent(organizationId)}&dmId=${encodeURIComponent(created.id)}#direct-messages`,
      );
    } catch {
      setError("The direct-message action could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!messageEndpoint || busy) return;
    const trimmed = body.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(messageEndpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ body: trimmed }),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      setBody("");
      window.location.reload();
    } catch {
      setError("The direct-message action could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  async function loadOlderHistory() {
    if (
      !conversationEndpoint
      || !hasOlderHistory
      || historyLoading
      || historyBeforeSequence === null
    ) return;
    setHistoryLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: "50",
        before_sequence: String(historyBeforeSequence),
      });
      const response = await fetch(
        `${conversationEndpoint}/messages?${params.toString()}`,
        { credentials: "same-origin", cache: "no-store" },
      );
      if (response.status === 403 || response.status === 404) {
        router.refresh();
        return;
      }
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      const page = await response.json() as DirectMessage[];
      if (!page.length) {
        setHasOlderHistory(false);
        return;
      }
      setVisibleMessages((current) => {
        const merged = new Map(current.map((message) => [message.id, message]));
        for (const message of page) merged.set(message.id, message);
        return [...merged.values()].sort((left, right) => left.sequence - right.sequence);
      });
      setHistoryBeforeSequence(page[0].sequence);
      setHasOlderHistory(page.length === 50);
    } catch {
      setError("Older direct-message history could not be loaded safely.");
    } finally {
      setHistoryLoading(false);
    }
  }

  function focusUnread(messageId: string) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const divider = document.getElementById(`dm-first-unread-${messageId}`);
        divider?.scrollIntoView({ block: "center" });
        divider?.focus({ preventScroll: true });
      });
    });
  }

  async function jumpToUnread() {
    if (!firstUnreadMessageId || !conversationEndpoint) return;
    const existing = document.getElementById(`dm-first-unread-${firstUnreadMessageId}`);
    if (existing) {
      existing.scrollIntoView({ block: "center" });
      existing.focus({ preventScroll: true });
      return;
    }
    try {
      const response = await fetch(
        `${conversationEndpoint}/messages/${encodeURIComponent(firstUnreadMessageId)}`,
        { credentials: "same-origin", cache: "no-store" },
      );
      if (response.status === 403 || response.status === 404) {
        setFirstUnreadMessageId(null);
        router.refresh();
        return;
      }
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      const target = await response.json() as DirectMessage;
      setVisibleMessages((current) => {
        const merged = current.some((message) => message.id === target.id)
          ? current
          : [...current, target];
        return [...merged].sort((left, right) => left.sequence - right.sequence);
      });
      focusUnread(target.id);
    } catch {
      setError("The first unread direct message could not be loaded safely.");
    }
  }

  return (
    <div className={styles.dmWorkspace}>
      <aside className={styles.conversations} aria-label="Direct conversations">
        <header>
          <div>
            <p className={styles.eyebrow}>Private collaboration</p>
            <h2>Direct messages</h2>
          </div>
          <span>{conversations.length}</span>
        </header>

        {createEndpoint ? (
          <form className={styles.newDm} onSubmit={createConversation}>
            <label htmlFor="dm-target-email">New DM</label>
            <div>
              <input
                id="dm-target-email"
                type="email"
                autoComplete="off"
                placeholder="member@company.com"
                value={targetEmail}
                maxLength={320}
                onChange={(event) => setTargetEmail(event.target.value)}
                required
              />
              <button type="submit" disabled={busy || !targetEmail.trim()}>
                Start
              </button>
            </div>
          </form>
        ) : (
          <p className={styles.readOnly}>Authenticated DM mutations are not active yet.</p>
        )}

        <nav className={styles.dmList}>
          {conversations.length ? conversations.map((conversation) => (
            <a
              key={conversation.id}
              href={`?organizationId=${encodeURIComponent(organizationId)}&dmId=${encodeURIComponent(conversation.id)}#direct-messages`}
              aria-current={selectedConversation?.id === conversation.id ? "page" : undefined}
            >
              <span className={styles.avatar}>{conversation.other_display_name.slice(0, 1).toUpperCase()}</span>
              <span>
                <strong>{conversation.other_display_name}</strong>
                <small>
                  {conversation.can_send ? conversation.other_email : `${conversation.other_email} · unavailable`}
                </small>
              </span>
            </a>
          )) : <p className={styles.empty}>No direct conversations yet.</p>}
        </nav>
      </aside>

      <section className={styles.messagePane} aria-label="Selected direct conversation">
        <div className={styles.privacyNotice} role="note">
          <strong>Participant-only.</strong>
          <span>DM content is not included in organisation-wide Search, Ask Brain, memory or executive views.</span>
        </div>

        {selectedConversation ? (
          <>
            <header className={styles.threadHeader}>
              <div>
                <span className={styles.avatar}>{selectedConversation.other_display_name.slice(0, 1).toUpperCase()}</span>
                <div>
                  <h3>{selectedConversation.other_display_name}</h3>
                  <small>{selectedConversation.other_email}</small>
                </div>
              </div>
              {selectedConversation.can_send && presenceEndpoint && presence.loaded ? (
                <span className={styles.presenceLabel} data-online={otherOnline || undefined}>
                  <i aria-hidden="true" />
                  {otherOnline ? "Online" : "Offline"} · 1:1 DM
                </span>
              ) : (
                <span>{selectedConversation.can_send ? "1:1 DM" : "History only"}</span>
              )}
            </header>

            <div className={styles.messages} aria-live="polite">
              {hasOlderHistory ? (
                <button
                  className={styles.loadOlder}
                  disabled={historyLoading}
                  onClick={() => void loadOlderHistory()}
                  type="button"
                >
                  {historyLoading ? "Loading older…" : "Load older messages"}
                </button>
              ) : null}
              {visibleMessages.length ? visibleMessages.map((message) => (
                <div className={styles.messageGroup} key={message.id}>
                  {message.id === firstUnreadMessageId ? (
                    <div
                      aria-label="New direct messages begin here"
                      className={styles.firstUnreadDivider}
                      id={`dm-first-unread-${message.id}`}
                      role="separator"
                      tabIndex={-1}
                    >
                      <span>New messages</span>
                    </div>
                  ) : null}
                  <article
                    className={message.is_mine ? styles.mine : styles.theirs}
                    id={`dm-message-${message.id}`}
                  >
                    <div>
                      <strong>{message.is_mine ? "You" : message.author_display_name}</strong>
                      <small>{timeLabel(message.created_at)}</small>
                    </div>
                    <p>{message.body}</p>
                  </article>
                </div>
              )) : <p className={styles.empty}>No messages are visible in this direct conversation.</p>}
            </div>

            {typingName ? (
              <p className={styles.typingStatus} aria-live="polite" role="status">
                {typingName} is typing…
              </p>
            ) : null}

            {!selectedConversation.can_send ? (
              <p className={styles.readOnly} role="status">
                This member is not currently available for direct messages. Your visible history remains read-only.
              </p>
            ) : messageEndpoint ? (
              <form className={styles.composer} onSubmit={sendMessage}>
                <label htmlFor="dm-message-body">Message {selectedConversation.other_display_name}</label>
                <textarea
                  id="dm-message-body"
                  value={body}
                  maxLength={20_000}
                  rows={3}
                  placeholder={`Message ${selectedConversation.other_display_name}`}
                  onChange={(event) => setBody(event.target.value)}
                  onFocus={() => setComposerFocused(true)}
                  onBlur={() => setComposerFocused(false)}
                />
                <div>
                  <small>{body.length.toLocaleString()} / 20,000</small>
                  <button type="submit" disabled={busy || !body.trim()}>
                    {busy ? "Sending…" : "Send"}
                  </button>
                </div>
              </form>
            ) : (
              <p className={styles.readOnly}>Secure authenticated message sending is not active yet.</p>
            )}
          </>
        ) : (
          <div className={styles.blankState}>
            <strong>Select a direct conversation</strong>
            <span>Only the two participants can open its messages.</span>
          </div>
        )}

        {error ? <p className={styles.error} role="alert">{error}</p> : null}
      </section>
    </div>
  );
}
