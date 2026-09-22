import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("DM lifecycle persistence is private and revisioned", () => {
  const models = read("backend/app/direct_message_models.py");
  const migration = read(
    "backend/migrations/versions/20260919_0035_direct_message_lifecycle.py",
  );

  assert.match(models, /class DirectMessageRevision\(Base\)/);
  assert.match(models, /fk_direct_message_revision_message_scope/);
  assert.match(models, /uq_direct_message_revision_message_revision/);
  assert.match(models, /revision: Mapped\[int\]/);
  assert.match(models, /deleted_at/);
  assert.match(migration, /down_revision: str \| None = "20260919_0034"/);
  assert.match(migration, /direct_message_revisions/);
});

test("DM lifecycle service is author and current-epoch scoped with optimistic concurrency", () => {
  const service = read("backend/app/direct_messages.py");
  const lifecycleStart = service.indexOf("def _visible_direct_message_for_update(");
  const sendStart = service.indexOf("\ndef send_direct_message(", lifecycleStart);
  assert.ok(lifecycleStart >= 0 && sendStart > lifecycleStart);
  const lifecycle = service.slice(lifecycleStart, sendStart);

  assert.match(lifecycle, /message\.author_user_id != user_id/);
  assert.match(lifecycle, /DirectMessage\.sequence >= visible_from_sequence/);
  assert.match(lifecycle, /expected_revision != message\.revision/);
  assert.match(lifecycle, /DirectMessageRevision/);
  assert.match(lifecycle, /action="edit"/);
  assert.match(lifecycle, /action="retract"/);
  assert.doesNotMatch(
    lifecycle,
    /RawEvent|CanonicalEvent|SearchDocument|WorkGraph|SecurityAuditEvent|append_audit_event/,
  );
});

test("retracted DMs are excluded from unread attention and serialized as tombstones", () => {
  const service = read("backend/app/direct_messages.py");
  const routes = read("backend/app/routes/direct_messages.py");

  const unreadStart = service.indexOf("def _direct_unread_summaries(");
  const listStart = service.indexOf("\ndef list_direct_conversations(", unreadStart);
  const unread = service.slice(unreadStart, listStart);
  assert.match(unread, /DirectMessage\.deleted_at\.is_\(None\)/);
  assert.match(routes, /body="" if deleted else message\.body/);
  assert.match(routes, /body_sha256="" if deleted else message\.body_sha256/);
  assert.match(routes, /can_edit=is_mine and not deleted/);
  assert.match(routes, /can_delete=is_mine and not deleted/);
});

test("DM lifecycle browser path is same-origin, revision-aware and author-affordance driven", () => {
  const panel = read("app/direct-message-panel.tsx");
  const bff = read("app/direct-message-bff.ts");
  const route = read(
    "docs/workos-activation/app-api-brain-direct-message-exact-route.ts.template",
  );

  assert.match(panel, /expected_revision: message\.revision/);
  assert.match(panel, /method: "PATCH"/);
  assert.match(panel, /method: "DELETE"/);
  assert.match(panel, /message\.can_edit/);
  assert.match(panel, /message\.can_delete/);
  assert.match(panel, /This direct message was retracted by its author/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(bff, /handleDirectMessageEdit/);
  assert.match(bff, /handleDirectMessageRetract/);
  assert.match(route, /export async function PATCH/);
  assert.match(route, /export async function DELETE/);
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /sec-fetch-site/);
  assert.match(route, /request\.nextUrl\.origin/);
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});
