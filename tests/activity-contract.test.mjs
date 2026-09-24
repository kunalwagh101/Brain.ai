import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Activity UI is reference-only and never handles backend bearer tokens", () => {
  const panel = read("app/activity-panel.tsx");
  const api = read("app/activity-api.ts");
  assert.match(panel, /does not copy private message text into this inbox/);
  assert.match(panel, /credentials:\s*"same-origin"/);
  assert.doesNotMatch(panel, /Authorization|Bearer|accessToken|body_sha256|message\.body/i);
  assert.match(api, /Authorization: `Bearer \$\{accessToken\}`/);
});

test("Activity supports the full attention queue and exact source links", () => {
  const api = read("app/activity-api.ts");
  const backend = read("backend/app/activity_inbox.py");
  for (const kind of [
    "channel_activity",
    "agent_approval",
    "agent_completed",
    "agent_failed",
    "project_update",
    "blocker_update",
    "integration_failure",
  ]) {
    assert.match(api, new RegExp(kind));
    assert.match(backend, new RegExp(kind.toUpperCase()));
  }
  assert.match(backend, /messageId=/);
  assert.match(backend, /threadRootId=/);
  assert.match(backend, /agentRunId=/);
  assert.match(backend, /agentStepId=/);
  assert.match(backend, /projectId=/);
  assert.match(backend, /blockerId=/);
  assert.match(backend, /integrationId=/);
});

test("Activity notification preferences are explicit, personal and same-origin", () => {
  const panel = read("app/activity-panel.tsx");
  const api = read("app/activity-api.ts");
  const bff = read("app/activity-bff.ts");
  const route = read("docs/workos-activation/app-api-brain-activity-preferences-route.ts.template");
  const activation = read("scripts/activate-workos-authkit.sh");

  for (const key of [
    "mentions",
    "thread_replies",
    "direct_messages",
    "channel_activity",
    "agent_approvals",
    "agent_run_events",
    "project_updates",
    "integration_failures",
  ]) {
    assert.match(api, new RegExp(key));
    assert.match(panel, new RegExp(key));
    assert.match(bff, new RegExp(key));
  }
  assert.match(panel, /type="checkbox"/);
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /MAX_BODY_BYTES = 4096/);
  assert.match(route, /sec-fetch-site/);
  assert.match(route, /request\.nextUrl\.origin/);
  assert.match(activation, /activity\/preferences/);
  assert.doesNotMatch(panel, /localStorage|sessionStorage|indexedDB/i);
});

test("Activity server composition loads permission-filtered summary and exposes global dock", () => {
  const production = read("app/production-workspace.tsx");
  assert.match(production, /getActivity\(accessToken, organization\.id\)/);
  assert.match(production, /<ActivityDock/);
  assert.match(production, /activityMutationBase/);
  assert.match(production, /enableActivityBff/);
});

test("Activity WorkOS mutations are session-bound and same-origin", () => {
  const one = read("docs/workos-activation/app-api-brain-activity-read-route.ts.template");
  const all = read("docs/workos-activation/app-api-brain-activity-read-all-route.ts.template");
  const preferences = read("docs/workos-activation/app-api-brain-activity-preferences-route.ts.template");
  const activation = read("scripts/activate-workos-authkit.sh");
  for (const route of [one, all, preferences]) {
    assert.match(route, /withAuth\(\)/);
    assert.doesNotMatch(route, /secret_ref|WORKOS_API_KEY|localStorage|sessionStorage/);
  }
  for (const route of [one, all, preferences]) {
    if (!route.includes("export async function PUT") && !route.includes("export async function POST")) continue;
    assert.match(route, /sec-fetch-site/);
    assert.match(route, /request\.nextUrl\.origin/);
  }
  assert.match(activation, /activity\/\[notificationId\]\/read/);
  assert.match(activation, /activity\/read-all/);
  assert.match(activation, /activity\/preferences/);
});

test("Activity backend re-checks source visibility before rendering", () => {
  const chat = read("backend/app/activity.py");
  const inbox = read("backend/app/activity_inbox.py");
  assert.match(chat, /can_read_channel/);
  assert.match(chat, /participant_a_visible_from_sequence/);
  assert.match(chat, /participant_b_visible_from_sequence/);
  assert.match(chat, /Permission\.NATIVE_CHAT_WRITE/);
  assert.match(inbox, /node_visible_to_user/);
  assert.match(inbox, /Permission\.AGENT_MANAGE/);
  assert.match(inbox, /Permission\.INTEGRATION_MANAGE/);
  assert.doesNotMatch(`${chat}\n${inbox}`, /body=/);
});

test("Activity migrations keep one reference-only inbox contract", () => {
  const base = read("backend/migrations/versions/20260918_0025_activity_notifications.py");
  const merge = read("backend/migrations/versions/20260918_0026_merge_notification_heads.py");
  const extension = read("backend/migrations/versions/20260918_0027_activity_inbox_extension.py");
  assert.match(base, /activity_notifications/);
  assert.match(base, /resource_id/);
  assert.match(base, /dedupe_key/);
  assert.match(merge, /20260917_0025/);
  assert.match(merge, /20260918_0025/);
  assert.match(extension, /activity_preferences/);
  assert.doesNotMatch(`${base}\n${extension}`, /message_body|body_preview|excerpt/);
});
