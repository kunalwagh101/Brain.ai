import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("channel administration uses optimistic settings revisions and no visibility conversion", () => {
  const api = read("app/brain-api.ts");
  const bff = read("app/native-chat-bff.ts");
  const backend = read("backend/app/native_chat.py");
  const routes = read("backend/app/routes/native_chat.py");

  assert.match(api, /settings_revision: number/);
  assert.match(api, /updateNativeChannelSettings/);
  assert.match(api, /setNativeChannelArchived/);
  assert.match(bff, /expected_revision/);
  assert.match(bff, /parseNativeChannelSettingsInput/);
  assert.match(backend, /channel\.settings_revision != expected_revision/);
  assert.match(backend, /track\.display_name = normalized_name/);
  assert.match(routes, /class NativeChannelSettingsWrite/);
  assert.doesNotMatch(
    bff.slice(
      bff.indexOf("parseNativeChannelSettingsInput"),
      bff.indexOf("parseNativeChannelLifecycleInput"),
    ),
    /visibility/,
  );
});

test("archived channel controls and restricted member access are production UI paths", () => {
  const settings = read("app/native-channel-settings.tsx");
  const chat = read("app/native-chat-panel.tsx");
  const workspace = read("app/workspace-shell.tsx");

  assert.match(settings, /Archive channel/);
  assert.match(settings, /Archived channels/);
  assert.match(settings, /Restore/);
  assert.match(settings, /credentials: "same-origin"/);
  assert.match(chat, /updateMemberAccess/);
  assert.match(chat, /Read & write/);
  assert.match(chat, /Manage restricted-channel members/);
  assert.match(workspace, /ArchivedChannelManager/);
  assert.doesNotMatch(
    settings,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});

test("WorkOS activation installs settings archive and restore routes", () => {
  const activation = read("scripts/activate-workos-authkit.sh");
  const settingsRoute = read(
    "docs/workos-activation/app-api-brain-native-channel-settings-route.ts.template",
  );
  const lifecycleRoute = read(
    "docs/workos-activation/app-api-brain-native-channel-lifecycle-route.ts.template",
  );

  for (const path of [
    "native-channels/[channelId]/settings",
    "native-channels/[channelId]/archive",
    "native-channels/[channelId]/restore",
  ]) {
    assert.match(activation, new RegExp(path.replace(/[.*+?^$\{\}()|[\]\\]/g, "\\$&")));
  }
  assert.match(settingsRoute, /withAuth\(\)/);
  assert.match(settingsRoute, /rejectCrossSiteMutation/);
  assert.match(lifecycleRoute, /withAuth\(\)/);
  assert.match(lifecycleRoute, /endsWith\("\/archive"\)/);
  assert.match(lifecycleRoute, /rejectCrossSiteMutation/);
});

test("channel settings migration follows Team-group chain", () => {
  const migration = read(
    "backend/migrations/versions/20260920_0040_native_channel_settings_revision.py",
  );
  assert.match(migration, /revision: str = "20260920_0040"/);
  assert.match(migration, /down_revision: str \| None = "20260920_0039"/);
  assert.match(migration, /settings_revision/);
});
