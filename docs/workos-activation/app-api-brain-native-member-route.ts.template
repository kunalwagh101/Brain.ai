import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import {
  handleNativeMemberAccessBff,
  handleNativeMemberRevokeBff,
} from "../../../../../../../../native-chat-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  readNativeChatJson,
  rejectCrossSiteMutation,
} from "../../../../../../../../native-chat-route";

export async function PUT(
  request: NextRequest,
  context: {
    params: Promise<{ organizationId: string; channelId: string; userId: string }>;
  },
) {
  const crossSite = rejectCrossSiteMutation(request);
  if (crossSite) return crossSite;
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId, channelId, userId } = await context.params;
    const result = await handleNativeMemberAccessBff(
      auth.accessToken,
      organizationId,
      channelId,
      userId,
      await readNativeChatJson(request, 1024),
    );
    return nativeChatJson(result, 200);
  } catch (error) {
    return nativeChatRouteError(error, "Native member access request");
  }
}

export async function DELETE(
  request: NextRequest,
  context: {
    params: Promise<{ organizationId: string; channelId: string; userId: string }>;
  },
) {
  const crossSite = rejectCrossSiteMutation(request);
  if (crossSite) return crossSite;
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId, channelId, userId } = await context.params;
    await handleNativeMemberRevokeBff(auth.accessToken, organizationId, channelId, userId);
    return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return nativeChatRouteError(error, "Native member request");
  }
}
