import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("channel attachments reuse governed evidence instead of a second blob store", () => {
  const models = read("backend/app/evidence_models.py");
  const relations = read("backend/app/native_conversation_models.py");
  const migration = read("backend/migrations/versions/20260918_0030_channel_attachments.py");
  assert.match(models, /native_channel_id/);
  assert.match(relations, /class NativeMessageAttachment\(Base\)/);
  assert.match(relations, /evidence_source_id/);
  assert.doesNotMatch(relations, /LargeBinary|raw_content|file_bytes/);
  assert.match(migration, /down_revision: str \| None = "20260918_0029"/);
  assert.match(migration, /native_message_attachments/);
});

test("restricted attachment evidence follows live channel membership", () => {
  const evidence = read("backend/app/evidence_ingestion.py");
  const chat = read("backend/app/native_chat.py");
  assert.match(evidence, /source\.native_channel_id is not None/);
  assert.match(evidence, /NativeChannelMembership\.revoked_at\.is_\(None\)/);
  assert.match(evidence, /document\.channel_id/);
  assert.match(chat, /SearchDocument\.channel_id == str\(channel\.id\)/);
  assert.match(chat, /_grant_channel_history/);
  assert.match(chat, /_revoke_channel_grants/);
});

test("message API accepts bounded attachment IDs and returns safe metadata only", () => {
  const routes = read("backend/app/routes/native_conversation.py");
  const chat = read("backend/app/native_chat.py");
  assert.match(routes, /attachment_source_ids: list\[uuid\.UUID\]/);
  assert.match(routes, /max_length=5/);
  assert.match(routes, /class AttachmentRead/);
  assert.match(routes, /MAX_EVIDENCE_BYTES \+ 1/);
  assert.match(chat, /A message can contain at most five attachments/);
  assert.match(chat, /allow_empty=bool\(sources\)/);
  assert.doesNotMatch(routes, /raw_content|extracted_text|chunk\.text/);
});

test("browser upload and send flow is same-origin, bounded and retry-safe", () => {
  const panel = read("app/native-chat-panel.tsx");
  const bff = read("app/native-chat-bff.ts");
  const route = read("docs/workos-activation/app-api-brain-native-attachment-upload-route.ts.template");
  assert.match(panel, /MAX_ATTACHMENTS_PER_MESSAGE = 5/);
  assert.match(panel, /MAX_ATTACHMENT_FILE_BYTES = 10_000_000/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.match(panel, /attachment_source_ids/);
  assert.match(panel, /Successful uploads were kept for retry/);
  assert.match(panel, /Uploaded files were kept so you can retry without re-uploading/);
  assert.doesNotMatch(panel, /Authorization|Bearer|accessToken|localStorage|sessionStorage|indexedDB/i);
  assert.match(bff, /MAX_NATIVE_ATTACHMENT_MULTIPART_BYTES = 10_500_000/);
  assert.match(bff, /multipart\/form-data/);
  assert.match(route, /withAuth\(\)/);
  assert.match(route, /rejectCrossSiteMutation/);
  assert.match(route, /readBoundedBody/);
});

test("attachment cards stay content-free and live invalidation tracks only structural state", () => {
  const panel = read("app/native-chat-panel.tsx");
  const live = read("app/live-updates-api.ts");
  assert.match(panel, /Governed evidence/);
  assert.match(panel, /retrieval_available/);
  assert.match(panel, /attachment\.filename/);
  assert.doesNotMatch(panel, /attachment\.raw_content|attachment\.extracted|attachment\.chunk/);
  assert.match(live, /attachment\.source_id/);
  assert.match(live, /attachment\.status/);
  assert.match(live, /attachment\.retrieval_available/);
  assert.doesNotMatch(live, /attachment\.filename|attachment\.title|attachment\.media_type/);
});

test("WorkOS activation installs attachment route and UAT gate", () => {
  const activation = read("scripts/activate-workos-authkit.sh");
  assert.match(activation, /app-api-brain-native-attachment-upload-route\.ts\.template/);
  assert.match(activation, /attachments\/uploads\/route\.ts/);
  assert.match(activation, /UAT\/F-10\.13\.md/);
});
