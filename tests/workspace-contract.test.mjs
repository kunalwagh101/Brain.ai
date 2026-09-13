import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

const pkg = JSON.parse(await source("package.json"));
const authkitInstalled = Boolean(pkg.dependencies?.["@workos-inc/authkit-nextjs"]);

test("production workspace is role-aware without making executive access the workspace gate", async () => {
  const text = await source("app/production-workspace.tsx");

  assert.match(text, /listWorkspaceNavigation/);
  assert.match(text, /listProjectStatuses/);
  assert.match(text, /listEvidenceSources/);
  assert.match(text, /listRuntimeOptions/);
  assert.match(text, /EXECUTIVE_ROLES\.has\(organization\.role\)/);
  assert.match(text, /AI_ROLES\.has\(organization\.role\)/);
  assert.match(text, /EVIDENCE_WRITE_ROLES\.has\(organization\.role\)/);
  assert.match(text, /Promise\.resolve\(null\)/);
  assert.match(text, /enableAskBrainBff/);
  assert.match(text, /enableEvidenceBff/);
  assert.match(text, /encodeURIComponent\(organization\.id\)/);
  assert.match(text, /<WorkspaceShell/);
  assert.doesNotMatch(text, /Executive overview is not available for this role/);
});

test("workspace shell uses real navigation, evidence and no employee scoring surface", async () => {
  const text = await source("app/workspace-shell.tsx");

  assert.match(text, /navigation\.tracks\.map/);
  assert.match(text, /navigation\.projects\.map/);
  assert.match(text, /organizations\.map/);
  assert.match(text, /Project Command Centre/);
  assert.match(text, /Confirmed decisions & blockers/);
  assert.match(text, /AskBrainPanel/);
  assert.match(text, /EvidenceWorkspace/);
  assert.match(text, /Structured work & evidence/);
  assert.match(text, /signOutAction/);
  assert.doesNotMatch(text, /employee_productivity_score/i);
  assert.doesNotMatch(text, /productivity score/i);
  assert.doesNotMatch(text, /employee worth/i);
});

test("Brain channels expose unread, exact mentions, reactions and accessible threads", async () => {
  const [workspace, shell, panel] = await Promise.all([
    source("app/production-workspace.tsx"),
    source("app/workspace-shell.tsx"),
    source("app/native-chat-panel.tsx"),
  ]);

  assert.match(workspace, /listNativeUnread/);
  assert.match(workspace, /latest_message_id/);
  assert.match(shell, /unreadBadge/);
  assert.match(shell, /nativeConversationEndpoint/);
  assert.match(panel, /message\.mentions\.map/);
  assert.match(panel, /aria-pressed/);
  assert.match(panel, /Reply in thread/);
  assert.match(panel, /aria-labelledby="thread-heading"/);
  assert.match(panel, /event\.key === "Escape"/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.doesNotMatch(panel, /Authorization\s*:/);
  assert.doesNotMatch(panel, /Bearer |accessToken|localStorage|sessionStorage/);
});

test("native channel BFF validates membership, identifiers and bounded inputs", async () => {
  const [bff, route] = await Promise.all([
    source("app/native-chat-bff.ts"),
    source("app/native-chat-route.ts"),
  ]);

  assert.match(bff, /requireChatReader/);
  assert.match(bff, /requireChatWriter/);
  assert.match(bff, /ALLOWED_REACTIONS/);
  assert.match(bff, /normalizeIdempotencyKey/);
  assert.match(bff, /normalizedUuid\(rootMessageId/);
  assert.match(route, /origin !== request\.nextUrl\.origin/);
  assert.match(route, /fetchSite !== "same-origin"/);
  assert.match(route, /TextEncoder/);
  assert.match(route, /SAFE_UPSTREAM_STATUSES/);
});

test("WorkOS activation includes every native conversation route", async () => {
  const files = [
    "docs/workos-activation/app-api-brain-native-channels-route.ts.template",
    "docs/workos-activation/app-api-brain-native-messages-route.ts.template",
    "docs/workos-activation/app-api-brain-native-replies-route.ts.template",
    "docs/workos-activation/app-api-brain-native-reaction-route.ts.template",
    "docs/workos-activation/app-api-brain-native-read-route.ts.template",
    "docs/workos-activation/app-api-brain-native-members-route.ts.template",
    "docs/workos-activation/app-api-brain-native-member-route.ts.template",
  ];
  const [activation, ...routes] = await Promise.all([
    source("scripts/activate-workos-authkit.sh"),
    ...files.map(source),
  ]);

  for (const [index, route] of routes.entries()) {
    assert.match(route, /withAuth\(\)/, files[index]);
    assert.match(route, /Cache-Control|nativeChatJson/, files[index]);
    assert.match(activation, new RegExp(files[index].split("/").at(-1).replaceAll(".", "\\.")));
  }
  for (const route of routes.filter((text) => /POST|PUT|DELETE/.test(text))) {
    assert.match(route, /rejectCrossSiteMutation/);
  }
});

test("Ask Brain browser component stays same-origin and never accepts or creates a bearer token", async () => {
  const text = await source("app/ask-brain-panel.tsx");

  assert.match(text, /credentials: "same-origin"/);
  assert.match(text, /fetch\(endpoint/);
  assert.doesNotMatch(text, /Authorization\s*:/);
  assert.doesNotMatch(text, /Bearer /);
  assert.doesNotMatch(text, /accessToken/);
  assert.doesNotMatch(text, /localStorage/);
  assert.doesNotMatch(text, /sessionStorage/);
});

test("Ask Brain BFF validates current Brain membership before forwarding", async () => {
  const [bff, membership] = await Promise.all([
    source("app/brain-bff.ts"),
    source("app/brain-membership.ts"),
  ]);

  assert.match(bff, /requireBrainOrganizationMembership\(accessToken, organizationId\)/);
  assert.match(bff, /BrainBffRequestError/);
  assert.match(bff, /askBrain\(accessToken, organizationId/);
  assert.match(membership, /listOrganizations\(accessToken\)/);
  assert.match(membership, /item\.id === organizationId/);
  assert.doesNotMatch(bff, /client-supplied role/i);
});

test("evidence browser component uses same-origin BFF without bearer-token access", async () => {
  const text = await source("app/evidence-workspace.tsx");

  assert.match(text, /MAX_FILE_BYTES = 10_000_000/);
  assert.match(text, /credentials: "same-origin"/);
  assert.match(text, /Idempotency-Key/);
  assert.match(text, /router\.refresh\(\)/);
  assert.match(text, /Source provenance/);
  assert.doesNotMatch(text, /Authorization\s*:/);
  assert.doesNotMatch(text, /Bearer /);
  assert.doesNotMatch(text, /accessToken/);
  assert.doesNotMatch(text, /localStorage|sessionStorage/);
});

test("evidence BFF validates membership, mutation role, size and source identifiers", async () => {
  const text = await source("app/evidence-bff.ts");

  assert.match(text, /requireBrainOrganizationMembership/);
  assert.match(text, /WRITE_ROLES/);
  assert.match(text, /MAX_EVIDENCE_MULTIPART_BYTES = 10_500_000/);
  assert.match(text, /multipart\/form-data/);
  assert.match(text, /Idempotency-Key/);
  assert.match(text, /requireUuid\(sourceId/);
  assert.match(text, /uploadEvidenceSource/);
  assert.match(text, /deleteEvidenceSource/);
});

test("reviewed WorkOS activation templates use official AuthKit and bounded BFF boundaries", async () => {
  const [proxy, callback, signIn, layout, page, askBff, evidenceUpload, evidenceDelete] = await Promise.all([
    source("docs/workos-activation/proxy.ts.template"),
    source("docs/workos-activation/app-auth-callback-route.ts.template"),
    source("docs/workos-activation/app-sign-in-route.ts.template"),
    source("docs/workos-activation/app-layout.tsx.template"),
    source("docs/workos-activation/app-page.tsx.template"),
    source("docs/workos-activation/app-api-brain-ask-route.ts.template"),
    source("docs/workos-activation/app-api-brain-evidence-upload-route.ts.template"),
    source("docs/workos-activation/app-api-brain-evidence-delete-route.ts.template"),
  ]);

  assert.match(proxy, /authkitProxy/);
  assert.match(callback, /handleAuth/);
  assert.match(signIn, /getSignInUrl/);
  assert.match(layout, /AuthKitProvider/);
  assert.match(page, /withAuth\(\{ ensureSignedIn: true \}\)/);
  assert.match(page, /signOut/);
  assert.match(page, /ProductionWorkspace/);
  assert.match(page, /enableEvidenceBff/);
  assert.match(askBff, /withAuth\(\)/);
  assert.match(askBff, /handleAskBrainBff/);
  assert.match(askBff, /Cache-Control/);
  assert.match(evidenceUpload, /withAuth\(\)/);
  assert.match(evidenceUpload, /readBoundedBody/);
  assert.match(evidenceUpload, /MAX_EVIDENCE_MULTIPART_BYTES/);
  assert.match(evidenceUpload, /handleEvidenceUploadBff/);
  assert.match(evidenceDelete, /handleEvidenceDeleteBff/);
  assert.match(evidenceDelete, /Cache-Control/);
  assert.doesNotMatch(`${askBff}\n${evidenceUpload}\n${evidenceDelete}`, /localStorage|sessionStorage/);
});

test("root is preview before AuthKit activation and production workspace after activation", async () => {
  const text = await source("app/page.tsx");

  if (authkitInstalled) {
    assert.match(text, /withAuth\(\{ ensureSignedIn: true \}\)/);
    assert.match(text, /ProductionWorkspace/);
    assert.doesNotMatch(text, /Interactive product preview/);
    return;
  }

  assert.match(text, /Interactive product preview/);
  assert.match(text, /No external source or AI provider is connected/);
  assert.doesNotMatch(text, /ProductionWorkspace/);
});
