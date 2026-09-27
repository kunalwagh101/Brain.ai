import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextResponse } from "next/server";
import { BrainApiError } from "../../../../../../../../brain-api";
import {
  AgentWorkspaceBffError,
  handleAgentWorkspaceCancel,
} from "../../../../../../../../agent-workspace-bff";

const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 422, 429, 503]);

function json(body: object, status: number) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(
  _request: Request,
  context: { params: Promise<{ organizationId: string; runId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) return json({ detail: "Authentication required" }, 401);
  try {
    const { organizationId, runId } = await context.params;
    const result = await handleAgentWorkspaceCancel(auth.accessToken, organizationId, runId);
    return json(result, 200);
  } catch (error) {
    if (error instanceof AgentWorkspaceBffError) {
      return json({ detail: "Invalid agent cancellation request" }, error.status);
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Brain agent request failed safely" }, status);
    }
    return json({ detail: "Brain agent request failed safely" }, 500);
  }
}
