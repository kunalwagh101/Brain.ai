"use client";

import { FormEvent, useState } from "react";
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
  presenceEndpoint,
}: {
  organizationId: string;
  conversations: DirectConversation[];
  selectedConversation: DirectConversation | null;
  messages: DirectMessage[];
  createEndpoint: string | null;
  messageEndpoint: string | null;
  presenceEndpoint: string | null;
}) {
  const [targetEmail, setTargetEmail] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [composerFocused, setComposerFocused] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
              {selectedConversation.can_send && presenceEndpoint ? (
                <span className={styles.presenceLabel} data-online={otherOnline || undefined}>
                  <i aria-hidden="true" />
                  {otherOnline ? "Online" : "Offline"} · 1:1 DM
                </span>
              ) : (
                <span>{selectedConversation.can_send ? "1:1 DM" : "History only"}</span>
              )}
            </header>

            <div className={styles.messages} aria-live="polite">
              {messages.length ? messages.map((message) => (
                <article
                  key={message.id}
                  className={message.is_mine ? styles.mine : styles.theirs}
                >
                  <div>
                    <strong>{message.is_mine ? "You" : message.author_display_name}</strong>
                    <small>{timeLabel(message.created_at)}</small>
                  </div>
                  <p>{message.body}</p>
                </article>
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
