import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest } from "next/server";
import {
  MAX_NATIVE_ATTACHMENT_MULTIPART_BYTES,
  NativeChatBffRequestError,
  handleNativeAttachmentUploadBff,
} from "../../../../../../../../native-chat-bff";
import {
  nativeChatJson,
  nativeChatRouteError,
  rejectCrossSiteMutation,
} from "../../../../../../../../native-chat-route";

async function readBoundedBody(request: NextRequest): Promise<Uint8Array> {
  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (
    Number.isFinite(declaredLength)
    && declaredLength > MAX_NATIVE_ATTACHMENT_MULTIPART_BYTES
  ) {
    throw new NativeChatBffRequestError(413, "Attachment upload body is too large");
  }
  if (!request.body) {
    throw new NativeChatBffRequestError(400, "Attachment upload body is required");
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_NATIVE_ATTACHMENT_MULTIPART_BYTES) {
      await reader.cancel();
      throw new NativeChatBffRequestError(413, "Attachment upload body is too large");
    }
    chunks.push(value);
  }

  if (!total) {
    throw new NativeChatBffRequestError(400, "Attachment upload body is required");
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
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
    const body = await readBoundedBody(request);
    const result = await handleNativeAttachmentUploadBff(
      auth.accessToken,
      organizationId,
      channelId,
      body,
      request.headers.get("content-type") ?? "",
      request.headers.get("idempotency-key") ?? "",
    );
    return nativeChatJson(result, 201);
  } catch (error) {
    return nativeChatRouteError(error, "Native attachment upload");
  }
}
