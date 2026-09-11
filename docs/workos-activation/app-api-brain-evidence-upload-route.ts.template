import { withAuth } from "@workos-inc/authkit-nextjs";
import { NextRequest, NextResponse } from "next/server";
import { BrainApiError } from "../../../../../../brain-api";
import {
  EvidenceBffRequestError,
  MAX_EVIDENCE_MULTIPART_BYTES,
  handleEvidenceUploadBff,
} from "../../../../../../evidence-bff";

const SAFE_UPSTREAM_STATUSES = new Set([400, 401, 403, 404, 409, 413, 415, 422, 429, 503]);

function json(body: object, status: number) {
  return NextResponse.json(body, {
    status,
    headers: { "Cache-Control": "no-store" },
  });
}

async function readBoundedBody(request: NextRequest): Promise<Uint8Array> {
  const declaredLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(declaredLength) && declaredLength > MAX_EVIDENCE_MULTIPART_BYTES) {
    throw new EvidenceBffRequestError(413, "Evidence upload body is too large");
  }
  if (!request.body) {
    throw new EvidenceBffRequestError(400, "Evidence upload body is required");
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_EVIDENCE_MULTIPART_BYTES) {
      await reader.cancel();
      throw new EvidenceBffRequestError(413, "Evidence upload body is too large");
    }
    chunks.push(value);
  }

  if (!total) {
    throw new EvidenceBffRequestError(400, "Evidence upload body is required");
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
  context: { params: Promise<{ organizationId: string }> },
) {
  const auth = await withAuth();
  if (!auth.user || !auth.accessToken) {
    return json({ detail: "Authentication required" }, 401);
  }

  try {
    const { organizationId } = await context.params;
    const body = await readBoundedBody(request);
    const result = await handleEvidenceUploadBff(
      auth.accessToken,
      organizationId,
      body,
      request.headers.get("content-type") ?? "",
      request.headers.get("idempotency-key") ?? "",
    );
    return json(result, 201);
  } catch (error) {
    if (error instanceof EvidenceBffRequestError) {
      return json({ detail: "Evidence upload request was not accepted" }, error.status);
    }
    if (error instanceof BrainApiError) {
      const status = SAFE_UPSTREAM_STATUSES.has(error.status) ? error.status : 502;
      return json({ detail: "Evidence upload failed safely" }, status);
    }
    return json({ detail: "Evidence upload failed safely" }, 500);
  }
}
