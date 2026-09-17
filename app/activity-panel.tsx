"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { ActivityPreferences, ActivitySummary } from "./activity-api";
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
  if (kind === "channel_activity") return "#";
  if (kind === "agent_approval") return "!";
  if (kind === "agent_completed") return "✓";
  if (kind === "agent_failed") return "×";
  if (kind === "project_update") return "P";
  if (kind === "blocker_update") return "B";
  if (kind === "integration_failure") return "⚠";
  return "•";
}

function activityTarget(href: string, organizationId: string): string {
  const [pathAndQuery, fragment] = href.split("#", 2);
  const separator = pathAndQuery.includes("?") ? "&" : "?";
  const query = `${pathAndQuery}${separator}organizationId=${encodeURIComponent(organizationId)}`;
  return fragment ? `${query}#${fragment}` : query;
}

const PREFERENCE_LABELS: Array<[keyof ActivityPreferences, string]> = [
  ["mentions", "@mentions"],
  ["thread_replies", "Thread replies"],
  ["direct_messages", "Direct messages"],
  ["channel_activity", "Unread channel activity"],
  ["agent_approvals", "Agent approval requests"],
  ["agent_run_events", "Agent completion and failure"],
  ["project_updates", "Project and blocker updates"],
  ["integration_failures", "Integration failures"],
];

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
  const [preferences, setPreferences] = useState<ActivityPreferences | null>(null);

  useEffect(() => {
    if (!mutationBase) return;
    let active = true;
    void fetch(`${mutationBase}/preferences`, { credentials: "same-origin", cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("preferences_unavailable");
        return await response.json() as ActivityPreferences;
      })
      .then((value) => {
        if (active) setPreferences(value);
      })
      .catch(() => {
        if (active) setError("Notification preferences could not be loaded right now.");
      });
    return () => {
      active = false;
    };
  }, [mutationBase]);

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
    window.location.assign(activityTarget(href, organizationId));
  }

  async function markAll() {
    if (!mutationBase) return;
    setBusyId("all");
    await post(`${mutationBase}/read-all`);
    setBusyId(null);
  }

  async function setPreference(key: keyof ActivityPreferences, value: boolean) {
    if (!mutationBase || !preferences) return;
    setError(null);
    const next = { ...preferences, [key]: value };
    setPreferences(next);
    try {
      const response = await fetch(`${mutationBase}/preferences`, {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: value }),
      });
      if (!response.ok) throw new Error("preference_update_failed");
      setPreferences(await response.json() as ActivityPreferences);
      router.refresh();
    } catch {
      setPreferences(preferences);
      setError("Notification preference could not be saved right now.");
    }
  }

  return (
    <section className={styles.activity} aria-labelledby="activity-heading">
      <header className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Your attention queue</p>
          <h2 id="activity-heading">Activity</h2>
          <p>
            Mentions, replies, unread channels, agent work, project blockers and integration failures.
            Brain links back to the source and does not copy private message text into this inbox.
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

      {mutationBase ? (
        <details>
          <summary>Notification preferences</summary>
          {preferences ? (
            <fieldset>
              <legend>Show in Activity</legend>
              {PREFERENCE_LABELS.map(([key, label]) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={preferences[key]}
                    onChange={(event) => void setPreference(key, event.currentTarget.checked)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
          ) : <p>Loading preferences…</p>}
        </details>
      ) : null}

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
            <span>New activity requiring your attention will appear here.</span>
          </div>
        )}
      </div>
    </section>
  );
}
