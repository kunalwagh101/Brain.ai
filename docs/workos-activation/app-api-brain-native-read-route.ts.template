import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import { handleNativeReadBff } from "../../../../../../../native-chat-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  readNativeChatJson,
  rejectCrossSiteMutation,
} from "../../../../../../../native-chat-route";

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
    const body = await readNativeChatJson(request, 1024);
    const result = await handleNativeReadBff(auth.accessToken, organizationId, channelId, body);
    return nativeChatJson(result, 200);
  } catch (error) {
    return nativeChatRouteError(error, "Native read request");
  }
}
