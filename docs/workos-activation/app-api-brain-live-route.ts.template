import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import { BrainApiError } from "../../../../../brain-api";
import {
  LiveUpdatesBffError,
  handleLiveWorkspaceState,
} from "../../../../../live-updates-bff";

const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 422, 429, 503]);

function json(body: object, status: number) {
  return NextResponse.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store, private",
      "Vary": "Cookie",
    },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return json({ detail: "Authentication required" }, 401);
  }

  try {
    const { organizationId } = await context.params;
    const channelId = request.nextUrl.searchParams.get("channelId");
    const dmId = request.nextUrl.searchParams.get("dmId");
    const state = await handleLiveWorkspaceState(
      auth.accessToken,
      organizationId,
      channelId,
      dmId,
    );
    return json(state, 200);
  } catch (error) {
    if (error instanceof LiveUpdatesBffError) {
      return json({ detail: "Invalid live workspace request" }, error.status);
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Brain live workspace request failed safely" }, status);
    }
    return json({ detail: "Brain live workspace request failed safely" }, 500);
  }
}
