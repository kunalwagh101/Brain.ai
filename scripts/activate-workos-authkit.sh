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
for (const name of ["NEXT_PUBLIC_WORKOS_REDIRECT_URI", "BRAIN_API_BASE_URL"]) {
  const parsed = new URL(process.env[name]);
  if (!["http:", "https:"].includes(parsed.protocol)) throw new Error(`${name} must be HTTP(S).`);
}
if (
  process.env.NODE_ENV === "production"
  && new URL(process.env.BRAIN_API_BASE_URL).protocol !== "https:"
) {
  throw new Error("Production BRAIN_API_BASE_URL must use HTTPS.");
}
NODE

if command -v git >/dev/null 2>&1; then
  dirty="$(git status --porcelain -- app/page.tsx app/layout.tsx proxy.ts app/auth app/sign-in app/api/brain)"
  if [[ -n "${dirty}" ]]; then
    echo "Refusing activation because WorkOS target paths already contain uncommitted changes." >&2
    exit 65
  fi
fi

mkdir -p app/auth/callback app/sign-in 'app/api/brain/organizations/[organizationId]/ask-brain'
cp docs/workos-activation/proxy.ts.template proxy.ts
cp docs/workos-activation/app-auth-callback-route.ts.template app/auth/callback/route.ts
cp docs/workos-activation/app-sign-in-route.ts.template app/sign-in/route.ts
cp docs/workos-activation/app-api-brain-ask-route.ts.template 'app/api/brain/organizations/[organizationId]/ask-brain/route.ts'
cp docs/workos-activation/app-layout.tsx.template app/layout.tsx
cp docs/workos-activation/app-page.tsx.template app/page.tsx

echo "Official WorkOS source templates activated. Running frontend gates without printing secrets..."
npm run lint
npm run build
node --test tests/*.test.mjs

echo "WorkOS source activation compiled and passed repository frontend gates."
echo "This is not production UAT. Complete docs/WORKOS_FRONTEND_ACCEPTANCE.md before marking S-10.04 DONE."
