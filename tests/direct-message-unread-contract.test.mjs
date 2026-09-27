import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("DM unread state is participant cursor state with an epoch-safe migration", () => {
  const models = read("backend/app/direct_message_models.py");
  const migration = read(
    "backend/migrations/versions/20260919_0034_direct_message_read_cursors.py",
  );
  const service = read("backend/app/direct_messages.py");

  assert.match(models, /participant_a_last_read_sequence/);
  assert.match(models, /participant_b_last_read_sequence/);
  assert.match(models, /last_read_sequence >= participant_a_visible_from_sequence - 1/);
  assert.match(migration, /down_revision: str \| None = "20260919_0033"/);
  assert.match(migration, /visible_from_sequence - 1/);
  assert.match(service, /participant_a_last_read_sequence = conversation\.next_message_sequence - 1/);
  assert.match(service, /participant_b_last_read_sequence = conversation\.next_message_sequence - 1/);
});

test("DM unread summaries are set-based and exclude the current user's messages", () => {
  const service = read("backend/app/direct_messages.py");
  const start = service.indexOf("def _direct_unread_summaries(");
  const end = service.indexOf("\ndef list_direct_conversations(", start);
  assert.ok(start >= 0 && end > start);
  const body = service.slice(start, end);

  assert.match(body, /func\.count\(\)\s*\.over/);
  assert.match(body, /func\.row_number\(\)/);
  assert.match(body, /DirectMessage\.author_user_id != user_id/);
  assert.match(body, /DirectMessage\.sequence >= visible_from/);
  assert.match(body, /DirectMessage\.sequence > last_read/);
  assert.doesNotMatch(body, /for conversation in conversations:/);
});

test("DM resume UI has unread badges, divider, jump and same-origin exact recovery", () => {
  const panel = read("app/direct-message-panel.tsx");
  const shell = read("app/workspace-shell.tsx");

  assert.match(panel, /Jump to unread/);
  assert.match(panel, /New direct messages begin here/);
  assert.match(panel, /dm-first-unread-/);
  assert.match(panel, /role="separator"/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(panel, /cache: "no-store"/);
  assert.match(shell, /conversation\.unread_count/);
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});

test("DM exact read and mark-read routes remain WorkOS server-session only", () => {
  const exact = read(
    "docs/workos-activation/app-api-brain-direct-message-exact-route.ts.template",
  );
  const markRead = read(
    "docs/workos-activation/app-api-brain-direct-message-read-route.ts.template",
  );
  const activation = read("scripts/activate-workos-authkit.sh");

  assert.match(exact, /withAuth\(\)/);
  assert.match(exact, /handleDirectMessageRead/);
  assert.match(markRead, /withAuth\(\)/);
  assert.match(markRead, /handleDirectMessageMarkRead/);
  assert.match(markRead, /sec-fetch-site/);
  assert.match(markRead, /request\.nextUrl\.origin/);
  assert.match(activation, /direct-message-exact-route\.ts\.template/);
  assert.match(activation, /direct-message-read-route\.ts\.template/);
});
