import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("native Teams are navigation-only revisioned metadata", () => {
  const model = read("backend/app/native_workspace_models.py");
  const service = read("backend/app/native_workspace.py");
  const migration = read("backend/migrations/versions/20260920_0038_native_teams.py");

  assert.match(model, /class NativeTeam\(Base\)/);
  assert.match(model, /revision >= 1/);
  assert.match(service, /def can_manage_team/);
  assert.match(service, /team\.revision != expected_revision/);
  assert.doesNotMatch(service, /ResourceGrant|NativeChannelMembership|DirectConversation/);
  assert.match(migration, /down_revision: str \| None = "20260920_0037"/);
  assert.match(migration, /drop_table\("native_teams"\)/);
});

test("Team browser mutations use same-origin WorkOS routes without client tokens", () => {
  const panel = read("app/native-team-manager.tsx");
  const bff = read("app/native-team-bff.ts");
  const createRoute = read("docs/workos-activation/app-api-brain-native-teams-route.ts.template");
  const updateRoute = read("docs/workos-activation/app-api-brain-native-team-route.ts.template");
  const lifecycleRoute = read(
    "docs/workos-activation/app-api-brain-native-team-lifecycle-route.ts.template",
  );

  assert.match(panel, /credentials: "same-origin"/);
  assert.match(panel, /expected_revision/);
  assert.match(bff, /requireBrainOrganizationMembership/);
  for (const route of [createRoute, updateRoute, lifecycleRoute]) {
    assert.match(route, /withAuth\(\)/);
    assert.match(route, /rejectCrossSiteMutation/);
  }
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});

test("workspace renders Teams and keeps every visible channel in unassigned fallback", () => {
  const production = read("app/production-workspace.tsx");
  const shell = read("app/workspace-shell.tsx");

  assert.match(production, /listNativeTeams\(accessToken, organization\.id, true\)/);
  assert.match(shell, /<span>Teams<\/span>/);
  assert.match(shell, /Unassigned channels/);
  assert.match(shell, /nativeChannels\.map/);
  assert.match(shell, /<NativeTeamManager/);
  assert.match(shell, /Direct messages/);
});
