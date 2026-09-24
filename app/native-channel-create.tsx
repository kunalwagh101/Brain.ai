"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { NativeChannel } from "./brain-api";
import styles from "./native-chat-panel.module.css";

function safeError(status: number): string {
  if (status === 400 || status === 422) return "The channel details were not accepted.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403) return "Your current role cannot create Brain channels.";
  if (status === 404) return "The organisation is no longer available to this account.";
  if (status === 409) return "A channel with this name already exists.";
  return "The channel could not be created safely.";
}

export function NativeChannelCreate({
  organizationId,
  endpoint,
}: {
  organizationId: string;
  endpoint: string | null;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<"idle" | "working">("idle");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!endpoint) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const description = String(form.get("description") ?? "").trim();
    const visibility = String(form.get("visibility") ?? "organization");
    if (!name) {
      setError("Channel name is required.");
      return;
    }

    setState("working");
    setError(null);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description: description || null,
          visibility,
        }),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        setState("idle");
        return;
      }
      const channel = await response.json() as NativeChannel;
      router.push(
        `?organizationId=${encodeURIComponent(organizationId)}&channelId=${encodeURIComponent(channel.id)}#native-chat`,
      );
      router.refresh();
    } catch {
      setError("The channel could not reach the secure Brain route.");
      setState("idle");
    }
  }

  if (!endpoint) {
    return (
      <div className={styles.notice} role="status">
        Channel creation stays disabled until the authenticated WorkOS same-origin BFF is active.
      </div>
    );
  }

  return (
    <div className={styles.channelCreate}>
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        {open ? "Cancel channel creation" : "+ New channel"}
      </button>
      {open ? (
        <form onSubmit={submit}>
          <label>
            <span>Channel name</span>
            <input name="name" maxLength={160} placeholder="product-launch" required />
          </label>
          <label>
            <span>Description <small>optional</small></span>
            <input name="description" maxLength={500} placeholder="What this channel is for" />
          </label>
          <label>
            <span>Visibility</span>
            <select name="visibility" defaultValue="organization">
              <option value="organization">Organisation</option>
              <option value="restricted">Restricted</option>
            </select>
          </label>
          <button disabled={state === "working"} type="submit">
            {state === "working" ? "Creating…" : "Create channel"}
          </button>
        </form>
      ) : null}
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
    </div>
  );
}
