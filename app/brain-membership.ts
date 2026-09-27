import { listOrganizations, type BrainOrganization } from "./brain-api";

export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export class BrainMembershipError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "BrainMembershipError";
    this.status = status;
  }
}

export function requireUuid(value: string, field = "identifier"): string {
  if (!UUID_PATTERN.test(value)) {
    throw new BrainMembershipError(400, `${field} must be a UUID`);
  }
  return value;
}

export async function requireBrainOrganizationMembership(
  accessToken: string,
  organizationId: string,
): Promise<BrainOrganization> {
  requireUuid(organizationId, "organizationId");
  const organizations = await listOrganizations(accessToken);
  const organization = organizations.find((item) => item.id === organizationId);
  if (!organization) {
    throw new BrainMembershipError(404, "Organisation unavailable");
  }
  return organization;
}
