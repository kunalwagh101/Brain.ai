import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("message lifecycle schema is revisioned and append-only", () => {
  const models = read("backend/app/native_chat_models.py");
  const migration = read("backend/migrations/versions/20260918_0028_native_message_lifecycle.py");
  const retentionMigration = read(
    "backend/migrations/versions/20260918_0029_native_message_revision_retention.py",
  );
  assert.match(models, /revision: Mapped\[int\]/);
  assert.match(models, /edited_at/);
  assert.match(models, /deleted_at/);
  assert.match(models, /class NativeMessageRevision\(Base\)/);
  assert.match(models, /NativeMessageRevisionAction/);
  assert.match(migration, /down_revision: str \| None = "20260918_0027"/);
  assert.match(migration, /native_message_revisions/);
  assert.match(retentionMigration, /down_revision: str \\| None = "20260918_0028"/);
  assert.match(retentionMigration, /native_message_revisions_deleted/);
});

test("backend lifecycle is author-only, optimistic and audit-safe", () => {
  const service = read("backend/app/native_conversation.py");
  assert.match(service, /message\.actor_kind != NativeMessageActorKind\.USER/);
  assert.match(service, /message\.author_user_id != user_id/);
  assert.match(service, /can_write_channel/);
  assert.match(service, /with_for_update/);
  assert.match(service, /message\.revision != expected_revision/);
  assert.match(service, /NativeMessageRevision/);
  assert.match(service, /_audit_payload/);
  assert.doesNotMatch(service, /metadata=\{[^}]*"body":/s);
});

test("retraction removes current search mentions reactions and unread contribution", () => {
  const service = read("backend/app/native_conversation.py");
  const activity = read("backend/app/activity.py");
  const inbox = read("backend/app/activity_inbox.py");
  assert.match(service, /document\.is_deleted = True/);
  assert.match(service, /document\.content = ""/);
  assert.match(service, /delete\(NativeMessageMention\)/);
  assert.match(service, /delete\(NativeMessageReaction\)/);
  assert.match(service, /NativeMessage\.deleted_at\.is_\(None\)/);
  assert.match(activity, /message\.deleted_at is not None/);
  assert.match(activity, /NativeMessageMention\.mentioned_user_id == user_id/);
  assert.match(inbox, /NativeMessage\.deleted_at\.is_\(None\)/);
});

test("browser lifecycle mutations stay same-origin and revision-bound", () => {
  const panel = read("app/native-chat-panel.tsx");
  const bff = read("app/native-chat-bff.ts");
  const route = read("docs/workos-activation/app-api-brain-native-message-lifecycle-route.ts.template");
  assert.match(panel, /method: "PATCH"/);
  assert.match(panel, /method: "DELETE"/);
  assert.match(panel, /expected_revision: message\.revision/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(panel, /This message was retracted by its author/);
  assert.doesNotMatch(panel, /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i);
  assert.match(bff, /parseNativeMessageEditInput/);
  assert.match(bff, /parseNativeMessageRetractInput/);
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /rejectCrossSiteMutation/);
});

test("live revision observes edit and retract metadata without message content", () => {
  const live = read("app/live-updates-api.ts");
  assert.match(live, /message\.revision/);
  assert.match(live, /message\.edited_at/);
  assert.match(live, /message\.deleted_at/);
  assert.doesNotMatch(live, /message\.body|message\.body_sha256/);
});

test("WorkOS activation installs lifecycle route and UAT gate", () => {
  const activation = read("scripts/activate-workos-authkit.sh");
  assert.match(activation, /app-api-brain-native-message-lifecycle-route\.ts\.template/);
  assert.match(activation, /messages\/\[messageId\]\/route\.ts/);
  assert.match(activation, /UAT\/F-10\.12\.md/);
});

test("message revision history obeys governed retention", () => {
  const governance = read("backend/app/data_governance.py");
  const models = read("backend/app/data_governance_models.py");
  const route = read("backend/app/routes/data_governance.py");
  assert.match(governance, /_purge_native_message_revisions/);
  assert.match(governance, /policy\.derived_content_days/);
  assert.match(governance, /native_message_revisions_deleted/);
  assert.match(models, /native_message_revisions_deleted/);
  assert.match(route, /native_message_revisions_deleted/);
});

test("human lifecycle service explicitly rejects agent-authored messages", () => {
  const service = read("backend/app/native_conversation.py");
  assert.match(service, /message\.actor_kind != NativeMessageActorKind\.USER/);
  assert.match(service, /message\.author_user_id != user_id/);
});
