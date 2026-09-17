import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import {
  ActivityBffError,
  handleActivityPreferences,
  handleGetActivityPreferences,
} from "../../../../../../activity-bff";
import type { ActivityPreferences } from "../../../../../../activity-api";
import { BrainApiError } from "../../../../../../brain-api";

const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 413, 415, 422, 429, 503]);
const MAX_BODY_BYTES = 4096;

function json(body: object, status: number) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

function requireSameOrigin(request: NextRequest) {
  const fetchSite = request.headers.get("sec-fetch-site")?.toLowerCase();
  if (fetchSite === "cross-site") {
    throw new ActivityBffError(403, "Cross-site activity mutation denied");
  }
  const origin = request.headers.get("origin");
  if (origin && origin !== request.nextUrl.origin) {
    throw new ActivityBffError(403, "Cross-origin activity mutation denied");
  }
}

function safeError(error: unknown) {
  if (error instanceof ActivityBffError) {
    return json({ detail: "Invalid activity request" }, error.status);
  }
  if (error instanceof BrainApiError) {
    const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
    return json({ detail: "Brain activity request failed safely" }, status);
  }
  return json({ detail: "Brain activity request failed safely" }, 500);
}

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return json({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId } = await context.params;
    return json(await handleGetActivityPreferences(auth.accessToken, organizationId), 200);
  } catch (error) {
    return safeError(error);
  }
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return json({ detail: "Authentication required" }, 401);
  }
  try {
    requireSameOrigin(request);
    const contentType = request.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase();
    if (contentType !== "application/json") {
      throw new ActivityBffError(415, "JSON required");
    }
    const raw = await request.text();
    if (new TextEncoder().encode(raw).byteLength > MAX_BODY_BYTES) {
      throw new ActivityBffError(413, "Preference payload is too large");
    }
    let payload: unknown;
    try {
      payload = JSON.parse(raw);
    } catch {
      throw new ActivityBffError(400, "Preference payload is invalid JSON");
    }
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new ActivityBffError(400, "Preference payload must be an object");
    }
    const { organizationId } = await context.params;
    return json(
      await handleActivityPreferences(
        auth.accessToken,
        organizationId,
        payload as Partial<ActivityPreferences>,
      ),
      200,
    );
  } catch (error) {
    return safeError(error);
  }
}
