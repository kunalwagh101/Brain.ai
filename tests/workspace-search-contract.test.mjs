import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("workspace search is keyboard-first and same-origin", () => {
  const component = read("app/workspace-search.tsx");
  assert.match(component, /event\.metaKey \|\| event\.ctrlKey/);
  assert.match(component, /showModal\(\)/);
  assert.match(component, /requestAnimationFrame/);
  assert.match(component, /250/);
  assert.match(component, /credentials: "same-origin"/);
  assert.match(component, /query\.trim\(\)\.length >= 2/);
  assert.doesNotMatch(component, /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i);
});

test("workspace search uses existing authorised navigation and Search API", () => {
  const component = read("app/workspace-search.tsx");
  const api = read("app/brain-api.ts");
  assert.match(component, /channels\.map/);
  assert.match(component, /projects\.map/);
  assert.match(component, /tracks\.map/);
  assert.match(component, /directConversations\.map/);
  assert.match(api, /searchWorkspaceDocuments/);
  assert.match(api, /mode: "keyword"/);
});

test("workspace search BFF revalidates membership and bounds response text", () => {
  const bff = read("app/workspace-search-bff.ts");
  assert.match(bff, /requireBrainOrganizationMembership/);
  assert.match(bff, /query\.length < 2 \|\| query\.length > 120/);
  assert.match(bff, /280/);
  assert.match(bff, /source_provider === "brain_native"/);
  assert.match(bff, /native_message_id/);
  assert.match(bff, /#message-/);
  assert.doesNotMatch(bff, /direct_messages|DirectMessage|dmFetch/);
});

test("WorkOS search route keeps reusable tokens server-side", () => {
  const route = read("docs/workos-activation/app-api-brain-search-route.ts.template");
  const activation = read("scripts/activate-workos-authkit.sh");
  const page = read("docs/workos-activation/app-page.tsx.template");
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /handleWorkspaceSearch/);
  assert.match(route, /no-store, private/);
  assert.match(route, /Vary/);
  assert.doesNotMatch(route, /localStorage|sessionStorage|indexedDB/);
  assert.match(activation, /app-api-brain-search-route\.ts\.template/);
  assert.match(page, /enableWorkspaceSearchBff/);
  assert.match(page, /requestedMessageId/);
});

test("native message deep links are permission-aware and message-addressable", () => {
  const routes = read("backend/app/routes/native_conversation.py");
  const panel = read("app/native-chat-panel.tsx");
  const workspace = read("app/production-workspace.tsx");
  assert.match(routes, /\/channels\/\{channel_id\}\/messages\/\{message_id\}/);
  assert.match(routes, /visible_message/);
  assert.match(panel, /message-\$\{message\.id\}/);
  assert.match(panel, /requestedMessage/);
  assert.match(workspace, /getNativeMessage/);
});
