import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { configurationIssues } from "../app/workspace-configuration.ts";
import { workspaceCreationInput } from "../app/workspace-creation-input.ts";

const valid = {
  WORKOS_CLIENT_ID: "client_staging",
  WORKOS_API_KEY: "sk_test_example",
  WORKOS_COOKIE_PASSWORD: "a".repeat(32),
  NEXT_PUBLIC_WORKOS_REDIRECT_URI: "https://brain.example.com/auth/callback",
  BRAIN_API_BASE_URL: "https://api.example.com",
};

test("deployment readiness identifies missing or mismatched settings without leaking their values", () => {
  const missing = configurationIssues({}, true);
  assert.deepEqual(missing, Object.keys(valid));
  assert.deepEqual(configurationIssues(valid, true), []);
  assert.deepEqual(configurationIssues({ ...valid, WORKOS_COOKIE_PASSWORD: "private" }, true), ["WORKOS_COOKIE_PASSWORD"]);
  assert.deepEqual(configurationIssues({ ...valid, NEXT_PUBLIC_WORKOS_REDIRECT_URI: "https://brain.example.com/not-callback" }, true), ["NEXT_PUBLIC_WORKOS_REDIRECT_URI"]);
  assert.deepEqual(configurationIssues({ ...valid, BRAIN_API_BASE_URL: "http://api.example.com" }, true), ["BRAIN_API_BASE_URL"]);
});

test("new workspaces use validated names and unique safe slugs", () => {
  assert.deepEqual(workspaceCreationInput("  Kunal’s   Team  ", "a1b2c3d4"), {
    name: "Kunal’s Team", slug: "kunal-s-team-a1b2c3d4",
  });
  assert.equal(workspaceCreationInput("東京", "a1b2c3d4").slug, "workspace-a1b2c3d4");
  assert.throws(() => workspaceCreationInput("  ", "a1b2c3d4"));
  assert.throws(() => workspaceCreationInput("x".repeat(161), "a1b2c3d4"));
  assert.throws(() => workspaceCreationInput("Team", "unsafe/path"));
});

test("staging test-user provisioning refuses absent and production WorkOS credentials", () => {
  for (const key of [undefined, "sk_live_fake"]) {
    const env = { ...process.env, WORKOS_API_KEY: key, BRAIN_DEMO_PROVISION: "1" };
    const result = spawnSync(process.execPath, ["scripts/provision-staging-users.mjs"], { env, encoding: "utf8" });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /staging WorkOS API key/i);
    assert.doesNotMatch(result.stdout + result.stderr, /sk_live_fake/);
  }
});
