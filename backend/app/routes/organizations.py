import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.data_governance import DataGovernanceError, append_audit_event
from app.database import get_db
from app.direct_message_models import DirectConversation
from app.models import Membership, MembershipRole, Organization, ResourceGrant, User
from app.native_chat_models import NativeChannelMembership
from app.permissions import (
    AuthorizationContext,
    Permission,
    require_organization_permission,
    role_has_permission,
)
from app.schemas import (
    MembershipCreate,
    MembershipRead,
    OrganizationCreate,
    OrganizationRead,
    ResourceGrantCreate,
    ResourceGrantRead,
)
from app.security_audit import audit_acl_change

router = APIRouter(prefix="/organizations", tags=["organizations"])

OrganizationReader = Annotated[
    AuthorizationContext,
    Depends(require_organization_permission(Permission.ORGANIZATION_READ)),
]
MembershipReader = Annotated[
    AuthorizationContext,
    Depends(require_organization_permission(Permission.MEMBERSHIP_READ)),
]
MembershipManager = Annotated[
    AuthorizationContext,
    Depends(require_organization_permission(Permission.MEMBERSHIP_MANAGE)),
]
AclManager = Annotated[
    AuthorizationContext,
    Depends(require_organization_permission(Permission.RESOURCE_ACL_MANAGE)),
]


class MembershipRoleUpdate(BaseModel):
    role: MembershipRole

    model_config = {"extra": "forbid"}


def _membership_or_404(
    db: Session,
    *,
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> Membership:
    membership = db.scalar(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    return membership


def _require_membership_mutation_authority(
    access: AuthorizationContext,
    *,
    current_role: MembershipRole,
    requested_role: MembershipRole | None = None,
) -> None:
    protected_roles = {MembershipRole.OWNER, MembershipRole.ADMIN}
    if access.role != MembershipRole.OWNER and (
        current_role in protected_roles
        or (requested_role is not None and requested_role in protected_roles)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can manage owner or admin memberships",
        )


def _require_owner_survives(
    db: Session,
    *,
    organization_id: uuid.UUID,
    target: Membership,
    requested_role: MembershipRole | None,
) -> None:
    if target.role != MembershipRole.OWNER:
        return
    if requested_role == MembershipRole.OWNER:
        return
    owner_count = db.scalar(
        select(func.count(Membership.id)).where(
            Membership.organization_id == organization_id,
            Membership.role == MembershipRole.OWNER,
        )
    ) or 0
    if owner_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The organization must retain at least one owner",
        )


def _revoke_direct_message_participation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    revoked_at: datetime,
) -> None:
    # Keep the other participant's historical private view while preventing the
    # removed/downgraded user from silently regaining old DM history if re-added.
    db.execute(
        update(DirectConversation)
        .where(
            DirectConversation.organization_id == organization_id,
            DirectConversation.participant_a_user_id == user_id,
            DirectConversation.participant_a_revoked_at.is_(None),
        )
        .values(participant_a_revoked_at=revoked_at)
    )
    db.execute(
        update(DirectConversation)
        .where(
            DirectConversation.organization_id == organization_id,
            DirectConversation.participant_b_user_id == user_id,
            DirectConversation.participant_b_revoked_at.is_(None),
        )
        .values(participant_b_revoked_at=revoked_at)
    )


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Organization:
    organization = Organization(name=payload.name.strip(), slug=payload.slug)
    db.add(organization)
    db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=current_user.id,
            role=MembershipRole.OWNER,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug exists",
        ) from None
    db.refresh(organization)
    return organization


@router.get("/{organization_id}", response_model=OrganizationRead)
def read_organization(
    organization_id: uuid.UUID,
    _access: OrganizationReader,
    db: Annotated[Session, Depends(get_db)],
) -> Organization:
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.post(
    "/{organization_id}/memberships",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
)
def create_membership(
    organization_id: uuid.UUID,
    payload: MembershipCreate,
    access: MembershipManager,
    db: Annotated[Session, Depends(get_db)],
) -> Membership:
    if access.role != MembershipRole.OWNER and payload.role in {
        MembershipRole.OWNER,
        MembershipRole.ADMIN,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners can assign owner or admin roles",
        )

    target = db.scalar(select(User).where(User.email == payload.user_email.strip().lower()))
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User must sign in before membership can be created",
        )

    membership = Membership(
        organization_id=organization_id,
        user_id=target.id,
        role=payload.role,
    )
    db.add(membership)
    try:
        db.flush()
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"membership.created:{membership.id}",
            event_type="membership.created",
            outcome="succeeded",
            actor_user_id=access.user_id,
            resource_type="membership",
            resource_id=membership.id,
            metadata={"target_user_id": membership.user_id, "role": membership.role.value},
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership already exists",
        ) from None
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Membership could not be audited",
        ) from exc
    db.refresh(membership)
    return membership


@router.get("/{organization_id}/memberships", response_model=list[MembershipRead])
def list_memberships(
    organization_id: uuid.UUID,
    _access: MembershipReader,
    db: Annotated[Session, Depends(get_db)],
) -> list[Membership]:
    return list(
        db.scalars(
            select(Membership)
            .where(Membership.organization_id == organization_id)
            .order_by(Membership.created_at, Membership.id)
        )
    )


@router.post(
    "/{organization_id}/memberships/{membership_id}/role",
    response_model=MembershipRead,
)
def update_membership_role(
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    payload: MembershipRoleUpdate,
    access: MembershipManager,
    db: Annotated[Session, Depends(get_db)],
) -> Membership:
    membership = _membership_or_404(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
    )
    _require_membership_mutation_authority(
        access,
        current_role=membership.role,
        requested_role=payload.role,
    )
    _require_owner_survives(
        db,
        organization_id=organization_id,
        target=membership,
        requested_role=payload.role,
    )
    if membership.role == payload.role:
        return membership

    previous_role = membership.role
    lost_dm_access = (
        role_has_permission(previous_role, Permission.NATIVE_CHAT_WRITE)
        and not role_has_permission(payload.role, Permission.NATIVE_CHAT_WRITE)
    )
    membership.role = payload.role
    if lost_dm_access:
        _revoke_direct_message_participation(
            db,
            organization_id=organization_id,
            user_id=membership.user_id,
            revoked_at=datetime.now(UTC),
        )
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"membership.role_changed:{membership.id}:{uuid.uuid4()}",
            event_type="membership.role_changed",
            outcome="succeeded",
            actor_user_id=access.user_id,
            resource_type="membership",
            resource_id=membership.id,
            metadata={
                "target_user_id": membership.user_id,
                "previous_role": previous_role.value,
                "new_role": payload.role.value,
                "direct_message_access_revoked": lost_dm_access,
            },
        )
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Membership role change could not be audited",
        ) from exc
    db.refresh(membership)
    return membership


@router.delete(
    "/{organization_id}/memberships/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_membership(
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    access: MembershipManager,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    membership = _membership_or_404(
        db,
        organization_id=organization_id,
        membership_id=membership_id,
    )
    _require_membership_mutation_authority(access, current_role=membership.role)
    _require_owner_survives(
        db,
        organization_id=organization_id,
        target=membership,
        requested_role=None,
    )
    target_user_id = membership.user_id
    previous_role = membership.role
    now = datetime.now(UTC)

    # Membership removal must clear dormant authorization. Otherwise re-adding the same
    # user could silently reactivate old Work Graph, channel or private-message access.
    db.execute(
        delete(ResourceGrant).where(
            ResourceGrant.organization_id == organization_id,
            ResourceGrant.user_id == target_user_id,
        )
    )
    db.execute(
        update(NativeChannelMembership)
        .where(
            NativeChannelMembership.organization_id == organization_id,
            NativeChannelMembership.user_id == target_user_id,
            NativeChannelMembership.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    _revoke_direct_message_participation(
        db,
        organization_id=organization_id,
        user_id=target_user_id,
        revoked_at=now,
    )
    db.delete(membership)
    try:
        append_audit_event(
            db,
            organization_id=organization_id,
            event_key=f"membership.deleted:{membership_id}:{uuid.uuid4()}",
            event_type="membership.deleted",
            outcome="succeeded",
            actor_user_id=access.user_id,
            resource_type="membership",
            resource_id=membership_id,
            metadata={
                "target_user_id": target_user_id,
                "previous_role": previous_role.value,
                "access_grants_cleared": True,
                "direct_message_access_revoked": True,
            },
        )
    except (DataGovernanceError, SQLAlchemyError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Membership removal could not be audited",
        ) from exc


@router.post(
    "/{organization_id}/resource-grants",
    response_model=ResourceGrantRead,
    status_code=status.HTTP_201_CREATED,
)
def create_resource_grant(
    organization_id: uuid.UUID,
    payload: ResourceGrantCreate,
    access: AclManager,
    db: Annotated[Session, Depends(get_db)],
) -> ResourceGrant:
    target_membership = db.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == payload.user_id,
        )
    )
    if target_membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target member not found")

    grant = ResourceGrant(
        organization_id=organization_id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        user_id=payload.user_id,
        access=payload.access,
        created_by_user_id=access.user_id,
    )
    db.add(grant)
    try:
        db.flush()
        audit_acl_change(
            action="created",
            organization_id=organization_id,
            actor_user_id=access.user_id,
            target_user_id=payload.user_id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            access=payload.access.value,
            db=db,
            required=True,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource grant already exists",
        ) from None
    db.refresh(grant)
    return grant


@router.get("/{organization_id}/resource-grants", response_model=list[ResourceGrantRead])
def list_resource_grants(
    organization_id: uuid.UUID,
    _access: AclManager,
    db: Annotated[Session, Depends(get_db)],
    resource_type: Annotated[
        str,
        Query(pattern=r"^[a-z][a-z0-9_.-]{0,63}$", max_length=64),
    ],
    resource_id: Annotated[str, Query(min_length=1, max_length=255)],
) -> list[ResourceGrant]:
    return list(
        db.scalars(
            select(ResourceGrant)
            .where(
                ResourceGrant.organization_id == organization_id,
                ResourceGrant.resource_type == resource_type,
                ResourceGrant.resource_id == resource_id,
            )
            .order_by(ResourceGrant.created_at, ResourceGrant.id)
        )
    )
