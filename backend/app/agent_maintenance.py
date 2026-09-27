import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent_models import AgentRun, AgentRunStatus, AgentStep, AgentStepStatus
from app.agent_tools import tool_definition
from app.data_governance import DataGovernanceError, append_audit_event

_STALE_AFTER = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class AgentMaintenanceResult:
    approvals_expired: int
    planning_recovered: int
    executions_recovered: int
    executions_failed_closed: int


def _now() -> datetime:
    return datetime.now(UTC)


def _locked(query, db: Session):
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return query.with_for_update(skip_locked=True)
    return query


def maintain_agent_runtime(
    db: Session,
    *,
    at: datetime | None = None,
    limit: int = 100,
) -> AgentMaintenanceResult:
    if limit < 1 or limit > 500:
        raise ValueError("Agent maintenance limit must be between 1 and 500")
    now = at or _now()
    stale_before = now - _STALE_AFTER
    approvals_expired = 0
    planning_recovered = 0
    executions_recovered = 0
    executions_failed_closed = 0

    approval_query = (
        select(AgentStep)
        .where(
            AgentStep.status == AgentStepStatus.WAITING_APPROVAL,
            AgentStep.approval_expires_at.is_not(None),
            AgentStep.approval_expires_at <= now,
        )
        .order_by(AgentStep.approval_expires_at, AgentStep.id)
        .limit(limit)
    )
    for step in list(db.scalars(_locked(approval_query, db))):
        run = db.get(AgentRun, step.run_id)
        if run is None or step.status != AgentStepStatus.WAITING_APPROVAL:
            continue
        step.status = AgentStepStatus.EXPIRED
        step.arguments_json = {}
        step.proposal_reason = None
        step.error_code = "approval_expired"
        step.completed_at = now
        run.status = AgentRunStatus.FAILED
        run.last_error_code = "approval_expired"
        try:
            append_audit_event(
                db,
                organization_id=step.organization_id,
                event_key=f"agent.approval.expired:{step.id}",
                event_type="agent.approval.expired",
                outcome="expired",
                actor_user_id=run.requested_by_user_id,
                resource_type="agent_step",
                resource_id=step.id,
                metadata={"run_id": run.id, "tool_name": step.tool_name},
            )
        except (DataGovernanceError, SQLAlchemyError):
            db.rollback()
            continue
        approvals_expired += 1

    planning_query = (
        select(AgentRun)
        .where(
            AgentRun.status == AgentRunStatus.PLANNING,
            AgentRun.planning_started_at.is_not(None),
            AgentRun.planning_started_at < stale_before,
        )
        .order_by(AgentRun.planning_started_at, AgentRun.id)
        .limit(limit)
    )
    for run in list(db.scalars(_locked(planning_query, db))):
        if run.status != AgentRunStatus.PLANNING:
            continue
        run.status = AgentRunStatus.READY
        run.planning_started_at = None
        run.last_error_code = "stale_planning_recovered"
        try:
            append_audit_event(
                db,
                organization_id=run.organization_id,
                event_key=f"agent.run.planning_recovered:{run.id}:{uuid.uuid4()}",
                event_type="agent.run.planning_recovered",
                outcome="recovered",
                actor_user_id=run.requested_by_user_id,
                resource_type="agent_run",
                resource_id=run.id,
            )
        except (DataGovernanceError, SQLAlchemyError):
            db.rollback()
            continue
        planning_recovered += 1

    execution_query = (
        select(AgentStep)
        .where(
            AgentStep.status == AgentStepStatus.EXECUTING,
            AgentStep.execution_started_at.is_not(None),
            AgentStep.execution_started_at < stale_before,
        )
        .order_by(AgentStep.execution_started_at, AgentStep.id)
        .limit(limit)
    )
    for step in list(db.scalars(_locked(execution_query, db))):
        run = db.get(AgentRun, step.run_id)
        if run is None or step.status != AgentStepStatus.EXECUTING:
            continue
        tool = tool_definition(step.tool_name)
        if tool is not None and tool.replay_safe:
            step.status = AgentStepStatus.APPROVED
            step.execution_started_at = None
            run.status = AgentRunStatus.READY
            run.last_error_code = "stale_execution_recovered"
            event_type = "agent.tool.execution_recovered"
            outcome = "recovered"
            executions_recovered += 1
        else:
            step.status = AgentStepStatus.FAILED
            step.arguments_json = {}
            step.proposal_reason = None
            step.error_code = "stale_execution_not_replay_safe"
            step.completed_at = now
            run.status = AgentRunStatus.FAILED
            run.last_error_code = "stale_execution_not_replay_safe"
            event_type = "agent.tool.execution_failed_closed"
            outcome = "failed"
            executions_failed_closed += 1
        try:
            append_audit_event(
                db,
                organization_id=step.organization_id,
                event_key=f"{event_type}:{step.id}:{uuid.uuid4()}",
                event_type=event_type,
                outcome=outcome,
                actor_user_id=run.requested_by_user_id,
                resource_type="agent_step",
                resource_id=step.id,
                metadata={"run_id": run.id, "tool_name": step.tool_name},
            )
        except (DataGovernanceError, SQLAlchemyError):
            db.rollback()
            if outcome == "recovered":
                executions_recovered -= 1
            else:
                executions_failed_closed -= 1

    return AgentMaintenanceResult(
        approvals_expired=approvals_expired,
        planning_recovered=planning_recovered,
        executions_recovered=executions_recovered,
        executions_failed_closed=executions_failed_closed,
    )
