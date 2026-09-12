"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type {
  NativeChannel,
  NativeChannelMember,
  NativeMessage,
} from "./brain-api";
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

function safeMessageError(status: number): string {
  if (status === 400 || status === 422) return "The message was not accepted. Check the content and try again.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403) return "Your current role cannot send messages.";
  if (status === 404) return "This channel is no longer available to your account.";
  if (status === 409) return "The message conflicts with the current channel state.";
  if (status === 429) return "Messages are temporarily rate limited.";
  return "The message could not be sent safely.";
}

function safeMemberError(status: number): string {
  if (status === 400 || status === 422) return "The member request was not accepted.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403) return "You cannot manage this channel's members.";
  if (status === 404) return "The channel or exact organisation member was not found.";
  if (status === 409) return "That membership change conflicts with the channel state.";
  return "The membership change could not be completed safely.";
}

export function NativeChatPanel({
  channel,
  messages,
  members,
  mutationEndpoint,
  memberEndpoint,
}: {
  channel: NativeChannel;
  messages: NativeMessage[];
  members: NativeChannelMember[];
  mutationEndpoint: string | null;
  memberEndpoint: string | null;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [status, setStatus] = useState<
    | { kind: "idle" }
    | { kind: "working"; text: string }
    | { kind: "error"; text: string }
  >({ kind: "idle" });
  const [memberError, setMemberError] = useState<string | null>(null);
  const [memberWorking, setMemberWorking] = useState(false);

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
        setStatus({ kind: "error", text: safeMessageError(response.status) });
        return;
      }
      setBody("");
      setStatus({ kind: "idle" });
      router.refresh();
    } catch {
      setStatus({ kind: "error", text: "The message could not reach the secure Brain route." });
    }
  }

  async function inviteMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!memberEndpoint) return;
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim().toLowerCase();
    const access = String(form.get("access") ?? "read");
    if (!email) {
      setMemberError("Enter the exact email of an existing organisation member.");
      return;
    }
    setMemberWorking(true);
    setMemberError(null);
    try {
      const response = await fetch(memberEndpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, access }),
      });
      if (!response.ok) {
        setMemberError(safeMemberError(response.status));
        return;
      }
      event.currentTarget.reset();
      router.refresh();
    } catch {
      setMemberError("The membership change could not reach the secure Brain route.");
    } finally {
      setMemberWorking(false);
    }
  }

  async function revokeMember(userId: string) {
    if (!memberEndpoint || userId === channel.created_by_user_id) return;
    setMemberWorking(true);
    setMemberError(null);
    try {
      const response = await fetch(`${memberEndpoint}/${encodeURIComponent(userId)}`, {
        method: "DELETE",
        credentials: "same-origin",
      });
      if (!response.ok) {
        setMemberError(safeMemberError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setMemberError("The membership change could not reach the secure Brain route.");
    } finally {
      setMemberWorking(false);
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

      {channel.can_manage_members ? (
        <details className={styles.memberManager}>
          <summary>Manage restricted-channel members</summary>
          {memberEndpoint ? (
            <form onSubmit={inviteMember}>
              <label>
                <span>Exact member email</span>
                <input name="email" type="email" maxLength={320} required />
              </label>
              <label>
                <span>Access</span>
                <select name="access" defaultValue="read">
                  <option value="read">Read</option>
                  <option value="write">Read & write</option>
                </select>
              </label>
              <button disabled={memberWorking} type="submit">
                {memberWorking ? "Working…" : "Invite member"}
              </button>
            </form>
          ) : (
            <p>Member mutations stay disabled until the authenticated WorkOS BFF is active.</p>
          )}
          <div className={styles.memberList}>
            {members.map((member) => (
              <div key={member.user_id}>
                <span>
                  <strong>{member.display_name ?? member.email}</strong>
                  <small>{member.email} · {member.role} · {member.access}</small>
                </span>
                {member.user_id === channel.created_by_user_id ? (
                  <small>Creator</small>
                ) : memberEndpoint ? (
                  <button
                    disabled={memberWorking}
                    type="button"
                    onClick={() => revokeMember(member.user_id)}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            ))}
          </div>
          {memberError ? <p className={styles.error} role="alert">{memberError}</p> : null}
        </details>
      ) : null}

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
