"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { ActivitySummary } from "./activity-api";
import styles from "./activity-panel.module.css";

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

function icon(kind: string): string {
  if (kind === "mention") return "@";
  if (kind === "thread_reply") return "↩";
  if (kind === "reaction") return "☺";
  if (kind === "direct_message") return "✉";
  if (kind === "agent_approval") return "✦";
  return "•";
}

export function ActivityPanel({
  activity,
  organizationId,
  mutationBase,
}: {
  activity: ActivitySummary;
  organizationId: string;
  mutationBase: string | null;
}) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function post(endpoint: string): Promise<boolean> {
    setError(null);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!response.ok) {
        setError("Activity could not be updated right now.");
        return false;
      }
      router.refresh();
      return true;
    } catch {
      setError("Activity could not be updated right now.");
      return false;
    }
  }

  async function openItem(id: string, href: string, read: boolean) {
    setBusyId(id);
    if (!read && mutationBase) {
      await post(`${mutationBase}/${encodeURIComponent(id)}/read`);
    }
    window.location.assign(
      `${href}${href.includes("?") ? "&" : "?"}organizationId=${encodeURIComponent(organizationId)}`,
    );
  }

  async function markAll() {
    if (!mutationBase) return;
    setBusyId("all");
    await post(`${mutationBase}/read-all`);
    setBusyId(null);
  }

  return (
    <section className={styles.activity} aria-labelledby="activity-heading">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Your attention queue</p>
          <h2 id="activity-heading">Activity</h2>
          <p>
            Mentions, thread replies, reactions and direct messages you can still access.
            Brain does not copy private message text into this inbox.
          </p>
        </div>
        <div className={styles.headerActions}>
          <span aria-label={`${activity.unread_count} unread activity items`}>
            {activity.unread_count} unread
          </span>
          {activity.unread_count > 0 && mutationBase ? (
            <button type="button" disabled={busyId === "all"} onClick={() => void markAll()}>
              Mark all read
            </button>
          ) : null}
        </div>
      </header>

      {error ? <p className={styles.error} role="alert">{error}</p> : null}

      <div className={styles.list}>
        {activity.items.length ? activity.items.map((item) => (
          <article key={item.id} className={item.read ? styles.read : styles.unread}>
            <span className={styles.kind} aria-hidden="true">{icon(item.kind)}</span>
            <div className={styles.content}>
              <strong>{item.label}</strong>
              <span>{item.context_label || "Brain"}</span>
              <small>{timeLabel(item.created_at)}</small>
            </div>
            <button
              type="button"
              disabled={busyId === item.id}
              onClick={() => void openItem(item.id, item.href, item.read)}
            >
              Open
            </button>
          </article>
        )) : (
          <div className={styles.empty}>
            <strong>You’re caught up.</strong>
            <span>New mentions, replies, reactions and direct messages will appear here.</span>
          </div>
        )}
      </div>
    </section>
  );
}
