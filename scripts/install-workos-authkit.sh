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

node --input-type=module <<'NODE'
const [major] = process.versions.node.split(".").map(Number);
if (major < 22) {
  console.error(`Brain requires Node >=22; current version is ${process.version}.`);
  process.exit(69);
}
NODE

if [[ ! -f package.json || ! -f package-lock.json ]]; then
  echo "Run this script from the Brain repository with package.json and package-lock.json present." >&2
  exit 66
fi

before_lock_sha="$(node --input-type=module <<'NODE'
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
console.log(createHash("sha256").update(readFileSync("package-lock.json")).digest("hex"));
NODE
)"

echo "Installing official WorkOS AuthKit packages through npm..."
npm install @workos-inc/authkit-nextjs @workos-inc/node

node --input-type=module <<'NODE'
import { readFile } from "node:fs/promises";

const pkg = JSON.parse(await readFile("package.json", "utf8"));
const lock = JSON.parse(await readFile("package-lock.json", "utf8"));
const required = ["@workos-inc/authkit-nextjs", "@workos-inc/node"];
for (const name of required) {
  const declared = pkg.dependencies?.[name] ?? pkg.devDependencies?.[name];
  if (!declared) throw new Error(`${name} is not declared after npm install`);
  const locked = lock.packages?.[`node_modules/${name}`];
  if (!locked?.version || !locked?.resolved || !locked?.integrity) {
    throw new Error(`${name} is not fully integrity-pinned in package-lock.json`);
  }
  console.log(`${name}: ${locked.version}`);
}
NODE

after_lock_sha="$(node --input-type=module <<'NODE'
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
console.log(createHash("sha256").update(readFileSync("package-lock.json")).digest("hex"));
NODE
)"

if [[ "${before_lock_sha}" == "${after_lock_sha}" ]]; then
  echo "package-lock.json did not change; packages may already have been installed and pinned."
else
  echo "package-lock.json updated by npm: ${after_lock_sha}"
fi

echo "Official WorkOS packages are installed and integrity-pinned."
echo "Next, provide the required WorkOS/BRAIN environment values and run:"
echo "  bash scripts/activate-workos-authkit.sh"
echo "Activation copies only the reviewed templates in docs/workos-activation and then runs lint/build/tests."
