import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Membership, MembershipRole, Organization, ResourceGrant, User
from app.permissions import AuthorizationContext, Permission, require_organization_permission
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
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership already exists",
        ) from None
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
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource grant already exists",
        ) from None
    db.refresh(grant)
    audit_acl_change(
        action="created",
        organization_id=organization_id,
        actor_user_id=access.user_id,
        target_user_id=payload.user_id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        access=payload.access.value,
    )
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


@router.delete(
    "/{organization_id}/resource-grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_resource_grant(
    organization_id: uuid.UUID,
    grant_id: uuid.UUID,
    access: AclManager,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    grant = db.scalar(
        select(ResourceGrant).where(
            ResourceGrant.id == grant_id,
            ResourceGrant.organization_id == organization_id,
        )
    )
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource grant not found",
        )

    target_user_id = grant.user_id
    resource_type = grant.resource_type
    resource_id = grant.resource_id
    grant_access = grant.access.value
    db.delete(grant)
    db.commit()
    audit_acl_change(
        action="deleted",
        organization_id=organization_id,
        actor_user_id=access.user_id,
        target_user_id=target_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        access=grant_access,
    )
