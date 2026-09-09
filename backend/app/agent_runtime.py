import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
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
from app.agent_tools import (
    TOOL_CATALOG,
    AgentToolError,
    ToolExecutionResult,
    execute_tool,
    normalize_tool_arguments,
    policy_valid_for_tool,
    tool_definition,
)
from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderConfiguration,
    AIProviderStatus,
)
from app.ai_provider_adapter import AIGatewayError, AIProviderAdapter
from app.ai_provider_registry import AIInvocationError, invoke_ai
from app.data_governance import DataGovernanceError, append_audit_event
from app.models import MembershipRole
from app.secrets import SecretStore

_APPROVAL_TTL = timedelta(hours=24)
_STALE_EXECUTION_AFTER = timedelta(minutes=5)
_MAX_OBJECTIVE_CHARS = 20_000


class AgentRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AgentAdvanceResult:
    run: AgentRun
    final_output: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _sha256_json(value: dict[str, object]) -> str:
    return _sha256_text(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _normalize_objective(objective: str) -> str:
    normalized = objective.strip()
    if not normalized:
        raise AgentRuntimeError("Agent objective is required")
    if len(normalized) > _MAX_OBJECTIVE_CHARS:
        raise AgentRuntimeError("Agent objective exceeds 20000 characters")
    return normalized


def _agent_definition(
    db: Session,
    *,
    organization_id: uuid.UUID,
    agent_definition_id: uuid.UUID,
) -> AgentDefinition:
    definition = db.scalar(
        select(AgentDefinition).where(
            AgentDefinition.id == agent_definition_id,
            AgentDefinition.organization_id == organization_id,
        )
    )
    if definition is None:
        raise AgentRuntimeError("Agent definition not found")
    return definition


def _policies_for_agent(db: Session, definition: AgentDefinition) -> dict[str, AgentToolPolicyMode]:
    rows = db.scalars(
        select(AgentToolPolicy).where(
            AgentToolPolicy.organization_id == definition.organization_id,
            AgentToolPolicy.agent_definition_id == definition.id,
        )
    )
    return {row.tool_name: row.policy for row in rows}


def create_agent_definition(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    description: str | None,
    provider_configuration_id: uuid.UUID,
    model_configuration_id: uuid.UUID,
    max_steps: int,
    tool_policies: dict[str, AgentToolPolicyMode],
) -> AgentDefinition:
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 160:
        raise AgentRuntimeError("Agent name must be between 1 and 160 characters")
    normalized_description = description.strip() if description else None
    if normalized_description and len(normalized_description) > 500:
        raise AgentRuntimeError("Agent description exceeds 500 characters")
    if not 1 <= max_steps <= 20:
        raise AgentRuntimeError("Agent max_steps must be between 1 and 20")
    if len(tool_policies) > len(TOOL_CATALOG):
        raise AgentRuntimeError("Agent tool policy contains unsupported tools")

    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == provider_configuration_id,
            AIProviderConfiguration.organization_id == organization_id,
        )
    )
    model = db.scalar(
        select(AIModelConfiguration).where(
            AIModelConfiguration.id == model_configuration_id,
            AIModelConfiguration.organization_id == organization_id,
            AIModelConfiguration.provider_configuration_id == provider_configuration_id,
        )
    )
    if provider is None or model is None:
        raise AgentRuntimeError("Agent provider/model configuration not found")
    if provider.status != AIProviderStatus.ENABLED or not model.enabled:
        raise AgentRuntimeError("Agent provider/model must be enabled when configured")

    for tool_name, policy in tool_policies.items():
        tool = tool_definition(tool_name)
        if tool is None:
            raise AgentRuntimeError(f"Unsupported agent tool: {tool_name}")
        if not policy_valid_for_tool(tool, policy):
            raise AgentRuntimeError(
                f"Policy {policy.value} cannot be assigned to tool {tool_name}"
            )

    definition = AgentDefinition(
        organization_id=organization_id,
        name=normalized_name,
        description=normalized_description,
        provider_configuration_id=provider_configuration_id,
        model_configuration_id=model_configuration_id,
        max_steps=max_steps,
        enabled=True,
        created_by_user_id=actor_user_id,
    )
    db.add(definition)
    try:
        db.flush()
        for tool_name, policy in sorted(tool_policies.items()):
            db.add(
                AgentToolPolicy(
                    organization_id=organization_id,
                    agent_definition_id=definition.id,
                    tool_name=tool_name,
                    policy=policy,
                    created_by_user_id=actor_user_id,
                )
            )
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"agent.definition.created:{definition.id}",
            event_type="agent.definition.created",
            outcome="succeeded",
            actor_user_id=actor_user_id,
            resource_type="agent_definition",
            resource_id=definition.id,
            metadata={
                "name": normalized_name,
                "max_steps": max_steps,
                "provider_configuration_id": provider_configuration_id,
                "model_configuration_id": model_configuration_id,
                "tool_policy_count": len(tool_policies),
            },
        )
    except IntegrityError as exc:
        db.rollback()
        raise AgentRuntimeError("Agent definition name already exists") from exc
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise AgentRuntimeError("Agent definition could not be audited") from exc
    db.refresh(definition)
    return definition


def set_agent_enabled(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    agent_definition_id: uuid.UUID,
    enabled: bool,
) -> AgentDefinition:
    definition = _agent_definition(
        db,
        organization_id=organization_id,
        agent_definition_id=agent_definition_id,
    )
    definition.enabled = enabled
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"agent.definition.status:{definition.id}:{uuid.uuid4()}",
            event_type="agent.definition.status_changed",
            outcome="succeeded",
            actor_user_id=actor_user_id,
            resource_type="agent_definition",
            resource_id=definition.id,
            metadata={"enabled": enabled},
        )
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise AgentRuntimeError("Agent status change could not be audited") from exc
    db.refresh(definition)
    return definition


def create_agent_run(
    db: Session,
    *,
    organization_id: uuid.UUID,
    agent_definition_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    objective: str,
) -> AgentRun:
    definition = _agent_definition(
        db,
        organization_id=organization_id,
        agent_definition_id=agent_definition_id,
    )
    if not definition.enabled:
        raise AgentRuntimeError("Agent definition is disabled")
    normalized = _normalize_objective(objective)
    run = AgentRun(
        organization_id=organization_id,
        agent_definition_id=definition.id,
        requested_by_user_id=requested_by_user_id,
        status=AgentRunStatus.READY,
        objective_sha256=_sha256_text(normalized),
        objective_char_count=len(normalized),
        step_count=0,
    )
    db.add(run)
    db.flush()
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"agent.run.created:{run.id}",
            event_type="agent.run.created",
            outcome="succeeded",
            actor_user_id=requested_by_user_id,
            resource_type="agent_run",
            resource_id=run.id,
            metadata={
                "agent_definition_id": definition.id,
                "objective_sha256": run.objective_sha256,
                "objective_char_count": run.objective_char_count,
            },
        )
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise AgentRuntimeError("Agent run could not be audited") from exc
    db.refresh(run)
    return run


def _load_requester_run(
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


def _pending_step(db: Session, run: AgentRun, status: AgentStepStatus) -> AgentStep | None:
    return db.scalar(
        select(AgentStep)
        .where(
            AgentStep.run_id == run.id,
            AgentStep.organization_id == run.organization_id,
            AgentStep.status == status,
        )
        .order_by(AgentStep.sequence)
        .limit(1)
    )


def _expire_approval(db: Session, run: AgentRun, step: AgentStep) -> None:
    step.status = AgentStepStatus.EXPIRED
    step.arguments_json = {}
    step.proposal_reason = None
    step.error_code = "approval_expired"
    step.completed_at = _now()
    run.status = AgentRunStatus.FAILED
    run.last_error_code = "approval_expired"
    append_audit_event(
        db,
        organization_id=run.organization_id,
        event_key=f"agent.approval.expired:{step.id}",
        event_type="agent.approval.expired",
        outcome="expired",
        actor_user_id=run.requested_by_user_id,
        resource_type="agent_step",
        resource_id=step.id,
        metadata={"tool_name": step.tool_name, "run_id": run.id},
    )


def decide_agent_step(
    db: Session,
    *,
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    step_id: uuid.UUID,
    user_id: uuid.UUID,
    approve: bool,
    reason: str | None,
) -> AgentStep:
    run = _load_requester_run(
        db,
        organization_id=organization_id,
        run_id=run_id,
        user_id=user_id,
    )
    step = db.scalar(
        select(AgentStep).where(
            AgentStep.id == step_id,
            AgentStep.run_id == run.id,
            AgentStep.organization_id == organization_id,
        )
    )
    if step is None:
        raise AgentRuntimeError("Agent step not found")
    if step.status != AgentStepStatus.WAITING_APPROVAL:
        raise AgentRuntimeError("Agent step is not waiting for approval")
    now = _now()
    if step.approval_expires_at is None or step.approval_expires_at <= now:
        try:
            _expire_approval(db, run, step)
        except (DataGovernanceError, SQLAlchemyError) as exc:
            db.rollback()
            raise AgentRuntimeError("Expired approval could not be audited") from exc
        raise AgentRuntimeError("Agent approval expired")

    normalized_reason = reason.strip()[:500] if reason and reason.strip() else None
    step.approved_by_user_id = user_id
    step.approval_reason = normalized_reason
    step.approved_at = now
    if approve:
        step.status = AgentStepStatus.APPROVED
        run.status = AgentRunStatus.READY
        event_type = "agent.approval.approved"
        outcome = "approved"
    else:
        step.status = AgentStepStatus.REJECTED
        step.arguments_json = {}
        step.proposal_reason = None
        step.completed_at = now
        run.status = AgentRunStatus.CANCELLED
        run.cancelled_at = now
        run.last_error_code = "approval_rejected"
        event_type = "agent.approval.rejected"
        outcome = "rejected"
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"{event_type}:{step.id}",
            event_type=event_type,
            outcome=outcome,
            actor_user_id=user_id,
            resource_type="agent_step",
            resource_id=step.id,
            metadata={
                "run_id": run.id,
                "tool_name": step.tool_name,
                "arguments_sha256": step.arguments_sha256,
            },
        )
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise AgentRuntimeError("Agent approval decision could not be audited") from exc
    db.refresh(step)
    return step


def cancel_agent_run(
    db: Session,
    *,
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AgentRun:
    run = _load_requester_run(
        db,
        organization_id=organization_id,
        run_id=run_id,
        user_id=user_id,
    )
    if run.status in {AgentRunStatus.COMPLETED, AgentRunStatus.CANCELLED}:
        return run
    if run.status == AgentRunStatus.PLANNING:
        raise AgentRuntimeError("Agent run is currently planning and cannot be cancelled safely")
    for step in db.scalars(
        select(AgentStep).where(
            AgentStep.run_id == run.id,
            AgentStep.status.in_(
                [AgentStepStatus.WAITING_APPROVAL, AgentStepStatus.APPROVED]
            ),
        )
    ):
        step.status = AgentStepStatus.REJECTED
        step.arguments_json = {}
        step.proposal_reason = None
        step.error_code = "run_cancelled"
        step.completed_at = _now()
    run.status = AgentRunStatus.CANCELLED
    run.cancelled_at = _now()
    run.last_error_code = "run_cancelled"
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"agent.run.cancelled:{run.id}",
            event_type="agent.run.cancelled",
            outcome="cancelled",
            actor_user_id=user_id,
            resource_type="agent_run",
            resource_id=run.id,
        )
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise AgentRuntimeError("Agent cancellation could not be audited") from exc
    db.refresh(run)
    return run


def _planner_system_text(policies: dict[str, AgentToolPolicyMode]) -> str:
    tool_lines: list[str] = []
    if policies.get("search.query") == AgentToolPolicyMode.READ:
        tool_lines.append(
            '- search.query policy=read arguments={"query": string, "limit": integer 1..5}'
        )
    if policies.get("work_graph.create_work_item") == AgentToolPolicyMode.ACT_WITH_APPROVAL:
        tool_lines.append(
            "- work_graph.create_work_item policy=act_with_approval "
            'arguments={"key": string, "display_name": string}'
        )
    tools = "\n".join(tool_lines) if tool_lines else "- no tools are enabled"
    return (
        "You are the planner inside Brain's governed agent runtime. Tool authority is enforced "
        "server-side. Never claim that an action executed unless its observation says it did. "
        "For company-specific facts, use available evidence tools rather than inventing facts. "
        "Return exactly one JSON object and no markdown. Valid shapes are: "
        '{"action":"tool","tool":"<name>","arguments":{...},"reason":"brief reason"} '
        'or {"action":"final","answer":"<answer>"}. '
        "Do not invent tool names. An approval-required proposal will pause for a human.\n"
        f"Available tools:\n{tools}"
    )


def _safe_transcript(db: Session, run: AgentRun) -> str:
    rows = []
    for step in db.scalars(
        select(AgentStep)
        .where(AgentStep.run_id == run.id)
        .order_by(AgentStep.sequence)
    ):
        rows.append(
            {
                "sequence": step.sequence,
                "tool": step.tool_name,
                "status": step.status.value,
                "result_metadata": step.result_metadata,
                "error_code": step.error_code,
            }
        )
    return json.dumps(rows, sort_keys=True, separators=(",", ":"))


def _parse_planner_output(output: str) -> tuple[str, str | None, dict[str, object], str | None]:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise AgentRuntimeError("Planner returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AgentRuntimeError("Planner output must be one JSON object")
    action = payload.get("action")
    if action == "final":
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise AgentRuntimeError("Planner final answer is empty")
        normalized = answer.strip()
        if len(normalized) > 50_000:
            raise AgentRuntimeError("Planner final answer exceeds 50000 characters")
        return "final", normalized, {}, None
    if action != "tool":
        raise AgentRuntimeError("Planner action must be final or tool")
    tool_name = payload.get("tool")
    arguments = payload.get("arguments")
    reason = payload.get("reason")
    if not isinstance(tool_name, str) or not tool_name:
        raise AgentRuntimeError("Planner tool name is missing")
    if not isinstance(arguments, dict):
        raise AgentRuntimeError("Planner tool arguments must be an object")
    normalized_reason = reason.strip()[:500] if isinstance(reason, str) and reason.strip() else None
    return "tool", tool_name, arguments, normalized_reason


def _mark_run_failed(
    db: Session,
    run: AgentRun,
    *,
    error_code: str,
    actor_user_id: uuid.UUID,
) -> None:
    run.status = AgentRunStatus.FAILED
    run.last_error_code = error_code[:128]
    run.planning_started_at = None
    append_audit_event(
        db,
        organization_id=run.organization_id,
        event_key=f"agent.run.failed:{run.id}:{uuid.uuid4()}",
        event_type="agent.run.failed",
        outcome="failed",
        actor_user_id=actor_user_id,
        resource_type="agent_run",
        resource_id=run.id,
        metadata={"error_code": error_code[:128]},
    )


def _execute_approved_step(
    db: Session,
    *,
    run: AgentRun,
    step: AgentStep,
    user_id: uuid.UUID,
    role: MembershipRole,
    tool_executor: Callable[..., ToolExecutionResult],
) -> str:
    definition = tool_definition(step.tool_name)
    if definition is None or not definition.replay_safe:
        _mark_run_failed(db, run, error_code="tool_not_replay_safe", actor_user_id=user_id)
        raise AgentRuntimeError("Approved tool is not replay-safe")
    now = _now()
    if step.status == AgentStepStatus.EXECUTING:
        if step.execution_started_at and step.execution_started_at > now - _STALE_EXECUTION_AFTER:
            raise AgentRuntimeError("Agent tool execution is already in progress")
    elif step.status != AgentStepStatus.APPROVED:
        raise AgentRuntimeError("Agent step is not approved")

    step.status = AgentStepStatus.EXECUTING
    step.execution_started_at = now
    db.commit()
    try:
        result = tool_executor(
            db,
            organization_id=run.organization_id,
            user_id=user_id,
            role=role,
            tool_name=step.tool_name,
            arguments=step.arguments_json,
        )
        step.status = AgentStepStatus.SUCCEEDED
        step.result_sha256 = result.output_sha256
        step.result_metadata = result.persisted_metadata
        step.arguments_json = {}
        step.proposal_reason = None
        step.error_code = None
        step.completed_at = _now()
        run.status = AgentRunStatus.READY
        run.last_error_code = None
        append_audit_event(
            db,
            organization_id=run.organization_id,
            event_key=f"agent.tool.succeeded:{step.id}",
            event_type="agent.tool.succeeded",
            outcome="succeeded",
            actor_user_id=user_id,
            resource_type="agent_step",
            resource_id=step.id,
            metadata={
                "run_id": run.id,
                "tool_name": step.tool_name,
                "policy": step.policy.value,
                "arguments_sha256": step.arguments_sha256,
                "result_sha256": result.output_sha256,
            },
        )
        return result.ephemeral_output
    except (AgentToolError, DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        run = db.get(AgentRun, run.id) or run
        step = db.get(AgentStep, step.id) or step
        step.status = AgentStepStatus.FAILED
        step.arguments_json = {}
        step.proposal_reason = None
        step.error_code = "tool_execution_failed"
        step.completed_at = _now()
        run.status = AgentRunStatus.FAILED
        run.last_error_code = "tool_execution_failed"
        try:
            append_audit_event(
                db,
                organization_id=run.organization_id,
                event_key=f"agent.tool.failed:{step.id}",
                event_type="agent.tool.failed",
                outcome="failed",
                actor_user_id=user_id,
                resource_type="agent_step",
                resource_id=step.id,
                metadata={"tool_name": step.tool_name, "error_code": "tool_execution_failed"},
            )
        except (DataGovernanceError, SQLAlchemyError):
            db.rollback()
        raise AgentRuntimeError("Agent tool execution failed") from exc


def advance_agent_run(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    objective: str,
    planner_adapter: AIProviderAdapter | None = None,
    tool_executor: Callable[..., ToolExecutionResult] = execute_tool,
) -> AgentAdvanceResult:
    normalized_objective = _normalize_objective(objective)
    run = _load_requester_run(
        db,
        organization_id=organization_id,
        run_id=run_id,
        user_id=user_id,
    )
    if _sha256_text(normalized_objective) != run.objective_sha256:
        raise AgentRuntimeError("Agent objective does not match the run")
    if run.status in {
        AgentRunStatus.COMPLETED,
        AgentRunStatus.FAILED,
        AgentRunStatus.CANCELLED,
        AgentRunStatus.STEP_LIMIT,
    }:
        raise AgentRuntimeError(f"Agent run is terminal: {run.status.value}")

    waiting = _pending_step(db, run, AgentStepStatus.WAITING_APPROVAL)
    if waiting is not None:
        if waiting.approval_expires_at and waiting.approval_expires_at <= _now():
            try:
                _expire_approval(db, run, waiting)
            except (DataGovernanceError, SQLAlchemyError) as exc:
                db.rollback()
                raise AgentRuntimeError("Expired approval could not be audited") from exc
            raise AgentRuntimeError("Agent approval expired")
        run.status = AgentRunStatus.WAITING_APPROVAL
        db.commit()
        return AgentAdvanceResult(run=run)

    observations: list[str] = []
    approved = _pending_step(db, run, AgentStepStatus.APPROVED)
    executing = _pending_step(db, run, AgentStepStatus.EXECUTING)
    if approved is not None or executing is not None:
        step = approved or executing
        assert step is not None
        observations.append(
            _execute_approved_step(
                db,
                run=run,
                step=step,
                user_id=user_id,
                role=role,
                tool_executor=tool_executor,
            )
        )
        db.refresh(run)

    definition = _agent_definition(
        db,
        organization_id=organization_id,
        agent_definition_id=run.agent_definition_id,
    )
    if not definition.enabled:
        _mark_run_failed(db, run, error_code="agent_disabled", actor_user_id=user_id)
        raise AgentRuntimeError("Agent definition is disabled")
    policies = _policies_for_agent(db, definition)

    while run.step_count < definition.max_steps:
        run.status = AgentRunStatus.PLANNING
        run.planning_started_at = _now()
        db.commit()
        planner_input = json.dumps(
            {
                "objective": normalized_objective,
                "durable_transcript": json.loads(_safe_transcript(db, run)),
                "ephemeral_observations": observations,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(planner_input) > 180_000:
            _mark_run_failed(db, run, error_code="planner_context_too_large", actor_user_id=user_id)
            raise AgentRuntimeError("Agent planner context is too large")
        try:
            invocation = invoke_ai(
                db,
                secret_store=secret_store,
                organization_id=organization_id,
                user_id=user_id,
                role=role,
                provider_configuration_id=definition.provider_configuration_id,
                model_configuration_id=definition.model_configuration_id,
                input_text=planner_input,
                system_text=_planner_system_text(policies),
                max_output_tokens=2000,
                attribution_node_id=None,
                adapter=planner_adapter,
            )
            action, value, raw_arguments, proposal_reason = _parse_planner_output(
                invocation.output_text
            )
        except (AIGatewayError, AIInvocationError, AgentRuntimeError) as exc:
            try:
                _mark_run_failed(
                    db,
                    run,
                    error_code="planner_failed",
                    actor_user_id=user_id,
                )
            except (DataGovernanceError, SQLAlchemyError):
                db.rollback()
            raise AgentRuntimeError("Agent planner failed") from exc

        run.planning_started_at = None
        if action == "final":
            assert value is not None
            run.status = AgentRunStatus.COMPLETED
            run.final_output_sha256 = _sha256_text(value)
            run.completed_at = _now()
            run.last_error_code = None
            try:
                append_audit_event(
                    db,
                    organization_id=organization_id,
                    event_key=f"agent.run.completed:{run.id}",
                    event_type="agent.run.completed",
                    outcome="succeeded",
                    actor_user_id=user_id,
                    resource_type="agent_run",
                    resource_id=run.id,
                    metadata={
                        "step_count": run.step_count,
                        "final_output_sha256": run.final_output_sha256,
                    },
                )
            except (DataGovernanceError, SQLAlchemyError) as exc:
                db.rollback()
                raise AgentRuntimeError("Agent completion could not be audited") from exc
            db.refresh(run)
            return AgentAdvanceResult(run=run, final_output=value)

        tool_name = value or ""
        tool = tool_definition(tool_name)
        policy = policies.get(tool_name, AgentToolPolicyMode.DENY)
        sequence = run.step_count + 1
        if tool is None or not policy_valid_for_tool(tool, policy) or policy == AgentToolPolicyMode.DENY:
            digest = _sha256_json(raw_arguments)
            step = AgentStep(
                organization_id=organization_id,
                run_id=run.id,
                sequence=sequence,
                tool_name=tool_name[:128] or "unknown",
                policy=AgentToolPolicyMode.DENY,
                status=AgentStepStatus.DENIED,
                arguments_json={},
                arguments_sha256=digest,
                proposal_reason=None,
                error_code="tool_denied",
                completed_at=_now(),
            )
            db.add(step)
            run.step_count = sequence
            run.status = AgentRunStatus.FAILED
            run.last_error_code = "tool_denied"
            db.flush()
            try:
                append_audit_event(
                    db,
                    organization_id=organization_id,
                    event_key=f"agent.tool.denied:{step.id}",
                    event_type="agent.tool.denied",
                    outcome="denied",
                    actor_user_id=user_id,
                    resource_type="agent_step",
                    resource_id=step.id,
                    metadata={
                        "run_id": run.id,
                        "tool_name": step.tool_name,
                        "arguments_sha256": digest,
                    },
                )
            except (DataGovernanceError, SQLAlchemyError) as exc:
                db.rollback()
                raise AgentRuntimeError("Denied tool proposal could not be audited") from exc
            raise AgentRuntimeError("Agent proposed a denied tool")

        try:
            normalized_arguments = normalize_tool_arguments(tool_name, raw_arguments)
        except AgentToolError as exc:
            _mark_run_failed(db, run, error_code="invalid_tool_arguments", actor_user_id=user_id)
            raise AgentRuntimeError("Agent proposed invalid tool arguments") from exc
        arguments_digest = _sha256_json(normalized_arguments)

        if policy == AgentToolPolicyMode.ACT_WITH_APPROVAL:
            step = AgentStep(
                organization_id=organization_id,
                run_id=run.id,
                sequence=sequence,
                tool_name=tool_name,
                policy=policy,
                status=AgentStepStatus.WAITING_APPROVAL,
                arguments_json=normalized_arguments,
                arguments_sha256=arguments_digest,
                proposal_reason=proposal_reason,
                approval_expires_at=_now() + _APPROVAL_TTL,
            )
            db.add(step)
            run.step_count = sequence
            run.status = AgentRunStatus.WAITING_APPROVAL
            db.flush()
            try:
                append_audit_event(
                    db,
                    organization_id=organization_id,
                    event_key=f"agent.approval.requested:{step.id}",
                    event_type="agent.approval.requested",
                    outcome="pending",
                    actor_user_id=user_id,
                    resource_type="agent_step",
                    resource_id=step.id,
                    metadata={
                        "run_id": run.id,
                        "tool_name": tool_name,
                        "arguments_sha256": arguments_digest,
                    },
                )
            except (DataGovernanceError, SQLAlchemyError) as exc:
                db.rollback()
                raise AgentRuntimeError("Agent approval request could not be audited") from exc
            db.refresh(run)
            return AgentAdvanceResult(run=run)

        step = AgentStep(
            organization_id=organization_id,
            run_id=run.id,
            sequence=sequence,
            tool_name=tool_name,
            policy=policy,
            status=AgentStepStatus.EXECUTING,
            arguments_json={},
            arguments_sha256=arguments_digest,
            proposal_reason=None,
            execution_started_at=_now(),
        )
        db.add(step)
        db.flush()
        try:
            result = tool_executor(
                db,
                organization_id=organization_id,
                user_id=user_id,
                role=role,
                tool_name=tool_name,
                arguments=normalized_arguments,
            )
            step.status = AgentStepStatus.SUCCEEDED
            step.result_sha256 = result.output_sha256
            step.result_metadata = result.persisted_metadata
            step.completed_at = _now()
            run.step_count = sequence
            run.status = AgentRunStatus.READY
            run.last_error_code = None
            append_audit_event(
                db,
                organization_id=organization_id,
                event_key=f"agent.tool.succeeded:{step.id}",
                event_type="agent.tool.succeeded",
                outcome="succeeded",
                actor_user_id=user_id,
                resource_type="agent_step",
                resource_id=step.id,
                metadata={
                    "run_id": run.id,
                    "tool_name": tool_name,
                    "policy": policy.value,
                    "arguments_sha256": arguments_digest,
                    "result_sha256": result.output_sha256,
                },
            )
            observations.append(result.ephemeral_output)
            db.refresh(run)
        except (AgentToolError, DataGovernanceError, SQLAlchemyError) as exc:
            db.rollback()
            run = db.get(AgentRun, run.id) or run
            step = db.get(AgentStep, step.id) or step
            step.status = AgentStepStatus.FAILED
            step.arguments_json = {}
            step.proposal_reason = None
            step.error_code = "tool_execution_failed"
            step.completed_at = _now()
            run.status = AgentRunStatus.FAILED
            run.last_error_code = "tool_execution_failed"
            try:
                append_audit_event(
                    db,
                    organization_id=organization_id,
                    event_key=f"agent.tool.failed:{step.id}",
                    event_type="agent.tool.failed",
                    outcome="failed",
                    actor_user_id=user_id,
                    resource_type="agent_step",
                    resource_id=step.id,
                    metadata={"tool_name": step.tool_name, "error_code": "tool_execution_failed"},
                )
            except (DataGovernanceError, SQLAlchemyError):
                db.rollback()
            raise AgentRuntimeError("Agent tool execution failed") from exc

    run.status = AgentRunStatus.STEP_LIMIT
    run.last_error_code = "step_limit_reached"
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"agent.run.step_limit:{run.id}",
            event_type="agent.run.step_limit",
            outcome="stopped",
            actor_user_id=user_id,
            resource_type="agent_run",
            resource_id=run.id,
            metadata={"step_count": run.step_count, "max_steps": definition.max_steps},
        )
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise AgentRuntimeError("Agent step-limit stop could not be audited") from exc
    db.refresh(run)
    return AgentAdvanceResult(run=run)
