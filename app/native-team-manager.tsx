"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { NativeTeam } from "./brain-api";
import styles from "./native-team-manager.module.css";

function safeError(status: number): string {
  if (status === 400 || status === 422) return "The Team details were not accepted.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403 || status === 404) return "You cannot manage this Team.";
  if (status === 409) return "The Team changed or that name is already in use. Refresh and try again.";
  return "The Team change could not be completed safely.";
}

export function NativeTeamManager({
  teams,
  endpoint,
}: {
  teams: NativeTeam[];
  endpoint: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!endpoint || busy) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const description = String(form.get("description") ?? "").trim();
    if (!name) return;
    setBusy("create");
    setError(null);
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description: description || null }),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      event.currentTarget.reset();
      router.refresh();
    } catch {
      setError("The Team change could not reach the secure Brain route.");
    } finally {
      setBusy(null);
    }
  }

  async function update(event: FormEvent<HTMLFormElement>, team: NativeTeam) {
    event.preventDefault();
    if (!endpoint || busy) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    const description = String(form.get("description") ?? "").trim();
    if (!name) return;
    setBusy(team.id);
    setError(null);
    try {
      const response = await fetch(`${endpoint}/${encodeURIComponent(team.id)}`, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description: description || null,
          expected_revision: team.revision,
        }),
      });
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setError("The Team change could not reach the secure Brain route.");
    } finally {
      setBusy(null);
    }
  }

  async function lifecycle(team: NativeTeam, archived: boolean) {
    if (!endpoint || busy) return;
    setBusy(team.id);
    setError(null);
    try {
      const response = await fetch(
        `${endpoint}/${encodeURIComponent(team.id)}/${archived ? "archive" : "restore"}`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_revision: team.revision }),
        },
      );
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setError("The Team change could not reach the secure Brain route.");
    } finally {
      setBusy(null);
    }
  }

  if (!endpoint && !teams.some((team) => team.can_manage)) return null;

  return (
    <details className={styles.manager}>
      <summary>Manage Teams</summary>
      <div className={styles.body}>
        {endpoint ? (
          <form className={styles.create} onSubmit={create}>
            <strong>New Team</strong>
            <label>
              <span>Name</span>
              <input name="name" maxLength={120} placeholder="Backend" required />
            </label>
            <label>
              <span>Description</span>
              <input name="description" maxLength={500} placeholder="Optional" />
            </label>
            <button disabled={busy !== null} type="submit">
              {busy === "create" ? "Creating…" : "Create Team"}
            </button>
          </form>
        ) : null}

        <div className={styles.rows}>
          {teams.filter((team) => team.can_manage).map((team) => (
            <form
              className={styles.row}
              key={team.id}
              onSubmit={(event) => void update(event, team)}
            >
              <div>
                <strong>{team.name}</strong>
                <small>{team.status} · revision {team.revision}</small>
              </div>
              <label>
                <span>Name</span>
                <input name="name" maxLength={120} defaultValue={team.name} required />
              </label>
              <label>
                <span>Description</span>
                <input
                  name="description"
                  maxLength={500}
                  defaultValue={team.description ?? ""}
                />
              </label>
              <div className={styles.actions}>
                <button disabled={!endpoint || busy !== null} type="submit">
                  Save
                </button>
                <button
                  disabled={!endpoint || busy !== null}
                  onClick={() => void lifecycle(team, team.status === "active")}
                  type="button"
                >
                  {team.status === "active" ? "Archive" : "Restore"}
                </button>
              </div>
            </form>
          ))}
        </div>
        {error ? <p className={styles.error} role="alert">{error}</p> : null}
      </div>
    </details>
  );
}
