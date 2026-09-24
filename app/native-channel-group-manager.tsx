"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import type { NativeChannel, NativeChannelGroup, NativeTeam } from "./brain-api";
import styles from "./native-channel-group-manager.module.css";

function safeError(status: number): string {
  if (status === 400 || status === 422) return "The channel-group change was not accepted.";
  if (status === 401) return "Your session is no longer authenticated.";
  if (status === 403 || status === 404) return "You cannot manage that Team, group or channel.";
  if (status === 409) return "The group changed or that name is already in use. Refresh and try again.";
  return "The channel-group change could not be completed safely.";
}

function channelTarget(channel: NativeChannel, activeGroupIds: Set<string>): string {
  if (!channel.team_id) return "unassigned";
  if (channel.channel_group_id && activeGroupIds.has(channel.channel_group_id)) {
    return `group:${channel.team_id}:${channel.channel_group_id}`;
  }
  return `team:${channel.team_id}`;
}

export function NativeChannelGroupManager({
  teams,
  groups,
  channels,
  endpoint,
}: {
  teams: NativeTeam[];
  groups: NativeChannelGroup[];
  channels: NativeChannel[];
  endpoint: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeTeams = teams.filter((team) => team.status === "active");
  const managedTeams = activeTeams.filter((team) => team.can_manage);
  const activeGroups = groups.filter((group) => group.status === "active");
  const activeGroupIds = new Set(activeGroups.map((group) => group.id));
  const managedChannels = channels.filter((channel) => channel.can_manage);

  async function createGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!endpoint || busy) return;
    const form = new FormData(event.currentTarget);
    const teamId = String(form.get("team_id") ?? "");
    const name = String(form.get("name") ?? "").trim();
    if (!teamId || !name) return;
    setBusy("create-group");
    setError(null);
    try {
      const response = await fetch(
        `${endpoint}/${encodeURIComponent(teamId)}/groups`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        },
      );
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      event.currentTarget.reset();
      router.refresh();
    } catch {
      setError("The channel-group change could not reach the secure Brain route.");
    } finally {
      setBusy(null);
    }
  }

  async function updateGroup(event: FormEvent<HTMLFormElement>, group: NativeChannelGroup) {
    event.preventDefault();
    if (!endpoint || busy) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") ?? "").trim();
    if (!name) return;
    setBusy(group.id);
    setError(null);
    try {
      const response = await fetch(
        `${endpoint}/${encodeURIComponent(group.team_id)}/groups/${encodeURIComponent(group.id)}`,
        {
          method: "PATCH",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, expected_revision: group.revision }),
        },
      );
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setError("The channel-group change could not reach the secure Brain route.");
    } finally {
      setBusy(null);
    }
  }

  async function groupLifecycle(group: NativeChannelGroup, archived: boolean) {
    if (!endpoint || busy) return;
    setBusy(group.id);
    setError(null);
    try {
      const response = await fetch(
        `${endpoint}/${encodeURIComponent(group.team_id)}/groups/${encodeURIComponent(group.id)}/${archived ? "archive" : "restore"}`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_revision: group.revision }),
        },
      );
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setError("The channel-group change could not reach the secure Brain route.");
    } finally {
      setBusy(null);
    }
  }

  async function assignChannel(event: FormEvent<HTMLFormElement>, channel: NativeChannel) {
    event.preventDefault();
    if (!endpoint || busy) return;
    const form = new FormData(event.currentTarget);
    const target = String(form.get("target") ?? "unassigned");
    let teamId: string | null = null;
    let groupId: string | null = null;
    if (target.startsWith("team:")) {
      teamId = target.slice("team:".length);
    } else if (target.startsWith("group:")) {
      const [, targetTeam, targetGroup] = target.split(":");
      teamId = targetTeam || null;
      groupId = targetGroup || null;
    }
    setBusy(channel.id);
    setError(null);
    try {
      const response = await fetch(
        `${endpoint}/channel-assignment/${encodeURIComponent(channel.id)}`,
        {
          method: "PATCH",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            team_id: teamId,
            channel_group_id: groupId,
          }),
        },
      );
      if (!response.ok) {
        setError(safeError(response.status));
        return;
      }
      router.refresh();
    } catch {
      setError("The channel move could not reach the secure Brain route.");
    } finally {
      setBusy(null);
    }
  }

  if (!endpoint || (!managedTeams.length && !managedChannels.length)) return null;

  return (
    <details className={styles.manager}>
      <summary>Manage channel groups</summary>
      <div className={styles.body}>
        {managedTeams.length ? (
          <form className={styles.form} onSubmit={createGroup}>
            <strong>New group</strong>
            <select name="team_id" required defaultValue="">
              <option value="" disabled>Choose Team</option>
              {managedTeams.map((team) => (
                <option key={team.id} value={team.id}>{team.name}</option>
              ))}
            </select>
            <input name="name" maxLength={120} placeholder="Backend services" required />
            <button disabled={busy !== null} type="submit">Create group</button>
          </form>
        ) : null}

        {groups.filter((group) => group.can_manage).map((group) => (
          <form
            className={styles.form}
            key={group.id}
            onSubmit={(event) => void updateGroup(event, group)}
          >
            <strong>{group.name}</strong>
            <small>{group.status} · revision {group.revision}</small>
            <input name="name" maxLength={120} defaultValue={group.name} required />
            <div className={styles.actions}>
              <button disabled={busy !== null} type="submit">Save</button>
              <button
                disabled={busy !== null}
                onClick={() => void groupLifecycle(group, group.status === "active")}
                type="button"
              >
                {group.status === "active" ? "Archive" : "Restore"}
              </button>
            </div>
          </form>
        ))}

        {managedChannels.length ? (
          <div className={styles.assignments}>
            <strong>Channel placement</strong>
            {managedChannels.map((channel) => (
              <form
                className={styles.assignment}
                key={channel.id}
                onSubmit={(event) => void assignChannel(event, channel)}
              >
                <span># {channel.name}</span>
                <select
                  name="target"
                  defaultValue={channelTarget(channel, activeGroupIds)}
                >
                  <option value="unassigned">Unassigned channels</option>
                  {managedTeams.map((team) => (
                    <optgroup key={team.id} label={team.name}>
                      <option value={`team:${team.id}`}>Ungrouped in {team.name}</option>
                      {activeGroups
                        .filter((group) => group.team_id === team.id)
                        .map((group) => (
                          <option
                            key={group.id}
                            value={`group:${team.id}:${group.id}`}
                          >
                            {group.name}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
                <button disabled={busy !== null} type="submit">Move</button>
              </form>
            ))}
          </div>
        ) : null}
        {error ? <p className={styles.error} role="alert">{error}</p> : null}
      </div>
    </details>
  );
}
