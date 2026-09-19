import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.data_governance import append_audit_event
from app.models import MembershipRole
from app.native_workspace_models import NativeTeam, NativeTeamStatus

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
