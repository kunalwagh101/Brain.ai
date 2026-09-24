"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  NativeChannel,
  NativeMessageSave,
} from "./brain-api";
import styles from "./saved-messages-panel.module.css";

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

export function SavedMessagesPanel({
  organizationId,
  items,
  channels,
  mutationBase,
}: {
  organizationId: string;
  items: NativeMessageSave[];
  channels: NativeChannel[];
  mutationBase: string | null;
}) {
  const router = useRouter();
  const [rows, setRows] = useState(items);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const channelById = useMemo(
    () => new Map(channels.map((channel) => [channel.id, channel])),
    [channels],
  );

  useEffect(() => {
    setRows(items);
  }, [items]);

  async function unsave(item: NativeMessageSave) {
    if (!mutationBase || working) return;
    setWorking(item.message.id);
    setError(null);
    try {
      const response = await fetch(
        `${mutationBase}/${encodeURIComponent(item.message.channel_id)}/messages/${encodeURIComponent(item.message.id)}/saved`,
        {
          method: "DELETE",
          credentials: "same-origin",
        },
      );
      if (!response.ok) {
        setError("That saved item could not be removed safely.");
        return;
      }
      setRows((current) => current.filter((row) => row.save_id !== item.save_id));
      router.refresh();
    } catch {
      setError("The Saved request could not reach the secure Brain route.");
    } finally {
      setWorking(null);
    }
  }

  return (
    <section className={styles.saved} aria-labelledby="saved-messages-heading">
      <header>
        <div>
          <p>Personal workspace</p>
          <h2 id="saved-messages-heading">Saved messages</h2>
        </div>
        <span>{rows.length}</span>
      </header>

      {rows.length ? (
        <div className={styles.list}>
          {rows.map((item) => {
            const channel = channelById.get(item.message.channel_id);
            const href =
              `?organizationId=${encodeURIComponent(organizationId)}`
              + `&channelId=${encodeURIComponent(item.message.channel_id)}`
              + `&messageId=${encodeURIComponent(item.message.id)}#native-chat`;
            return (
              <article key={item.save_id}>
                <div>
                  <small>
                    # {channel?.name ?? "channel"} · saved {formatTime(item.saved_at)}
                  </small>
                  <strong>{item.message.actor_display_name}</strong>
                  <p>
                    {item.message.body
                      ? item.message.body
                      : item.message.attachments.length
                        ? "Attachment-only message"
                        : "Message"}
                  </p>
                </div>
                <div>
                  <a href={href}>
                    {item.message.thread_root_id ? "Open thread" : "Open message"}
                  </a>
                  {mutationBase ? (
                    <button
                      disabled={working === item.message.id}
                      onClick={() => void unsave(item)}
                      type="button"
                    >
                      {working === item.message.id ? "Working…" : "Unsave"}
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <p className={styles.empty}>
          Save a channel message or thread reply and it will appear here for you only.
        </p>
      )}

      {error ? <p className={styles.error} role="alert">{error}</p> : null}
    </section>
  );
}
