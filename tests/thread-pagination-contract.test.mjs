import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("thread reply history uses stable bounded sequence cursors", () => {
  const service = read("backend/app/native_conversation.py");
  const routes = read("backend/app/routes/native_conversation.py");
  const bff = read("app/native-chat-bff.ts");

  const start = service.indexOf("def list_thread_replies(");
  const end = service.indexOf("\ndef list_saved_messages(", start);
  const body = service.slice(start, end);
  assert.match(body, /NativeMessage\.thread_root_id == root_message_id/);
  assert.match(body, /NativeMessage\.message_sequence < before_sequence/);
  assert.match(body, /message_sequence\.desc\(\)/);
  assert.doesNotMatch(body, /offset\(/i);
  assert.match(routes, /before_sequence: Annotated\[int \| None, Query\(ge=1\)\]/);
  assert.match(bff, /handleNativeThreadListBff/);
  assert.match(bff, /limit < 1 \|\| limit > 200/);
});

test("thread WorkOS GET accepts bounded cursor without browser bearer tokens", () => {
  const route = read(
    "docs/workos-activation/app-api-brain-native-replies-route.ts.template",
  );
  const panel = read("app/native-chat-panel.tsx");

  assert.match(route, /request\.nextUrl\.searchParams\.get\("before_sequence"\)/);
  assert.match(route, /withAuth\(\)/);
  assert.match(panel, /Load older replies/);
  assert.match(panel, /before_sequence/);
  assert.match(panel, /threadBeforeSequence/);
  assert.match(panel, /new Map/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});
