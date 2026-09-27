import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("unread summary exposes first unread with one set-based window query", () => {
  const service = read("backend/app/native_conversation.py");
  const route = read("backend/app/routes/native_conversation.py");
  const start = service.indexOf("def channel_unread_summaries(");
  const end = service.indexOf("\ndef mark_read(", start);
  assert.ok(start >= 0 && end > start);
  const body = service.slice(start, end);

  assert.match(body, /unread_ranked/);
  assert.match(body, /func\.count\(\)\s*\.over\(partition_by=NativeMessage\.channel_id\)/);
  assert.match(body, /func\.row_number\(\)/);
  assert.match(body, /order_by=NativeMessage\.message_sequence/);
  assert.match(body, /unread_ranked\.c\.unread_rank == 1/);
  assert.doesNotMatch(body, /for channel in channels:/);
  assert.match(route, /first_unread_message_id/);
});

test("first-unread UI is accessible and survives read-refresh remounts", () => {
  const panel = read("app/native-chat-panel.tsx");
  const shell = read("app/workspace-shell.tsx");

  assert.match(panel, /Jump to unread/);
  assert.match(panel, /New messages begin here/);
  assert.match(panel, /role="separator"/);
  assert.match(panel, /first-unread-/);
  assert.match(panel, /scrollIntoView/);
  assert.match(panel, /focus\(\{ preventScroll: true \}\)/);
  assert.match(shell, /key=\{selectedNativeChannel\.id\}/);
  assert.doesNotMatch(
    shell,
    /key=\{\`\$\{selectedNativeChannel\.id\}:\$\{selectedNativeChannel\.latest_message_id/,
  );
});

test("jump recovery reuses exact permission-aware same-origin message read", () => {
  const panel = read("app/native-chat-panel.tsx");
  const bff = read("app/native-chat-bff.ts");
  const route = read(
    "docs/workos-activation/app-api-brain-native-message-lifecycle-route.ts.template",
  );
  const backend = read("backend/app/routes/native_conversation.py");

  assert.match(panel, /credentials: "same-origin"/);
  assert.match(panel, /cache: "no-store"/);
  assert.match(panel, /thread_root_id/);
  assert.match(bff, /handleNativeMessageReadBff/);
  assert.match(bff, /requireChatReader/);
  assert.match(bff, /getNativeMessage/);
  assert.match(route, /export async function GET/);
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /handleNativeMessageReadBff/);
  assert.match(backend, /def read_message\(/);
  assert.match(backend, /visible_message\(/);
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});

test("first-unread adds no persistence or migration surface", () => {
  const api = read("app/brain-api.ts");
  const service = read("backend/app/native_conversation.py");

  assert.match(api, /first_unread_message_id/);
  assert.match(service, /NativeChannelReadState\.last_read_sequence/);
  assert.doesNotMatch(service, /class FirstUnread|FirstUnreadState|first_unread_table/i);
});
