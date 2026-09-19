import {
  createNativeTeam,
  setNativeTeamArchived,
  updateNativeTeam,
  type NativeTeam,
} from "./brain-api";
import { NativeChatBffRequestError } from "./native-chat-bff";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

const TEAM_WRITE_ROLES = new Set(["owner", "admin", "executive", "manager", "member"]);

export class NativeTeamBffError extends NativeChatBffRequestError {
  constructor(status: number, message: string) {
    super(status, message);
    this.name = "NativeTeamBffError";
  }
}

function invalid(status: number, message: string): never {
  throw new NativeTeamBffError(status, message);
}

async function requireWriter(accessToken: string, organizationId: string) {
  try {
    const organization = await requireBrainOrganizationMembership(accessToken, organizationId);
    if (!TEAM_WRITE_ROLES.has(organization.role)) {
      invalid(403, "Team management is not available for this role");
    }
    return organization;
  } catch (error) {
    if (error instanceof NativeTeamBffError) throw error;
    if (error instanceof BrainMembershipError) {
      throw new NativeTeamBffError(error.status, error.message);
    }
    throw error;
  }
}

function exactObject(value: unknown, allowed: Set<string>): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    invalid(400, "Team request is invalid");
  }
  const record = value as Record<string, unknown>;
  if (Object.keys(record).some((key) => !allowed.has(key))) {
    invalid(400, "Team request contains unexpected fields");
  }
  return record;
}

function text(value: unknown, field: string, max: number): string {
  if (typeof value !== "string") invalid(400, field + " must be a string");
  const normalized = value.trim().replace(/\s+/g, " ");
  if (!normalized || normalized.length > max) invalid(400, field + " is invalid");
  return normalized;
}

function optionalText(value: unknown, max: number): string | null {
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") invalid(400, "description must be a string or null");
  const normalized = value.trim().replace(/\s+/g, " ");
  if (normalized.length > max) invalid(400, "description is invalid");
  return normalized || null;
}

function revision(value: unknown): number {
  if (!Number.isInteger(value) || Number(value) < 1) {
    invalid(400, "expected_revision is invalid");
  }
  return Number(value);
}

function teamId(value: string): string {
  try {
    return requireUuid(value, "teamId");
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new NativeTeamBffError(error.status, error.message);
    }
    throw error;
  }
}

export async function handleNativeTeamCreate(
  accessToken: string,
  organizationId: string,
  body: unknown,
): Promise<NativeTeam> {
  await requireWriter(accessToken, organizationId);
  const input = exactObject(body, new Set(["name", "description"]));
  return createNativeTeam(accessToken, organizationId, {
    name: text(input.name, "name", 120),
    description: optionalText(input.description, 500),
  });
}

export async function handleNativeTeamUpdate(
  accessToken: string,
  organizationId: string,
  rawTeamId: string,
  body: unknown,
): Promise<NativeTeam> {
  await requireWriter(accessToken, organizationId);
  const input = exactObject(
    body,
    new Set(["name", "description", "expected_revision"]),
  );
  return updateNativeTeam(accessToken, organizationId, teamId(rawTeamId), {
    name: text(input.name, "name", 120),
    description: optionalText(input.description, 500),
    expected_revision: revision(input.expected_revision),
  });
}

export async function handleNativeTeamLifecycle(
  accessToken: string,
  organizationId: string,
  rawTeamId: string,
  body: unknown,
  archived: boolean,
): Promise<NativeTeam> {
  await requireWriter(accessToken, organizationId);
  const input = exactObject(body, new Set(["expected_revision"]));
  return setNativeTeamArchived(
    accessToken,
    organizationId,
    teamId(rawTeamId),
    revision(input.expected_revision),
    archived,
  );
}
