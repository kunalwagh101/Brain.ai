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

test("admin mutations use one same-origin route and browser code never handles bearer tokens", () => {
  const api = read("app/admin-center-api.ts");
  const panel = read("app/admin-center-panel.tsx");
  const bff = read("app/admin-center-bff.ts");
  const template = read("docs/workos-activation/app-api-brain-admin-center-actions-route.ts.template");

  assert.match(api, /Authorization: `Bearer \$\{accessToken\}`/);
  assert.match(panel, /"use client"/);
  assert.match(panel, /\/admin-center\/actions/);
  assert.match(panel, /credentials: "same-origin"/);
  assert.doesNotMatch(panel, /Authorization|Bearer|accessToken|secret_ref|api[_-]?key|refresh[_-]?token/i);
  assert.match(bff, /const ADMIN_ROLES = new Set\(\["owner", "admin"\]\)/);
  assert.match(bff, /parseAdminCenterAction/);
  assert.match(template, /withAuth\(\)/);
  assert.match(template, /MAX_BODY_BYTES = 8 \* 1024/);
});

test("admin aggregate serializes credential presence but not stored secret values", () => {
  const backend = read("backend/app/routes/admin_center.py");
  assert.match(backend, /credential_present=bool\(grant\.secret_ref\)/);
  assert.match(backend, /viewer_role=authorization\.role/);
  assert.doesNotMatch(backend, /secret_ref:\s*str/);
  assert.doesNotMatch(backend, /credentials:\s*dict/);
  assert.doesNotMatch(backend, /external_account_id:\s*str/);
});

test("membership removal clears dormant authorization and keeps a last-owner invariant", () => {
  const organizations = read("backend/app/routes/organizations.py");
  assert.match(organizations, /The organization must retain at least one owner/);
  assert.match(organizations, /delete\(ResourceGrant\)/);
  assert.match(organizations, /update\(NativeChannelMembership\)/);
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
