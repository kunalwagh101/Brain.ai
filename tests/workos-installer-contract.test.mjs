import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("WorkOS installer requests the reviewed AuthKit major", () => {
  const installer = read("scripts/install-workos-authkit.sh");
  assert.match(installer, /@workos-inc\/authkit-nextjs@\^4/);
  assert.match(installer, /@workos-inc\/node/);
  assert.match(installer, /locked\.version\.startsWith\("4\."\)/);
});

test("WorkOS install and activation both require genuine lockfile metadata", () => {
  const installer = read("scripts/install-workos-authkit.sh");
  const activation = read("scripts/activate-workos-authkit.sh");
  for (const source of [installer, activation]) {
    assert.match(source, /\.resolved/);
    assert.match(source, /\.integrity/);
  }
});

test("WorkOS activation validates the reviewed production redirect boundary", () => {
  const activation = read("scripts/activate-workos-authkit.sh");
  assert.match(activation, /redirect\.pathname !== "\/auth\/callback"/);
  assert.match(activation, /redirect\.search/);
  assert.match(activation, /parsed\.username \|\| parsed\.password \|\| parsed\.hash/);
  assert.match(activation, /Production NEXT_PUBLIC_WORKOS_REDIRECT_URI must use HTTPS/);
  assert.match(activation, /Production BRAIN_API_BASE_URL must use HTTPS/);
});
