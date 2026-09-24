import {
  getActivityPreferences,
  markActivityRead,
  markAllActivityRead,
  updateActivityPreferences,
  type ActivityPreferences,
} from "./activity-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
  requireUuid,
} from "./brain-membership";

export class ActivityBffError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ActivityBffError";
    this.status = status;
  }
}

async function requireMembership(accessToken: string, organizationId: string) {
  try {
    return await requireBrainOrganizationMembership(accessToken, organizationId);
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new ActivityBffError(error.status, error.message);
    }
    throw error;
  }
}

export async function handleMarkActivityRead(
  accessToken: string,
  organizationId: string,
  notificationId: string,
): Promise<void> {
  await requireMembership(accessToken, organizationId);
  let normalized: string;
  try {
    normalized = requireUuid(notificationId, "notification_id");
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new ActivityBffError(error.status, error.message);
    }
    throw error;
  }
  await markActivityRead(accessToken, organizationId, normalized);
}

export async function handleMarkAllActivityRead(
  accessToken: string,
  organizationId: string,
): Promise<void> {
  await requireMembership(accessToken, organizationId);
  await markAllActivityRead(accessToken, organizationId);
}

export async function handleGetActivityPreferences(
  accessToken: string,
  organizationId: string,
): Promise<ActivityPreferences> {
  await requireMembership(accessToken, organizationId);
  return getActivityPreferences(accessToken, organizationId);
}

export async function handleActivityPreferences(
  accessToken: string,
  organizationId: string,
  values: Partial<ActivityPreferences>,
): Promise<ActivityPreferences> {
  await requireMembership(accessToken, organizationId);
  if (!values || typeof values !== "object" || Array.isArray(values)) {
    throw new ActivityBffError(400, "Notification preference payload is invalid");
  }
  const keys = Object.keys(values);
  const allowed = new Set<keyof ActivityPreferences>([
    "mentions",
    "thread_replies",
    "direct_messages",
    "channel_activity",
    "agent_approvals",
    "agent_run_events",
    "project_updates",
    "integration_failures",
  ]);
  if (!keys.length || keys.length > allowed.size) {
    throw new ActivityBffError(400, "At least one notification preference is required");
  }
  for (const key of keys) {
    const typedKey = key as keyof ActivityPreferences;
    if (!allowed.has(typedKey) || typeof values[typedKey] !== "boolean") {
      throw new ActivityBffError(400, "Notification preference payload is invalid");
    }
  }
  return updateActivityPreferences(accessToken, organizationId, values);
}
