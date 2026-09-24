import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("channel and DM history use stable sequence cursors without OFFSET", () => {
  const channel = read("backend/app/native_chat.py");
  const dm = read("backend/app/direct_messages.py");
  assert.match(channel, /NativeMessage\.message_sequence < before_sequence/);
  assert.match(dm, /DirectMessage\.sequence < before_sequence/);
  assert.match(dm, /DirectMessage\.sequence >= visible_from_sequence/);
  assert.doesNotMatch(channel + dm, /\.offset\(|OFFSET\s/i);
});

test("history cursor inputs are bounded by backend and BFF", () => {
  const nativeRoutes = read("backend/app/routes/native_conversation.py");
  const dmRoutes = read("backend/app/routes/direct_messages.py");
  const nativeBff = read("app/native-chat-bff.ts");
  const dmBff = read("app/direct-message-bff.ts");

  assert.match(nativeRoutes, /before_sequence: Annotated\[int \| None, Query\(ge=1\)\]/);
  assert.match(dmRoutes, /before_sequence: Annotated\[int \| None, Query\(ge=1\)\]/);
  assert.match(nativeBff, /limit < 1 \|\| limit > 200/);
  assert.match(dmBff, /limit < 1 \|\| limit > 200/);
  assert.match(nativeBff, /beforeSequence < 1/);
  assert.match(dmBff, /beforeSequence < 1/);
});

test("both WorkOS message routes expose server-authenticated history GET", () => {
  const nativeRoute = read(
    "docs/workos-activation/app-api-brain-native-messages-route.ts.template",
  );
  const dmRoute = read(
    "docs/workos-activation/app-api-brain-direct-message-route.ts.template",
  );
  assert.match(nativeRoute, /export async function GET/);
  assert.match(nativeRoute, /withAuth\(\)/);
  assert.match(nativeRoute, /handleNativeMessageListBff/);
  assert.match(dmRoute, /export async function GET/);
  assert.match(dmRoute, /withAuth\(\)/);
  assert.match(dmRoute, /handleDirectMessageList/);
});

test("channel and DM panels load older pages without browser bearer tokens", () => {
  const channel = read("app/native-chat-panel.tsx");
  const dm = read("app/direct-message-panel.tsx");

  for (const source of [channel, dm]) {
    assert.match(source, /Load older messages/);
    assert.match(source, /before_sequence/);
    assert.match(source, /limit: "50"/);
    assert.match(source, /credentials: "same-origin"/);
    assert.match(source, /cache: "no-store"/);
    assert.match(source, /new Map/);
    assert.doesNotMatch(
      source,
      /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
    );
  }
});
