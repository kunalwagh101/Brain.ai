import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.activity import ActivityItem, emit_activity
from app.activity_models import (
    ActivityKind,
    ActivityNotification,
    ActivityPreference,
    ActivityResourceType,
)
from app.agent_models import AgentRun, AgentRunStatus, AgentStep, AgentStepStatus
from app.agent_workspace_models import AgentRunContext
from app.decision_memory_models import DecisionMemoryCandidate, MemoryKind, MemoryState
from app.models import (
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Membership,
)
from app.native_chat_models import NativeChannel, NativeMessage
from app.native_conversation_models import NativeChannelReadState
from app.permissions import Permission, role_has_permission
from app.project_status_models import ProjectProgressItem
from app.work_graph import node_visible_to_user
from app.work_graph_models import WorkGraphNode


SYSTEM_KINDS = frozenset(
    {
        ActivityKind.CHANNEL_ACTIVITY,
        ActivityKind.AGENT_APPROVAL,
        ActivityKind.AGENT_COMPLETED,
        ActivityKind.AGENT_FAILED,
        ActivityKind.PROJECT_UPDATE,
        ActivityKind.BLOCKER_UPDATE,
        ActivityKind.INTEGRATION_FAILURE,
    }
)


def get_activity_preferences(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ActivityPreference:
    row = db.scalar(
        select(ActivityPreference).where(
            ActivityPreference.organization_id == organization_id,
            ActivityPreference.user_id == user_id,
        )
    )
    if row is not None:
        return row
    row = ActivityPreference(organization_id=organization_id, user_id=user_id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_activity_preferences(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    values: dict[str, bool],
) -> ActivityPreference:
    row = get_activity_preferences(
        db,
        organization_id=organization_id,
        user_id=user_id,
    )
    allowed = {
        "mentions",
        "thread_replies",
        "direct_messages",
        "channel_activity",
        "agent_approvals",
        "agent_run_events",
        "project_updates",
        "integration_failures",
    }
    unknown = set(values) - allowed
    if unknown:
        raise ValueError("Unknown Activity preference")
    for key, value in values.items():
        if not isinstance(value, bool):
            raise ValueError("Activity preferences must be boolean")
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def preference_payload(row: ActivityPreference) -> dict[str, bool]:
    return {
        "mentions": row.mentions,
        "thread_replies": row.thread_replies,
        "direct_messages": row.direct_messages,
        "channel_activity": row.channel_activity,
        "agent_approvals": row.agent_approvals,
        "agent_run_events": row.agent_run_events,
        "project_updates": row.project_updates,
        "integration_failures": row.integration_failures,
    }


def kind_enabled(preferences: ActivityPreference, kind: ActivityKind) -> bool:
    if kind == ActivityKind.MENTION:
        return preferences.mentions
    if kind == ActivityKind.THREAD_REPLY:
        return preferences.thread_replies
    if kind == ActivityKind.DIRECT_MESSAGE:
        return preferences.direct_messages
    if kind == ActivityKind.CHANNEL_ACTIVITY:
        return preferences.channel_activity
    if kind == ActivityKind.AGENT_APPROVAL:
        return preferences.agent_approvals
    if kind in {ActivityKind.AGENT_COMPLETED, ActivityKind.AGENT_FAILED}:
        return preferences.agent_run_events
    if kind in {ActivityKind.PROJECT_UPDATE, ActivityKind.BLOCKER_UPDATE}:
        return preferences.project_updates
    if kind == ActivityKind.INTEGRATION_FAILURE:
        return preferences.integration_failures
    return True


def _membership(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
    return db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    )


def _channel_visible(db: Session, channel: NativeChannel, user_id: uuid.UUID) -> bool:
    from app.native_chat import can_read_channel

    return can_read_channel(db, channel, user_id=user_id)


def _context_visible(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    membership: Membership,
    context: AgentRunContext | None,
) -> bool:
    if context is None:
        return True
    if context.organization_id != organization_id:
        return False
    if context.native_channel_id is not None:
        channel = db.get(NativeChannel, context.native_channel_id)
        return bool(
            channel is not None
            and channel.organization_id == organization_id
            and _channel_visible(db, channel, user_id)
        )
    if context.project_node_id is not None:
        node = db.get(WorkGraphNode, context.project_node_id)
        return bool(
            node is not None
            and node.organization_id == organization_id
            and node_visible_to_user(db, node, user_id=user_id, role=membership.role)
        )
    return False


def _upsert_channel_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    channel: NativeChannel,
    latest: NativeMessage,
) -> None:
    key = f"channel-activity:{channel.id}:{user_id}"
    row = db.scalar(
        select(ActivityNotification).where(
            ActivityNotification.organization_id == organization_id,
            ActivityNotification.recipient_user_id == user_id,
            ActivityNotification.dedupe_key == key,
        )
    )
    if row is None:
        db.add(
            ActivityNotification(
                organization_id=organization_id,
                recipient_user_id=user_id,
                actor_user_id=latest.author_user_id,
                kind=ActivityKind.CHANNEL_ACTIVITY,
                resource_type=ActivityResourceType.NATIVE_CHANNEL,
                resource_id=channel.id,
                context_id=latest.id,
                dedupe_key=key,
                created_at=latest.created_at,
            )
        )
        db.commit()
        return
    if row.context_id != latest.id:
        row.context_id = latest.id
        row.actor_user_id = latest.author_user_id
        row.created_at = latest.created_at
        row.read_at = None
        db.commit()


def _materialize_channel_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    channels = list(
        db.scalars(
            select(NativeChannel).where(NativeChannel.organization_id == organization_id)
        )
    )
    for channel in channels:
        if not _channel_visible(db, channel, user_id):
            continue
        latest = db.scalar(
            select(NativeMessage)
            .where(
                NativeMessage.organization_id == organization_id,
                NativeMessage.channel_id == channel.id,
                or_(
                    NativeMessage.author_user_id.is_(None),
                    NativeMessage.author_user_id != user_id,
                ),
            )
            .order_by(NativeMessage.sequence.desc())
            .limit(1)
        )
        if latest is None:
            continue
        read_state = db.scalar(
            select(NativeChannelReadState).where(
                NativeChannelReadState.organization_id == organization_id,
                NativeChannelReadState.channel_id == channel.id,
                NativeChannelReadState.user_id == user_id,
            )
        )
        if read_state is not None and read_state.last_read_sequence >= latest.sequence:
            continue
        _upsert_channel_activity(
            db,
            organization_id=organization_id,
            user_id=user_id,
            channel=channel,
            latest=latest,
        )


def _materialize_agent_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    membership: Membership,
) -> None:
    requester_runs = list(
        db.scalars(
            select(AgentRun).where(
                AgentRun.organization_id == organization_id,
                AgentRun.requested_by_user_id == user_id,
                AgentRun.status.in_((AgentRunStatus.COMPLETED, AgentRunStatus.FAILED)),
            )
            .order_by(AgentRun.updated_at.desc())
            .limit(50)
        )
    )
    for run in requester_runs:
        context = db.scalar(select(AgentRunContext).where(AgentRunContext.run_id == run.id))
        if not _context_visible(
            db,
            organization_id=organization_id,
            user_id=user_id,
            membership=membership,
            context=context,
        ):
            continue
        kind = (
            ActivityKind.AGENT_COMPLETED
            if run.status == AgentRunStatus.COMPLETED
            else ActivityKind.AGENT_FAILED
        )
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=None,
            kind=kind,
            resource_type=ActivityResourceType.AGENT_RUN,
            resource_id=run.id,
            context_id=None,
            dedupe_key=f"agent-run:{run.id}:{run.status.value}:{user_id}",
        )

    if not role_has_permission(membership.role, Permission.AGENT_MANAGE):
        return
    waiting_steps = db.execute(
        select(AgentStep, AgentRun)
        .join(AgentRun, AgentRun.id == AgentStep.run_id)
        .where(
            AgentStep.organization_id == organization_id,
            AgentStep.status == AgentStepStatus.WAITING_APPROVAL,
            AgentRun.status == AgentRunStatus.WAITING_APPROVAL,
        )
        .order_by(AgentStep.proposed_at.desc())
        .limit(50)
    ).all()
    for step, run in waiting_steps:
        context = db.scalar(select(AgentRunContext).where(AgentRunContext.run_id == run.id))
        if not _context_visible(
            db,
            organization_id=organization_id,
            user_id=user_id,
            membership=membership,
            context=context,
        ):
            continue
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=run.requested_by_user_id,
            kind=ActivityKind.AGENT_APPROVAL,
            resource_type=ActivityResourceType.AGENT_RUN,
            resource_id=run.id,
            context_id=step.id,
            dedupe_key=f"agent-approval:{step.id}:{user_id}",
        )


def _materialize_project_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    membership: Membership,
) -> None:
    progress_rows = list(
        db.scalars(
            select(ProjectProgressItem)
            .where(ProjectProgressItem.organization_id == organization_id)
            .order_by(ProjectProgressItem.updated_at.desc())
            .limit(100)
        )
    )
    for progress in progress_rows:
        project = db.get(WorkGraphNode, progress.project_node_id)
        if (
            project is None
            or not node_visible_to_user(
                db,
                project,
                user_id=user_id,
                role=membership.role,
            )
        ):
            continue
        stamp = progress.updated_at.isoformat(timespec="seconds")
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=progress.updated_by_user_id,
            kind=ActivityKind.PROJECT_UPDATE,
            resource_type=ActivityResourceType.PROJECT,
            resource_id=project.id,
            context_id=progress.id,
            dedupe_key=f"project-update:{progress.id}:{stamp}:{user_id}",
        )

    blockers = list(
        db.scalars(
            select(DecisionMemoryCandidate)
            .where(
                DecisionMemoryCandidate.organization_id == organization_id,
                DecisionMemoryCandidate.kind == MemoryKind.BLOCKER,
                DecisionMemoryCandidate.state.in_((MemoryState.CONFIRMED, MemoryState.RESOLVED)),
                DecisionMemoryCandidate.work_graph_node_id.is_not(None),
            )
            .order_by(DecisionMemoryCandidate.updated_at.desc())
            .limit(100)
        )
    )
    for blocker in blockers:
        node = db.get(WorkGraphNode, blocker.work_graph_node_id)
        if (
            node is None
            or not node_visible_to_user(
                db,
                node,
                user_id=user_id,
                role=membership.role,
            )
        ):
            continue
        stamp = blocker.updated_at.isoformat(timespec="seconds")
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=blocker.created_by_user_id,
            kind=ActivityKind.BLOCKER_UPDATE,
            resource_type=ActivityResourceType.BLOCKER,
            resource_id=blocker.id,
            context_id=node.id,
            dedupe_key=f"blocker-update:{blocker.id}:{blocker.state.value}:{stamp}:{user_id}",
        )


def _materialize_integration_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    membership: Membership,
) -> None:
    if not role_has_permission(membership.role, Permission.INTEGRATION_MANAGE):
        return
    failures = list(
        db.scalars(
            select(IntegrationConnection)
            .where(
                IntegrationConnection.organization_id == organization_id,
                or_(
                    IntegrationConnection.health.in_((IntegrationHealth.DEGRADED, IntegrationHealth.ERROR)),
                    IntegrationConnection.status == IntegrationStatus.REVOKE_FAILED,
                ),
            )
            .order_by(IntegrationConnection.updated_at.desc())
            .limit(50)
        )
    )
    for integration in failures:
        stamp = integration.updated_at.isoformat(timespec="seconds")
        emit_activity(
            db,
            organization_id=organization_id,
            recipient_user_id=user_id,
            actor_user_id=None,
            kind=ActivityKind.INTEGRATION_FAILURE,
            resource_type=ActivityResourceType.INTEGRATION,
            resource_id=integration.id,
            context_id=None,
            dedupe_key=f"integration-failure:{integration.id}:{stamp}:{user_id}",
        )


def materialize_system_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    membership = _membership(db, organization_id, user_id)
    if membership is None:
        return
    preferences = get_activity_preferences(
        db,
        organization_id=organization_id,
        user_id=user_id,
    )
    if preferences.channel_activity:
        _materialize_channel_activity(
            db,
            organization_id=organization_id,
            user_id=user_id,
        )
    if preferences.agent_approvals or preferences.agent_run_events:
        _materialize_agent_activity(
            db,
            organization_id=organization_id,
            user_id=user_id,
            membership=membership,
        )
    if preferences.project_updates:
        _materialize_project_activity(
            db,
            organization_id=organization_id,
            user_id=user_id,
            membership=membership,
        )
    if preferences.integration_failures:
        _materialize_integration_activity(
            db,
            organization_id=organization_id,
            user_id=user_id,
            membership=membership,
        )


def _system_item(
    db: Session,
    *,
    row: ActivityNotification,
    user_id: uuid.UUID,
    membership: Membership,
) -> ActivityItem | None:
    if row.kind == ActivityKind.CHANNEL_ACTIVITY:
        channel = db.get(NativeChannel, row.resource_id)
        latest = db.get(NativeMessage, row.context_id) if row.context_id else None
        if (
            channel is None
            or latest is None
            or channel.organization_id != row.organization_id
            or latest.channel_id != channel.id
            or not _channel_visible(db, channel, user_id)
        ):
            return None
        read_state = db.scalar(
            select(NativeChannelReadState).where(
                NativeChannelReadState.organization_id == row.organization_id,
                NativeChannelReadState.channel_id == channel.id,
                NativeChannelReadState.user_id == user_id,
            )
        )
        if read_state is not None and read_state.last_read_sequence >= latest.sequence:
            return None
        return ActivityItem(
            id=row.id,
            kind=row.kind,
            actor_display_name=None,
            label=f"Unread activity in #{channel.name}",
            context_label=f"#{channel.name}",
            href=f"?channelId={channel.id}&messageId={latest.id}#native-chat",
            read=row.read_at is not None,
            created_at=row.created_at,
        )

    if row.kind in {
        ActivityKind.AGENT_APPROVAL,
        ActivityKind.AGENT_COMPLETED,
        ActivityKind.AGENT_FAILED,
    }:
        run = db.get(AgentRun, row.resource_id)
        if run is None or run.organization_id != row.organization_id:
            return None
        context = db.scalar(select(AgentRunContext).where(AgentRunContext.run_id == run.id))
        if not _context_visible(
            db,
            organization_id=row.organization_id,
            user_id=user_id,
            membership=membership,
            context=context,
        ):
            return None
        if row.kind == ActivityKind.AGENT_APPROVAL:
            if not role_has_permission(membership.role, Permission.AGENT_MANAGE):
                return None
            step = db.get(AgentStep, row.context_id) if row.context_id else None
            if step is None or step.status != AgentStepStatus.WAITING_APPROVAL:
                return None
            label = f"Agent approval required for {step.tool_name}"
            href = f"?agentRunId={run.id}&agentStepId={step.id}#agent-workspace"
        elif row.kind == ActivityKind.AGENT_COMPLETED:
            if run.requested_by_user_id != user_id or run.status != AgentRunStatus.COMPLETED:
                return None
            label = "Agent run completed"
            href = f"?agentRunId={run.id}#agent-workspace"
        else:
            if run.requested_by_user_id != user_id or run.status != AgentRunStatus.FAILED:
                return None
            label = "Agent run failed"
            href = f"?agentRunId={run.id}#agent-workspace"
        return ActivityItem(
            id=row.id,
            kind=row.kind,
            actor_display_name=None,
            label=label,
            context_label="Agent workspace",
            href=href,
            read=row.read_at is not None,
            created_at=row.created_at,
        )

    if row.kind == ActivityKind.PROJECT_UPDATE:
        project = db.get(WorkGraphNode, row.resource_id)
        if (
            project is None
            or project.organization_id != row.organization_id
            or not node_visible_to_user(db, project, user_id=user_id, role=membership.role)
        ):
            return None
        return ActivityItem(
            id=row.id,
            kind=row.kind,
            actor_display_name=None,
            label=f"Project updated: {project.display_name or 'Project'}",
            context_label=project.display_name or "Project",
            href=f"?projectId={project.id}#project-status",
            read=row.read_at is not None,
            created_at=row.created_at,
        )

    if row.kind == ActivityKind.BLOCKER_UPDATE:
        blocker = db.get(DecisionMemoryCandidate, row.resource_id)
        node = db.get(WorkGraphNode, row.context_id) if row.context_id else None
        if (
            blocker is None
            or node is None
            or blocker.organization_id != row.organization_id
            or not node_visible_to_user(db, node, user_id=user_id, role=membership.role)
        ):
            return None
        verb = "resolved" if blocker.state == MemoryState.RESOLVED else "updated"
        return ActivityItem(
            id=row.id,
            kind=row.kind,
            actor_display_name=None,
            label=f"Blocker {verb}",
            context_label=node.display_name or "Project",
            href=f"?projectId={node.id}&blockerId={blocker.id}#project-status",
            read=row.read_at is not None,
            created_at=row.created_at,
        )

    if row.kind == ActivityKind.INTEGRATION_FAILURE:
        if not role_has_permission(membership.role, Permission.INTEGRATION_MANAGE):
            return None
        integration = db.get(IntegrationConnection, row.resource_id)
        if integration is None or integration.organization_id != row.organization_id:
            return None
        failing = integration.health in {IntegrationHealth.DEGRADED, IntegrationHealth.ERROR} or integration.status == IntegrationStatus.REVOKE_FAILED
        if not failing:
            return None
        return ActivityItem(
            id=row.id,
            kind=row.kind,
            actor_display_name=None,
            label=f"Integration needs attention: {integration.display_name}",
            context_label=integration.provider,
            href=f"?integrationId={integration.id}#admin-center",
            read=row.read_at is not None,
            created_at=row.created_at,
        )
    return None


def list_system_activity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    unread_only: bool = False,
) -> list[ActivityItem]:
    membership = _membership(db, organization_id, user_id)
    if membership is None:
        return []
    preferences = get_activity_preferences(
        db,
        organization_id=organization_id,
        user_id=user_id,
    )
    query = (
        select(ActivityNotification)
        .where(
            ActivityNotification.organization_id == organization_id,
            ActivityNotification.recipient_user_id == user_id,
            ActivityNotification.kind.in_(tuple(SYSTEM_KINDS)),
        )
        .order_by(ActivityNotification.created_at.desc(), ActivityNotification.id.desc())
        .limit(max(limit * 3, 100))
    )
    if unread_only:
        query = query.where(ActivityNotification.read_at.is_(None))
    items: list[ActivityItem] = []
    for row in db.scalars(query):
        if not kind_enabled(preferences, row.kind):
            continue
        item = _system_item(db, row=row, user_id=user_id, membership=membership)
        if item is not None:
            items.append(item)
            if len(items) >= limit:
                break
    return items


def system_unread_count(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    return len(
        list_system_activity(
            db,
            organization_id=organization_id,
            user_id=user_id,
            limit=500,
            unread_only=True,
        )
    )


def mark_system_activity_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> bool:
    membership = _membership(db, organization_id, user_id)
    if membership is None:
        return False
    row = db.scalar(
        select(ActivityNotification).where(
            ActivityNotification.id == notification_id,
            ActivityNotification.organization_id == organization_id,
            ActivityNotification.recipient_user_id == user_id,
            ActivityNotification.kind.in_(tuple(SYSTEM_KINDS)),
        )
    )
    if row is None or _system_item(db, row=row, user_id=user_id, membership=membership) is None:
        return False
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        db.commit()
    return True


def mark_all_system_activity_read(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    items = list_system_activity(
        db,
        organization_id=organization_id,
        user_id=user_id,
        limit=500,
        unread_only=True,
    )
    ids = [item.id for item in items]
    if not ids:
        return 0
    result = db.execute(
        update(ActivityNotification)
        .where(
            ActivityNotification.organization_id == organization_id,
            ActivityNotification.recipient_user_id == user_id,
            ActivityNotification.id.in_(ids),
            ActivityNotification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
    return int(result.rowcount or 0)


def precise_chat_href(db: Session, item: ActivityItem) -> str:
    row = db.get(ActivityNotification, item.id)
    if row is None:
        return item.href
    if row.resource_type == ActivityResourceType.NATIVE_MESSAGE:
        message = db.get(NativeMessage, row.resource_id)
        if message is None:
            return item.href
        params = f"channelId={message.channel_id}&messageId={message.id}"
        if message.thread_root_id is not None:
            params += f"&threadRootId={message.thread_root_id}"
        return f"?{params}#native-chat"
    if row.resource_type == ActivityResourceType.DIRECT_MESSAGE:
        return f"{item.href.split('#', 1)[0]}&messageId={row.resource_id}#direct-messages"
    return item.href
