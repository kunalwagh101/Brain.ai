import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("admin center is owner/admin gated before privileged fetch", () => {
  const production = read("app/production-workspace.tsx");
  assert.match(production, /const ADMIN_ROLES = new Set\(\["owner", "admin"\]\)/);
  assert.match(
    production,
    /ADMIN_ROLES\.has\(organization\.role\)[\s\S]*?getAdminCenter\(accessToken, organization\.id\)[\s\S]*?Promise\.resolve\(null\)/,
  );
});

test("admin mutations use one same-origin route and browser never handles reusable bearer tokens", () => {
  const api = read("app/admin-center-api.ts");
  const panel = read("app/admin-center-panel.tsx");
  const bff = read("app/admin-center-bff.ts");
  const template = read("docs/workos-activation/app-api-brain-admin-center-actions-route.ts.template");

  assert.match(api, /Authorization: `Bearer \$\{accessToken\}`/);
  assert.match(panel, /"use client"/);
  assert.match(panel, /\/admin-center\/actions/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.doesNotMatch(panel, /Authorization\s*:|Bearer\s+|accessToken|secret_ref/i);
  assert.doesNotMatch(panel, /localStorage|sessionStorage|indexedDB/i);
  assert.match(bff, /const ADMIN_ROLES = new Set\(\["owner", "admin"\]\)/);
  assert.match(bff, /parseAdminCenterAction/);
  assert.match(template, /withAuth\(\)/);
  assert.match(template, /MAX_BODY_BYTES = 32 \* 1024/);
  assert.match(template, /sec-fetch-site/);
  assert.match(template, /origin !== request\.nextUrl\.origin/);
});

test("secret entry is transient, bounded and never loaded from Admin Center state", () => {
  const panel = read("app/admin-center-panel.tsx");
  const bff = read("app/admin-center-bff.ts");
  const backend = read("backend/app/routes/admin_center.py");

  assert.match(panel, /type="password"/);
  assert.match(panel, /form\.reset\(\)/);
  assert.match(panel, /Credential JSON/);
  assert.match(panel, /secret value is not retained|never returned|never displayed/i);
  assert.doesNotMatch(panel, /defaultValue=\{[^}]*credential|value=\{[^}]*credential/i);
  assert.match(bff, /credentials must contain 1-16 fields/);
  assert.match(bff, /raw\.length > 8192/);
  assert.doesNotMatch(backend, /secret_ref:\s*str/);
  assert.doesNotMatch(backend, /credentials:\s*dict/);
});

test("admin aggregate serializes credential presence but not stored secret values", () => {
  const backend = read("backend/app/routes/admin_center.py");
  assert.match(backend, /credential_present=bool\(grant\.secret_ref\)/);
  assert.match(backend, /viewer_role=authorization\.role/);
  assert.doesNotMatch(backend, /secret_ref:\s*str/);
  assert.doesNotMatch(backend, /credentials:\s*dict/);
  assert.doesNotMatch(backend, /external_account_id:\s*str/);
});

test("Admin Center can bootstrap AI providers/models and API services without direct API work", () => {
  const panel = read("app/admin-center-panel.tsx");
  const bff = read("app/admin-center-bff.ts");
  const api = read("app/admin-center-api.ts");

  for (const action of ["ai_provider_create", "ai_model_create", "api_service_create", "api_grant_create"]) {
    assert.match(panel, new RegExp(action));
    assert.match(bff, new RegExp(action));
  }
  assert.match(api, /createAIProvider/);
  assert.match(api, /createAIModel/);
  assert.match(api, /createAPIService/);
  assert.match(api, /createAPIGrant/);
});

test("API grant lifecycle exposes governed owner, scope, environment and rotation actions", () => {
  const panel = read("app/admin-center-panel.tsx");
  const bff = read("app/admin-center-bff.ts");
  for (const action of ["api_grant_owner", "api_grant_scopes", "api_grant_environment", "api_grant_rotate"]) {
    assert.match(panel, new RegExp(action));
    assert.match(bff, new RegExp(action));
  }
});

test("AI provider rotation is server-side and secret-safe", () => {
  const route = read("backend/app/routes/ai_provider_credentials.py");
  const service = read("backend/app/ai_provider_credentials.py");
  assert.match(route, /Permission\.AI_MANAGE/);
  assert.match(service, /secret_store\.replace_secret/);
  assert.match(service, /credential_rotated_at/);
  assert.doesNotMatch(route, /secret_ref:\s*str|api_key:\s*str/);
});

test("membership removal clears dormant authorization and keeps a last-owner invariant", () => {
  const organizations = read("backend/app/routes/organizations.py");
  assert.match(organizations, /The organization must retain at least one owner/);
  assert.match(organizations, /delete\(ResourceGrant\)/);
  assert.match(organizations, /update\(NativeChannelMembership\)/);
  assert.match(organizations, /_revoke_direct_message_participation/);
  assert.match(organizations, /access_grants_cleared/);
});

test("workspace renders admin navigation only when admin data exists", () => {
  const shell = read("app/workspace-shell.tsx");
  assert.match(shell, /adminCenter \? <a href="#admin-center"/);
  assert.match(shell, /adminCenter \? \([\s\S]*?<AdminCenterPanel admin=\{adminCenter\}/);
});

test("WorkOS activation installs the reviewed admin action route", () => {
  const script = read("scripts/activate-workos-authkit.sh");
  assert.match(script, /admin-center\/actions/);
  assert.match(script, /app-api-brain-admin-center-actions-route\.ts\.template/);
});
