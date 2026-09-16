import uuid
from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent_locking import AgentRunBusyError, agent_run_lock
from app.agent_models import AgentRunStatus
from app.agent_runtime import AgentRuntimeError, advance_agent_run
from app.agent_workspace import (
    AgentWorkspaceError,
    execute_workspace_tool,
    get_workspace_run,
    resolve_workspace_context,
)
from app.database import get_db
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.secrets import SecretStore, get_secret_store

router = APIRouter(
    prefix="/organizations/{organization_id}/agent-workspace",
    tags=["agent-workspace"],
)
_use_agents = require_organization_permission(Permission.AGENT_USE)


class AgentWorkspaceAdvanceRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=20_000)

    model_config = {"extra": "forbid"}


class AgentWorkspaceAdvanceResponse(BaseModel):
    run_id: uuid.UUID
    status: AgentRunStatus
    final_output: str | None


def _raise_workspace_error(exc: AgentWorkspaceError) -> None:
    code = (
        status.HTTP_404_NOT_FOUND
        if exc.code in {"workspace_context_not_found", "workspace_run_not_found"}
        else status.HTTP_400_BAD_REQUEST
    )
    raise HTTPException(
        status_code=code,
        detail={"code": exc.code, "message": str(exc)},
    ) from exc


@router.post("/runs/{run_id}/advance", response_model=AgentWorkspaceAdvanceResponse)
def advance_workspace_run(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    payload: AgentWorkspaceAdvanceRequest,
    authorization: Annotated[AuthorizationContext, Depends(_use_agents)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> AgentWorkspaceAdvanceResponse:
    try:
        with agent_run_lock(db, run_id):
            run, binding = get_workspace_run(
                db,
                organization_id=organization_id,
                user_id=authorization.user_id,
                run_id=run_id,
            )
            context = resolve_workspace_context(
                db,
                organization_id=organization_id,
                user_id=authorization.user_id,
                role=authorization.role,
                project_node_id=binding.project_node_id,
                native_channel_id=binding.native_channel_id,
            )
            result = advance_agent_run(
                db,
                secret_store=secret_store,
                organization_id=organization_id,
                run_id=run.id,
                user_id=authorization.user_id,
                role=authorization.role,
                objective=payload.objective,
                tool_executor=partial(
                    execute_workspace_tool,
                    run_id=run.id,
                    project=context.project,
                ),
            )
    except AgentRunBusyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AgentWorkspaceError as exc:
        _raise_workspace_error(exc)
    except AgentRuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent workspace run could not advance safely",
        ) from exc

    return AgentWorkspaceAdvanceResponse(
        run_id=result.run.id,
        status=result.run.status,
        final_output=result.final_output,
    )
