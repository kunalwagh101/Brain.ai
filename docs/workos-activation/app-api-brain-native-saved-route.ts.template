import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import { handleNativeSavedListBff } from "../../../../../native-chat-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
} from "../../../../../native-chat-route";

export async function GET(
  _request: NextRequest,
  context: { params: Promise<{ organizationId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return nativeChatJson({ detail: "Authentication required" }, 401);
  }
  try {
    const { organizationId } = await context.params;
    const result = await handleNativeSavedListBff(
      auth.accessToken,
      organizationId,
    );
    return nativeChatJson(result, 200);
  } catch (error) {
    return nativeChatRouteError(error, "Saved messages request");
  }
}
