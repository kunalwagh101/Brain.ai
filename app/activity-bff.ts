import { markActivityRead, markAllActivityRead } from "./activity-api";
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
