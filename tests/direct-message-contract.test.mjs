import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("direct-message panel never handles backend bearer tokens", () => {
  const panel = read("app/direct-message-panel.tsx");
  assert.match(panel, /credentials:\s*"same-origin"/);
  assert.doesNotMatch(panel, /Authorization|Bearer|accessToken|secret_ref/i);
});

test("server validates requested dm against participant-scoped list before message fetch", () => {
  const production = read("app/production-workspace.tsx");
  assert.match(production, /listDirectConversations\(accessToken, organization\.id\)/);
  assert.match(
    production,
    /requestedDirectMessageId[\s\S]*?directConversations\.find\(\(item\) => item\.id === requestedDirectMessageId\)[\s\S]*?listDirectMessages\(accessToken, organization\.id, selectedDirectConversation\.id\)/,
  );
});

test("explicit dm selection suppresses ambient default-channel context", () => {
  const production = read("app/production-workspace.tsx");
  assert.match(
    production,
    /const selectedChannel = requestedDirectMessageId\s*\? null\s*:\s*requestedChannelId/,
  );
  assert.match(
    production,
    /!requestedDirectMessageId && requestedChannelId && !selectedChannel/,
  );
});

test("dm reads and writes require current native-messaging capability", () => {
  const route = read("backend/app/routes/direct_messages.py");
  assert.match(
    route,
    /_dm_access = require_organization_permission\(Permission\.NATIVE_CHAT_WRITE\)/,
  );
  assert.doesNotMatch(route, /Depends\(_read\)|Permission\.ORGANIZATION_READ/);
});

test("dm service does not project private content into company evidence/search", () => {
  const service = read("backend/app/direct_messages.py");
  assert.doesNotMatch(service, /RawEvent|CanonicalEvent|SearchDocument|project_canonical_event|upsert_search_document/);
  assert.match(service, /participant_a_user_id == user_id/);
  assert.match(service, /participant_b_user_id == user_id/);
});

test("dm visibility epochs use monotonic sequences rather than timestamps", () => {
  const models = read("backend/app/direct_message_models.py");
  const service = read("backend/app/direct_messages.py");
  const migration = read("backend/migrations/versions/20260916_0024_direct_message_participant_epochs.py");

  assert.match(models, /next_message_sequence/);
  assert.match(models, /participant_a_visible_from_sequence/);
  assert.match(models, /participant_b_visible_from_sequence/);
  assert.match(models, /sequence: Mapped\[int\]/);
  assert.match(service, /visible_from_sequence/);
  assert.match(service, /conversation\.next_message_sequence = sequence \+ 1/);
  assert.match(service, /\.with_for_update\(\)/);
  assert.doesNotMatch(service, /participant_[ab]_visible_from(?!_sequence)/);
  assert.match(migration, /ROW_NUMBER\(\) OVER/);
  assert.match(migration, /uq_direct_message_conversation_sequence/);
});

test("history-only DM state is server controlled", () => {
  const api = read("app/direct-message-api.ts");
  const production = read("app/production-workspace.tsx");
  const panel = read("app/direct-message-panel.tsx");

  assert.match(api, /can_send: boolean/);
  assert.match(production, /selectedDirectConversation\.can_send/);
  assert.match(panel, /History only|history-only|no longer available/i);
});

test("dm WorkOS routes use server auth and are included in guarded activation", () => {
  const createRoute = read("docs/workos-activation/app-api-brain-direct-messages-route.ts.template");
  const sendRoute = read("docs/workos-activation/app-api-brain-direct-message-route.ts.template");
  const activation = read("scripts/activate-workos-authkit.sh");
  for (const route of [createRoute, sendRoute]) {
    assert.match(route, /withAuth\(\)/);
    assert.match(route, /sec-fetch-site/);
    assert.match(route, /request\.nextUrl\.origin/);
    assert.doesNotMatch(route, /secret_ref|WORKOS_API_KEY/);
  }
  assert.match(activation, /app-api-brain-direct-messages-route\.ts\.template/);
  assert.match(activation, /app-api-brain-direct-message-route\.ts\.template/);
});

test("native dm privacy decision excludes organisation-wide AI/retrieval", () => {
  const questions = read("OPEN_QUESTIONS.md");
  assert.match(questions, /OQ-008 Brain-native direct-message privacy — RESOLVED 2026-09-16/);
  assert.match(questions, /excluded from organisation-wide Search, Ask Brain, Decision Memory, Project Command Centre and Executive Overview/);
  assert.match(questions, /private_message_days/);
  assert.match(questions, /Normal DM creation and sends do not create organisation-wide per-message\/per-conversation audit records/);
});

test("private dm retention is an independent governance class", () => {
  const models = read("backend/app/data_governance_models.py");
  const service = read("backend/app/data_governance.py");
  assert.match(models, /private_message_days/);
  assert.match(models, /private_messages_deleted/);
  assert.match(service, /policy\.private_message_days/);
  assert.match(service, /DirectMessage\.created_at/);
});
