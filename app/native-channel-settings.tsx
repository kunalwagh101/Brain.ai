"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { NativeChannel } from "./brain-api";
import styles from "./native-channel-settings.module.css";

function safeError(status: number): string {
  if (status === 400 || status === 422) return "The channel settings were not accepted.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403 || status === 404) return "You cannot manage this channel.";
  if (status === 409) return "The channel changed or that name is already in use. Refresh and try again.";
  return "The channel settings could not be completed safely.";
}

export function NativeChannelSettings({
  channel,
  endpoint,
}: {
  channel: NativeChannel;
  endpoint: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!channel.can_manage || !endpoint) return null;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const description = String(form.get("description") ?? "").trim();
    if (!name) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${endpoint}/settings`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description: description || null,
          expected_revision: channel.settings_revision,
        }),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setError("The channel settings could not reach the secure Brain route.");
    } finally {
      setBusy(false);
    }
  }

  async function archive() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${endpoint}/archive`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: channel.settings_revision }),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      window.location.assign(
        `?organizationId=${encodeURIComponent(channel.organization_id)}#native-chat`,
      );
    } catch {
      setError("The channel archive request could not reach the secure Brain route.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className={styles.settings}>
      <summary>Channel settings</summary>
      <form onSubmit={save}>
        <label>
          <span>Name</span>
          <input name="name" maxLength={160} defaultValue={channel.name} required />
        </label>
        <label>
          <span>Description</span>
          <input
            name="description"
            maxLength={500}
            defaultValue={channel.description ?? ""}
          />
        </label>
        <p>
          Visibility stays <strong>{channel.visibility}</strong>. Converting channel
          visibility is intentionally not part of this settings flow.
        </p>
        <div>
          <button disabled={busy} type="submit">Save settings</button>
          <button disabled={busy} onClick={() => void archive()} type="button">
            Archive channel
          </button>
        </div>
      </form>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
    </details>
  );
}

export function ArchivedChannelManager({
  channels,
  mutationBase,
}: {
  channels: NativeChannel[];
  mutationBase: string | null;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!channels.length) return null;

  async function restore(channel: NativeChannel) {
    if (!mutationBase || busy) return;
    setBusy(channel.id);
    setError(null);
    try {
      const response = await fetch(
        `${mutationBase}/${encodeURIComponent(channel.id)}/restore`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_revision: channel.settings_revision }),
        },
      );
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      window.location.assign(
        `?organizationId=${encodeURIComponent(channel.organization_id)}&channelId=${encodeURIComponent(channel.id)}#native-chat`,
      );
    } catch {
      setError("The channel restore request could not reach the secure Brain route.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <details className={styles.archived}>
      <summary>Archived channels ({channels.length})</summary>
      <div>
        {channels.map((channel) => (
          <article key={channel.id}>
            <span>
              <strong># {channel.name}</strong>
              <small>{channel.description ?? "No description"}</small>
            </span>
            <button
              disabled={!mutationBase || busy !== null}
              onClick={() => void restore(channel)}
              type="button"
            >
              {busy === channel.id ? "Restoring…" : "Restore"}
            </button>
          </article>
        ))}
      </div>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
    </details>
  );
}
