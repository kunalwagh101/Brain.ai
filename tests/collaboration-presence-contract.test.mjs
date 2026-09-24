import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("presence persistence is ephemeral lease state, not activity history", () => {
  const models = read("backend/app/collaboration_presence_models.py");
  const migration = read(
    "backend/migrations/versions/20260919_0031_collaboration_presence.py",
  );

  assert.match(models, /class CollaborationPresenceLease\(Base\)/);
  assert.match(models, /class CollaborationTypingLease\(Base\)/);
  assert.match(models, /expires_at/);
  assert.match(models, /fk_collaboration_presence_membership/);
  assert.match(models, /fk_collaboration_typing_channel_scope/);
  assert.match(models, /fk_collaboration_typing_dm_scope/);
  assert.match(models, /ck_collaboration_typing_exact_context/);
  assert.doesNotMatch(
    models,
    /last_seen|created_at|updated_at|draft|body|keystroke|cursor|ip_address|user_agent/i,
  );
  assert.match(migration, /down_revision: str \| None = "20260918_0030"/);
  assert.match(migration, /collaboration_presence_leases/);
  assert.match(migration, /collaboration_typing_leases/);
});

test("presence service keeps fixed short leases and no normal audit trail", () => {
  const service = read("backend/app/collaboration_presence.py");
  const route = read("backend/app/routes/collaboration_presence.py");

  assert.match(service, /PRESENCE_TTL_SECONDS = 75/);
  assert.match(service, /TYPING_TTL_SECONDS = 8/);
  assert.match(service, /CollaborationContextKind\.CHANNEL/);
  assert.match(service, /DM = "dm"/);
  assert.match(service, /participant_a_revoked_at\.is_\(None\)/);
  assert.match(service, /participant_b_revoked_at\.is_\(None\)/);
  assert.match(service, /NativeChannelMembership\.revoked_at\.is_\(None\)/);
  assert.doesNotMatch(
    service,
    /append_audit_event|audit_authorization_decision|SecurityAuditEvent/,
  );
  assert.doesNotMatch(
    route,
    /require_organization_permission|AuthorizationContext/,
  );
  assert.match(route, /Depends\(get_current_user\)/);
});

test("presence polling stays read-only while writes clean expired leases", () => {
  const service = read("backend/app/collaboration_presence.py");
  const getStart = service.indexOf("def get_context_presence(");
  assert.ok(getStart >= 0);
  const getBody = service.slice(getStart);

  assert.doesNotMatch(getBody, /_purge_expired\(/);
  assert.doesNotMatch(getBody, /db\.commit\(\)/);
  assert.match(service, /def heartbeat_presence[\s\S]*_purge_expired\(/);
  assert.match(service, /def set_typing[\s\S]*_purge_expired\(/);
});

test("WorkOS BFF validates identifiers but leaves access authority to FastAPI", () => {
  const bff = read("app/collaboration-presence-bff.ts");
  const heartbeat = read(
    "docs/workos-activation/app-api-brain-presence-heartbeat-route.ts.template",
  );
  const context = read(
    "docs/workos-activation/app-api-brain-presence-context-route.ts.template",
  );

  assert.match(bff, /requireUuid/);
  assert.match(bff, /new Set\(\["channel", "dm"\]\)/);
  assert.doesNotMatch(bff, /requireBrainOrganizationMembership/);
  assert.match(bff, /Authorization: `Bearer \$\{accessToken\}`/);

  assert.match(heartbeat, /withAuth\(\)/);
  assert.match(heartbeat, /rejectCrossSiteMutation/);
  assert.match(context, /withAuth\(\)/);
  assert.match(context, /rejectCrossSiteMutation/);
  assert.match(context, /export async function GET/);
  assert.match(context, /export async function PUT/);
  assert.match(context, /export async function DELETE/);
});

test("browser presence sends no reusable token or draft content", () => {
  const heartbeat = read("app/presence-heartbeat.tsx");
  const hook = read("app/use-collaboration-presence.ts");

  assert.match(heartbeat, /HEARTBEAT_INTERVAL_MS = 30_000/);
  assert.match(heartbeat, /document\.visibilityState === "visible"/);
  assert.match(heartbeat, /navigator\.onLine/);
  assert.match(heartbeat, /credentials: "same-origin"/);

  assert.match(hook, /PRESENCE_POLL_INTERVAL_MS = 3_000/);
  assert.match(hook, /TYPING_REFRESH_INTERVAL_MS = 3_000/);
  assert.match(hook, /method: "PUT"/);
  assert.match(hook, /method: "DELETE"/);
  assert.match(hook, /keepalive: true/);
  assert.match(hook, /loaded: boolean/);
  assert.doesNotMatch(
    heartbeat + hook,
    /Authorization|Bearer|localStorage|sessionStorage|indexedDB|draft|message_body|cursor|keystroke/i,
  );
});

test("channel and DM UI broadcast typing only from focused non-empty composers", () => {
  const channel = read("app/native-chat-panel.tsx");
  const dm = read("app/direct-message-panel.tsx");

  assert.match(channel, /composerFocused && body\.trim\(\)/);
  assert.match(channel, /threadFocused && threadBody\.trim\(\)/);
  assert.match(channel, /aria-live="polite"/);
  assert.match(channel, /presence\.loaded/);

  assert.match(dm, /composerFocused/);
  assert.match(dm, /body\.trim\(\)/);
  assert.match(dm, /aria-live="polite"/);
  assert.match(dm, /presence\.loaded/);
});

test("activation installs presence routes and production feature flag", () => {
  const activation = read("scripts/activate-workos-authkit.sh");
  const page = read("docs/workos-activation/app-page.tsx.template");

  assert.match(activation, /presence\/heartbeat\/route\.ts/);
  assert.match(
    activation,
    /presence\/\[contextKind\]\/\[contextId\]\/route\.ts/,
  );
  assert.match(activation, /UAT\/F-10\.14\.md/);
  assert.match(page, /enableCollaborationPresenceBff/);
});
