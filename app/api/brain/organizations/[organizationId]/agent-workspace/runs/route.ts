import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import { BrainApiError } from "../../../../../../brain-api";
import {
  AgentWorkspaceBffError,
  handleAgentWorkspaceStart,
} from "../../../../../../agent-workspace-bff";

const MAX_BODY_BYTES = 24 * 1024;
const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 422, 429, 503]);

function json(body: object, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

async function readJson(request: NextRequest): Promise<unknown> {
  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.startsWith("application/json")) {
    throw new AgentWorkspaceBffError(415, "Content-Type must be application/json");
  }
  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    throw new AgentWorkspaceBffError(413, "Request body is too large");
  }
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
    throw new AgentWorkspaceBffError(413, "Request body is too large");
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new AgentWorkspaceBffError(400, "Request body must be valid JSON");
  }
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) return json({ detail: "Authentication required" }, 401);
  try {
    const { organizationId } = await context.params;
    const result = await handleAgentWorkspaceStart(
      auth.accessToken,
      organizationId,
      await readJson(request),
    );
    return json(result, 201);
  } catch (error) {
    if (error instanceof AgentWorkspaceBffError) {
      return json({ detail: "Invalid agent workspace request" }, error.status);
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Brain agent request failed safely" }, status);
    }
    return json({ detail: "Brain agent request failed safely" }, 500);
  }
}
