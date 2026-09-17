import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import { ActivityBffError, handleMarkAllActivityRead } from "../../../../../../activity-bff";
import { BrainApiError } from "../../../../../../brain-api";

const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 413, 415, 422, 429, 503]);

function json(body: object, status: number) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

function requireSameOrigin(request: NextRequest) {
  const fetchSite = request.headers.get("sec-fetch-site")?.toLowerCase();
  if (fetchSite === "cross-site") throw new ActivityBffError(403, "Cross-site activity mutation denied");
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin) {
    throw new ActivityBffError(403, "Cross-origin activity mutation denied");
  }
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) return json({ detail: "Authentication required" }, 401);
  try {
    requireSameOrigin(request);
    const { organizationId } = await context.params;
    await handleMarkAllActivityRead(auth.accessToken, organizationId);
    return json({ ok: true }, 200);
  } catch (error) {
    if (error instanceof ActivityBffError) return json({ detail: "Invalid activity request" }, error.status);
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Brain activity request failed safely" }, status);
    }
    return json({ detail: "Brain activity request failed safely" }, 500);
  }
}
