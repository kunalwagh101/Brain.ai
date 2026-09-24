import { NextRequest, NextResponse } from "next/server";
import { BrainApiError } from "./brain-api";
import { NativeChatBffRequestError } from "./native-chat-bff";

const SAFE_UPSTREAM_STATUSES = new Set([
  400, 401, 403, 404, 409, 413, 415, 422, 429, 503,
]);

export function nativeChatJson(body: object, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

export function rejectCrossSiteMutation(request: NextRequest) {
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  if (origin !== request.nextUrl.origin || (fetchSite && fetchSite !== "same-origin")) {
    return nativeChatJson({ detail: "Cross-site mutation rejected" }, 403);
  }
  return null;
}

export async function readNativeChatJson(
  request: NextRequest,
  maxBodyBytes: number,
): Promise<unknown> {
  const contentType = request.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.startsWith("application/json")) {
    throw new NativeChatBffRequestError(415, "Content-Type must be application/json");
  }
  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > maxBodyBytes) {
    throw new NativeChatBffRequestError(413, "Request body is too large");
  }
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > maxBodyBytes) {
    throw new NativeChatBffRequestError(413, "Request body is too large");
  }
  try {
    return JSON.parse(raw) as unknown;
  } catch {
    throw new NativeChatBffRequestError(400, "Request body must be valid JSON");
  }
}

export function nativeChatRouteError(error: unknown, action: string) {
  if (error instanceof NativeChatBffRequestError) {
    return nativeChatJson({ detail: `${action} was not accepted` }, error.status);
  }
  if (error instanceof BrainApiError) {
    const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
    return nativeChatJson({ detail: `${action} failed safely` }, status);
  }
  return nativeChatJson({ detail: `${action} failed safely` }, 500);
}
