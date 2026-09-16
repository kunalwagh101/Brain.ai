import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent_models import AgentDefinition, AgentRun, AgentStep, AgentToolPolicy
from app.agent_runtime import AgentRuntimeError, cancel_agent_run, create_agent_run
from app.agent_tools import (
    AgentToolError,
    ToolExecutionResult,
    ToolRisk,
    execute_tool,
    normalize_tool_arguments,
    tool_definition,
)
from app.agent_workspace_models import AgentRunContext
from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderConfiguration,
    AIProviderStatus,
)
from app.data_governance import DataGovernanceError, append_audit_event
from app.models import Membership, MembershipRole
from app.native_chat import get_visible_channel
from app.native_chat_models import NativeChannel, NativeChannelStatus
from app.permissions import role_has_permission
from app.work_graph import _get_or_create_edge, _get_or_create_node, node_visible_to_user
from app.work_graph_models import (
    WorkGraphEdgeSource,
    WorkGraphEdgeType,
    WorkGraphEvidenceState,
    WorkGraphNode,
    WorkGraphNodeType,
)


class AgentWorkspaceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code[:128]


@dataclass(frozen=True, slots=True)
class ResolvedWorkspaceContext:
    project: WorkGraphNode | None
    channel: NativeChannel | None


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    definition: AgentDefinition
    provider: AIProviderConfiguration
    model: AIModelConfiguration
    policies: tuple[AgentToolPolicy, ...]


@dataclass(frozen=True, slots=True)
class AgentArtifact:
    kind: str
    label: str
    reference_id: str
    metadata: dict[str, object]


def resolve_workspace_context(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    project_node_id: uuid.UUID | None,
    native_channel_id: uuid.UUID | None,
) -> ResolvedWorkspaceContext:
    if project_node_id is None and native_channel_id is None:
        raise AgentWorkspaceError(
            "workspace_context_required",
            "Agent workspace runs require a visible project or Brain channel context",
        )

    project: WorkGraphNode | None = None
    if project_node_id is not None:
        candidate = db.scalar(
            select(WorkGraphNode).where(
                WorkGraphNode.id == project_node_id,
                WorkGraphNode.organization_id == organization_id,
                WorkGraphNode.node_type == WorkGraphNodeType.PROJECT,
            )
        )
        if candidate is None or not node_visible_to_user(
            db,
            candidate,
            user_id=user_id,
            role=role,
        ):
            raise AgentWorkspaceError(
                "workspace_context_not_found",
                "Workspace context not found",
            )
        project = candidate

    channel: NativeChannel | None = None
    if native_channel_id is not None:
        channel = get_visible_channel(
            db,
            organization_id=organization_id,
            channel_id=native_channel_id,
            user_id=user_id,
        )
        if channel is None or channel.status != NativeChannelStatus.ACTIVE:
            raise AgentWorkspaceError(
                "workspace_context_not_found",
                "Workspace context not found",
            )

    return ResolvedWorkspaceContext(project=project, channel=channel)


def _executable_agent_identity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    agent_definition_id: uuid.UUID,
) -> AgentIdentity:
    definition = db.scalar(
        select(AgentDefinition).where(
            AgentDefinition.id == agent_definition_id,
            AgentDefinition.organization_id == organization_id,
            AgentDefinition.enabled.is_(True),
        )
    )
    if definition is None:
        raise AgentWorkspaceError("agent_unavailable", "Agent is unavailable")

    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == definition.provider_configuration_id,
            AIProviderConfiguration.organization_id == organization_id,
            AIProviderConfiguration.status == AIProviderStatus.ENABLED,
        )
    )
    model = db.scalar(
        select(AIModelConfiguration).where(
            AIModelConfiguration.id == definition.model_configuration_id,
            AIModelConfiguration.organization_id == organization_id,
            AIModelConfiguration.enabled.is_(True),
        )
    )
    if provider is None or model is None:
        raise AgentWorkspaceError("agent_unavailable", "Agent is unavailable")

    policies = tuple(
        db.scalars(
            select(AgentToolPolicy)
            .where(
                AgentToolPolicy.organization_id == organization_id,
                AgentToolPolicy.agent_definition_id == definition.id,
            )
            .order_by(AgentToolPolicy.tool_name)
        )
    )
    return AgentIdentity(
        definition=definition,
        provider=provider,
        model=model,
        policies=policies,
    )


def create_workspace_run(
    db: Session,
    *,
    organization_id: uuid.UUID,
    agent_definition_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    role: MembershipRole,
    objective: str,
    project_node_id: uuid.UUID | None,
    native_channel_id: uuid.UUID | None,
) -> tuple[AgentRun, AgentRunContext]:
    context = resolve_workspace_context(
        db,
        organization_id=organization_id,
        user_id=requested_by_user_id,
        role=role,
        project_node_id=project_node_id,
        native_channel_id=native_channel_id,
    )
    _executable_agent_identity(
        db,
        organization_id=organization_id,
        agent_definition_id=agent_definition_id,
    )

    run = create_agent_run(
        db,
        organization_id=organization_id,
        agent_definition_id=agent_definition_id,
        requested_by_user_id=requested_by_user_id,
        objective=objective,
    )
    binding = AgentRunContext(
        organization_id=organization_id,
        run_id=run.id,
        project_node_id=context.project.id if context.project else None,
        native_channel_id=context.channel.id if context.channel else None,
    )
    try:
        db.add(binding)
        db.flush()
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"agent.workspace.bound:{run.id}",
            event_type="agent.workspace.bound",
            outcome="succeeded",
            actor_user_id=requested_by_user_id,
            resource_type="agent_run",
            resource_id=run.id,
            metadata={
                "project_node_id": binding.project_node_id,
                "native_channel_id": binding.native_channel_id,
            },
        )
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        try:
            cancel_agent_run(
                db,
                organization_id=organization_id,
                run_id=run.id,
                user_id=requested_by_user_id,
            )
        except (AgentRuntimeError, DataGovernanceError, SQLAlchemyError):
            pass
        raise AgentWorkspaceError(
            "workspace_context_binding_failed",
            "Agent workspace run could not be bound safely",
        ) from exc

    db.refresh(binding)
    return run, binding


def list_workspace_runs(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    project_node_id: uuid.UUID | None = None,
    native_channel_id: uuid.UUID | None = None,
) -> list[tuple[AgentRun, AgentRunContext]]:
    query = (
        select(AgentRun, AgentRunContext)
        .join(AgentRunContext, AgentRunContext.run_id == AgentRun.id)
        .where(
            AgentRun.organization_id == organization_id,
            AgentRun.requested_by_user_id == user_id,
            AgentRunContext.organization_id == organization_id,
        )
    )
    if project_node_id is not None:
        query = query.where(AgentRunContext.project_node_id == project_node_id)
    if native_channel_id is not None:
        query = query.where(AgentRunContext.native_channel_id == native_channel_id)
    return list(
        db.execute(
            query.order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(limit)
        ).all()
    )


def get_workspace_run(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
) -> tuple[AgentRun, AgentRunContext]:
    row = db.execute(
        select(AgentRun, AgentRunContext)
        .join(AgentRunContext, AgentRunContext.run_id == AgentRun.id)
        .where(
            AgentRun.id == run_id,
            AgentRun.organization_id == organization_id,
            AgentRun.requested_by_user_id == user_id,
            AgentRunContext.organization_id == organization_id,
        )
    ).first()
    if row is None:
        raise AgentWorkspaceError("workspace_run_not_found", "Agent workspace run not found")
    return row[0], row[1]


def list_agent_identities(
    db: Session,
    *,
    organization_id: uuid.UUID,
) -> list[AgentIdentity]:
    definition_ids = list(
        db.scalars(
            select(AgentDefinition.id)
            .where(
                AgentDefinition.organization_id == organization_id,
                AgentDefinition.enabled.is_(True),
            )
            .order_by(AgentDefinition.name, AgentDefinition.id)
        )
    )
    identities: list[AgentIdentity] = []
    for definition_id in definition_ids:
        try:
            identities.append(
                _executable_agent_identity(
                    db,
                    organization_id=organization_id,
                    agent_definition_id=definition_id,
                )
            )
        except AgentWorkspaceError:
            continue
    return identities


def execute_workspace_tool(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    tool_name: str,
    arguments: dict[str, object],
    run_id: uuid.UUID,
    project: WorkGraphNode | None,
) -> ToolExecutionResult:
    if tool_name != "work_graph.create_work_item":
        return execute_tool(
            db,
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            tool_name=tool_name,
            arguments=arguments,
        )

    definition = tool_definition(tool_name)
    if definition is None or not role_has_permission(role, definition.required_permission):
        raise AgentToolError("Current user is not permitted to execute this tool")
    if project is None or project.organization_id != organization_id:
        raise AgentToolError("Project context is required for workspace work-item creation")

    normalized = normalize_tool_arguments(tool_name, arguments)
    normalized_key = str(normalized["key"]).strip().lower()
    node = _get_or_create_node(
        db,
        organization_id=organization_id,
        node_type=WorkGraphNodeType.WORK_ITEM,
        stable_key=f"agent-workspace:{run_id}:work_item:{normalized_key}",
        display_name=str(normalized["display_name"]),
        source_visibility=project.source_visibility,
        source_acl=list(project.source_acl),
        attributes={
            "source": "agent_workspace",
            "created_by_user_id": str(user_id),
            "agent_run_id": str(run_id),
            "project_node_id": str(project.id),
        },
    )
    _get_or_create_edge(
        db,
        organization_id=organization_id,
        source_node=project,
        target_node=node,
        edge_type=WorkGraphEdgeType.CONTAINS,
        source_kind=WorkGraphEdgeSource.MANUAL,
        evidence_state=WorkGraphEvidenceState.VERIFIED,
        confidence=1.0,
        provenance_key=f"agent-workspace:{run_id}:contains:{node.id}",
        provenance={
            "agent_run_id": str(run_id),
            "project_node_id": str(project.id),
            "actor_user_id": str(user_id),
        },
        created_by_user_id=user_id,
    )
    db.commit()

    output_data = {
        "node_id": str(node.id),
        "node_type": node.node_type.value,
        "stable_key": node.stable_key,
        "display_name": node.display_name,
        "project_node_id": str(project.id),
    }
    output = json.dumps(output_data, sort_keys=True, separators=(",", ":"))
    return ToolExecutionResult(
        ephemeral_output=output,
        persisted_metadata=output_data,
        output_sha256=hashlib.sha256(output.encode()).hexdigest(),
    )


def run_artifacts(db: Session, run: AgentRun) -> list[AgentArtifact]:
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == run.organization_id,
            Membership.user_id == run.requested_by_user_id,
        )
    )
    if membership is None:
        return []

    steps = list(
        db.scalars(
            select(AgentStep)
            .where(
                AgentStep.organization_id == run.organization_id,
                AgentStep.run_id == run.id,
            )
            .order_by(AgentStep.sequence)
        )
    )
    artifacts: list[AgentArtifact] = []
    for step in steps:
        if step.tool_name != "work_graph.create_work_item" or not step.result_metadata:
            continue
        node_id = step.result_metadata.get("node_id")
        display_name = step.result_metadata.get("display_name")
        if not isinstance(node_id, str) or not isinstance(display_name, str):
            continue
        try:
            parsed_node_id = uuid.UUID(node_id)
        except ValueError:
            continue
        node = db.scalar(
            select(WorkGraphNode).where(
                WorkGraphNode.id == parsed_node_id,
                WorkGraphNode.organization_id == run.organization_id,
                WorkGraphNode.node_type == WorkGraphNodeType.WORK_ITEM,
            )
        )
        if node is None or not node_visible_to_user(
            db,
            node,
            user_id=run.requested_by_user_id,
            role=membership.role,
        ):
            continue
        artifacts.append(
            AgentArtifact(
                kind="work_item",
                label=display_name,
                reference_id=node_id,
                metadata={
                    "stable_key": step.result_metadata.get("stable_key"),
                    "node_type": step.result_metadata.get("node_type"),
                    "project_node_id": step.result_metadata.get("project_node_id"),
                    "step_id": str(step.id),
                },
            )
        )
    return artifacts


def policy_risk(policy: AgentToolPolicy) -> tuple[str, bool]:
    definition = tool_definition(policy.tool_name)
    if definition is None:
        return "unknown", False
    risk = definition.risk.value if isinstance(definition.risk, ToolRisk) else str(definition.risk)
    return risk, definition.replay_safe
