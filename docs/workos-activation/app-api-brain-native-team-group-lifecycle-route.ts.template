import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import { handleNativeChannelGroupLifecycle } from "../../../../../../../../../native-team-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  readNativeChatJson,
  rejectCrossSiteMutation,
} from "../../../../../../../../../native-chat-route";

type Params = Promise<{ organizationId: string; teamId: string; groupId: string }>;

export async function POST(request: NextRequest, context: { params: Params }) {
  const crossSite = rejectCrossSiteMutation(request);
  if (crossSite) return crossSite;
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId, teamId, groupId } = await context.params;
    const archived = request.nextUrl.pathname.endsWith("/archive");
    const result = await handleNativeChannelGroupLifecycle(
      auth.accessToken,
      organizationId,
      teamId,
      groupId,
      await readNativeChatJson(request, 1024),
      archived,
    );
    return nativeChatJson(result, 200);
  } catch (error) {
    return nativeChatRouteError(error, "Native channel-group lifecycle");
  }
}
