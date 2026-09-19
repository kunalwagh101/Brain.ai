import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("saved-message persistence is private reference-only state", () => {
  const models = read("backend/app/native_conversation_models.py");
  const migration = read(
    "backend/migrations/versions/20260919_0033_native_message_saves.py",
  );
  const start = models.indexOf("class NativeMessageSave(Base):");
  assert.ok(start >= 0);
  const saveModel = models.slice(start);

  assert.match(saveModel, /fk_native_message_save_membership/);
  assert.match(saveModel, /fk_native_message_save_message_scope/);
  assert.match(saveModel, /uq_native_message_save_user_message/);
  assert.doesNotMatch(
    saveModel,
    /body|attachment|evidence|raw_content|canonical_event|body_sha256/,
  );
  assert.match(migration, /down_revision: str \| None = "20260919_0032"/);
  assert.match(migration, /native_message_saves/);
});

test("saved list is bound to authenticated user and current visible channels", () => {
  const service = read("backend/app/native_conversation.py");
  const route = read("backend/app/routes/native_conversation.py");

  assert.match(service, /def list_saved_messages/);
  assert.match(service, /list_visible_channels/);
  assert.match(service, /NativeMessageSave\.user_id == user_id/);
  assert.match(service, /NativeMessage\.deleted_at\.is_\(None\)/);
  assert.match(route, /authorization\.user_id/);
  assert.match(route, /def list_saved\(/);
  assert.doesNotMatch(route, /saved[\s\S]{0,300}user_id: uuid\.UUID/);
});

test("save requires read visibility but not channel write permission or human authorship", () => {
  const service = read("backend/app/native_conversation.py");
  const start = service.indexOf("def save_message(");
  const end = service.indexOf("def unsave_message(", start);
  assert.ok(start >= 0 && end > start);
  const body = service.slice(start, end);

  assert.match(body, /visible_message\(/);
  assert.match(body, /message\.deleted_at is not None/);
  assert.match(body, /IntegrityError/);
  assert.doesNotMatch(body, /can_write_channel/);
  assert.doesNotMatch(body, /NativeMessageActorKind/);
});

test("retraction removes personal saves in the same lifecycle transaction", () => {
  const service = read("backend/app/native_conversation.py");
  const start = service.indexOf("def retract_message(");
  const end = service.indexOf("def list_thread_replies(", start);
  const body = service.slice(start, end);

  assert.match(body, /delete\(NativeMessageSave\)/);
  assert.ok(
    body.indexOf("delete(NativeMessageSave)") < body.indexOf("db.commit()"),
  );
});

test("browser Saved UX is same-origin and exact-message linked", () => {
  const chat = read("app/native-chat-panel.tsx");
  const panel = read("app/saved-messages-panel.tsx");
  const bff = read("app/native-chat-bff.ts");

  assert.match(chat, /Unsave message/);
  assert.match(chat, /Save message/);
  assert.match(chat, /\/saved/);
  assert.match(chat, /credentials: "same-origin"/);
  assert.match(panel, /messageId=/);
  assert.match(panel, /#native-chat/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(bff, /handleNativeSavedListBff/);
  assert.match(bff, /handleNativeSavedBff/);
  assert.doesNotMatch(
    chat + panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});

test("WorkOS activation installs Saved routes and UAT gate", () => {
  const activation = read("scripts/activate-workos-authkit.sh");
  const listRoute = read(
    "docs/workos-activation/app-api-brain-native-saved-route.ts.template",
  );
  const saveRoute = read(
    "docs/workos-activation/app-api-brain-native-save-route.ts.template",
  );

  assert.match(activation, /app-api-brain-native-saved-route\.ts\.template/);
  assert.match(activation, /app-api-brain-native-save-route\.ts\.template/);
  assert.match(activation, /saved-messages\/route\.ts/);
  assert.match(activation, /messages\/\[messageId\]\/saved\/route\.ts/);
  assert.match(activation, /UAT\/F-10\.16\.md/);
  assert.match(listRoute, /withAuth\(\)/);
  assert.match(saveRoute, /withAuth\(\)/);
  assert.match(saveRoute, /rejectCrossSiteMutation/);
});
