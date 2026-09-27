import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("channel group schema keeps navigation references separate from ACLs", () => {
  const workspaceModels = read("backend/app/native_workspace_models.py");
  const channelModels = read("backend/app/native_chat_models.py");
  const service = read("backend/app/native_workspace.py");
  const migration = read(
    "backend/migrations/versions/20260920_0039_native_channel_groups.py",
  );

  assert.match(workspaceModels, /class NativeChannelGroup\(Base\)/);
  assert.match(channelModels, /team_id: Mapped\[uuid\.UUID \| None\]/);
  assert.match(channelModels, /channel_group_id: Mapped\[uuid\.UUID \| None\]/);
  const start = service.indexOf("def assign_channel_navigation(");
  const body = service.slice(start);
  assert.match(body, /can_manage_channel/);
  assert.match(body, /_managed_active_team/);
  assert.match(body, /_managed_group/);
  assert.doesNotMatch(body, /_grant_channel_history|_revoke_channel_grants|ResourceGrant|NativeChannelMembership/);
  assert.match(migration, /down_revision: str \| None = "20260920_0038"/);
});

test("nested workspace renders only already-authorised channels with fallbacks", () => {
  const production = read("app/production-workspace.tsx");
  const shell = read("app/workspace-shell.tsx");

  assert.match(production, /listNativeChannelGroups\(accessToken, organization\.id, true\)/);
  assert.match(shell, /activeGroupsByTeam/);
  assert.match(shell, /Ungrouped/);
  assert.match(shell, /globalUnassignedChannels/);
  assert.match(shell, /Unassigned channels/);
  assert.match(shell, /Direct messages/);
  assert.doesNotMatch(shell, /team.*grant|group.*grant/i);
});

test("channel-group management is same-origin and no browser bearer token is exposed", () => {
  const panel = read("app/native-channel-group-manager.tsx");
  const bff = read("app/native-team-bff.ts");
  const assignment = read(
    "docs/workos-activation/app-api-brain-native-channel-assignment-route.ts.template",
  );
  const groups = read(
    "docs/workos-activation/app-api-brain-native-team-groups-route.ts.template",
  );

  assert.match(panel, /credentials: "same-origin"/);
  assert.match(panel, /channel-assignment/);
  assert.match(bff, /handleNativeChannelAssignment/);
  assert.match(bff, /channel_group_id requires team_id/);
  assert.match(assignment, /withAuth\(\)/);
  assert.match(assignment, /rejectCrossSiteMutation/);
  assert.match(groups, /withAuth\(\)/);
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});
