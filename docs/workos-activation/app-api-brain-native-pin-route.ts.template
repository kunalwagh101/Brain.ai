import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import { handleNativePinBff } from "../../../../../../../../../native-chat-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  rejectCrossSiteMutation,
} from "../../../../../../../../../native-chat-route";

type Params = Promise<{
  organizationId: string;
  channelId: string;
  messageId: string;
}>;

async function mutate(
  request: NextRequest,
  params: Params,
  active: boolean,
) {
  const crossSite = rejectCrossSiteMutation(request);
  if (crossSite) return crossSite;
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId, channelId, messageId } = await params;
    const result = await handleNativePinBff(
      auth.accessToken,
      organizationId,
      channelId,
      messageId,
      active,
    );
    return active
      ? nativeChatJson(result ?? {}, 200)
      : new Response(null, {
          status: 204,
          headers: { "Cache-Control": "no-store" },
        });
  } catch (error) {
    return nativeChatRouteError(error, "Native pin request");
  }
}

export async function PUT(request: NextRequest, context: { params: Params }) {
  return mutate(request, context.params, true);
}

export async function DELETE(request: NextRequest, context: { params: Params }) {
  return mutate(request, context.params, false);
}
