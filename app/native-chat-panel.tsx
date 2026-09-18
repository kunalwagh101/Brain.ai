"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type {
  NativeChannel,
  NativeChannelMember,
  NativeMessage,
} from "./brain-api";
import styles from "./native-chat-panel.module.css";

const ALLOWED_REACTIONS = ["👍", "❤️", "🎉", "👀", "✅"] as const;
const EXACT_EMAIL_MENTION =
  /(^|[^A-Za-z0-9._%+\-])@([A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63})/gi;

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
  if (status === 400 || status === 422) return "The request was not accepted. Check it and try again.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403) return "Your current role cannot change this channel.";
  if (status === 404) return "This channel or message is no longer available to your account.";
  if (status === 409) return "The request conflicts with the current channel state.";
  if (status === 429) return "Channel actions are temporarily rate limited.";
  return "The channel request could not be completed safely.";
}

function safeMemberError(status: number): string {
  if (status === 400 || status === 422) return "The member request was not accepted.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403) return "You cannot manage this channel's members.";
  if (status === 404) return "The channel or exact organisation member was not found.";
  if (status === 409) return "That membership change conflicts with the channel state.";
  return "The membership change could not be completed safely.";
}

function messageBody(message: NativeMessage): ReactNode[] | string {
  const resolvedEmails = new Set(message.mentions.map((item) => item.email.toLowerCase()));
  if (!resolvedEmails.size) return message.body;

  const result: ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;
  EXACT_EMAIL_MENTION.lastIndex = 0;
  while ((match = EXACT_EMAIL_MENTION.exec(message.body)) !== null) {
    const prefix = match[1] ?? "";
    const email = match[2] ?? "";
    const mentionStart = match.index + prefix.length;
    if (!resolvedEmails.has(email.toLowerCase())) continue;
    result.push(message.body.slice(cursor, mentionStart));
    result.push(
      <mark className={styles.mention} key={`${mentionStart}-${email}`}>
        @{email}
      </mark>,
    );
    cursor = mentionStart + email.length + 1;
  }
  result.push(message.body.slice(cursor));
  return result;
}

function updateReaction(
  message: NativeMessage,
  reaction: string,
  active: boolean,
): NativeMessage {
  const current = message.reactions.find((item) => item.reaction === reaction);
  if (active && !current) {
    return {
      ...message,
      reactions: [...message.reactions, { reaction, count: 1, reacted_by_me: true }],
    };
  }
  if (!current || current.reacted_by_me === active) return message;
  const nextCount = Math.max(0, current.count + (active ? 1 : -1));
  return {
    ...message,
    reactions: message.reactions
      .map((item) => item.reaction === reaction
        ? { ...item, count: nextCount, reacted_by_me: active }
        : item)
      .filter((item) => item.count > 0),
  };
}

function MessageCard({
  message,
  canPost,
  reactionWorking,
  onThread,
  onReaction,
}: {
  message: NativeMessage;
  canPost: boolean;
  reactionWorking: string | null;
  onThread?: (message: NativeMessage) => void;
  onReaction: (message: NativeMessage, reaction: string) => void;
}) {
  return (
    <article
      className={styles.message}
      data-agent={message.actor_kind === "agent" || undefined}
      id={`message-${message.id}`}
    >
      <span className={styles.avatar} data-agent={message.actor_kind === "agent" || undefined}>
        {message.actor_kind === "agent" ? "AI" : initials(message.actor_display_name)}
      </span>
      <div className={styles.messageContent}>
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
        <p className={styles.body}>{messageBody(message)}</p>
        <div className={styles.messageActions} aria-label="Message actions">
          {ALLOWED_REACTIONS.map((reaction) => {
            const current = message.reactions.find((item) => item.reaction === reaction);
            const key = `${message.id}:${reaction}`;
            return (
              <button
                aria-label={`${current?.reacted_by_me ? "Remove" : "Add"} ${reaction} reaction`}
                aria-pressed={current?.reacted_by_me ?? false}
                data-active={current?.reacted_by_me || undefined}
                disabled={!canPost || reactionWorking === key}
                key={reaction}
                onClick={() => onReaction(message, reaction)}
                type="button"
              >
                <span aria-hidden="true">{reaction}</span>
                {current ? <small>{current.count}</small> : null}
              </button>
            );
          })}
          {onThread ? (
            <button className={styles.threadButton} onClick={() => onThread(message)} type="button">
              {message.reply_count
                ? `${message.reply_count} ${message.reply_count === 1 ? "reply" : "replies"}`
                : "Reply in thread"}
            </button>
          ) : null}
        </div>
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
  );
}

export function NativeChatPanel({
  channel,
  messages,
  requestedMessage,
  members,
  mutationEndpoint,
  memberEndpoint,
  conversationEndpoint,
}: {
  channel: NativeChannel;
  messages: NativeMessage[];
  requestedMessage: NativeMessage | null;
  members: NativeChannelMember[];
  mutationEndpoint: string | null;
  memberEndpoint: string | null;
  conversationEndpoint: string | null;
}) {
  const router = useRouter();
  const threadHeading = useRef<HTMLHeadingElement>(null);
  const handledDeepLink = useRef<string | null>(null);
  const [rootMessages, setRootMessages] = useState(messages);
  const [body, setBody] = useState("");
  const [threadRoot, setThreadRoot] = useState<NativeMessage | null>(null);
  const [threadReplies, setThreadReplies] = useState<NativeMessage[]>([]);
  const [threadBody, setThreadBody] = useState("");
  const [threadLoading, setThreadLoading] = useState(false);
  const [reactionWorking, setReactionWorking] = useState<string | null>(null);
  const [status, setStatus] = useState<
    | { kind: "idle" }
    | { kind: "working"; text: string }
    | { kind: "error"; text: string }
  >({ kind: "idle" });
  const [memberError, setMemberError] = useState<string | null>(null);
  const [memberWorking, setMemberWorking] = useState(false);
  const threadRootId = threadRoot?.id ?? null;

  useEffect(() => {
    setRootMessages(messages);
    setThreadRoot((current) => {
      if (!current) return current;
      return messages.find((message) => message.id === current.id) ?? current;
    });
  }, [messages]);

  useEffect(() => {
    if (!requestedMessage || handledDeepLink.current === requestedMessage.id) return;

    if (!requestedMessage.thread_root_id) {
      handledDeepLink.current = requestedMessage.id;
      requestAnimationFrame(() => {
        document.getElementById(`message-${requestedMessage.id}`)?.scrollIntoView({
          block: "center",
        });
      });
      return;
    }

    if (!conversationEndpoint) return;
    const root = rootMessages.find((message) => message.id === requestedMessage.thread_root_id);
    if (!root) return;

    handledDeepLink.current = requestedMessage.id;
    const controller = new AbortController();
    setThreadRoot(root);
    setThreadLoading(true);
    void fetch(
      `${conversationEndpoint}/messages/${encodeURIComponent(root.id)}/replies`,
      { credentials: "same-origin", cache: "no-store", signal: controller.signal },
    )
      .then(async (response) => {
        if (!response.ok) throw new Error(`thread_deep_link_${response.status}`);
        setThreadReplies(await response.json() as NativeMessage[]);
        requestAnimationFrame(() => {
          document.getElementById(`message-${requestedMessage.id}`)?.scrollIntoView({
            block: "center",
          });
        });
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setStatus({ kind: "error", text: "The linked thread is no longer available." });
        }
      })
      .finally(() => setThreadLoading(false));

    return () => controller.abort();
  }, [conversationEndpoint, requestedMessage, rootMessages]);

  useEffect(() => {
    if (!threadRootId) return;
    threadHeading.current?.focus();
  }, [threadRootId]);

  useEffect(() => {
    if (!conversationEndpoint || !threadRootId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;

    const schedule = (delay: number) => {
      if (timer) clearTimeout(timer);
      if (!stopped) timer = setTimeout(() => void refreshReplies(), delay);
    };

    async function refreshReplies() {
      if (stopped) return;
      if (document.visibilityState !== "visible" || !navigator.onLine) {
        schedule(15_000);
        return;
      }
      controller?.abort();
      const requestController = new AbortController();
      controller = requestController;
      try {
        const response = await fetch(
          `${conversationEndpoint}/messages/${encodeURIComponent(threadRootId)}/replies`,
          { credentials: "same-origin", cache: "no-store", signal: requestController.signal },
        );
        if (response.status === 403 || response.status === 404) {
          setThreadRoot(null);
          setThreadReplies([]);
          router.refresh();
          return;
        }
        if (response.ok) {
          setThreadReplies(await response.json() as NativeMessage[]);
        }
      } catch {
        if (requestController.signal.aborted || stopped) return;
      }
      schedule(4_000);
    }

    const wake = () => {
      if (document.visibilityState === "visible" && navigator.onLine) schedule(250);
    };
    document.addEventListener("visibilitychange", wake);
    window.addEventListener("online", wake);
    schedule(4_000);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", wake);
      window.removeEventListener("online", wake);
    };
  }, [conversationEndpoint, router, threadRootId]);

  useEffect(() => {
    if (!conversationEndpoint || !channel.latest_message_id || !channel.unread_count) return;
    const controller = new AbortController();
    void fetch(`${conversationEndpoint}/read`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ through_message_id: channel.latest_message_id }),
      signal: controller.signal,
    }).then((response) => {
      if (response.ok) router.refresh();
    }).catch(() => undefined);
    return () => controller.abort();
  }, [channel.latest_message_id, channel.unread_count, conversationEndpoint, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = body.trim();
    if (!mutationEndpoint || !channel.can_post || !normalized) return;
    if (normalized.length > 20_000) {
      setStatus({ kind: "error", text: "Messages are limited to 20,000 characters." });
      return;
    }

    setStatus({ kind: "working", text: "Sending message…" });
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

  async function openThread(message: NativeMessage) {
    setThreadRoot(message);
    setThreadReplies([]);
    setThreadLoading(true);
    setStatus({ kind: "idle" });
    if (!conversationEndpoint) {
      setThreadLoading(false);
      return;
    }
    try {
      const response = await fetch(
        `${conversationEndpoint}/messages/${encodeURIComponent(message.id)}/replies`,
        { credentials: "same-origin" },
      );
      if (!response.ok) {
        setStatus({ kind: "error", text: safeMessageError(response.status) });
        return;
      }
      setThreadReplies(await response.json() as NativeMessage[]);
    } catch {
      setStatus({ kind: "error", text: "The thread could not reach the secure Brain route." });
    } finally {
      setThreadLoading(false);
    }
  }

  async function submitReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = threadBody.trim();
    if (!conversationEndpoint || !threadRoot || !channel.can_post || !normalized) return;
    setStatus({ kind: "working", text: "Sending reply…" });
    try {
      const response = await fetch(
        `${conversationEndpoint}/messages/${encodeURIComponent(threadRoot.id)}/replies`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({ body: normalized }),
        },
      );
      if (!response.ok) {
        setStatus({ kind: "error", text: safeMessageError(response.status) });
        return;
      }
      const reply = await response.json() as NativeMessage;
      setThreadReplies((current) => current.some((item) => item.id === reply.id)
        ? current
        : [...current, reply]);
      setRootMessages((current) => current.map((item) => item.id === threadRoot.id
        ? { ...item, reply_count: item.reply_count + 1 }
        : item));
      setThreadRoot((current) => current
        ? { ...current, reply_count: current.reply_count + 1 }
        : current);
      setThreadBody("");
      setStatus({ kind: "idle" });
    } catch {
      setStatus({ kind: "error", text: "The reply could not reach the secure Brain route." });
    }
  }

  async function toggleReaction(message: NativeMessage, reaction: string) {
    if (!conversationEndpoint || !channel.can_post) return;
    const current = message.reactions.find((item) => item.reaction === reaction);
    const active = !(current?.reacted_by_me ?? false);
    const key = `${message.id}:${reaction}`;
    setReactionWorking(key);
    setStatus({ kind: "idle" });
    try {
      const response = await fetch(
        `${conversationEndpoint}/messages/${encodeURIComponent(message.id)}/reaction`,
        {
          method: active ? "PUT" : "DELETE",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reaction }),
        },
      );
      if (!response.ok) {
        setStatus({ kind: "error", text: safeMessageError(response.status) });
        return;
      }
      setRootMessages((items) => items.map((item) => item.id === message.id
        ? updateReaction(item, reaction, active)
        : item));
      setThreadReplies((items) => items.map((item) => item.id === message.id
        ? updateReaction(item, reaction, active)
        : item));
      setThreadRoot((item) => item?.id === message.id
        ? updateReaction(item, reaction, active)
        : item);
    } catch {
      setStatus({ kind: "error", text: "The reaction could not reach the secure Brain route." });
    } finally {
      setReactionWorking(null);
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
            <p>Member changes stay disabled until the authenticated WorkOS route is active.</p>
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

      <div className={styles.conversation} data-thread-open={Boolean(threadRoot) || undefined}>
        <div className={styles.channelPane}>
          <div className={styles.feed} role="log" aria-live="polite" aria-label={`${channel.name} messages`}>
            {rootMessages.length ? rootMessages.map((message) => (
              <MessageCard
                canPost={Boolean(conversationEndpoint && channel.can_post)}
                key={message.id}
                message={message}
                onReaction={toggleReaction}
                onThread={openThread}
                reactionWorking={reactionWorking}
              />
            )) : (
              <div className={styles.empty}>
                <strong>No messages yet.</strong>
                <span>Start the channel with the composer below.</span>
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
                <p className={styles.composerHint}>Mention a permitted member using their exact @email.</p>
                <div>
                  <span>{body.length.toLocaleString()} / 20,000</span>
                  <button disabled={status.kind === "working" || !body.trim()} type="submit">
                    {status.kind === "working" ? "Sending…" : "Send"}
                  </button>
                </div>
              </form>
            ) : (
              <div className={styles.notice} role="status">
                This channel is readable, but sending stays disabled until the authenticated WorkOS route is active.
              </div>
            )
          ) : (
            <div className={styles.notice} role="status">
              You can read this channel, but your role or membership does not allow posting.
            </div>
          )}
        </div>

        {threadRoot ? (
          <aside
            className={styles.threadPane}
            aria-labelledby="thread-heading"
            onKeyDown={(event) => {
              if (event.key === "Escape") setThreadRoot(null);
            }}
          >
            <header className={styles.threadHeader}>
              <div><h3 id="thread-heading" ref={threadHeading} tabIndex={-1}>Thread</h3><small>#{channel.name}</small></div>
              <button aria-label="Close thread" onClick={() => setThreadRoot(null)} type="button">×</button>
            </header>
            <div className={styles.threadFeed}>
              <MessageCard
                canPost={Boolean(conversationEndpoint && channel.can_post)}
                message={threadRoot}
                onReaction={toggleReaction}
                reactionWorking={reactionWorking}
              />
              <div className={styles.replyDivider}>
                <span>{threadRoot.reply_count} {threadRoot.reply_count === 1 ? "reply" : "replies"}</span>
              </div>
              {threadLoading ? <p className={styles.threadStatus} role="status">Loading replies…</p> : null}
              {!threadLoading && threadReplies.length ? threadReplies.map((reply) => (
                <MessageCard
                  canPost={Boolean(conversationEndpoint && channel.can_post)}
                  key={reply.id}
                  message={reply}
                  onReaction={toggleReaction}
                  reactionWorking={reactionWorking}
                />
              )) : null}
              {!threadLoading && !threadReplies.length ? (
                <p className={styles.threadStatus}>No replies yet.</p>
              ) : null}
            </div>
            {channel.can_post && conversationEndpoint ? (
              <form className={styles.composer} onSubmit={submitReply}>
                <label htmlFor="native-thread-body">Reply in thread</label>
                <textarea
                  id="native-thread-body"
                  value={threadBody}
                  onChange={(event) => setThreadBody(event.target.value)}
                  maxLength={20_000}
                  placeholder="Reply…"
                  rows={3}
                  required
                />
                <div>
                  <span>{threadBody.length.toLocaleString()} / 20,000</span>
                  <button disabled={status.kind === "working" || !threadBody.trim()} type="submit">
                    {status.kind === "working" ? "Sending…" : "Reply"}
                  </button>
                </div>
              </form>
            ) : null}
          </aside>
        ) : null}
      </div>

      {status.kind === "working" ? <div className={styles.srOnly} role="status">{status.text}</div> : null}
      {status.kind === "error" ? <div className={styles.error} role="alert">{status.text}</div> : null}
    </section>
  );
}
