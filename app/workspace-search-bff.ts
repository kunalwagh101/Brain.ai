import {
  searchWorkspaceDocuments,
  type WorkspaceSearchResult,
} from "./brain-api";
import {
  BrainMembershipError,
  requireBrainOrganizationMembership,
} from "./brain-membership";

export type WorkspaceSearchItem = {
  id: string;
  title: string;
  excerpt: string;
  source: string;
  object_type: string;
  href: string;
  occurred_at: string | null;
};

export type WorkspaceSearchPayload = {
  query: string;
  items: WorkspaceSearchItem[];
};

export class WorkspaceSearchBffError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "WorkspaceSearchBffError";
    this.status = status;
  }
}

function normalizeQuery(value: string): string {
  const query = value.trim().replace(/\s+/g, " ");
  if (query.length < 2 || query.length > 120) {
    throw new WorkspaceSearchBffError(400, "Search query must be 2 to 120 characters");
  }
  return query;
}

function boundedExcerpt(value: string): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (normalized.length <= 280) return normalized;
  return `${normalized.slice(0, 277)}…`;
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function itemHref(
  organizationId: string,
  item: WorkspaceSearchResult,
): string {
  if (item.source_provider === "brain_native") {
    const channelId = stringValue(item.provenance.channel_id);
    const messageId = stringValue(item.provenance.native_message_id)
      ?? item.object_external_id;
    if (channelId && messageId) {
      const params = new URLSearchParams({
        organizationId,
        channelId,
        messageId,
      });
      return `?${params.toString()}#message-${encodeURIComponent(messageId)}`;
    }
  }

  if (
    item.object_type.includes("document")
    || item.object_type.includes("transcript")
    || item.source_provider.includes("evidence")
  ) {
    return "#files";
  }
  return "#ask-brain";
}

export async function handleWorkspaceSearch(
  accessToken: string,
  organizationId: string,
  rawQuery: string,
): Promise<WorkspaceSearchPayload> {
  try {
    await requireBrainOrganizationMembership(accessToken, organizationId);
  } catch (error) {
    if (error instanceof BrainMembershipError) {
      throw new WorkspaceSearchBffError(error.status, error.message);
    }
    throw error;
  }

  const query = normalizeQuery(rawQuery);
  const result = await searchWorkspaceDocuments(accessToken, organizationId, query, 12);
  return {
    query: result.query,
    items: result.results.map((item) => ({
      id: item.document_id,
      title: item.title || item.object_type,
      excerpt: boundedExcerpt(item.content),
      source: item.source_provider,
      object_type: item.object_type,
      href: itemHref(organizationId, item),
      occurred_at: item.occurred_at,
    })),
  };
}
