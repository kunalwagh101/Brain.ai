export type WorkspaceView =
  | "home" | "activity" | "channels" | "direct-messages" | "saved"
  | "tracks" | "projects" | "agents" | "admin" | "memory"
  | "ask" | "files";

/** Keep every existing deep link useful when the workspace switches screens. */
export function viewForWorkspaceHash(hash: string): WorkspaceView {
  let target = hash.replace(/^#/, "");
  try { target = decodeURIComponent(target); } catch { /* Treat malformed fragments as unknown. */ }
  if (target === "native-chat") return "channels";
  if (target === "direct-messages") return "direct-messages";
  if (target === "saved-messages") return "saved";
  if (target === "activity-center") return "activity";
  if (target === "agent-workspace") return "agents";
  if (target === "admin-center") return "admin";
  if (target === "memory") return "memory";
  if (target === "ask-brain") return "ask";
  if (target === "files") return "files";
  if (target === "tracks" || target.startsWith("track-")) return "tracks";
  if (target === "projects" || target.startsWith("project-")) return "projects";
  return "home";
}
