import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextResponse } from "next/server";
import { BrainApiError } from "../../../../../../brain-api";
import {
  EvidenceBffRequestError,
  handleEvidenceDeleteBff,
} from "../../../../../../evidence-bff";

const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 422, 429, 503]);

function json(body: object, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function DELETE(
  _request: Request,
  context: { params: Promise<{ organizationId: string; sourceId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return json({ detail: "Authentication required" }, 401);
  }

  try {
    const { organizationId, sourceId } = await context.params;
    const result = await handleEvidenceDeleteBff(auth.accessToken, organizationId, sourceId);
    return json(result, 200);
  } catch (error) {
    if (error instanceof EvidenceBffRequestError) {
      return json({ detail: "Evidence deletion request was not accepted" }, error.status);
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Evidence deletion failed safely" }, status);
    }
    return json({ detail: "Evidence deletion failed safely" }, 500);
  }
}
