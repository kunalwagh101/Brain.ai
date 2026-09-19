import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import { handleNativeTeamCreate } from "../../../../../native-team-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  readNativeChatJson,
  rejectCrossSiteMutation,
} from "../../../../../native-chat-route";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const crossSite = rejectCrossSiteMutation(request);
  if (crossSite) return crossSite;
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId } = await context.params;
    const result = await handleNativeTeamCreate(
      auth.accessToken,
      organizationId,
      await readNativeChatJson(request, 2 * 1024),
    );
    return nativeChatJson(result, 201);
  } catch (error) {
    return nativeChatRouteError(error, "Native Team request");
  }
}
