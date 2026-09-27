import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import {
  handleNativeMessageCreateBff,
  handleNativeMessageListBff,
} from "../../../../../../../native-chat-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  readNativeChatJson,
  rejectCrossSiteMutation,
} from "../../../../../../../native-chat-route";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string; channelId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId, channelId } = await context.params;
    const rawLimit = request.nextUrl.searchParams.get("limit") ?? "50";
    const rawBefore = request.nextUrl.searchParams.get("before_sequence");
    const limit = Number(rawLimit);
    const beforeSequence = rawBefore === null ? null : Number(rawBefore);
    const result = await handleNativeMessageListBff(
      auth.accessToken,
      organizationId,
      channelId,
      limit,
      beforeSequence,
    );
    return nativeChatJson(result, 200);
  } catch (error) {
    return nativeChatRouteError(error, "Native message history");
  }
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string; channelId: string }> },
) {
  const crossSite = rejectCrossSiteMutation(request);
  if (crossSite) return crossSite;
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId, channelId } = await context.params;
    const body = await readNativeChatJson(request, 24 * 1024);
    const result = await handleNativeMessageCreateBff(
      auth.accessToken,
      organizationId,
      channelId,
      body,
      request.headers.get("idempotency-key") ?? "",
    );
    return nativeChatJson(result, 201);
  } catch (error) {
    return nativeChatRouteError(error, "Native message request");
  }
}
