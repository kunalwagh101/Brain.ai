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
    assert.match(html, /Interactive product preview/i);
    assert.match(html, /No external source or AI provider is connected/i);
    assert.match(html, /Secure foundation before AI/i);
    assert.match(html, /Run daily brief/i);
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
    assert.match(page, /withAuth\(\{ ensureSignedIn: true \}\)/);
    assert.match(page, /ProductionWorkspace/);
    assert.match(proxy, /authkitProxy/);
  },
);
