import assert from "node:assert/strict";
import test from "node:test";
import { resultsForQuery } from "../app/workspace-search-state.ts";

test("an earlier authorised excerpt cannot appear under a different search query", () => {
  const completed = { query: "design", items: [{ title: "Restricted design note" }] };
  assert.equal(resultsForQuery(completed, "budget"), null);
  assert.equal(resultsForQuery(completed, ""), null);
  assert.deepEqual(resultsForQuery(completed, " design "), completed.items);
  assert.deepEqual(resultsForQuery({ query: "budget", items: [] }, "budget"), []);
  assert.equal(resultsForQuery(null, "budget"), null);
  assert.equal(resultsForQuery({ query: "org-a::budget", items: completed.items }, "org-b::budget"), null);
});
