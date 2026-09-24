import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import { BrainApiError } from "../../../../../../brain-api";
import {
  CollaborationPresenceBffError,
  handlePresenceHeartbeat,
} from "../../../../../../collaboration-presence-bff";
import { rejectCrossSiteMutation } from "../../../../../../native-chat-route";

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

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const crossSite = rejectCrossSiteMutation(request);
  if (crossSite) return crossSite;
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return json({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId } = await context.params;
    const result = await handlePresenceHeartbeat(auth.accessToken, organizationId);
    return json(result as object, 200);
  } catch (error) {
    if (error instanceof CollaborationPresenceBffError) {
      return json({ detail: "Presence request was not accepted" }, error.status);
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Presence request failed safely" }, status);
    }
    return json({ detail: "Presence request failed safely" }, 500);
  }
}
