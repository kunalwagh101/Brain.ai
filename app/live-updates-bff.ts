import { BrainMembershipError, requireBrainOrganizationMembership, requireUuid } from "./brain-membership";
import { getLiveWorkspaceState, type LiveWorkspaceState } from "./live-updates-api";

export class LiveUpdatesBffError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "LiveUpdatesBffError";
    this.status = status;
  }
}

function optionalUuid(value: string | null, field: string): string | null {
  if (!value) return null;
  try {
    return requireUuid(value, field);
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new LiveUpdatesBffError(error.status, error.message);
    }
    throw error;
  }
}

export async function handleLiveWorkspaceState(
  accessToken: string,
  organizationId: string,
  selectedChannelId: string | null,
  selectedDirectMessageId: string | null,
): Promise<LiveWorkspaceState> {
  try {
    await requireBrainOrganizationMembership(accessToken, organizationId);
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new LiveUpdatesBffError(error.status, error.message);
    }
    throw error;
  }

  const channelId = optionalUuid(selectedChannelId, "channel_id");
  const directMessageId = optionalUuid(selectedDirectMessageId, "dm_id");
  if (channelId && directMessageId) {
    throw new LiveUpdatesBffError(400, "Only one live conversation context may be selected");
  }

  return getLiveWorkspaceState(
    accessToken,
    organizationId,
    channelId,
    directMessageId,
  );
}
