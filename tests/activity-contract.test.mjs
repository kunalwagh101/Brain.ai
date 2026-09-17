import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Activity UI is reference-only and never handles backend bearer tokens", () => {
  const panel = read("app/activity-panel.tsx");
  const api = read("app/activity-api.ts");
  assert.match(panel, /Brain does not copy private message text into this inbox/);
  assert.match(panel, /credentials:\s*"same-origin"/);
  assert.doesNotMatch(panel, /Authorization|Bearer|accessToken|body_sha256|message\.body/i);
  assert.match(api, /Authorization: `Bearer \$\{accessToken\}`/);
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
  const activation = read("scripts/activate-workos-authkit.sh");
  for (const route of [one, all]) {
    assert.match(route, /withAuth\(\)/);
    assert.match(route, /sec-fetch-site/);
    assert.match(route, /request\.nextUrl\.origin/);
    assert.doesNotMatch(route, /secret_ref|WORKOS_API_KEY|localStorage|sessionStorage/);
  }
  assert.match(activation, /activity\/\[notificationId\]\/read/);
  assert.match(activation, /activity\/read-all/);
});

test("Activity backend re-checks native channel and DM visibility before rendering", () => {
  const service = read("backend/app/activity.py");
  assert.match(service, /can_read_channel/);
  assert.match(service, /participant_a_visible_from_sequence/);
  assert.match(service, /participant_b_visible_from_sequence/);
  assert.match(service, /Permission\.NATIVE_CHAT_WRITE/);
  assert.doesNotMatch(service, /body=/);
});

test("Activity migration is reference-only and contains no copied message text column", () => {
  const migration = read("backend/migrations/versions/20260918_0025_activity_notifications.py");
  assert.match(migration, /activity_notifications/);
  assert.match(migration, /resource_id/);
  assert.match(migration, /dedupe_key/);
  assert.doesNotMatch(migration, /message_body|body_preview|content|excerpt/);
});
