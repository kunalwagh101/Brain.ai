import assert from "node:assert/strict";
import { test } from "node:test";
import { viewForWorkspaceHash } from "../app/workspace-view-routes.ts";

test("workspace deep links open the matching feature instead of hiding their target", () => {
  const routes = {
    "#native-chat": "channels", "#direct-messages": "direct-messages",
    "#saved-messages": "saved", "#activity-center": "activity",
    "#track-live-1": "tracks", "#project-live-1": "projects",
    "#agent-workspace": "agents", "#admin-center": "admin", "#memory": "memory",
    "#ask-brain": "ask", "#files": "files", "#company-pulse": "home",
  };
  for (const [hash, expected] of Object.entries(routes)) {
    assert.equal(viewForWorkspaceHash(hash), expected, hash);
  }
  assert.equal(viewForWorkspaceHash("#track-project%20one"), "tracks");
  assert.equal(viewForWorkspaceHash("#%E0%A4%A"), "home");
});
