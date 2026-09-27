import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.agent_maintenance import maintain_agent_runtime
from app.agent_models import (
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    AgentToolPolicyMode,
)
from app.models import Organization, User


def _run(db: Session, suffix: str) -> tuple[Organization, User, AgentRun]:
    user = User(email=f"agent-maint-{suffix}@example.com")
    organization = Organization(name=f"Agent Maint {suffix}", slug=f"agent-maint-{suffix}")
    db.add_all([user, organization])
    db.flush()
    run = AgentRun(
        organization_id=organization.id,
        agent_definition_id=uuid.uuid4(),
        requested_by_user_id=user.id,
        status=AgentRunStatus.READY,
        objective_sha256=hashlib.sha256(b"objective").hexdigest(),
        objective_char_count=9,
        step_count=0,
    )
    return organization, user, run


def test_expired_approval_is_cleared_and_run_fails(db_session: Session) -> None:
    now = datetime.now(UTC)
    organization, _, run = _run(db_session, "expiry")
    db_session.add(run)
    db_session.flush()
    step = AgentStep(
        organization_id=organization.id,
        run_id=run.id,
        sequence=1,
        tool_name="work_graph.create_work_item",
        policy=AgentToolPolicyMode.ACT_WITH_APPROVAL,
        status=AgentStepStatus.WAITING_APPROVAL,
        arguments_json={"key": "pending", "display_name": "Pending"},
        arguments_sha256=hashlib.sha256(b"pending").hexdigest(),
        approved_by_user_id=None,
        approval_expires_at=now - timedelta(seconds=1),
    )
    run.status = AgentRunStatus.WAITING_APPROVAL
    run.step_count = 1
    db_session.add(step)
    db_session.commit()

    result = maintain_agent_runtime(db_session, at=now, limit=10)

    assert result.approvals_expired == 1
    db_session.refresh(run)
    db_session.refresh(step)
    assert run.status == AgentRunStatus.FAILED
    assert step.status == AgentStepStatus.EXPIRED
    assert step.arguments_json == {}
    assert step.proposal_reason is None


def test_stale_planning_run_returns_to_ready(db_session: Session) -> None:
    now = datetime.now(UTC)
    _, _, run = _run(db_session, "planning")
    run.status = AgentRunStatus.PLANNING
    run.planning_started_at = now - timedelta(minutes=10)
    db_session.add(run)
    db_session.commit()

    result = maintain_agent_runtime(db_session, at=now, limit=10)

    assert result.planning_recovered == 1
    db_session.refresh(run)
    assert run.status == AgentRunStatus.READY
    assert run.planning_started_at is None
