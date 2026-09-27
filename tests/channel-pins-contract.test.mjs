import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("pin persistence is reference-only and tenant/channel scoped", () => {
  const models = read("backend/app/native_conversation_models.py");
  const migration = read(
    "backend/migrations/versions/20260919_0032_native_message_pins.py",
  );
  const start = models.indexOf("class NativeMessagePin(Base):");
  assert.ok(start >= 0);
  const pinModel = models.slice(start);

  assert.match(pinModel, /message_id/);
  assert.match(pinModel, /pinned_by_user_id/);
  assert.match(pinModel, /fk_native_message_pin_message_scope/);
  assert.match(pinModel, /uq_native_message_pin_channel_message/);
  assert.doesNotMatch(
    pinModel,
    /body|attachment|evidence|raw_content|content_sha256|canonical_event/,
  );
  assert.match(migration, /down_revision: str \| None = "20260919_0031"/);
  assert.match(migration, /native_message_pins/);
});

test("pin service uses current channel access and allows visible agent messages", () => {
  const service = read("backend/app/native_conversation.py");
  const pinStart = service.indexOf("def pin_message(");
  const unpinStart = service.indexOf("def unpin_message(", pinStart);
  assert.ok(pinStart >= 0 && unpinStart > pinStart);
  const pinBody = service.slice(pinStart, unpinStart);

  assert.match(pinBody, /visible_message\(/);
  assert.match(pinBody, /can_write_channel/);
  assert.match(pinBody, /message\.deleted_at is not None/);
  assert.match(pinBody, /IntegrityError/);
  assert.doesNotMatch(pinBody, /NativeMessageActorKind/);

  const lifecycleStart = service.indexOf("def _mutable_author_message(");
  const lifecycleEnd = service.indexOf("def _require_expected_revision", lifecycleStart);
  const lifecycleBody = service.slice(lifecycleStart, lifecycleEnd);
  assert.match(lifecycleBody, /NativeMessageActorKind\.USER/);
});

test("pin list reuses safe message materialisation and is bounded", () => {
  const service = read("backend/app/native_conversation.py");
  const routes = read("backend/app/routes/native_conversation.py");

  assert.match(service, /def list_message_pins/);
  assert.match(service, /can_read_channel/);
  assert.match(service, /NativeMessage\.deleted_at\.is_\(None\)/);
  assert.match(service, /NativeMessagePin\.created_at\.desc\(\)/);
  assert.match(routes, /class PinnedMessageRead/);
  assert.match(routes, /message: ConversationMessageRead/);
  assert.match(routes, /Query\(ge=1, le=100\)/);
  assert.match(routes, /_message_reads\(db, messages, user_id\)/);
});

test("message retraction removes active pins in the same lifecycle transaction", () => {
  const service = read("backend/app/native_conversation.py");
  const retractStart = service.indexOf("def retract_message(");
  const repliesStart = service.indexOf("def list_thread_replies(", retractStart);
  const body = service.slice(retractStart, repliesStart);

  assert.match(body, /delete\(NativeMessagePin\)/);
  assert.match(body, /db\.commit\(\)/);
  assert.ok(
    body.indexOf("delete(NativeMessagePin)") < body.indexOf("db.commit()"),
  );
});

test("browser pin mutations stay same-origin and token-free", () => {
  const panel = read("app/native-chat-panel.tsx");
  const bff = read("app/native-chat-bff.ts");
  const pinRoute = read(
    "docs/workos-activation/app-api-brain-native-pin-route.ts.template",
  );
  const pinsRoute = read(
    "docs/workos-activation/app-api-brain-native-pins-route.ts.template",
  );

  assert.match(panel, /\/messages\/\$\{encodeURIComponent\(message\.id\)\}\/pin/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(panel, /Pinned messages/);
  assert.match(panel, /Open thread/);
  assert.match(panel, /aria-pressed=\{pinned\}/);
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );

  assert.match(bff, /handleNativePinsListBff/);
  assert.match(bff, /handleNativePinBff/);
  assert.match(pinRoute, /withAuth\(\)/);
  assert.match(pinRoute, /rejectCrossSiteMutation/);
  assert.match(pinsRoute, /withAuth\(\)/);
});

test("live invalidation uses only structural pin metadata", () => {
  const live = read("app/live-updates-api.ts");

  assert.match(live, /selectedChannelPins/);
  assert.match(live, /pin\.pin_id/);
  assert.match(live, /pin\.message\.id/);
  assert.match(live, /pin\.pinned_at/);
  assert.doesNotMatch(
    live,
    /pin\.message\.body|pin\.message\.body_sha256|pin\.message\.attachments/,
  );
});

test("WorkOS activation installs pin routes and UAT gate", () => {
  const activation = read("scripts/activate-workos-authkit.sh");

  assert.match(activation, /app-api-brain-native-pins-route\.ts\.template/);
  assert.match(activation, /app-api-brain-native-pin-route\.ts\.template/);
  assert.match(activation, /pins\/route\.ts/);
  assert.match(activation, /messages\/\[messageId\]\/pin\/route\.ts/);
  assert.match(activation, /UAT\/F-10\.15\.md/);
});
