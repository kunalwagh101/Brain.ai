import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const pkg = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const authkitInstalled = Boolean(pkg.dependencies?.["@workos-inc/authkit-nextjs"]);

test(
  "renders the Brain working surface with honest preview labelling before WorkOS activation",
  { skip: authkitInstalled },
  async () => {
    const workerUrl = new URL("../dist/server/index.js", import.meta.url);
    workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
    const { default: worker } = await import(workerUrl.href);
    const response = await worker.fetch(
      new Request("http://localhost/", { headers: { accept: "text/html" } }),
      { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
      { waitUntil() {}, passThroughOnException() {} },
    );
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.match(html, /<title>Brain<\/title>/i);
    assert.match(html, /Interactive sample workspace/i);
    assert.match(html, /Example data · Read only · No account or backend connected/i);
    assert.doesNotMatch(html, /Permission-aware live data/i);
    assert.doesNotMatch(html, />Signed in</i);
    assert.match(html, /Northstar Studio/i);
    assert.match(html, /activity-center/i);
    assert.match(html, /native-chat/i);
    assert.match(html, /direct-messages/i);
    assert.match(html, /admin-center/i);
    assert.match(html, /project-mobile-app/i);
    assert.match(html, /67%/);
    assert.match(html, /Progress not configured/);
    assert.match(
      html,
      /property="og:image"[^>]+brain-control-plane\.waghkunal1997\.chatgpt\.site\/og\.png/i,
    );
    assert.doesNotMatch(html, /codex-preview/i);
  },
);

test(
  "does not pretend an unauthenticated rendered-html request is production UAT after WorkOS activation",
  { skip: !authkitInstalled },
  async () => {
    const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
    const proxy = await readFile(new URL("../proxy.ts", import.meta.url), "utf8");
    assert.match(page, /getBrainSession\(\)/);
    assert.match(page, /if \(!user \|\| !accessToken\) redirect\(demoAvailable\(\) \? "\/demo-signup" : "\/sign-in"\)/);
    assert.match(page, /ProductionWorkspace/);
    assert.match(page, /revokeDemoSession/);
    assert.match(proxy, /authkitProxy/);
  },
);

test(
  "sample route rejects unknown channel and DM selectors without exposing conversation content",
  { skip: authkitInstalled },
  async () => {
    const workerUrl = new URL("../dist/server/index.js", import.meta.url);
    workerUrl.searchParams.set("test", `invalid-demo-${process.pid}-${Date.now()}`);
    const { default: worker } = await import(workerUrl.href);
    const response = await worker.fetch(
      new Request("http://localhost/demo?channelId=unseen&dmId=unseen", { headers: { accept: "text/html" } }),
      { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
      { waitUntil() {}, passThroughOnException() {} },
    );
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.match(html, /Channel unavailable/);
    assert.match(html, /Direct conversation unavailable/);
    assert.doesNotMatch(html, /The accessibility review is underway/);
    assert.doesNotMatch(html, /Can we review the navigation together this afternoon/);
  },
);
