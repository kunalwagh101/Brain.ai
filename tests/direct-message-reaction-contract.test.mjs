import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("private DM reactions are scoped and migration-backed", () => {
  const models = read("backend/app/direct_message_models.py");
  const migration = read(
    "backend/migrations/versions/20260920_0037_direct_message_reactions.py",
  );
  assert.match(models, /class DirectMessageReaction\(Base\)/);
  assert.match(models, /fk_direct_message_reaction_message_scope/);
  assert.match(models, /fk_direct_message_reaction_membership/);
  assert.match(models, /uq_direct_message_reaction_message_user_value/);
  assert.match(migration, /down_revision: str \| None = "20260920_0036"/);
});

test("DM reaction aggregation is batched and exposes no participant list", () => {
  const service = read("backend/app/direct_messages.py");
  const routes = read("backend/app/routes/direct_messages.py");
  const start = service.indexOf("def direct_message_reaction_summaries(");
  const end = service.indexOf("\ndef _normalize_direct_reaction(", start);
  const body = service.slice(start, end);

  assert.match(body, /func\.count\(\)/);
  assert.match(body, /reacted_by_me/);
  assert.match(routes, /reactions: list\[DirectReactionRead\]/);
  assert.doesNotMatch(routes, /reacted_by(?!_me)|reaction_users|user_ids.*reaction/i);
  assert.match(routes, /reaction_map = direct_message_reaction_summaries/);
});

test("DM reaction mutation has no company-intelligence projection", () => {
  const service = read("backend/app/direct_messages.py");
  const start = service.indexOf("def add_direct_message_reaction(");
  const end = service.indexOf("\ndef mark_direct_conversation_read(", start);
  const lifecycle = service.slice(start, end);

  assert.match(lifecycle, /get_direct_message/);
  assert.match(lifecycle, /message\.deleted_at is not None/);
  assert.match(lifecycle, /IntegrityError/);
  assert.doesNotMatch(
    lifecycle,
    /RawEvent|CanonicalEvent|SearchDocument|SecurityAuditEvent|append_audit_event|WorkGraph/,
  );
});

test("DM reaction browser path is same-origin allow-listed and token-free", () => {
  const panel = read("app/direct-message-panel.tsx");
  const bff = read("app/direct-message-bff.ts");
  const route = read(
    "docs/workos-activation/app-api-brain-direct-message-reaction-route.ts.template",
  );

  assert.match(panel, /DIRECT_REACTIONS/);
  assert.match(panel, /method: active \? "PUT" : "DELETE"/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(bff, /DIRECT_REACTIONS/);
  assert.match(bff, /handleDirectMessageReaction/);
  assert.match(route, /export async function PUT/);
  assert.match(route, /export async function DELETE/);
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /sec-fetch-site/);
  assert.match(route, /request\.nextUrl\.origin/);
  assert.doesNotMatch(
    panel,
    /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i,
  );
});
