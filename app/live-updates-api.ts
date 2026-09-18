import { getActivity, type ActivitySummary } from "./activity-api";
import {
  listNativeChannels,
  listNativeMessages,
  listNativeUnread,
  type NativeChannel,
  type NativeChannelUnread,
  type NativeMessage,
} from "./brain-api";
import {
  listDirectConversations,
  listDirectMessages,
  type DirectConversation,
  type DirectMessage,
} from "./direct-message-api";

export type LiveWorkspaceState = {
  revision: string;
  unread_count: number;
};

type LiveRevisionInput = {
  activity: ActivitySummary;
  channels: NativeChannel[];
  unread: NativeChannelUnread[];
  selectedChannelMessages: NativeMessage[];
  directConversations: DirectConversation[];
  directMessages: DirectMessage[];
};

function byId<T extends { id: string }>(rows: T[]): T[] {
  return [...rows].sort((left, right) => left.id.localeCompare(right.id));
}

export async function computeLiveRevision(input: LiveRevisionInput): Promise<string> {
  const payload = {
    activity: byId(input.activity.items).map((item) => [
      item.id,
      item.kind,
      item.read,
      item.created_at,
    ]),
    channels: byId(input.channels).map((channel) => [
      channel.id,
      channel.updated_at,
      channel.status,
      channel.can_post,
      channel.can_manage_members,
    ]),
    unread: [...input.unread]
      .sort((left, right) => left.channel_id.localeCompare(right.channel_id))
      .map((item) => [
        item.channel_id,
        item.unread_count,
        item.latest_message_id,
        item.last_read_at,
      ]),
    selectedChannelMessages: byId(input.selectedChannelMessages).map((message) => [
      message.id,
      message.created_at,
      message.projection_status,
      message.reply_count,
      message.revision,
      message.edited_at,
      message.deleted_at,
      [...message.reactions]
        .sort((left, right) => left.reaction.localeCompare(right.reaction))
        .map((reaction) => [reaction.reaction, reaction.count, reaction.reacted_by_me]),
    ]),
    directConversations: byId(input.directConversations).map((conversation) => [
      conversation.id,
      conversation.updated_at,
      conversation.can_send,
    ]),
    directMessages: byId(input.directMessages).map((message) => [
      message.id,
      message.created_at,
      message.is_mine,
    ]),
  };

  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function getLiveWorkspaceState(
  accessToken: string,
  organizationId: string,
  selectedChannelId?: string | null,
  selectedDirectMessageId?: string | null,
): Promise<LiveWorkspaceState> {
  const [activity, channels, unread, directConversations] = await Promise.all([
    getActivity(accessToken, organizationId, 50),
    listNativeChannels(accessToken, organizationId),
    listNativeUnread(accessToken, organizationId),
    listDirectConversations(accessToken, organizationId),
  ]);

  const readableChannel = selectedChannelId
    ? channels.find((channel) => channel.id === selectedChannelId) ?? null
    : null;
  const readableDirectConversation = selectedDirectMessageId
    ? directConversations.find((conversation) => conversation.id === selectedDirectMessageId) ?? null
    : null;

  const [selectedChannelMessages, directMessages] = await Promise.all([
    readableChannel
      ? listNativeMessages(accessToken, organizationId, readableChannel.id, 100)
      : Promise.resolve([]),
    readableDirectConversation
      ? listDirectMessages(accessToken, organizationId, readableDirectConversation.id)
      : Promise.resolve([]),
  ]);

  return {
    revision: await computeLiveRevision({
      activity,
      channels,
      unread,
      selectedChannelMessages,
      directConversations,
      directMessages,
    }),
    unread_count: activity.unread_count,
  };
}
