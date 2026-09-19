"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type {
  NativeAttachment,
  NativeChannel,
  NativeChannelMember,
  NativeMessage,
  NativeMessagePin,
} from "./brain-api";
import styles from "./native-chat-panel.module.css";
import {
  useCollaborationPresence,
  type CollaborationPresenceUser,
} from "./use-collaboration-presence";

const ALLOWED_REACTIONS = ["👍", "❤️", "🎉", "👀", "✅"] as const;
const MAX_ATTACHMENTS_PER_MESSAGE = 5;
const MAX_ATTACHMENT_FILE_BYTES = 10_000_000;
const ATTACHMENT_ACCEPT = [
  ".txt", ".md", ".csv", ".json", ".vtt", ".srt", ".pdf", ".docx",
  "text/plain", "text/markdown", "text/csv", "application/json",
  "text/vtt", "application/x-subrip", "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
].join(",");
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

function formatBytes(value: number): string {
  if (value < 1_000) return `${value} B`;
  if (value < 1_000_000) return `${(value / 1_000).toFixed(1)} KB`;
  return `${(value / 1_000_000).toFixed(1)} MB`;
}

function attachmentKind(file: File): "document" | "transcript" {
  const lower = file.name.toLowerCase();
  return lower.endsWith(".vtt") || lower.endsWith(".srt")
    ? "transcript"
    : "document";
}

function safeAttachmentError(status: number): string {
  if (status === 400 || status === 415 || status === 422) {
    return "That file type or upload request was not accepted.";
  }
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403 || status === 404) {
    return "This channel is no longer writable by your account.";
  }
  if (status === 409) return "That upload conflicts with an existing retry key.";
  if (status === 413) return "Each attachment must be 10 MB or smaller.";
  if (status === 429) return "File uploads are temporarily rate limited.";
  return "The attachment could not be uploaded safely.";
}

function typingLabel(users: CollaborationPresenceUser[]): string {
  if (users.length === 1) return `${users[0].display_name} is typing…`;
  if (users.length === 2) {
    return `${users[0].display_name} and ${users[1].display_name} are typing…`;
  }
  return users.length > 2 ? `${users.length} people are typing…` : "";
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

function lifecycleError(status: number): string {
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403 || status === 404) {
    return "This message is no longer editable by your account.";
  }
  if (status === 409) return "This message changed. Refresh and try your edit again.";
  if (status === 413) return "The edit is too large.";
  if (status === 422) return "The edit was not accepted.";
  return "The message change could not be completed safely.";
}

function MessageCard({
  message,
  canPost,
  reactionWorking,
  lifecycleEndpoint,
  pinned,
  pinWorking,
  saved,
  saveWorking,
  onThread,
  onReaction,
  onPin,
  onSave,
  onLifecycleChange,
}: {
  message: NativeMessage;
  canPost: boolean;
  reactionWorking: string | null;
  lifecycleEndpoint: string | null;
  pinned: boolean;
  pinWorking: string | null;
  saved: boolean;
  saveWorking: string | null;
  onThread?: (message: NativeMessage) => void;
  onReaction: (message: NativeMessage, reaction: string) => void;
  onPin?: (message: NativeMessage, active: boolean) => void;
  onSave?: (message: NativeMessage, active: boolean) => void;
  onLifecycleChange: (message: NativeMessage) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editBody, setEditBody] = useState("");
  const [confirmRetract, setConfirmRetract] = useState(false);
  const [working, setWorking] = useState<"edit" | "retract" | null>(null);
  const [lifecycleErrorText, setLifecycleErrorText] = useState<string | null>(null);
  const deleted = message.deleted_at !== null;
  const canEdit = Boolean(lifecycleEndpoint && message.can_edit && !deleted);
  const canDelete = Boolean(lifecycleEndpoint && message.can_delete && !deleted);

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lifecycleEndpoint || !canEdit || working) return;
    const normalized = editBody.trim();
    if (!normalized || normalized.length > 20_000) return;

    setWorking("edit");
    setLifecycleErrorText(null);
    try {
      const response = await fetch(
        `${lifecycleEndpoint}/messages/${encodeURIComponent(message.id)}`,
        {
          method: "PATCH",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            body: normalized,
            expected_revision: message.revision,
          }),
        },
      );
      if (!response.ok) {
        setLifecycleErrorText(lifecycleError(response.status));
        return;
      }
      const updated = await response.json() as NativeMessage;
      setEditing(false);
      setEditBody("");
      onLifecycleChange(updated);
    } catch {
      setLifecycleErrorText("The edit could not reach the secure Brain route.");
    } finally {
      setWorking(null);
    }
  }

  async function retract() {
    if (!lifecycleEndpoint || !canDelete || working) return;
    setWorking("retract");
    setLifecycleErrorText(null);
    try {
      const response = await fetch(
        `${lifecycleEndpoint}/messages/${encodeURIComponent(message.id)}`,
        {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_revision: message.revision }),
        },
      );
      if (!response.ok) {
        setLifecycleErrorText(lifecycleError(response.status));
        return;
      }
      const updated = await response.json() as NativeMessage;
      setConfirmRetract(false);
      onLifecycleChange(updated);
    } catch {
      setLifecycleErrorText("The retraction could not reach the secure Brain route.");
    } finally {
      setWorking(null);
    }
  }

  return (
    <article
      className={styles.message}
      data-agent={message.actor_kind === "agent" || undefined}
      data-deleted={deleted || undefined}
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
          {message.edited_at && !deleted ? <span className={styles.editedMarker}>edited</span> : null}
          {message.projection_status !== "ready" ? (
            <span className={styles.projection} data-status={message.projection_status}>
              {message.projection_status}
            </span>
          ) : null}
        </div>

        {deleted ? (
          <p className={styles.tombstone}>This message was retracted by its author.</p>
        ) : editing ? (
          <form className={styles.editForm} onSubmit={submitEdit}>
            <label htmlFor={`edit-message-${message.id}`}>Edit message</label>
            <textarea
              id={`edit-message-${message.id}`}
              maxLength={20_000}
              onChange={(event) => setEditBody(event.target.value)}
              rows={3}
              value={editBody}
            />
            <div>
              <span>{editBody.length.toLocaleString()} / 20,000</span>
              <button
                disabled={working === "edit" || !editBody.trim()}
                type="submit"
              >
                {working === "edit" ? "Saving…" : "Save"}
              </button>
              <button
                disabled={working !== null}
                onClick={() => {
                  setEditing(false);
                  setEditBody("");
                  setLifecycleErrorText(null);
                }}
                type="button"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <p className={styles.body}>{messageBody(message)}</p>
        )}

        {!deleted && message.attachments.length ? (
          <div className={styles.attachments} aria-label="Message attachments">
            {message.attachments.map((attachment) => (
              <a
                aria-disabled={!attachment.retrieval_available}
                data-unavailable={!attachment.retrieval_available || undefined}
                href={attachment.retrieval_available ? "#files" : undefined}
                key={attachment.source_id}
                onClick={(event) => {
                  if (!attachment.retrieval_available) event.preventDefault();
                }}
              >
                <span aria-hidden="true">📎</span>
                <span>
                  <strong>{attachment.title || attachment.filename}</strong>
                  <small>
                    {attachment.filename} · {attachment.kind} · {formatBytes(attachment.byte_size)}
                  </small>
                </span>
                <em>
                  {attachment.retrieval_available
                    ? "Governed evidence"
                    : attachment.status === "deleted"
                      ? "Deleted"
                      : "Unavailable"}
                </em>
              </a>
            ))}
          </div>
        ) : null}

        {!editing ? (
          <div className={styles.messageActions} aria-label="Message actions">
            {!deleted ? ALLOWED_REACTIONS.map((reaction) => {
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
            }) : null}
            {onThread && (!deleted || message.reply_count > 0) ? (
              <button className={styles.threadButton} onClick={() => onThread(message)} type="button">
                {message.reply_count
                  ? `${message.reply_count} ${message.reply_count === 1 ? "reply" : "replies"}`
                  : "Reply in thread"}
              </button>
            ) : null}
            {!deleted && onPin ? (
              <button
                aria-label={pinned ? "Unpin message" : "Pin message"}
                aria-pressed={pinned}
                data-active={pinned || undefined}
                disabled={!canPost || pinWorking === message.id}
                onClick={() => onPin(message, !pinned)}
                type="button"
              >
                {pinWorking === message.id ? "Working…" : pinned ? "Unpin" : "Pin"}
              </button>
            ) : null}
            {!deleted && onSave ? (
              <button
                aria-label={saved ? "Unsave message" : "Save message"}
                aria-pressed={saved}
                data-active={saved || undefined}
                disabled={saveWorking === message.id}
                onClick={() => onSave(message, !saved)}
                type="button"
              >
                {saveWorking === message.id ? "Working…" : saved ? "Unsave" : "Save"}
              </button>
            ) : null}
            {canEdit ? (
              <button
                onClick={() => {
                  setEditBody(message.body);
                  setEditing(true);
                  setConfirmRetract(false);
                  setLifecycleErrorText(null);
                }}
                type="button"
              >
                Edit
              </button>
            ) : null}
            {canDelete && !confirmRetract ? (
              <button onClick={() => setConfirmRetract(true)} type="button">
                Retract
              </button>
            ) : null}
          </div>
        ) : null}

        {confirmRetract && !deleted ? (
          <div className={styles.retractConfirm} role="group" aria-label="Confirm message retraction">
            <span>Retract this message from the current conversation and search?</span>
            <button disabled={working !== null} onClick={() => void retract()} type="button">
              {working === "retract" ? "Retracting…" : "Yes, retract"}
            </button>
            <button
              disabled={working !== null}
              onClick={() => {
                setConfirmRetract(false);
                setLifecycleErrorText(null);
              }}
              type="button"
            >
              Cancel
            </button>
          </div>
        ) : null}

        {lifecycleErrorText ? (
          <p className={styles.lifecycleError} role="alert">{lifecycleErrorText}</p>
        ) : null}

        {!deleted ? (
          <details className={styles.provenance}>
            <summary>Evidence provenance</summary>
            <dl>
              <div><dt>Message</dt><dd><code>{message.id}</code></dd></div>
              <div><dt>Revision</dt><dd>{message.revision}</dd></div>
              <div><dt>SHA-256</dt><dd><code>{message.body_sha256}</code></dd></div>
              {message.canonical_event_id ? (
                <div>
                  <dt>Canonical event</dt>
                  <dd><code>{message.canonical_event_id}</code></dd>
                </div>
              ) : null}
              {message.agent_run_id ? (
                <div><dt>Agent run</dt><dd><code>{message.agent_run_id}</code></dd></div>
              ) : null}
            </dl>
          </details>
        ) : null}
      </div>
    </article>
  );
}

export function NativeChatPanel({
  channel,
  messages,
  pins,
  savedMessageIds,
  requestedMessage,
  members,
  mutationEndpoint,
  memberEndpoint,
  conversationEndpoint,
  presenceEndpoint,
}: {
  channel: NativeChannel;
  messages: NativeMessage[];
  pins: NativeMessagePin[];
  savedMessageIds: string[];
  requestedMessage: NativeMessage | null;
  members: NativeChannelMember[];
  mutationEndpoint: string | null;
  memberEndpoint: string | null;
  conversationEndpoint: string | null;
  presenceEndpoint: string | null;
}) {
  const router = useRouter();
  const threadHeading = useRef<HTMLHeadingElement>(null);
  const handledDeepLink = useRef<string | null>(null);
  const activeChannelIdRef = useRef(channel.id);
  const messageRetryKey = useRef<string | null>(null);
  const threadRetryKey = useRef<{ rootId: string; key: string } | null>(null);
  const [rootMessages, setRootMessages] = useState(messages);
  const [pinRows, setPinRows] = useState(pins);
  const [pinsOpen, setPinsOpen] = useState(false);
  const [pinWorking, setPinWorking] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState(savedMessageIds);
  const [saveWorking, setSaveWorking] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [attachments, setAttachments] = useState<NativeAttachment[]>([]);
  const [threadRoot, setThreadRoot] = useState<NativeMessage | null>(null);
  const [threadReplies, setThreadReplies] = useState<NativeMessage[]>([]);
  const [threadBody, setThreadBody] = useState("");
  const [threadAttachments, setThreadAttachments] = useState<NativeAttachment[]>([]);
  const [threadAttachmentRootId, setThreadAttachmentRootId] = useState<string | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [composerFocused, setComposerFocused] = useState(false);
  const [threadFocused, setThreadFocused] = useState(false);
  const [uploadingTarget, setUploadingTarget] = useState<"channel" | "thread" | null>(null);
  const [reactionWorking, setReactionWorking] = useState<string | null>(null);
  const [status, setStatus] = useState<
    | { kind: "idle" }
    | { kind: "working"; text: string }
    | { kind: "error"; text: string }
  >({ kind: "idle" });
  const [memberError, setMemberError] = useState<string | null>(null);
  const [memberWorking, setMemberWorking] = useState(false);
  const threadRootId = threadRoot?.id ?? null;

  const presence = useCollaborationPresence(
    presenceEndpoint,
    Boolean(
      channel.can_post
      && (
        (composerFocused && body.trim())
        || (threadFocused && threadBody.trim())
      )
    ),
  );
  const typingText = typingLabel(presence.typing_users);

  useEffect(() => {
    activeChannelIdRef.current = channel.id;
    setBody("");
    setAttachments([]);
    setThreadRoot(null);
    setThreadReplies([]);
    setThreadBody("");
    setThreadAttachments([]);
    setThreadAttachmentRootId(null);
    setComposerFocused(false);
    setThreadFocused(false);
    setPinsOpen(false);
    messageRetryKey.current = null;
    threadRetryKey.current = null;
  }, [channel.id]);

  useEffect(() => {
    setRootMessages(messages);
    setThreadRoot((current) => {
      if (!current) return current;
      return messages.find((message) => message.id === current.id) ?? current;
    });
  }, [messages]);

  useEffect(() => {
    setPinRows(pins);
  }, [pins]);

  useEffect(() => {
    setSavedIds(savedMessageIds);
  }, [savedMessageIds]);


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
        const replies = await response.json() as NativeMessage[];
      setThreadReplies(replies);
      if (focusMessageId) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            document.getElementById(`message-${focusMessageId}`)?.scrollIntoView({
              block: "center",
            });
          });
        });
      }
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

  function keepUploadedAttachments(
    uploaded: NativeAttachment[],
    target: "channel" | "thread",
  ) {
    if (!uploaded.length) return;
    const merge = (items: NativeAttachment[]) => [
      ...items,
      ...uploaded.filter(
        (item) => !items.some((existing) => existing.source_id === item.source_id),
      ),
    ];
    if (target === "channel") {
      setAttachments(merge);
      messageRetryKey.current = null;
    } else {
      setThreadAttachments(merge);
      if (threadRoot) {
        setThreadAttachmentRootId(threadRoot.id);
        threadRetryKey.current = null;
      }
    }
  }

  async function uploadAttachments(
    files: File[],
    target: "channel" | "thread",
  ) {
    if (!conversationEndpoint || !channel.can_post || !files.length) return;
    if (target === "thread" && !threadRoot) return;
    const uploadChannelId = channel.id;
    const uploadThreadId = target === "thread" ? threadRoot?.id ?? null : null;
    const current = target === "channel" ? attachments : threadAttachments;
    const remaining = MAX_ATTACHMENTS_PER_MESSAGE - current.length;
    if (files.length > remaining) {
      setStatus({
        kind: "error",
        text: `A message can contain at most ${MAX_ATTACHMENTS_PER_MESSAGE} attachments.`,
      });
      return;
    }
    const oversized = files.find((file) => file.size > MAX_ATTACHMENT_FILE_BYTES);
    if (oversized) {
      setStatus({
        kind: "error",
        text: `${oversized.name} is larger than 10 MB.`,
      });
      return;
    }

    setUploadingTarget(target);
    setStatus({
      kind: "working",
      text: files.length === 1 ? "Uploading governed file…" : "Uploading governed files…",
    });
    const uploaded: NativeAttachment[] = [];
    try {
      for (const file of files) {
        const form = new FormData();
        form.set("file", file);
        form.set("kind", attachmentKind(file));
        form.set("title", file.name);
        const response = await fetch(`${conversationEndpoint}/attachments/uploads`, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Idempotency-Key": `native-attachment:${crypto.randomUUID()}` },
          body: form,
        });
        if (!response.ok) {
          if (activeChannelIdRef.current === uploadChannelId) {
            keepUploadedAttachments(uploaded, target);
            setStatus({ kind: "error", text: safeAttachmentError(response.status) });
          }
          return;
        }
        uploaded.push(await response.json() as NativeAttachment);
      }
      if (
        activeChannelIdRef.current === uploadChannelId
        && (target === "channel" || threadRoot?.id === uploadThreadId)
      ) {
        keepUploadedAttachments(uploaded, target);
        setStatus({ kind: "idle" });
      }
    } catch {
      if (
        activeChannelIdRef.current === uploadChannelId
        && (target === "channel" || threadRoot?.id === uploadThreadId)
      ) {
        keepUploadedAttachments(uploaded, target);
        setStatus({
          kind: "error",
          text: "The file upload could not reach the secure Brain route. Successful uploads were kept for retry.",
        });
      }
    } finally {
      setUploadingTarget(null);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = body.trim();
    if (!mutationEndpoint || !channel.can_post || (!normalized && !attachments.length)) return;
    if (normalized.length > 20_000) {
      setStatus({ kind: "error", text: "Messages are limited to 20,000 characters." });
      return;
    }

    const retryKey = messageRetryKey.current ?? crypto.randomUUID();
    messageRetryKey.current = retryKey;
    setStatus({ kind: "working", text: "Sending message…" });
    try {
      const response = await fetch(mutationEndpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": retryKey,
        },
        body: JSON.stringify({
          body: normalized,
          attachment_source_ids: attachments.map((item) => item.source_id),
        }),
      });
      if (!response.ok) {
        setStatus({ kind: "error", text: safeMessageError(response.status) });
        return;
      }
      setBody("");
      setAttachments([]);
      messageRetryKey.current = null;
      setStatus({ kind: "idle" });
      router.refresh();
    } catch {
      setStatus({
        kind: "error",
        text: "The message send failed. Uploaded files were kept so you can retry without re-uploading.",
      });
    }
  }

  async function openThread(message: NativeMessage, focusMessageId?: string) {
    if (uploadingTarget === "thread" && threadRoot?.id !== message.id) {
      setStatus({
        kind: "error",
        text: "Finish the current thread file upload before switching threads.",
      });
      return;
    }
    if (threadAttachmentRootId && threadAttachmentRootId !== message.id) {
      setThreadAttachments([]);
      setThreadAttachmentRootId(null);
    }
    if (threadRetryKey.current?.rootId !== message.id) {
      threadRetryKey.current = null;
    }
    setThreadRoot(message);
    setThreadFocused(false);
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
    if (
      !conversationEndpoint
      || !threadRoot
      || !channel.can_post
      || (
        !normalized
        && !(threadAttachmentRootId === threadRoot.id && threadAttachments.length)
      )
    ) return;
    const retryKey = threadRetryKey.current?.rootId === threadRoot.id
      ? threadRetryKey.current.key
      : crypto.randomUUID();
    threadRetryKey.current = { rootId: threadRoot.id, key: retryKey };
    setStatus({ kind: "working", text: "Sending reply…" });
    try {
      const response = await fetch(
        `${conversationEndpoint}/messages/${encodeURIComponent(threadRoot.id)}/replies`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": retryKey,
          },
          body: JSON.stringify({
            body: normalized,
            attachment_source_ids: threadAttachmentRootId === threadRoot.id
              ? threadAttachments.map((item) => item.source_id)
              : [],
          }),
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
      setThreadAttachments([]);
      setThreadAttachmentRootId(null);
      threadRetryKey.current = null;
      setStatus({ kind: "idle" });
    } catch {
      setStatus({
        kind: "error",
        text: "The reply send failed. Uploaded files were kept so you can retry without re-uploading.",
      });
    }
  }

  async function togglePin(message: NativeMessage, active: boolean) {
    if (!conversationEndpoint || !channel.can_post || message.deleted_at) return;
    setPinWorking(message.id);
    setStatus({ kind: "idle" });
    try {
      const response = await fetch(
        `${conversationEndpoint}/messages/${encodeURIComponent(message.id)}/pin`,
        {
          method: active ? "PUT" : "DELETE",
          credentials: "same-origin",
        },
      );
      if (!response.ok) {
        setStatus({ kind: "error", text: safeMessageError(response.status) });
        return;
      }
      if (active) {
        const pin = await response.json() as NativeMessagePin;
        setPinRows((items) => [
          pin,
          ...items.filter((item) => item.message.id !== message.id),
        ]);
      } else {
        setPinRows((items) => items.filter((item) => item.message.id !== message.id));
      }
    } catch {
      setStatus({ kind: "error", text: "The pin change could not reach the secure Brain route." });
    } finally {
      setPinWorking(null);
    }
  }

  async function openPinned(pin: NativeMessagePin) {
    const message = pin.message;
    setPinsOpen(false);
    if (!message.thread_root_id) {
      setThreadRoot(null);
      setThreadReplies([]);
      setRootMessages((items) => items.some((item) => item.id === message.id)
        ? items
        : [message, ...items]);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          document.getElementById(`message-${message.id}`)?.scrollIntoView({
            block: "center",
          });
        });
      });
      return;
    }

    if (!conversationEndpoint) return;
    let root = rootMessages.find((item) => item.id === message.thread_root_id) ?? null;
    if (!root) {
      try {
        const response = await fetch(
          `${conversationEndpoint}/messages/${encodeURIComponent(message.thread_root_id)}`,
          { credentials: "same-origin", cache: "no-store" },
        );
        if (!response.ok) {
          setStatus({ kind: "error", text: safeMessageError(response.status) });
          return;
        }
        root = await response.json() as NativeMessage;
        setRootMessages((items) => items.some((item) => item.id === root?.id)
          ? items
          : root ? [root, ...items] : items);
      } catch {
        setStatus({ kind: "error", text: "The pinned thread could not be opened safely." });
        return;
      }
    }
    if (root) await openThread(root, message.id);
  }

  async function toggleSave(message: NativeMessage, active: boolean) {
    if (!conversationEndpoint || message.deleted_at) return;
    setSaveWorking(message.id);
    setStatus({ kind: "idle" });
    try {
      const response = await fetch(
        `${conversationEndpoint}/messages/${encodeURIComponent(message.id)}/saved`,
        {
          method: active ? "PUT" : "DELETE",
          credentials: "same-origin",
        },
      );
      if (!response.ok) {
        setStatus({ kind: "error", text: safeMessageError(response.status) });
        return;
      }
      setSavedIds((items) => active
        ? items.includes(message.id) ? items : [message.id, ...items]
        : items.filter((id) => id !== message.id));
      router.refresh();
    } catch {
      setStatus({ kind: "error", text: "The Saved change could not reach the secure Brain route." });
    } finally {
      setSaveWorking(null);
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

  function applyLifecycleMessage(updated: NativeMessage) {
    if (updated.deleted_at) {
      setPinRows((items) => items.filter((item) => item.message.id !== updated.id));
      setSavedIds((items) => items.filter((id) => id !== updated.id));
    } else {
      setPinRows((items) => items.map((item) => item.message.id === updated.id
        ? { ...item, message: updated }
        : item));
    }
    setRootMessages((items) => items.map((item) => item.id === updated.id ? updated : item));
    setThreadReplies((items) => items.map((item) => item.id === updated.id ? updated : item));
    setThreadRoot((item) => item?.id === updated.id ? updated : item);
    router.refresh();
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
          {presenceEndpoint && presence.loaded ? (
            <span>{presence.online_users.length} online</span>
          ) : null}
          <span>{channel.status}</span>
          <button
            aria-expanded={pinsOpen}
            className={styles.pinsButton}
            onClick={() => setPinsOpen((value) => !value)}
            type="button"
          >
            Pins {pinRows.length ? `(${pinRows.length})` : ""}
          </button>
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

      {pinsOpen ? (
        <section className={styles.pinsPanel} aria-labelledby="channel-pins-heading">
          <header>
            <div>
              <p className={styles.eyebrow}>Channel context</p>
              <h3 id="channel-pins-heading">Pinned messages</h3>
            </div>
            <span>{pinRows.length}</span>
          </header>
          {pinRows.length ? (
            <div className={styles.pinList}>
              {pinRows.map((pin) => (
                <article key={pin.pin_id}>
                  <div>
                    <strong>{pin.message.actor_display_name}</strong>
                    <small>
                      Pinned by {pin.pinned_by_display_name} · {formatTime(pin.pinned_at)}
                    </small>
                    <p>
                      {pin.message.body
                        ? pin.message.body
                        : pin.message.attachments.length
                          ? "Attachment-only message"
                          : "Message"}
                    </p>
                  </div>
                  <div>
                    <button
                      disabled={Boolean(pin.message.thread_root_id && !conversationEndpoint)}
                      onClick={() => void openPinned(pin)}
                      type="button"
                    >
                      {pin.message.thread_root_id ? "Open thread" : "Open message"}
                    </button>
                    {channel.can_post && conversationEndpoint ? (
                      <button
                        disabled={pinWorking === pin.message.id}
                        onClick={() => void togglePin(pin.message, false)}
                        type="button"
                      >
                        {pinWorking === pin.message.id ? "Working…" : "Unpin"}
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className={styles.pinsEmpty}>No pinned messages in this channel yet.</p>
          )}
        </section>
      ) : null}

      <div className={styles.conversation} data-thread-open={Boolean(threadRoot) || undefined}>
        <div className={styles.channelPane}>
          <div className={styles.feed} role="log" aria-live="polite" aria-label={`${channel.name} messages`}>
            {rootMessages.length ? rootMessages.map((message) => (
              <MessageCard
                canPost={Boolean(conversationEndpoint && channel.can_post)}
                key={message.id}
                lifecycleEndpoint={conversationEndpoint}
                message={message}
                onLifecycleChange={applyLifecycleMessage}
                onPin={channel.can_post ? togglePin : undefined}
                onReaction={toggleReaction}
                pinned={pinRows.some((pin) => pin.message.id === message.id)}
                pinWorking={pinWorking}
                saved={savedIds.includes(message.id)}
                saveWorking={saveWorking}
                onSave={conversationEndpoint ? toggleSave : undefined}
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

          {presenceEndpoint && typingText ? (
            <p className={styles.typingStatus} aria-live="polite" role="status">
              {typingText}
            </p>
          ) : null}

          {channel.can_post ? (
            mutationEndpoint ? (
              <form className={styles.composer} onSubmit={submit}>
                <label htmlFor="native-message-body">Message #{channel.name}</label>
                <textarea
                  id="native-message-body"
                  value={body}
                  onChange={(event) => {
                    setBody(event.target.value);
                    messageRetryKey.current = null;
                  }}
                  onFocus={() => setComposerFocused(true)}
                  onBlur={() => setComposerFocused(false)}
                  maxLength={20_000}
                  placeholder={`Message #${channel.name}`}
                  rows={3}
                />
                <p className={styles.composerHint}>Mention a permitted member using their exact @email.</p>
                {attachments.length ? (
                  <div className={styles.pendingAttachments} aria-label="Files ready to send">
                    {attachments.map((attachment) => (
                      <span key={attachment.source_id}>
                        <span aria-hidden="true">📎</span>
                        <span>{attachment.filename}</span>
                        <small>{formatBytes(attachment.byte_size)} · governed</small>
                      </span>
                    ))}
                    <p>Uploads are already saved in Brain and will be reused if sending fails.</p>
                  </div>
                ) : null}
                <div className={styles.composerFooter}>
                  <label className={styles.attachButton}>
                    <span>Attach files</span>
                    <input
                      accept={ATTACHMENT_ACCEPT}
                      disabled={
                        uploadingTarget !== null
                        || attachments.length >= MAX_ATTACHMENTS_PER_MESSAGE
                      }
                      multiple
                      onChange={(event) => {
                        const files = Array.from(event.currentTarget.files ?? []);
                        event.currentTarget.value = "";
                        void uploadAttachments(files, "channel");
                      }}
                      type="file"
                    />
                  </label>
                  <span>{body.length.toLocaleString()} / 20,000 · {attachments.length}/5 files</span>
                  <button
                    disabled={
                      status.kind === "working"
                      || uploadingTarget !== null
                      || (!body.trim() && !attachments.length)
                    }
                    type="submit"
                  >
                    {status.kind === "working" ? "Working…" : "Send"}
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
              if (event.key === "Escape" && uploadingTarget !== "thread") {
                setThreadFocused(false);
                setThreadRoot(null);
              }
            }}
          >
            <header className={styles.threadHeader}>
              <div><h3 id="thread-heading" ref={threadHeading} tabIndex={-1}>Thread</h3><small>#{channel.name}</small></div>
              <button
                aria-label="Close thread"
                disabled={uploadingTarget === "thread"}
                onClick={() => {
                  setThreadFocused(false);
                  setThreadRoot(null);
                }}
                type="button"
              >
                ×
              </button>
            </header>
            <div className={styles.threadFeed}>
              <MessageCard
                canPost={Boolean(conversationEndpoint && channel.can_post)}
                lifecycleEndpoint={conversationEndpoint}
                message={threadRoot}
                onLifecycleChange={applyLifecycleMessage}
                onPin={channel.can_post ? togglePin : undefined}
                onReaction={toggleReaction}
                pinned={pinRows.some((pin) => pin.message.id === threadRoot.id)}
                pinWorking={pinWorking}
                saved={savedIds.includes(threadRoot.id)}
                saveWorking={saveWorking}
                onSave={conversationEndpoint ? toggleSave : undefined}
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
                  lifecycleEndpoint={conversationEndpoint}
                  message={reply}
                  onLifecycleChange={applyLifecycleMessage}
                  onPin={channel.can_post ? togglePin : undefined}
                  onReaction={toggleReaction}
                  pinned={pinRows.some((pin) => pin.message.id === reply.id)}
                  pinWorking={pinWorking}
                  saved={savedIds.includes(reply.id)}
                  saveWorking={saveWorking}
                  onSave={conversationEndpoint ? toggleSave : undefined}
                  reactionWorking={reactionWorking}
                />
              )) : null}
              {!threadLoading && !threadReplies.length ? (
                <p className={styles.threadStatus}>No replies yet.</p>
              ) : null}
            </div>
            {channel.can_post && conversationEndpoint && !threadRoot.deleted_at ? (
              <form className={styles.composer} onSubmit={submitReply}>
                <label htmlFor="native-thread-body">Reply in thread</label>
                <textarea
                  id="native-thread-body"
                  value={threadBody}
                  onChange={(event) => {
                    setThreadBody(event.target.value);
                    threadRetryKey.current = null;
                  }}
                  onFocus={() => setThreadFocused(true)}
                  onBlur={() => setThreadFocused(false)}
                  maxLength={20_000}
                  placeholder="Reply…"
                  rows={3}
                />
                {threadAttachmentRootId === threadRoot.id && threadAttachments.length ? (
                  <div className={styles.pendingAttachments} aria-label="Thread files ready to send">
                    {threadAttachments.map((attachment) => (
                      <span key={attachment.source_id}>
                        <span aria-hidden="true">📎</span>
                        <span>{attachment.filename}</span>
                        <small>{formatBytes(attachment.byte_size)} · governed</small>
                      </span>
                    ))}
                    <p>Uploads are already saved in Brain and will be reused if sending fails.</p>
                  </div>
                ) : null}
                <div className={styles.composerFooter}>
                  <label className={styles.attachButton}>
                    <span>Attach files</span>
                    <input
                      accept={ATTACHMENT_ACCEPT}
                      disabled={
                        uploadingTarget !== null
                        || (
                          threadAttachmentRootId === threadRoot.id
                          && threadAttachments.length >= MAX_ATTACHMENTS_PER_MESSAGE
                        )
                      }
                      multiple
                      onChange={(event) => {
                        const files = Array.from(event.currentTarget.files ?? []);
                        event.currentTarget.value = "";
                        void uploadAttachments(files, "thread");
                      }}
                      type="file"
                    />
                  </label>
                  <span>
                    {threadBody.length.toLocaleString()} / 20,000 · {
                      threadAttachmentRootId === threadRoot.id ? threadAttachments.length : 0
                    }/5 files
                  </span>
                  <button
                    disabled={
                      status.kind === "working"
                      || uploadingTarget !== null
                      || (
                        !threadBody.trim()
                        && !(
                          threadAttachmentRootId === threadRoot.id
                          && threadAttachments.length
                        )
                      )
                    }
                    type="submit"
                  >
                    {status.kind === "working" ? "Working…" : "Reply"}
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
