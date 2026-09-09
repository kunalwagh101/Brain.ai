import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_locking import AgentRunBusyError, agent_run_lock
from app.agent_models import (
    AgentDefinition,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    AgentToolPolicy,
    AgentToolPolicyMode,
)
from app.agent_runtime import (
    AgentRuntimeError,
    advance_agent_run,
    cancel_agent_run,
    create_agent_definition,
    create_agent_run,
    decide_agent_step,
    set_agent_enabled,
)
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.secrets import SecretStore, get_secret_store

router = APIRouter(prefix="/organizations/{organization_id}/agents", tags=["agents"])
_manage_agents = require_organization_permission(Permission.AGENT_MANAGE)
_use_agents = require_organization_permission(Permission.AGENT_USE)


class AgentToolPolicyInput(BaseModel):
    tool_name: str = Field(min_length=1, max_length=128)
    policy: AgentToolPolicyMode


class AgentDefinitionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    provider_configuration_id: uuid.UUID
    model_configuration_id: uuid.UUID
    max_steps: int = Field(default=8, ge=1, le=20)
    tool_policies: list[AgentToolPolicyInput] = Field(default_factory=list, max_length=20)


class AgentDefinitionStatusUpdate(BaseModel):
    enabled: bool


class AgentToolPolicyRead(BaseModel):
    tool_name: str
    policy: AgentToolPolicyMode


class AgentDefinitionRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    provider_configuration_id: uuid.UUID
    model_configuration_id: uuid.UUID
    enabled: bool
    max_steps: int
    tool_policies: list[AgentToolPolicyRead]
    created_at: datetime
    updated_at: datetime


class AgentRunCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=20_000)


class AgentAdvanceRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=20_000)


class AgentApprovalRequest(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=500)


class AgentStepRead(BaseModel):
    id: uuid.UUID
    sequence: int
    tool_name: str
    policy: AgentToolPolicyMode
    status: AgentStepStatus
    arguments: dict[str, object]
    arguments_sha256: str
    proposal_reason: str | None
    result_sha256: str | None
    result_metadata: dict[str, object]
    approval_expires_at: datetime | None
    approved_at: datetime | None
    completed_at: datetime | None
    error_code: str | None


class AgentRunRead(BaseModel):
    id: uuid.UUID
    agent_definition_id: uuid.UUID
    status: AgentRunStatus
    objective_sha256: str
    objective_char_count: int
    step_count: int
    final_output_sha256: str | None
    last_error_code: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    steps: list[AgentStepRead]


class AgentAdvanceResponse(BaseModel):
    run: AgentRunRead
    final_output: str | None = None


def _raise_runtime_error(exc: AgentRuntimeError) -> None:
    message = str(exc)
    if "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    elif (
        "terminal" in message
        or "waiting for approval" in message
        or "currently planning" in message
        or "already in progress" in message
        or "expired" in message
        or "disabled" in message
    ):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=message) from exc


def _definition_read(db: Session, definition: AgentDefinition) -> AgentDefinitionRead:
    policies = list(
        db.scalars(
            select(AgentToolPolicy)
            .where(AgentToolPolicy.agent_definition_id == definition.id)
            .order_by(AgentToolPolicy.tool_name)
        )
    )
    return AgentDefinitionRead(
        id=definition.id,
        name=definition.name,
        description=definition.description,
        provider_configuration_id=definition.provider_configuration_id,
        model_configuration_id=definition.model_configuration_id,
        enabled=definition.enabled,
        max_steps=definition.max_steps,
        tool_policies=[
            AgentToolPolicyRead(tool_name=item.tool_name, policy=item.policy)
            for item in policies
        ],
        created_at=definition.created_at,
        updated_at=definition.updated_at,
    )


def _run_for_requester(
    db: Session,
    *,
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AgentRun:
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.organization_id == organization_id,
            AgentRun.requested_by_user_id == user_id,
        )
    )
    if run is None:
        raise AgentRuntimeError("Agent run not found")
    return run


def _ensure_run_definition_enabled(db: Session, run: AgentRun) -> None:
    enabled = db.scalar(
        select(AgentDefinition.enabled).where(
            AgentDefinition.id == run.agent_definition_id,
            AgentDefinition.organization_id == run.organization_id,
        )
    )
    if enabled is not True:
        raise AgentRuntimeError("Agent definition is disabled")


def _run_read(db: Session, run: AgentRun) -> AgentRunRead:
    steps = list(
        db.scalars(
            select(AgentStep)
            .where(AgentStep.run_id == run.id)
            .order_by(AgentStep.sequence)
        )
    )
    return AgentRunRead(
        id=run.id,
        agent_definition_id=run.agent_definition_id,
        status=run.status,
        objective_sha256=run.objective_sha256,
        objective_char_count=run.objective_char_count,
        step_count=run.step_count,
        final_output_sha256=run.final_output_sha256,
        last_error_code=run.last_error_code,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
        cancelled_at=run.cancelled_at,
        steps=[
            AgentStepRead(
                id=step.id,
                sequence=step.sequence,
                tool_name=step.tool_name,
                policy=step.policy,
                status=step.status,
                arguments=step.arguments_json,
                arguments_sha256=step.arguments_sha256,
                proposal_reason=step.proposal_reason,
                result_sha256=step.result_sha256,
                result_metadata=step.result_metadata,
                approval_expires_at=step.approval_expires_at,
                approved_at=step.approved_at,
                completed_at=step.completed_at,
                error_code=step.error_code,
            )
            for step in steps
        ],
    )


@router.post("/definitions", response_model=AgentDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_definition(
    organization_id: uuid.UUID,
    payload: AgentDefinitionCreate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentDefinitionRead:
    policies: dict[str, AgentToolPolicyMode] = {}
    for item in payload.tool_policies:
        if item.tool_name in policies:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate agent tool policy",
            )
        policies[item.tool_name] = item.policy
    try:
        definition = create_agent_definition(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            name=payload.name,
            description=payload.description,
            provider_configuration_id=payload.provider_configuration_id,
            model_configuration_id=payload.model_configuration_id,
            max_steps=payload.max_steps,
            tool_policies=policies,
        )
    except AgentRuntimeError as exc:
        _raise_runtime_error(exc)
    return _definition_read(db, definition)


@router.get("/definitions", response_model=list[AgentDefinitionRead])
def list_definitions(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AgentDefinitionRead]:
    del authorization
    definitions = list(
        db.scalars(
            select(AgentDefinition)
            .where(
                AgentDefinition.organization_id == organization_id,
                AgentDefinition.enabled.is_(True),
            )
            .order_by(AgentDefinition.name, AgentDefinition.id)
        )
    )
    return [_definition_read(db, item) for item in definitions]


@router.post("/definitions/{agent_id}/status", response_model=AgentDefinitionRead)
def update_definition_status(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    payload: AgentDefinitionStatusUpdate,
    authorization: Annotated[AuthorizationContext, Depends(_manage_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentDefinitionRead:
    try:
        definition = set_agent_enabled(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user_id,
            agent_definition_id=agent_id,
            enabled=payload.enabled,
        )
    except AgentRuntimeError as exc:
        _raise_runtime_error(exc)
    return _definition_read(db, definition)


@router.post(
    "/definitions/{agent_id}/runs",
    response_model=AgentRunRead,
    status_code=status.HTTP_201_CREATED,
)
def start_run(
    organization_id: uuid.UUID,
    agent_id: uuid.UUID,
    payload: AgentRunCreate,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentRunRead:
    try:
        run = create_agent_run(
            db,
            organization_id=organization_id,
            agent_definition_id=agent_id,
            requested_by_user_id=authorization.user_id,
            objective=payload.objective,
        )
    except AgentRuntimeError as exc:
        _raise_runtime_error(exc)
    return _run_read(db, run)


@router.get("/runs/{run_id}", response_model=AgentRunRead)
def read_run(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentRunRead:
    try:
        run = _run_for_requester(
            db,
            organization_id=organization_id,
            run_id=run_id,
            user_id=authorization.user_id,
        )
    except AgentRuntimeError as exc:
        _raise_runtime_error(exc)
    return _run_read(db, run)


@router.post("/runs/{run_id}/advance", response_model=AgentAdvanceResponse)
def advance_run(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: AgentAdvanceRequest,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> AgentAdvanceResponse:
    try:
        with agent_run_lock(db, run_id):
            run = _run_for_requester(
                db,
                organization_id=organization_id,
                run_id=run_id,
                user_id=authorization.user_id,
            )
            _ensure_run_definition_enabled(db, run)
            result = advance_agent_run(
                db,
                secret_store=secret_store,
                organization_id=organization_id,
                run_id=run_id,
                user_id=authorization.user_id,
                role=authorization.role,
                objective=payload.objective,
            )
    except AgentRunBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        _raise_runtime_error(exc)
    return AgentAdvanceResponse(run=_run_read(db, result.run), final_output=result.final_output)


@router.post("/runs/{run_id}/steps/{step_id}/approval", response_model=AgentRunRead)
def decide_step(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    payload: AgentApprovalRequest,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentRunRead:
    try:
        with agent_run_lock(db, run_id):
            run = _run_for_requester(
                db,
                organization_id=organization_id,
                run_id=run_id,
                user_id=authorization.user_id,
            )
            if payload.approve:
                _ensure_run_definition_enabled(db, run)
            decide_agent_step(
                db,
                organization_id=organization_id,
                run_id=run_id,
                step_id=step_id,
                user_id=authorization.user_id,
                approve=payload.approve,
                reason=payload.reason,
            )
            run = _run_for_requester(
                db,
                organization_id=organization_id,
                run_id=run_id,
                user_id=authorization.user_id,
            )
    except AgentRunBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        _raise_runtime_error(exc)
    return _run_read(db, run)


@router.post("/runs/{run_id}/cancel", response_model=AgentRunRead)
def cancel_run(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
) -> AgentRunRead:
    try:
        with agent_run_lock(db, run_id):
            run = cancel_agent_run(
                db,
                organization_id=organization_id,
                run_id=run_id,
                user_id=authorization.user_id,
            )
    except AgentRunBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        _raise_runtime_error(exc)
    return _run_read(db, run)
