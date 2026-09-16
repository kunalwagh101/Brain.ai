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

test("dm service does not project private content into company evidence/search", () => {
  const service = read("backend/app/direct_messages.py");
  assert.doesNotMatch(service, /RawEvent|CanonicalEvent|SearchDocument|project_canonical_event|upsert_search_document/);
  assert.match(service, /participant_a_user_id == user_id/);
  assert.match(service, /participant_b_user_id == user_id/);
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
});
