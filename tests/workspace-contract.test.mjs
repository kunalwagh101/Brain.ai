import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function source(path) {
  return readFile(new URL(`../${path}`, import.meta.url), "utf8");
}

test("production workspace is role-aware without making executive access the workspace gate", async () => {
  const text = await source("app/production-workspace.tsx");

  assert.match(text, /listWorkspaceNavigation/);
  assert.match(text, /listProjectStatuses/);
  assert.match(text, /listRuntimeOptions/);
  assert.match(text, /EXECUTIVE_ROLES\.has\(organization\.role\)/);
  assert.match(text, /AI_ROLES\.has\(organization\.role\)/);
  assert.match(text, /Promise\.resolve\(null\)/);
  assert.match(text, /<WorkspaceShell/);
  assert.doesNotMatch(text, /Executive overview is not available for this role/);
});

test("workspace shell uses real navigation and contains no employee scoring surface", async () => {
  const text = await source("app/workspace-shell.tsx");

  assert.match(text, /navigation\.tracks\.map/);
  assert.match(text, /navigation\.projects\.map/);
  assert.match(text, /organizations\.map/);
  assert.match(text, /Project Command Centre/);
  assert.match(text, /Confirmed decisions & blockers/);
  assert.match(text, /AskBrainPanel/);
  assert.match(text, /Structured work & evidence/);
  assert.doesNotMatch(text, /employee_productivity_score/i);
  assert.doesNotMatch(text, /productivity score/i);
  assert.doesNotMatch(text, /employee worth/i);
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

test("Ask Brain BFF validates membership before forwarding to FastAPI", async () => {
  const text = await source("app/brain-bff.ts");

  assert.match(text, /listOrganizations\(accessToken\)/);
  assert.match(text, /item\.id === organizationId/);
  assert.match(text, /askBrain\(accessToken, organizationId/);
  assert.doesNotMatch(text, /client-supplied role/i);
});

test("root remains an explicitly labelled preview until official WorkOS activation", async () => {
  const text = await source("app/page.tsx");

  assert.match(text, /Interactive product preview/);
  assert.match(text, /No external source or AI provider is connected/);
  assert.doesNotMatch(text, /ProductionWorkspace/);
});
