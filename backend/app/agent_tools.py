import hashlib
import json
import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from app.agent_models import AgentToolPolicyMode
from app.models import MembershipRole
from app.permissions import Permission, role_has_permission
from app.search import SearchMode, search_documents
from app.work_graph import _get_or_create_node
from app.work_graph_models import WorkGraphNodeType


class AgentToolError(RuntimeError):
    pass


class ToolRisk(StrEnum):
    READ = "read"
    ACTION = "action"
    HIGH_RISK_ACTION = "high_risk_action"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    risk: ToolRisk
    required_permission: Permission
    replay_safe: bool


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    ephemeral_output: str
    persisted_metadata: dict[str, object]
    output_sha256: str


TOOL_CATALOG: dict[str, ToolDefinition] = {
    "search.query": ToolDefinition(
        name="search.query",
        risk=ToolRisk.READ,
        required_permission=Permission.RESOURCE_READ,
        replay_safe=True,
    ),
    "work_graph.create_work_item": ToolDefinition(
        name="work_graph.create_work_item",
        risk=ToolRisk.HIGH_RISK_ACTION,
        required_permission=Permission.RESOURCE_WRITE,
        replay_safe=True,
    ),
}


def tool_definition(tool_name: str) -> ToolDefinition | None:
    return TOOL_CATALOG.get(tool_name)


def policy_valid_for_tool(tool: ToolDefinition, policy: AgentToolPolicyMode) -> bool:
    if policy == AgentToolPolicyMode.DENY:
        return True
    if tool.risk == ToolRisk.READ:
        return policy == AgentToolPolicyMode.READ
    if tool.risk == ToolRisk.ACTION:
        return policy in {
            AgentToolPolicyMode.ACT,
            AgentToolPolicyMode.ACT_WITH_APPROVAL,
        }
    return policy == AgentToolPolicyMode.ACT_WITH_APPROVAL


def normalize_tool_arguments(tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    if tool_name == "search.query":
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise AgentToolError("search.query requires a non-empty query")
        normalized_query = " ".join(query.split())
        if len(normalized_query) > 500:
            raise AgentToolError("search.query query exceeds 500 characters")
        raw_limit = arguments.get("limit", 5)
        if isinstance(raw_limit, bool) or not isinstance(raw_limit, int):
            raise AgentToolError("search.query limit must be an integer")
        if not 1 <= raw_limit <= 5:
            raise AgentToolError("search.query limit must be between 1 and 5")
        return {"query": normalized_query, "limit": raw_limit}

    if tool_name == "work_graph.create_work_item":
        key = arguments.get("key")
        display_name = arguments.get("display_name")
        if not isinstance(key, str) or not key.strip():
            raise AgentToolError("work_graph.create_work_item requires key")
        if not isinstance(display_name, str) or not display_name.strip():
            raise AgentToolError("work_graph.create_work_item requires display_name")
        normalized_key = key.strip()
        normalized_name = display_name.strip()
        if len(normalized_key) > 100:
            raise AgentToolError("work item key exceeds 100 characters")
        if len(normalized_name) > 255:
            raise AgentToolError("work item display_name exceeds 255 characters")
        return {"key": normalized_key, "display_name": normalized_name}

    raise AgentToolError("Unknown agent tool")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def execute_tool(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    tool_name: str,
    arguments: dict[str, object],
) -> ToolExecutionResult:
    definition = tool_definition(tool_name)
    if definition is None:
        raise AgentToolError("Unknown agent tool")
    if not role_has_permission(role, definition.required_permission):
        raise AgentToolError("Current user is not permitted to execute this tool")

    normalized = normalize_tool_arguments(tool_name, arguments)
    if tool_name == "search.query":
        data = search_documents(
            db,
            organization_id=organization_id,
            user_id=user_id,
            query=str(normalized["query"]),
            mode=SearchMode.KEYWORD,
            limit=int(normalized["limit"]),
            embedding_client=None,
            embedding_model=None,
        )
        rows = [
            {
                "title": hit.document.title,
                "content_excerpt": hit.document.content[:2000],
                "source_provider": hit.document.source_provider,
                "object_type": hit.document.object_type,
                "object_external_id": hit.document.object_external_id,
                "canonical_event_id": str(hit.document.canonical_event_id),
            }
            for hit in data.hits
        ]
        output = json.dumps(
            {"results": rows, "result_count": len(rows)},
            sort_keys=True,
            separators=(",", ":"),
        )
        return ToolExecutionResult(
            ephemeral_output=output,
            persisted_metadata={"result_count": len(rows)},
            output_sha256=_digest(output),
        )

    if tool_name == "work_graph.create_work_item":
        normalized_key = str(normalized["key"]).strip().lower()
        node = _get_or_create_node(
            db,
            organization_id=organization_id,
            node_type=WorkGraphNodeType.WORK_ITEM,
            stable_key=f"manual:{WorkGraphNodeType.WORK_ITEM.value}:{normalized_key}",
            display_name=str(normalized["display_name"]),
            attributes={
                "source": "agent",
                "created_by_user_id": str(user_id),
            },
        )
        output_data = {
            "node_id": str(node.id),
            "node_type": node.node_type.value,
            "stable_key": node.stable_key,
            "display_name": node.display_name,
        }
        output = json.dumps(output_data, sort_keys=True, separators=(",", ":"))
        return ToolExecutionResult(
            ephemeral_output=output,
            persisted_metadata=output_data,
            output_sha256=_digest(output),
        )

    raise AgentToolError("Unknown agent tool")
