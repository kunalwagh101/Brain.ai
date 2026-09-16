import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import (
    AgentDefinition,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    AgentToolPolicy,
    AgentToolPolicyMode,
)
from app.agent_workspace import (
    AgentWorkspaceError,
    create_workspace_run,
    get_workspace_run,
    list_agent_identities,
    list_workspace_runs,
    policy_risk,
    resolve_workspace_context,
    run_artifacts,
)
from app.agent_workspace_models import AgentRunContext
from app.ai_gateway_models import AIModelConfiguration, AIProviderConfiguration
from app.database import get_db
from app.native_chat import get_visible_channel
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.work_graph import node_visible_to_user
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType

router = APIRouter(
    prefix="/organizations/{organization_id}/agent-workspace",
    tags=["agent-workspace"],
)
_use_agents = require_organization_permission(Permission.AGENT_USE)


class AgentWorkspaceToolPolicyRead(BaseModel):
    tool_name: str
    policy: AgentToolPolicyMode
    risk: str
    replay_safe: bool
    approval_required: bool


class AgentWorkspaceAgentRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    enabled: bool
    max_steps: int
    provider_key: str
    provider_display_name: str
    model_key: str
    model_display_name: str
    tool_policies: list[AgentWorkspaceToolPolicyRead]


class AgentWorkspaceProjectContextRead(BaseModel):
    node_id: uuid.UUID
    name: str
    provider: str | None
    repository_id: str | None


class AgentWorkspaceChannelContextRead(BaseModel):
    channel_id: uuid.UUID
    name: str
    visibility: str


class AgentWorkspaceContextRead(BaseModel):
    available: bool
    project: AgentWorkspaceProjectContextRead | None
    channel: AgentWorkspaceChannelContextRead | None


class AgentWorkspaceArtifactRead(BaseModel):
    kind: str
    label: str
    reference_id: str
    metadata: dict[str, object]


class AgentWorkspaceStepRead(BaseModel):
    id: uuid.UUID
    sequence: int
    tool_name: str
    policy: AgentToolPolicyMode
    status: AgentStepStatus
    arguments: dict[str, object]
    arguments_sha256: str
    proposal_reason: str | None
    result_sha256: str | None
    approval_expires_at: datetime | None
    approved_at: datetime | None
    completed_at: datetime | None
    error_code: str | None


class AgentWorkspaceRunRead(BaseModel):
    id: uuid.UUID
    agent_definition_id: uuid.UUID
    agent_name: str
    provider_key: str
    provider_display_name: str
    model_key: str
    model_display_name: str
    status: AgentRunStatus
    objective_sha256: str
    objective_char_count: int
    step_count: int
    final_output_sha256: str | None
    last_error_code: str | None
    context: AgentWorkspaceContextRead
    artifacts: list[AgentWorkspaceArtifactRead]
    steps: list[AgentWorkspaceStepRead]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None


class AgentWorkspaceRead(BaseModel):
    agents: list[AgentWorkspaceAgentRead]
    runs: list[AgentWorkspaceRunRead]


class AgentWorkspaceRunCreate(BaseModel):
    agent_definition_id: uuid.UUID
    objective: str = Field(min_length=1, max_length=20_000)
    project_node_id: uuid.UUID | None = None
    native_channel_id: uuid.UUID | None = None

    model_config = {"extra": "forbid"}


def _raise_workspace_error(exc: AgentWorkspaceError) -> None:
    if exc.code in {"workspace_context_not_found", "workspace_run_not_found"}:
        code = status.HTTP_404_NOT_FOUND
    elif exc.code == "workspace_context_binding_failed":
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(
        status_code=code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


def _tool_policy_read(policy: AgentToolPolicy) -> AgentWorkspaceToolPolicyRead:
    risk, replay_safe = policy_risk(policy)
    return AgentWorkspaceToolPolicyRead(
        tool_name=policy.tool_name,
        policy=policy.policy,
        risk=risk,
        replay_safe=replay_safe,
        approval_required=policy.policy == AgentToolPolicyMode.ACT_WITH_APPROVAL,
    )


def _agent_reads(db: Session, organization_id: uuid.UUID) -> list[AgentWorkspaceAgentRead]:
    return [
        AgentWorkspaceAgentRead(
            id=item.definition.id,
            name=item.definition.name,
            description=item.definition.description,
            enabled=item.definition.enabled,
            max_steps=item.definition.max_steps,
            provider_key=item.provider.provider_key,
            provider_display_name=item.provider.display_name,
            model_key=item.model.model_key,
            model_display_name=item.model.display_name,
            tool_policies=[_tool_policy_read(policy) for policy in item.policies],
        )
        for item in list_agent_identities(db, organization_id=organization_id)
    ]


def _run_identity(
    db: Session,
    run: AgentRun,
) -> tuple[AgentDefinition, AIProviderConfiguration, AIModelConfiguration]:
    definition = db.scalar(
        select(AgentDefinition).where(
            AgentDefinition.id == run.agent_definition_id,
            AgentDefinition.organization_id == run.organization_id,
        )
    )
    if definition is None:
        raise AgentWorkspaceError("workspace_run_invalid", "Agent workspace run is invalid")
    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == definition.provider_configuration_id,
            AIProviderConfiguration.organization_id == run.organization_id,
        )
    )
    model = db.scalar(
        select(AIModelConfiguration).where(
            AIModelConfiguration.id == definition.model_configuration_id,
            AIModelConfiguration.organization_id == run.organization_id,
        )
    )
    if provider is None or model is None:
        raise AgentWorkspaceError("workspace_run_invalid", "Agent workspace run is invalid")
    return definition, provider, model


def _current_context_read(
    db: Session,
    *,
    binding: AgentRunContext,
    authorization: AuthorizationContext,
) -> AgentWorkspaceContextRead:
    project_read: AgentWorkspaceProjectContextRead | None = None
    if binding.project_node_id is not None:
        project = db.scalar(
            select(WorkGraphNode).where(
                WorkGraphNode.id == binding.project_node_id,
                WorkGraphNode.organization_id == authorization.organization_id,
                WorkGraphNode.node_type == WorkGraphNodeType.PROJECT,
            )
        )
        if project is not None and node_visible_to_user(
            db,
            project,
            user_id=authorization.user_id,
            role=authorization.role,
        ):
            provider = project.attributes.get("provider")
            repository_id = project.attributes.get("repository_id")
            project_read = AgentWorkspaceProjectContextRead(
                node_id=project.id,
                name=project.display_name or "Untitled project",
                provider=provider if isinstance(provider, str) else None,
                repository_id=(
                    str(repository_id) if repository_id not in (None, "") else None
                ),
            )

    channel_read: AgentWorkspaceChannelContextRead | None = None
    if binding.native_channel_id is not None:
        channel = get_visible_channel(
            db,
            organization_id=authorization.organization_id,
            channel_id=binding.native_channel_id,
            user_id=authorization.user_id,
        )
        if channel is not None:
            channel_read = AgentWorkspaceChannelContextRead(
                channel_id=channel.id,
                name=channel.name,
                visibility=channel.visibility.value,
            )

    return AgentWorkspaceContextRead(
        available=project_read is not None or channel_read is not None,
        project=project_read,
        channel=channel_read,
    )


def _run_read(
    db: Session,
    *,
    run: AgentRun,
    binding: AgentRunContext,
    authorization: AuthorizationContext,
) -> AgentWorkspaceRunRead:
    definition, provider, model = _run_identity(db, run)
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
    return AgentWorkspaceRunRead(
        id=run.id,
        agent_definition_id=run.agent_definition_id,
        agent_name=definition.name,
        provider_key=provider.provider_key,
        provider_display_name=provider.display_name,
        model_key=model.model_key,
        model_display_name=model.display_name,
        status=run.status,
        objective_sha256=run.objective_sha256,
        objective_char_count=run.objective_char_count,
        step_count=run.step_count,
        final_output_sha256=run.final_output_sha256,
        last_error_code=run.last_error_code,
        context=_current_context_read(
            db,
            binding=binding,
            authorization=authorization,
        ),
        artifacts=[
            AgentWorkspaceArtifactRead(
                kind=item.kind,
                label=item.label,
                reference_id=item.reference_id,
                metadata=item.metadata,
            )
            for item in run_artifacts(db, run)
        ],
        steps=[
            AgentWorkspaceStepRead(
                id=step.id,
                sequence=step.sequence,
                tool_name=step.tool_name,
                policy=step.policy,
                status=step.status,
                arguments=step.arguments_json,
                arguments_sha256=step.arguments_sha256,
                proposal_reason=step.proposal_reason,
                result_sha256=step.result_sha256,
                approval_expires_at=step.approval_expires_at,
                approved_at=step.approved_at,
                completed_at=step.completed_at,
                error_code=step.error_code,
            )
            for step in steps
        ],
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
        cancelled_at=run.cancelled_at,
    )


def _validate_filter_context(
    db: Session,
    *,
    authorization: AuthorizationContext,
    project_node_id: uuid.UUID | None,
    native_channel_id: uuid.UUID | None,
) -> None:
    if project_node_id is None and native_channel_id is None:
        return
    try:
        resolve_workspace_context(
            db,
            organization_id=authorization.organization_id,
            user_id=authorization.user_id,
            role=authorization.role,
            project_node_id=project_node_id,
            native_channel_id=native_channel_id,
        )
    except AgentWorkspaceError as exc:
        _raise_workspace_error(exc)


@router.get("", response_model=AgentWorkspaceRead)
def read_agent_workspace(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    project_node_id: uuid.UUID | None = None,
    native_channel_id: uuid.UUID | None = None,
) -> AgentWorkspaceRead:
    _validate_filter_context(
        db,
        authorization=authorization,
        project_node_id=project_node_id,
        native_channel_id=native_channel_id,
    )
    rows = list_workspace_runs(
        db,
        organization_id=organization_id,
        user_id=authorization.user_id,
        limit=limit,
        project_node_id=project_node_id,
        native_channel_id=native_channel_id,
    )
    return AgentWorkspaceRead(
        agents=_agent_reads(db, organization_id),
        runs=[
            _run_read(
                db,
                run=run,
                binding=binding,
                authorization=authorization,
            )
            for run, binding in rows
        ],
    )


@router.post("/runs", response_model=AgentWorkspaceRunRead, status_code=status.HTTP_201_CREATED)
def start_workspace_run(
    organization_id: uuid.UUID,
    payload: AgentWorkspaceRunCreate,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentWorkspaceRunRead:
    try:
        run, binding = create_workspace_run(
            db,
            organization_id=organization_id,
            agent_definition_id=payload.agent_definition_id,
            requested_by_user_id=authorization.user_id,
            role=authorization.role,
            objective=payload.objective,
            project_node_id=payload.project_node_id,
            native_channel_id=payload.native_channel_id,
        )
    except AgentWorkspaceError as exc:
        _raise_workspace_error(exc)
    except Exception as exc:
        # Existing S-08 runtime errors are intentionally not expanded into browser-visible details.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent workspace run could not be created",
        ) from exc
    return _run_read(
        db,
        run=run,
        binding=binding,
        authorization=authorization,
    )


@router.get("/runs/{run_id}", response_model=AgentWorkspaceRunRead)
def read_workspace_run(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentWorkspaceRunRead:
    try:
        run, binding = get_workspace_run(
            db,
            organization_id=organization_id,
            user_id=authorization.user_id,
            run_id=run_id,
        )
    except AgentWorkspaceError as exc:
        _raise_workspace_error(exc)
    return _run_read(
        db,
        run=run,
        binding=binding,
        authorization=authorization,
    )
