import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import { BrainApiError } from "../../../../../brain-api";
import { BrainBffRequestError, handleAskBrainBff } from "../../../../../brain-bff";

const MAX_BODY_BYTES = 16 * 1024;
const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 422, 429, 503]);

function json(body: object, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return json({ detail: "Authentication required" }, 401);
  }

  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.startsWith("application/json")) {
    return json({ detail: "Content-Type must be application/json" }, 415);
  }

  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    return json({ detail: "Request body is too large" }, 413);
  }

  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
    return json({ detail: "Request body is too large" }, 413);
  }

  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return json({ detail: "Request body must be valid JSON" }, 400);
  }

  const { organizationId } = await context.params;
  try {
    const result = await handleAskBrainBff(auth.accessToken, organizationId, body);
    return json(result, 200);
  } catch (error) {
    if (error instanceof BrainBffRequestError) {
      return json(
        { detail: error.status === 404 ? "Organisation unavailable" : "Invalid Ask Brain request" },
        error.status,
      );
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Brain request failed safely" }, status);
    }
    return json({ detail: "Brain request failed safely" }, 500);
  }
}
