import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import { handleNativeTeamUpdate } from "../../../../../../native-team-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  readNativeChatJson,
  rejectCrossSiteMutation,
} from "../../../../../../native-chat-route";

type Params = Promise<{ organizationId: string; teamId: string }>;

export async function PATCH(request: NextRequest, context: { params: Params }) {
  const crossSite = rejectCrossSiteMutation(request);
  if (crossSite) return crossSite;
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId, teamId } = await context.params;
    const result = await handleNativeTeamUpdate(
      auth.accessToken,
      organizationId,
      teamId,
      await readNativeChatJson(request, 2 * 1024),
    );
    return nativeChatJson(result, 200);
  } catch (error) {
    return nativeChatRouteError(error, "Native Team update");
  }
}
