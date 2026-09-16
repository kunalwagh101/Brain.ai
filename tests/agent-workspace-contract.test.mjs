import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("agent workspace is embedded in the permission-aware Brain shell", () => {
  const production = read("app/production-workspace.tsx");
  const shell = read("app/workspace-shell.tsx");
  assert.match(production, /getAgentWorkspace\(accessToken, organization\.id\)/);
  assert.match(production, /enableAgentWorkspaceBff/);
  assert.match(shell, /Developer & agents/);
  assert.match(shell, /<AgentWorkspacePanel/);
  assert.match(shell, /projects=\{projects\}/);
  assert.match(shell, /channels=\{nativeChannels\}/);
});

test("browser agent panel uses same-origin mutations and never handles reusable bearer credentials", () => {
  const panel = read("app/agent-workspace-panel.tsx");
  assert.doesNotMatch(panel, /Authorization\s*:/i);
  assert.doesNotMatch(panel, /Bearer\s+/i);
  assert.doesNotMatch(panel, /accessToken/);
  assert.match(panel, /credentials:\s*"same-origin"/);
  assert.match(panel, /This is not a shell command/);
  assert.doesNotMatch(panel, /child_process|spawn\(|exec\(|shell_command|terminal_command/);
});

test("agent BFF accepts only governed run, objective, context and approval fields", () => {
  const bff = read("app/agent-workspace-bff.ts");
  assert.match(bff, /agent_definition_id/);
  assert.match(bff, /project_node_id/);
  assert.match(bff, /native_channel_id/);
  assert.match(bff, /new Set\(\["approve", "reason"\]\)/);
  assert.doesNotMatch(bff, /provider_configuration_id|model_configuration_id|secret_ref|api_key/);
  assert.match(bff, /requireBrainOrganizationMembership/);
});

test("WorkOS activation owns agent mutations and keeps tokens server-side", () => {
  const start = read("docs/workos-activation/app-api-brain-agent-workspace-runs-route.ts.template");
  const advance = read("docs/workos-activation/app-api-brain-agent-workspace-advance-route.ts.template");
  const approval = read("docs/workos-activation/app-api-brain-agent-workspace-approval-route.ts.template");
  const cancel = read("docs/workos-activation/app-api-brain-agent-workspace-cancel-route.ts.template");
  for (const route of [start, advance, approval, cancel]) {
    assert.match(route, /withAuth\(\)/);
    assert.match(route, /auth\.accessToken/);
    assert.match(route, /Cache-Control/);
    assert.doesNotMatch(route, /NextResponse\.json\([^\n]*accessToken/);
  }

  const activation = read("scripts/activate-workos-authkit.sh");
  assert.match(activation, /app-api-brain-agent-workspace-runs-route\.ts\.template/);
  assert.match(activation, /app-api-brain-agent-workspace-advance-route\.ts\.template/);
  assert.match(activation, /app-api-brain-agent-workspace-approval-route\.ts\.template/);
  assert.match(activation, /app-api-brain-agent-workspace-cancel-route\.ts\.template/);
});

test("agent workspace does not persist objective plaintext in its response contract", () => {
  const route = read("backend/app/routes/agent_workspace.py");
  const model = read("backend/app/agent_workspace_models.py");
  assert.match(route, /objective_sha256/);
  assert.match(route, /objective_char_count/);
  assert.doesNotMatch(model, /objective\s*:/);
  assert.doesNotMatch(model, /objective_text|objective_plaintext/);
});
