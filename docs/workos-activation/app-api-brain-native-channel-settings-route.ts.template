import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import { handleNativeChannelSettingsBff } from "../../../../../../../native-chat-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  readNativeChatJson,
  rejectCrossSiteMutation,
} from "../../../../../../../native-chat-route";

export async function PATCH(
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
    const result = await handleNativeChannelSettingsBff(
      auth.accessToken,
      organizationId,
      channelId,
      await readNativeChatJson(request, 2 * 1024),
    );
    return nativeChatJson(result, 200);
  } catch (error) {
    return nativeChatRouteError(error, "Native channel settings");
  }
}
