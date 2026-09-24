import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("live client uses adaptive same-origin checks without browser bearer tokens", () => {
  const client = read("app/live-workspace-refresh.tsx");
  assert.match(client, /VISIBLE_INTERVAL_MS = 4_000/);
  assert.match(client, /HIDDEN_INTERVAL_MS = 30_000/);
  assert.match(client, /MAX_ERROR_BACKOFF_MS = 30_000/);
  assert.match(client, /credentials: "same-origin"/);
  assert.match(client, /router\.refresh\(\)/);
  assert.match(client, /document\.visibilityState/);
  assert.match(client, /navigator\.onLine/);
  assert.doesNotMatch(client, /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i);
});

test("live revision is structural and does not serialize message or DM bodies", () => {
  const api = read("app/live-updates-api.ts");
  assert.match(api, /crypto\.subtle\.digest\("SHA-256"/);
  assert.match(api, /reply_count/);
  assert.match(api, /selectedChannelPins/);
  assert.match(api, /pin\.pin_id/);
  assert.match(api, /pin\.message\.id/);
  assert.doesNotMatch(api, /pin\.message\.body|pin\.message\.body_sha256/);
  assert.match(api, /reacted_by_me/);
  assert.match(api, /directConversations/);
  assert.match(api, /activity\.items/);
  assert.doesNotMatch(api, /message\.body|message\.body_sha256|excerpt|secret_ref|api_key/);
});

test("live BFF revalidates membership and UUID context", () => {
  const bff = read("app/live-updates-bff.ts");
  assert.match(bff, /requireBrainOrganizationMembership/);
  assert.match(bff, /requireUuid/);
  assert.match(bff, /Only one live conversation context may be selected/);
});

test("WorkOS live route keeps the access token server-side", () => {
  const route = read("docs/workos-activation/app-api-brain-live-route.ts.template");
  const activation = read("scripts/activate-workos-authkit.sh");
  const page = read("docs/workos-activation/app-page.tsx.template");
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /handleLiveWorkspaceState/);
  assert.match(route, /Cache-Control/);
  assert.match(route, /Vary/);
  assert.doesNotMatch(route, /localStorage|sessionStorage|indexedDB/);
  assert.match(activation, /app-api-brain-live-route\.ts\.template/);
  assert.match(page, /enableLiveUpdatesBff/);
});

test("open threads refresh through the existing same-origin conversation route", () => {
  const panel = read("app/native-chat-panel.tsx");
  assert.match(panel, /threadRootId/);
  assert.match(panel, /schedule\(4_000\)/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(panel, /setThreadReplies/);
  assert.doesNotMatch(panel, /Authorization\s*:/);
});

test("production workspace derives and mounts live revision from already-loaded authorised state", () => {
  const workspace = read("app/production-workspace.tsx");
  assert.match(workspace, /computeLiveRevision/);
  assert.match(workspace, /<LiveWorkspaceRefresh/);
  assert.match(workspace, /selectedChannelMessages: nativeMessages/);
  assert.match(workspace, /selectedChannelPins: selectedNativePins/);
  assert.match(workspace, /directMessages/);
  assert.match(workspace, /enableLiveUpdatesBff/);
});
