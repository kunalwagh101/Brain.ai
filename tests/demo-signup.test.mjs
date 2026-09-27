import assert from "node:assert/strict";
import test from "node:test";
import { demoModeReady } from "../app/workspace-configuration.ts";
import { browserOrigin } from "../app/same-origin.ts";

test("demo entry only opens with explicit staging opt-in and an HTTPS API", () => {
  const env = {
    BRAIN_ENVIRONMENT: "staging",
    BRAIN_DEMO_SIGNUP_ENABLED: "true",
    BRAIN_API_BASE_URL: "https://brain-api.example.com",
  };
  assert.equal(demoModeReady(env, true), true);
  assert.equal(demoModeReady({ ...env, BRAIN_ENVIRONMENT: "production" }, true), false);
  assert.equal(demoModeReady({ ...env, BRAIN_DEMO_SIGNUP_ENABLED: "false" }, true), false);
  assert.equal(demoModeReady({ ...env, BRAIN_API_BASE_URL: "http://brain-api.example.com" }, true), false);
  assert.equal(demoModeReady({ ...env, BRAIN_API_BASE_URL: "https://user@brain-api.example.com/path" }, true), false);
});

test("browser origin uses the public Host when Next normalises its internal URL", () => {
  const request = {
    headers: new Headers({ host: "127.0.0.1:13000" }),
    nextUrl: new URL("http://localhost:13000/demo-session"),
  };
  assert.equal(browserOrigin(request), "http://127.0.0.1:13000");
});
