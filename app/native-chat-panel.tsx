"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { NativeChannel, NativeMessage } from "./brain-api";
import styles from "./native-chat-panel.module.css";

function formatTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown time";
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function initials(value: string): string {
  return value
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "?";
}

function safeError(status: number): string {
  if (status === 400 || status === 422) return "The message was not accepted. Check the content and try again.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403) return "Your current role cannot send messages.";
  if (status === 404) return "This channel is no longer available to your account.";
  if (status === 409) return "The message conflicts with the current channel state.";
  if (status === 429) return "Messages are temporarily rate limited.";
  return "The message could not be sent safely.";
}

export function NativeChatPanel({
  channel,
  messages,
  mutationEndpoint,
}: {
  channel: NativeChannel;
  messages: NativeMessage[];
  mutationEndpoint: string | null;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [status, setStatus] = useState<
    | { kind: "idle" }
    | { kind: "working"; text: string }
    | { kind: "error"; text: string }
  >({ kind: "idle" });

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = body.trim();
    if (!mutationEndpoint || !channel.can_post || !normalized) return;
    if (normalized.length > 20_000) {
      setStatus({ kind: "error", text: "Messages are limited to 20,000 characters." });
      return;
    }

    setStatus({ kind: "working", text: "Sending…" });
    try {
      const response = await fetch(mutationEndpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ body: normalized }),
      });
      if (!response.ok) {
        setStatus({ kind: "error", text: safeError(response.status) });
        return;
      }
      setBody("");
      setStatus({ kind: "idle" });
      router.refresh();
    } catch {
      setStatus({ kind: "error", text: "The message could not reach the secure Brain route." });
    }
  }

  return (
    <section className={styles.chat} aria-labelledby="native-channel-heading">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Brain channel</p>
          <h2 id="native-channel-heading"># {channel.name}</h2>
          <p>{channel.description ?? "No channel description."}</p>
        </div>
        <div className={styles.channelMeta}>
          <span>{channel.visibility}</span>
          {channel.visibility === "restricted" ? <span>{channel.member_count} member(s)</span> : null}
          <span>{channel.status}</span>
        </div>
      </header>

      <div className={styles.feed} role="log" aria-live="polite" aria-label={`${channel.name} messages`}>
        {messages.length ? messages.map((message) => (
          <article className={styles.message} key={message.id}>
            <span className={styles.avatar} data-agent={message.actor_kind === "agent" || undefined}>
              {message.actor_kind === "agent" ? "AI" : initials(message.actor_display_name)}
            </span>
            <div>
              <div className={styles.messageMeta}>
                <strong>{message.actor_display_name}</strong>
                {message.actor_kind === "agent" ? <span className={styles.agentBadge}>Agent</span> : null}
                <time dateTime={message.created_at}>{formatTime(message.created_at)}</time>
                {message.projection_status !== "ready" ? (
                  <span className={styles.projection} data-status={message.projection_status}>
                    {message.projection_status}
                  </span>
                ) : null}
              </div>
              <p className={styles.body}>{message.body}</p>
              <details className={styles.provenance}>
                <summary>Evidence provenance</summary>
                <dl>
                  <div><dt>Message</dt><dd><code>{message.id}</code></dd></div>
                  <div><dt>SHA-256</dt><dd><code>{message.body_sha256}</code></dd></div>
                  {message.canonical_event_id ? (
                    <div><dt>Canonical event</dt><dd><code>{message.canonical_event_id}</code></dd></div>
                  ) : null}
                  {message.agent_run_id ? (
                    <div><dt>Agent run</dt><dd><code>{message.agent_run_id}</code></dd></div>
                  ) : null}
                </dl>
              </details>
            </div>
          </article>
        )) : (
          <div className={styles.empty}>
            <strong>No messages yet.</strong>
            <span>Start the channel when the authenticated mutation route is available.</span>
          </div>
        )}
      </div>

      {channel.can_post ? (
        mutationEndpoint ? (
          <form className={styles.composer} onSubmit={submit}>
            <label htmlFor="native-message-body">Message #{channel.name}</label>
            <textarea
              id="native-message-body"
              value={body}
              onChange={(event) => setBody(event.target.value)}
              maxLength={20_000}
              placeholder={`Message #${channel.name}`}
              rows={3}
              required
            />
            <div>
              <span>{body.length.toLocaleString()} / 20,000</span>
              <button disabled={status.kind === "working" || !body.trim()} type="submit">
                {status.kind === "working" ? "Sending…" : "Send"}
              </button>
            </div>
          </form>
        ) : (
          <div className={styles.notice} role="status">
            This channel is readable, but sending stays disabled until the authenticated WorkOS same-origin BFF is activated.
          </div>
        )
      ) : (
        <div className={styles.notice} role="status">
          You can read this channel, but your current role or channel membership does not allow posting.
        </div>
      )}

      {status.kind === "error" ? (
        <div className={styles.error} role="alert">{status.text}</div>
      ) : null}
    </section>
  );
}
