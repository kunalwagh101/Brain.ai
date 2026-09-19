import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import { BrainApiError } from "../../../../../../../brain-api";
import {
  DirectMessageBffError,
  handleDirectMessageMarkRead,
} from "../../../../../../../direct-message-bff";

const MAX_BODY_BYTES = 2 * 1024;
const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 413, 415, 422, 429, 503]);

function json(body: object, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store, private", Vary: "Cookie" },
  });
}

function requireSameOrigin(request: NextRequest) {
  const fetchSite = request.headers.get("sec-fetch-site")?.toLowerCase();
  if (fetchSite === "cross-site") {
    throw new DirectMessageBffError(403, "Cross-site DM read mutation denied");
  }
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin) {
    throw new DirectMessageBffError(403, "Cross-origin DM read mutation denied");
  }
}

async function readJson(request: NextRequest): Promise<unknown> {
  requireSameOrigin(request);
  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.startsWith("application/json")) {
    throw new DirectMessageBffError(415, "Content-Type must be application/json");
  }
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
    throw new DirectMessageBffError(413, "Request body is too large");
  }
  try {
    return JSON.parse(raw);
  } catch {
    throw new DirectMessageBffError(400, "Request body must be valid JSON");
  }
}

export async function POST(
  request: NextRequest,
  context: {
    params: Promise<{ organizationId: string; conversationId: string }>;
  },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return json({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId, conversationId } = await context.params;
    const result = await handleDirectMessageMarkRead(
      auth.accessToken,
      organizationId,
      conversationId,
      await readJson(request),
    );
    return json(result as object, 200);
  } catch (error) {
    if (error instanceof DirectMessageBffError) {
      return json({ detail: "Invalid direct-message request" }, error.status);
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Brain direct-message request failed safely" }, status);
    }
    return json({ detail: "Brain direct-message request failed safely" }, 500);
  }
}
