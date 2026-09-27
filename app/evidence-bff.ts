import {
  deleteEvidenceSource,
  uploadEvidenceSource,
  type EvidenceSource,
} from "./brain-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

export const MAX_EVIDENCE_FILE_BYTES = 10_000_000;
export const MAX_EVIDENCE_MULTIPART_BYTES = 10_500_000;
const IDEMPOTENCY_KEY_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const WRITE_ROLES = new Set(["owner", "admin", "manager", "member"]);

export class EvidenceBffRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "EvidenceBffRequestError";
    this.status = status;
  }
}

function invalid(status: number, message: string): never {
  throw new EvidenceBffRequestError(status, message);
}

function normalizeContentType(value: string): string {
  const normalized = value.trim();
  if (!/^multipart\/form-data\s*;/i.test(normalized) || !/boundary=/i.test(normalized)) {
    invalid(415, "Evidence upload must use multipart/form-data with a boundary");
  }
  return normalized;
}

function normalizeIdempotencyKey(value: string): string {
  const normalized = value.trim();
  if (!IDEMPOTENCY_KEY_PATTERN.test(normalized)) {
    invalid(400, "Idempotency-Key is invalid");
  }
  return normalized;
}

async function requireWritableMembership(accessToken: string, organizationId: string) {
  try {
    const organization = await requireBrainOrganizationMembership(accessToken, organizationId);
    if (!WRITE_ROLES.has(organization.role)) {
      invalid(403, "Evidence mutation is not available for this role");
    }
    return organization;
  } catch (error) {
    if (error instanceof EvidenceBffRequestError) throw error;
    if (error instanceof BrainMembershipError) {
      throw new EvidenceBffRequestError(error.status, error.message);
    }
    throw error;
  }
}

export async function handleEvidenceUploadBff(
  accessToken: string,
  organizationId: string,
  body: Uint8Array,
  contentType: string,
  idempotencyKey: string,
): Promise<EvidenceSource> {
  await requireWritableMembership(accessToken, organizationId);
  if (!body.byteLength || body.byteLength > MAX_EVIDENCE_MULTIPART_BYTES) {
    invalid(413, "Evidence upload body is too large");
  }
  return uploadEvidenceSource(
    accessToken,
    organizationId,
    body,
    normalizeContentType(contentType),
    normalizeIdempotencyKey(idempotencyKey),
  );
}

export async function handleEvidenceDeleteBff(
  accessToken: string,
  organizationId: string,
  sourceId: string,
): Promise<EvidenceSource> {
  await requireWritableMembership(accessToken, organizationId);
  try {
    requireUuid(sourceId, "sourceId");
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new EvidenceBffRequestError(error.status, error.message);
    }
    throw error;
  }
  return deleteEvidenceSource(accessToken, organizationId, sourceId);
}
