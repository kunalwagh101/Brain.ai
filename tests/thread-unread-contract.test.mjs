import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("thread read state is scoped, monotonic and migration-backed", () => {
  const models = read("backend/app/native_conversation_models.py");
  const migration = read(
    "backend/migrations/versions/20260920_0036_native_thread_read_states.py",
  );
  const service = read("backend/app/native_conversation.py");

  assert.match(models, /class NativeThreadReadState\(Base\)/);
  assert.match(models, /uq_native_thread_read_state_root_user/);
  assert.match(migration, /down_revision: str \| None = "20260919_0035"/);
  assert.match(service, /def mark_thread_read/);
  assert.match(service, /cursor > state\.last_read_sequence/);
  assert.match(service, /through\.thread_root_id != root\.id/);
});

test("thread unread summary is set-based and excludes own/retracted replies", () => {
  const service = read("backend/app/native_conversation.py");
  const start = service.indexOf("def thread_unread_summaries(");
  const end = service.indexOf("\ndef mark_thread_read(", start);
  const body = service.slice(start, end);

  assert.match(body, /func\.count\(\)\s*\.over/);
  assert.match(body, /func\.row_number\(\)/);
  assert.match(body, /NativeMessage\.deleted_at\.is_\(None\)/);
  assert.match(body, /NativeMessage\.author_user_id != user_id/);
  assert.match(body, /NativeMessage\.message_sequence\s*> NativeThreadReadState\.last_read_sequence/);
  assert.match(body, /NativeThreadReadState\.organization_id/);
  assert.match(body, /NativeThreadReadState\.channel_id/);
  assert.doesNotMatch(body, /for root in roots:/);
});

test("thread resume UI captures first unread and uses same-origin mark-read", () => {
  const panel = read("app/native-chat-panel.tsx");
  const route = read(
    "docs/workos-activation/app-api-brain-native-thread-read-route.ts.template",
  );
  assert.match(panel, /thread_first_unread_reply_id/);
  assert.match(panel, /New replies/);
  assert.match(panel, /Jump to unread/);
  assert.match(panel, /thread-read/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /rejectCrossSiteMutation/);
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});
