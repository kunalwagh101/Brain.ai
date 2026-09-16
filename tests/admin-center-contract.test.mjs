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

test("admin center client is server-token based and panel never handles bearer tokens", () => {
  const api = read("app/admin-center-api.ts");
  const panel = read("app/admin-center-panel.tsx");
  assert.match(api, /Authorization: `Bearer \$\{accessToken\}`/);
  assert.doesNotMatch(panel, /Authorization|Bearer|accessToken|secret_ref|credentials/i);
  assert.doesNotMatch(panel, /"use client"/);
});

test("admin aggregate serializes credential presence but not stored secret values", () => {
  const backend = read("backend/app/routes/admin_center.py");
  assert.match(backend, /credential_present=bool\(grant\.secret_ref\)/);
  assert.doesNotMatch(backend, /secret_ref:\s*str/);
  assert.doesNotMatch(backend, /credentials:\s*dict/);
  assert.doesNotMatch(backend, /external_account_id:\s*str/);
});

test("workspace renders admin navigation only when admin data exists", () => {
  const shell = read("app/workspace-shell.tsx");
  assert.match(shell, /adminCenter \? <a href="#admin-center"/);
  assert.match(shell, /adminCenter \? \([\s\S]*?<AdminCenterPanel admin=\{adminCenter\}/);
});
