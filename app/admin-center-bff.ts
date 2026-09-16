import {
  changeOrganizationMemberRole,
  inviteOrganizationMember,
  removeOrganizationMember,
  revokeAIProvider,
  revokeAPIGrant,
  revokeIntegration,
  setAIModelEnabled,
  setAIProviderEnabled,
  setAPIGrantEnabled,
} from "./admin-center-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

const ADMIN_ROLES = new Set(["owner", "admin"]);
const MEMBERSHIP_ROLES = new Set(["owner", "admin", "executive", "manager", "member", "guest"]);

export type AdminCenterAction =
  | { action: "member_invite"; email: string; role: string }
  | { action: "member_role"; membership_id: string; role: string }
  | { action: "member_remove"; membership_id: string }
  | { action: "integration_revoke"; integration_id: string }
  | { action: "ai_provider_status"; provider_id: string; enabled: boolean }
  | { action: "ai_provider_revoke"; provider_id: string }
  | { action: "ai_model_status"; model_id: string; enabled: boolean }
  | { action: "api_grant_status"; grant_id: string; enabled: boolean; reason: string | null }
  | { action: "api_grant_revoke"; grant_id: string; reason: string | null };

export class AdminCenterBffError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "AdminCenterBffError";
    this.status = status;
  }
}

function invalid(status: number, message: string): never {
  throw new AdminCenterBffError(status, message);
}

function exactObject(value: unknown, allowed: Set<string>, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) invalid(400, `${label} must be an object`);
  const body = value as Record<string, unknown>;
  for (const key of Object.keys(body)) {
    if (!allowed.has(key)) invalid(400, `Unexpected ${label} field: ${key}`);
  }
  return body;
}

function requiredString(value: unknown, field: string, maxLength: number): string {
  if (typeof value !== "string") invalid(400, `${field} must be a string`);
  const normalized = value.trim();
  if (!normalized || normalized.length > maxLength) invalid(400, `${field} is invalid`);
  return normalized;
}

function role(value: unknown): string {
  const normalized = requiredString(value, "role", 32).toLowerCase();
  if (!MEMBERSHIP_ROLES.has(normalized)) invalid(400, "role is invalid");
  return normalized;
}

function uuid(value: unknown, field: string): string {
  const text = requiredString(value, field, 64);
  try {
    return requireUuid(text, field);
  } catch (error) {
    if (error instanceof BrainMembershipError) invalid(error.status, error.message);
    throw error;
  }
}

function bool(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") invalid(400, `${field} must be a boolean`);
  return value;
}

function reason(value: unknown): string | null {
  if (value === undefined || value === null) return null;
  if (typeof value !== "string") invalid(400, "reason must be a string or null");
  const normalized = value.trim();
  if (normalized.length > 512) invalid(400, "reason is too long");
  return normalized || null;
}

function email(value: unknown): string {
  const normalized = requiredString(value, "email", 320).toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) invalid(400, "email is invalid");
  return normalized;
}

export function parseAdminCenterAction(value: unknown): AdminCenterAction {
  const base = exactObject(
    value,
    new Set([
      "action",
      "email",
      "role",
      "membership_id",
      "integration_id",
      "provider_id",
      "model_id",
      "grant_id",
      "enabled",
      "reason",
    ]),
    "admin action",
  );
  const action = requiredString(base.action, "action", 64);

  if (action === "member_invite") {
    return { action, email: email(base.email), role: role(base.role) };
  }
  if (action === "member_role") {
    return { action, membership_id: uuid(base.membership_id, "membership_id"), role: role(base.role) };
  }
  if (action === "member_remove") {
    return { action, membership_id: uuid(base.membership_id, "membership_id") };
  }
  if (action === "integration_revoke") {
    return { action, integration_id: uuid(base.integration_id, "integration_id") };
  }
  if (action === "ai_provider_status") {
    return { action, provider_id: uuid(base.provider_id, "provider_id"), enabled: bool(base.enabled, "enabled") };
  }
  if (action === "ai_provider_revoke") {
    return { action, provider_id: uuid(base.provider_id, "provider_id") };
  }
  if (action === "ai_model_status") {
    return { action, model_id: uuid(base.model_id, "model_id"), enabled: bool(base.enabled, "enabled") };
  }
  if (action === "api_grant_status") {
    return {
      action,
      grant_id: uuid(base.grant_id, "grant_id"),
      enabled: bool(base.enabled, "enabled"),
      reason: reason(base.reason),
    };
  }
  if (action === "api_grant_revoke") {
    return { action, grant_id: uuid(base.grant_id, "grant_id"), reason: reason(base.reason) };
  }
  invalid(400, "Unknown admin action");
}

async function requireAdmin(accessToken: string, organizationId: string): Promise<string> {
  try {
    const organization = await requireBrainOrganizationMembership(accessToken, organizationId);
    if (!ADMIN_ROLES.has(organization.role)) invalid(403, "Admin Center is not available for this role");
    return organization.role;
  } catch (error) {
    if (error instanceof AdminCenterBffError) throw error;
    if (error instanceof BrainMembershipError) throw new AdminCenterBffError(error.status, error.message);
    throw error;
  }
}

export async function handleAdminCenterAction(
  accessToken: string,
  organizationId: string,
  value: unknown,
): Promise<void> {
  const viewerRole = await requireAdmin(accessToken, organizationId);
  const action = parseAdminCenterAction(value);

  if (viewerRole !== "owner") {
    if (
      (action.action === "member_invite" && ["owner", "admin"].includes(action.role))
      || (action.action === "member_role" && ["owner", "admin"].includes(action.role))
    ) {
      invalid(403, "Only owners can assign owner or admin roles");
    }
  }

  switch (action.action) {
    case "member_invite":
      await inviteOrganizationMember(accessToken, organizationId, action.email, action.role);
      return;
    case "member_role":
      await changeOrganizationMemberRole(accessToken, organizationId, action.membership_id, action.role);
      return;
    case "member_remove":
      await removeOrganizationMember(accessToken, organizationId, action.membership_id);
      return;
    case "integration_revoke":
      await revokeIntegration(accessToken, organizationId, action.integration_id);
      return;
    case "ai_provider_status":
      await setAIProviderEnabled(accessToken, organizationId, action.provider_id, action.enabled);
      return;
    case "ai_provider_revoke":
      await revokeAIProvider(accessToken, organizationId, action.provider_id);
      return;
    case "ai_model_status":
      await setAIModelEnabled(accessToken, organizationId, action.model_id, action.enabled);
      return;
    case "api_grant_status":
      await setAPIGrantEnabled(accessToken, organizationId, action.grant_id, action.enabled, action.reason);
      return;
    case "api_grant_revoke":
      await revokeAPIGrant(accessToken, organizationId, action.grant_id, action.reason);
      return;
  }
}
