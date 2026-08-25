import assert from "node:assert/strict";
import test from "node:test";

test("renders the Brain working surface with honest preview labelling", async () => {
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
  assert.match(html, /property="og:image"[^>]+brain-control-plane\.waghkunal1997\.chatgpt\.site\/og\.png/i);
  assert.doesNotMatch(html, /codex-preview/i);
});
