import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import { BrainApiError } from "../../../../../brain-api";
import {
  WorkspaceSearchBffError,
  handleWorkspaceSearch,
} from "../../../../../workspace-search-bff";

const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 422, 429, 503]);

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
    const query = request.nextUrl.searchParams.get("q") ?? "";
    return json(
      await handleWorkspaceSearch(auth.accessToken, organizationId, query),
      200,
    );
  } catch (error) {
    if (error instanceof WorkspaceSearchBffError) {
      return json({ detail: "Invalid workspace search request" }, error.status);
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Brain search request failed safely" }, status);
    }
    return json({ detail: "Brain search request failed safely" }, 500);
  }
}
