import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";

function read(path) {
  return readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
}

test("Next.js 16 AuthKit proxy covers the workspace and every Brain BFF route", () => {
  const proxy = read("docs/workos-activation/proxy.ts.template");
  assert.match(proxy, /authkitProxy/);
  assert.match(proxy, /"\/"/);
  assert.match(proxy, /"\/api\/brain\/:path\*"/);
  assert.match(proxy, /"\/sign-in"/);
  assert.match(proxy, /"\/auth\/callback"/);
  assert.doesNotMatch(proxy, /\(\.\*\)|_next\/static|_next\/image/);
});

test("callback, sign-in and layout use the reviewed server-side AuthKit flow", () => {
  const callback = read("docs/workos-activation/app-auth-callback-route.ts.template");
  const signIn = read("docs/workos-activation/app-sign-in-route.ts.template");
  const layout = read("docs/workos-activation/app-layout.tsx.template");

  assert.match(callback, /handleAuth\(\{ returnPathname: "\/" \}\)/);
  assert.match(signIn, /getSignInUrl\(\)/);
  assert.match(signIn, /redirect\(signInUrl\)/);
  assert.match(layout, /AuthKitProvider/);
  assert.doesNotMatch(layout, /accessToken|refreshToken|WORKOS_API_KEY/);
});

test("every reviewed Brain BFF template authenticates with WorkOS on the server", () => {
  const directory = new URL("../docs/workos-activation/", import.meta.url);
  const templates = readdirSync(directory)
    .filter((name) => name.startsWith("app-api-brain-") && name.endsWith(".ts.template"));

  assert.ok(templates.length >= 10, "expected the reviewed Brain BFF template set");
  for (const name of templates) {
    const source = read(`docs/workos-activation/${name}`);
    assert.match(source, /withAuth\(\)/, `${name} must authenticate server-side`);
    assert.doesNotMatch(source, /localStorage|sessionStorage|indexedDB/i, `${name} must not persist auth in browser storage`);
    assert.doesNotMatch(source, /WORKOS_API_KEY/, `${name} must not serialize the WorkOS API key`);
  }
});

test("activation fails closed on package, redirect, HTTPS and proxy-source drift", () => {
  const activation = read("scripts/activate-workos-authkit.sh");

  assert.match(activation, /@workos-inc\/authkit-nextjs/);
  assert.match(activation, /@workos-inc\/node/);
  assert.match(activation, /integrity-pinned/);
  assert.match(activation, /authkitVersion\.startsWith\("4\."\)/);
  assert.match(activation, /WORKOS_COOKIE_PASSWORD\.length < 32/);
  assert.match(activation, /redirect\.pathname !== "\/auth\/callback"/);
  assert.match(activation, /Production NEXT_PUBLIC_WORKOS_REDIRECT_URI must use HTTPS/);
  assert.match(activation, /Production BRAIN_API_BASE_URL must use HTTPS/);
  assert.match(activation, /"\/api\/brain\/:path\*"/);
});

test("activation installs every reviewed Brain BFF template", () => {
  const activation = read("scripts/activate-workos-authkit.sh");
  const directory = new URL("../docs/workos-activation/", import.meta.url);
  const templates = readdirSync(directory)
    .filter((name) => name.startsWith("app-api-brain-") && name.endsWith(".ts.template"));

  for (const name of templates) {
    assert.match(activation, new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")), `${name} must be copied by activation`);
  }
});
