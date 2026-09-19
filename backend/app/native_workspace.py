import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.data_governance import append_audit_event
from app.models import MembershipRole
from app.native_chat import can_manage_channel
from app.native_chat_models import NativeChannel
from app.native_workspace_models import (
    NativeChannelGroup,
    NativeTeam,
    NativeTeamStatus,
)

MAX_TEAM_NAME_CHARS = 120
MAX_TEAM_DESCRIPTION_CHARS = 500


class NativeWorkspaceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code[:128]


class NativeWorkspaceConflictError(NativeWorkspaceError):
    pass


def _normalize_name(value: str) -> str:
    name = " ".join(value.strip().split())
    if not name or len(name) > MAX_TEAM_NAME_CHARS:
        raise NativeWorkspaceError("invalid_team_name", "Team name is invalid")
    return name


def _normalize_description(value: str | None) -> str | None:
    if value is None:
        return None
    description = " ".join(value.strip().split())
    if len(description) > MAX_TEAM_DESCRIPTION_CHARS:
        raise NativeWorkspaceError(
            "invalid_team_description",
            "Team description is too long",
        )
    return description or None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:96]
    if not slug:
        raise NativeWorkspaceError("invalid_team_name", "Team name is invalid")
    return slug


def can_manage_team(
    team: NativeTeam,
    *,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
) -> bool:
    return team.created_by_user_id == actor_user_id or actor_role in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
    }


def list_teams(
    db: Session,
    *,
    organization_id: uuid.UUID,
    include_archived: bool = False,
) -> list[NativeTeam]:
    query = select(NativeTeam).where(NativeTeam.organization_id == organization_id)
    if not include_archived:
        query = query.where(NativeTeam.status == NativeTeamStatus.ACTIVE)
    return list(db.scalars(query.order_by(NativeTeam.name, NativeTeam.id)))


def get_team(
    db: Session,
    *,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
) -> NativeTeam:
    team = db.scalar(
        select(NativeTeam).where(
            NativeTeam.id == team_id,
            NativeTeam.organization_id == organization_id,
        )
    )
    if team is None:
        raise NativeWorkspaceError("team_not_found", "Team not found")
    return team


def create_team(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    description: str | None,
    request_id: str | None = None,
) -> NativeTeam:
    normalized_name = _normalize_name(name)
    row = NativeTeam(
        organization_id=organization_id,
        name=normalized_name,
        slug=_slugify(normalized_name),
        description=_normalize_description(description),
        status=NativeTeamStatus.ACTIVE,
        revision=1,
        created_by_user_id=actor_user_id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise NativeWorkspaceConflictError(
            "team_slug_conflict",
            "A Team with this name already exists",
        ) from exc
    db.refresh(row)
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_workspace.team.created:{row.id}",
        event_type="native_workspace.team.created",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_team",
        resource_id=row.id,
        request_id=request_id,
        metadata={"team_slug": row.slug},
    )
    return row


def update_team(
    db: Session,
    *,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    expected_revision: int,
    name: str,
    description: str | None,
    request_id: str | None = None,
) -> NativeTeam:
    query = select(NativeTeam).where(
        NativeTeam.id == team_id,
        NativeTeam.organization_id == organization_id,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    team = db.scalar(query)
    if team is None or not can_manage_team(
        team,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    ):
        raise NativeWorkspaceError("team_not_found", "Team not found")
    if expected_revision < 1 or team.revision != expected_revision:
        raise NativeWorkspaceConflictError(
            "team_revision_conflict",
            "Team changed since it was loaded",
        )
    normalized_name = _normalize_name(name)
    team.name = normalized_name
    team.slug = _slugify(normalized_name)
    team.description = _normalize_description(description)
    team.revision += 1
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise NativeWorkspaceConflictError(
            "team_slug_conflict",
            "A Team with this name already exists",
        ) from exc
    db.refresh(team)
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_workspace.team.updated:{team.id}:{team.revision}",
        event_type="native_workspace.team.updated",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_team",
        resource_id=team.id,
        request_id=request_id,
        metadata={"revision": team.revision, "team_slug": team.slug},
    )
    return team


def set_team_archived(
    db: Session,
    *,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    expected_revision: int,
    archived: bool,
    request_id: str | None = None,
) -> NativeTeam:
    query = select(NativeTeam).where(
        NativeTeam.id == team_id,
        NativeTeam.organization_id == organization_id,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    team = db.scalar(query)
    if team is None or not can_manage_team(
        team,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    ):
        raise NativeWorkspaceError("team_not_found", "Team not found")
    if expected_revision < 1 or team.revision != expected_revision:
        raise NativeWorkspaceConflictError(
            "team_revision_conflict",
            "Team changed since it was loaded",
        )
    next_status = NativeTeamStatus.ARCHIVED if archived else NativeTeamStatus.ACTIVE
    if team.status == next_status:
        return team
    team.status = next_status
    team.archived_at = datetime.now(UTC) if archived else None
    team.revision += 1
    db.commit()
    db.refresh(team)
    action = "archived" if archived else "restored"
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_workspace.team.{action}:{team.id}:{team.revision}",
        event_type=f"native_workspace.team.{action}",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_team",
        resource_id=team.id,
        request_id=request_id,
        metadata={"revision": team.revision},
    )
    return team

def list_channel_groups(
    db: Session,
    *,
    organization_id: uuid.UUID,
    include_archived: bool = False,
) -> list[NativeChannelGroup]:
    query = select(NativeChannelGroup).where(
        NativeChannelGroup.organization_id == organization_id
    )
    if not include_archived:
        query = query.where(NativeChannelGroup.status == NativeTeamStatus.ACTIVE)
    return list(
        db.scalars(
            query.order_by(
                NativeChannelGroup.team_id,
                NativeChannelGroup.name,
                NativeChannelGroup.id,
            )
        )
    )


def _managed_active_team(
    db: Session,
    *,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
) -> NativeTeam:
    team = get_team(
        db,
        organization_id=organization_id,
        team_id=team_id,
    )
    if (
        team.status != NativeTeamStatus.ACTIVE
        or not can_manage_team(
            team,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
    ):
        raise NativeWorkspaceError("team_not_found", "Team not found")
    return team


def _managed_group(
    db: Session,
    *,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    group_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    require_active: bool = False,
) -> tuple[NativeTeam, NativeChannelGroup]:
    team = _managed_active_team(
        db,
        organization_id=organization_id,
        team_id=team_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )
    query = select(NativeChannelGroup).where(
        NativeChannelGroup.id == group_id,
        NativeChannelGroup.organization_id == organization_id,
        NativeChannelGroup.team_id == team_id,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    group = db.scalar(query)
    if (
        group is None
        or (require_active and group.status != NativeTeamStatus.ACTIVE)
    ):
        raise NativeWorkspaceError("group_not_found", "Channel group not found")
    return team, group


def create_channel_group(
    db: Session,
    *,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    name: str,
    request_id: str | None = None,
) -> NativeChannelGroup:
    _managed_active_team(
        db,
        organization_id=organization_id,
        team_id=team_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )
    normalized_name = _normalize_name(name)
    row = NativeChannelGroup(
        organization_id=organization_id,
        team_id=team_id,
        name=normalized_name,
        slug=_slugify(normalized_name),
        status=NativeTeamStatus.ACTIVE,
        revision=1,
        created_by_user_id=actor_user_id,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise NativeWorkspaceConflictError(
            "group_slug_conflict",
            "A channel group with this name already exists in this Team",
        ) from exc
    db.refresh(row)
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_workspace.group.created:{row.id}",
        event_type="native_workspace.group.created",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_channel_group",
        resource_id=row.id,
        request_id=request_id,
        metadata={"team_id": str(team_id), "group_slug": row.slug},
    )
    return row


def update_channel_group(
    db: Session,
    *,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    group_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    expected_revision: int,
    name: str,
    request_id: str | None = None,
) -> NativeChannelGroup:
    _, group = _managed_group(
        db,
        organization_id=organization_id,
        team_id=team_id,
        group_id=group_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )
    if expected_revision < 1 or group.revision != expected_revision:
        raise NativeWorkspaceConflictError(
            "group_revision_conflict",
            "Channel group changed since it was loaded",
        )
    normalized_name = _normalize_name(name)
    group.name = normalized_name
    group.slug = _slugify(normalized_name)
    group.revision += 1
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise NativeWorkspaceConflictError(
            "group_slug_conflict",
            "A channel group with this name already exists in this Team",
        ) from exc
    db.refresh(group)
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_workspace.group.updated:{group.id}:{group.revision}",
        event_type="native_workspace.group.updated",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_channel_group",
        resource_id=group.id,
        request_id=request_id,
        metadata={"team_id": str(team_id), "revision": group.revision},
    )
    return group


def set_channel_group_archived(
    db: Session,
    *,
    organization_id: uuid.UUID,
    team_id: uuid.UUID,
    group_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    expected_revision: int,
    archived: bool,
    request_id: str | None = None,
) -> NativeChannelGroup:
    _, group = _managed_group(
        db,
        organization_id=organization_id,
        team_id=team_id,
        group_id=group_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    )
    if expected_revision < 1 or group.revision != expected_revision:
        raise NativeWorkspaceConflictError(
            "group_revision_conflict",
            "Channel group changed since it was loaded",
        )
    next_status = NativeTeamStatus.ARCHIVED if archived else NativeTeamStatus.ACTIVE
    if group.status == next_status:
        return group
    group.status = next_status
    group.archived_at = datetime.now(UTC) if archived else None
    group.revision += 1
    db.commit()
    db.refresh(group)
    action = "archived" if archived else "restored"
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=f"native_workspace.group.{action}:{group.id}:{group.revision}",
        event_type=f"native_workspace.group.{action}",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_channel_group",
        resource_id=group.id,
        request_id=request_id,
        metadata={"team_id": str(team_id), "revision": group.revision},
    )
    return group


def assign_channel_navigation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    channel_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: MembershipRole,
    team_id: uuid.UUID | None,
    group_id: uuid.UUID | None,
    request_id: str | None = None,
) -> NativeChannel:
    query = select(NativeChannel).where(
        NativeChannel.id == channel_id,
        NativeChannel.organization_id == organization_id,
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    channel = db.scalar(query)
    if channel is None or not can_manage_channel(
        channel,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    ):
        raise NativeWorkspaceError("channel_not_found", "Channel not found")

    if team_id is None:
        if group_id is not None:
            raise NativeWorkspaceError(
                "group_requires_team",
                "A channel group requires a Team",
            )
    else:
        _managed_active_team(
            db,
            organization_id=organization_id,
            team_id=team_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        if group_id is not None:
            _managed_group(
                db,
                organization_id=organization_id,
                team_id=team_id,
                group_id=group_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                require_active=True,
            )

    if channel.team_id == team_id and channel.channel_group_id == group_id:
        return channel
    channel.team_id = team_id
    channel.channel_group_id = group_id
    db.commit()
    db.refresh(channel)
    append_audit_event(
        db,
        organization_id=organization_id,
        event_key=(
            f"native_workspace.channel_navigation:"
            f"{channel.id}:{team_id or 'none'}:{group_id or 'none'}"
        ),
        event_type="native_workspace.channel_navigation.updated",
        outcome="succeeded",
        actor_user_id=actor_user_id,
        resource_type="native_channel",
        resource_id=channel.id,
        request_id=request_id,
        metadata={
            "team_id": str(team_id) if team_id else None,
            "channel_group_id": str(group_id) if group_id else None,
        },
    )
    return channel
