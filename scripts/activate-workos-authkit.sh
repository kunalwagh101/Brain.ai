#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

command -v node >/dev/null 2>&1 || {
  echo "Node.js is required." >&2
  exit 69
}
command -v npm >/dev/null 2>&1 || {
  echo "npm is required." >&2
  exit 69
}

if [[ ! -f package.json || ! -f package-lock.json ]]; then
  echo "Brain package.json and package-lock.json are required." >&2
  exit 66
fi

node --input-type=module <<'NODE'
import { readFileSync } from "node:fs";

const pkg = JSON.parse(readFileSync("package.json", "utf8"));
const lock = JSON.parse(readFileSync("package-lock.json", "utf8"));
for (const name of ["@workos-inc/authkit-nextjs", "@workos-inc/node"]) {
  if (!pkg.dependencies?.[name] && !pkg.devDependencies?.[name]) {
    throw new Error(`${name} is not installed. Run scripts/install-workos-authkit.sh first.`);
  }
  const locked = lock.packages?.[`node_modules/${name}`];
  if (!locked?.version || !locked?.resolved || !locked?.integrity) {
    throw new Error(`${name} is not integrity-pinned in package-lock.json.`);
  }
}

const authkitVersion = lock.packages?.["node_modules/@workos-inc/authkit-nextjs"]?.version;
if (typeof authkitVersion !== "string" || !authkitVersion.startsWith("4.")) {
  throw new Error("@workos-inc/authkit-nextjs must stay on the reviewed 4.x line before activation.");
}

const required = [
  "WORKOS_CLIENT_ID",
  "WORKOS_API_KEY",
  "WORKOS_COOKIE_PASSWORD",
  "NEXT_PUBLIC_WORKOS_REDIRECT_URI",
  "BRAIN_API_BASE_URL",
];
for (const name of required) {
  if (!process.env[name]?.trim()) throw new Error(`${name} is required for activation verification.`);
}
if (process.env.WORKOS_COOKIE_PASSWORD.length < 32) {
  throw new Error("WORKOS_COOKIE_PASSWORD must be at least 32 characters.");
}

const redirect = new URL(process.env.NEXT_PUBLIC_WORKOS_REDIRECT_URI);
const brainApi = new URL(process.env.BRAIN_API_BASE_URL);
for (const [name, parsed] of [
  ["NEXT_PUBLIC_WORKOS_REDIRECT_URI", redirect],
  ["BRAIN_API_BASE_URL", brainApi],
]) {
  if (!["http:", "https:"].includes(parsed.protocol)) throw new Error(`${name} must be HTTP(S).`);
  if (parsed.username || parsed.password || parsed.hash) {
    throw new Error(`${name} must not contain embedded credentials or a URL fragment.`);
  }
}
if (redirect.pathname !== "/auth/callback" || redirect.search) {
  throw new Error("NEXT_PUBLIC_WORKOS_REDIRECT_URI must point exactly to /auth/callback with no query string.");
}
if (process.env.NODE_ENV === "production") {
  if (redirect.protocol !== "https:") {
    throw new Error("Production NEXT_PUBLIC_WORKOS_REDIRECT_URI must use HTTPS.");
  }
  if (brainApi.protocol !== "https:") {
    throw new Error("Production BRAIN_API_BASE_URL must use HTTPS.");
  }
}

const proxyTemplate = readFileSync("docs/workos-activation/proxy.ts.template", "utf8");
for (const requiredSource of [
  "authkitProxy",
  '"/"',
  '"/api/brain/:path*"',
  '"/sign-in"',
  '"/auth/callback"',
]) {
  if (!proxyTemplate.includes(requiredSource)) {
    throw new Error(`WorkOS proxy template is missing required coverage: ${requiredSource}`);
  }
}
const callbackTemplate = readFileSync("docs/workos-activation/app-auth-callback-route.ts.template", "utf8");
if (!callbackTemplate.includes("handleAuth") || !callbackTemplate.includes('returnPathname: "/"')) {
  throw new Error("WorkOS callback template no longer matches the reviewed AuthKit contract.");
}
const signInTemplate = readFileSync("docs/workos-activation/app-sign-in-route.ts.template", "utf8");
if (!signInTemplate.includes("getSignInUrl") || !signInTemplate.includes("redirect(signInUrl)")) {
  throw new Error("WorkOS sign-in template no longer matches the reviewed AuthKit contract.");
}
NODE

if command -v git >/dev/null 2>&1; then
  dirty="$(git status --porcelain -- app/page.tsx app/layout.tsx proxy.ts app/auth app/sign-in app/api/brain)"
  if [[ -n "${dirty}" ]]; then
    echo "Refusing activation because WorkOS target paths already contain uncommitted changes." >&2
    exit 65
  fi
fi

mkdir -p \
  app/auth/callback \
  app/sign-in \
  'app/api/brain/organizations/[organizationId]/ask-brain' \
  'app/api/brain/organizations/[organizationId]/evidence/uploads' \
  'app/api/brain/organizations/[organizationId]/evidence/[sourceId]' \
  'app/api/brain/organizations/[organizationId]/native-channels' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/pins' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/attachments/uploads' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[rootMessageId]/replies' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[rootMessageId]/thread-read' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[messageId]' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[messageId]/reaction' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[messageId]/pin' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[messageId]/saved' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/read' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/members' \
  'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/members/[userId]' \
  'app/api/brain/organizations/[organizationId]/direct-messages' \
  'app/api/brain/organizations/[organizationId]/direct-messages/[conversationId]/messages' \
  'app/api/brain/organizations/[organizationId]/direct-messages/[conversationId]/messages/[messageId]' \
  'app/api/brain/organizations/[organizationId]/direct-messages/[conversationId]/read' \
  'app/api/brain/organizations/[organizationId]/activity/[notificationId]/read' \
  'app/api/brain/organizations/[organizationId]/activity/read-all' \
  'app/api/brain/organizations/[organizationId]/activity/preferences' \
  'app/api/brain/organizations/[organizationId]/live' \
  'app/api/brain/organizations/[organizationId]/presence/heartbeat' \
  'app/api/brain/organizations/[organizationId]/presence/[contextKind]/[contextId]' \
  'app/api/brain/organizations/[organizationId]/saved-messages' \
  'app/api/brain/organizations/[organizationId]/search' \
  'app/api/brain/organizations/[organizationId]/agent-workspace/runs' \
  'app/api/brain/organizations/[organizationId]/agent-workspace/runs/[runId]/advance' \
  'app/api/brain/organizations/[organizationId]/agent-workspace/runs/[runId]/cancel' \
  'app/api/brain/organizations/[organizationId]/agent-workspace/runs/[runId]/steps/[stepId]/approval' \
  'app/api/brain/organizations/[organizationId]/admin-center/actions'
cp docs/workos-activation/proxy.ts.template proxy.ts
cp docs/workos-activation/app-auth-callback-route.ts.template app/auth/callback/route.ts
cp docs/workos-activation/app-sign-in-route.ts.template app/sign-in/route.ts
cp docs/workos-activation/app-api-brain-ask-route.ts.template 'app/api/brain/organizations/[organizationId]/ask-brain/route.ts'
cp docs/workos-activation/app-api-brain-evidence-upload-route.ts.template 'app/api/brain/organizations/[organizationId]/evidence/uploads/route.ts'
cp docs/workos-activation/app-api-brain-evidence-delete-route.ts.template 'app/api/brain/organizations/[organizationId]/evidence/[sourceId]/route.ts'
cp docs/workos-activation/app-api-brain-native-channels-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/route.ts'
cp docs/workos-activation/app-api-brain-native-messages-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/route.ts'
cp docs/workos-activation/app-api-brain-native-pins-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/pins/route.ts'
cp docs/workos-activation/app-api-brain-native-attachment-upload-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/attachments/uploads/route.ts'
cp docs/workos-activation/app-api-brain-native-replies-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[rootMessageId]/replies/route.ts'
cp docs/workos-activation/app-api-brain-native-thread-read-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[rootMessageId]/thread-read/route.ts'
cp docs/workos-activation/app-api-brain-native-message-lifecycle-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[messageId]/route.ts'
cp docs/workos-activation/app-api-brain-native-reaction-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[messageId]/reaction/route.ts'
cp docs/workos-activation/app-api-brain-native-pin-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[messageId]/pin/route.ts'
cp docs/workos-activation/app-api-brain-native-save-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/messages/[messageId]/saved/route.ts'
cp docs/workos-activation/app-api-brain-native-read-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/read/route.ts'
cp docs/workos-activation/app-api-brain-native-members-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/members/route.ts'
cp docs/workos-activation/app-api-brain-native-member-route.ts.template 'app/api/brain/organizations/[organizationId]/native-channels/[channelId]/members/[userId]/route.ts'
cp docs/workos-activation/app-api-brain-direct-messages-route.ts.template 'app/api/brain/organizations/[organizationId]/direct-messages/route.ts'
cp docs/workos-activation/app-api-brain-direct-message-route.ts.template 'app/api/brain/organizations/[organizationId]/direct-messages/[conversationId]/messages/route.ts'
cp docs/workos-activation/app-api-brain-direct-message-exact-route.ts.template 'app/api/brain/organizations/[organizationId]/direct-messages/[conversationId]/messages/[messageId]/route.ts'
cp docs/workos-activation/app-api-brain-direct-message-read-route.ts.template 'app/api/brain/organizations/[organizationId]/direct-messages/[conversationId]/read/route.ts'
cp docs/workos-activation/app-api-brain-activity-read-route.ts.template 'app/api/brain/organizations/[organizationId]/activity/[notificationId]/read/route.ts'
cp docs/workos-activation/app-api-brain-activity-read-all-route.ts.template 'app/api/brain/organizations/[organizationId]/activity/read-all/route.ts'
cp docs/workos-activation/app-api-brain-activity-preferences-route.ts.template 'app/api/brain/organizations/[organizationId]/activity/preferences/route.ts'
cp docs/workos-activation/app-api-brain-live-route.ts.template 'app/api/brain/organizations/[organizationId]/live/route.ts'
cp docs/workos-activation/app-api-brain-presence-heartbeat-route.ts.template 'app/api/brain/organizations/[organizationId]/presence/heartbeat/route.ts'
cp docs/workos-activation/app-api-brain-presence-context-route.ts.template 'app/api/brain/organizations/[organizationId]/presence/[contextKind]/[contextId]/route.ts'
cp docs/workos-activation/app-api-brain-native-saved-route.ts.template 'app/api/brain/organizations/[organizationId]/saved-messages/route.ts'
cp docs/workos-activation/app-api-brain-search-route.ts.template 'app/api/brain/organizations/[organizationId]/search/route.ts'
cp docs/workos-activation/app-api-brain-agent-workspace-runs-route.ts.template 'app/api/brain/organizations/[organizationId]/agent-workspace/runs/route.ts'
cp docs/workos-activation/app-api-brain-agent-workspace-advance-route.ts.template 'app/api/brain/organizations/[organizationId]/agent-workspace/runs/[runId]/advance/route.ts'
cp docs/workos-activation/app-api-brain-agent-workspace-cancel-route.ts.template 'app/api/brain/organizations/[organizationId]/agent-workspace/runs/[runId]/cancel/route.ts'
cp docs/workos-activation/app-api-brain-agent-workspace-approval-route.ts.template 'app/api/brain/organizations/[organizationId]/agent-workspace/runs/[runId]/steps/[stepId]/approval/route.ts'
cp docs/workos-activation/app-api-brain-admin-center-actions-route.ts.template 'app/api/brain/organizations/[organizationId]/admin-center/actions/route.ts'
cp docs/workos-activation/app-layout.tsx.template app/layout.tsx
cp docs/workos-activation/app-page.tsx.template app/page.tsx

echo "Official WorkOS source templates activated. Running frontend gates without printing secrets..."
npm run lint
npm run build
node --test tests/*.test.mjs

echo "WorkOS source activation compiled and passed repository frontend gates."
echo "This is not production UAT. Complete docs/WORKOS_FRONTEND_ACCEPTANCE.md before marking S-10.04 DONE."
echo "Complete UAT/F-10.06.md before marking S-10.06.01 DONE or accepted."
echo "Complete UAT/F-10.06.02.md before marking S-10.06.02 DONE or accepted."
echo "Complete UAT/F-10.07.md before marking S-10.07.01 DONE or accepted."
echo "Complete UAT/F-10.08.md before marking S-10.08.01 DONE or accepted."
echo "Complete UAT/F-10.09.md before marking S-10.09.01 DONE or accepted."
echo "Complete UAT/F-10.10.md before marking S-10.10.01 DONE or accepted."
echo "Complete UAT/F-10.11.md before marking S-10.11.01 DONE or accepted."
echo "Complete UAT/F-10.12.md before marking S-10.12.01 DONE or accepted."
echo "Complete UAT/F-10.13.md before marking S-10.13.01 DONE or accepted."
echo "Complete UAT/F-10.14.md before marking S-10.14.01 DONE or accepted."
echo "Complete UAT/F-10.15.md before marking S-10.15.01 DONE or accepted."
echo "Complete UAT/F-10.16.md before marking S-10.16.01 DONE or accepted."
echo "Complete UAT/F-10.17.md before marking S-10.17.01 DONE or accepted."
echo "Complete UAT/F-10.18.md before marking S-10.18.01 DONE or accepted."
echo "Complete UAT/F-10.19.md before marking S-10.19.01 DONE or accepted."
echo "Complete UAT/F-10.20.md before marking S-10.20.01 DONE or accepted."
echo "Complete UAT/F-10.21.md before marking S-10.21.01 DONE or accepted."
echo "Complete UAT/F-10.22.md before marking S-10.22.01 DONE or accepted."
