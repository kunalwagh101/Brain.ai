import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Membership, MembershipRole, ResourceAccessLevel, ResourceGrant, User
from app.observability import bind_organization_context
from app.security_audit import audit_authorization_decision


class Permission(StrEnum):
    ORGANIZATION_READ = "organization.read"
    MEMBERSHIP_READ = "membership.read"
    MEMBERSHIP_MANAGE = "membership.manage"
    RESOURCE_READ = "resource.read"
    RESOURCE_WRITE = "resource.write"
    RESOURCE_ACL_MANAGE = "resource_acl.manage"
    INTEGRATION_MANAGE = "integration.manage"
    IDENTITY_MANAGE = "identity.manage"
    NATIVE_CHAT_WRITE = "native_chat.write"
    AI_USE = "ai.use"
    AI_MANAGE = "ai.manage"
    AGENT_USE = "agent.use"
    AGENT_MANAGE = "agent.manage"
    API_MANAGE = "api.manage"
    DATA_GOVERNANCE_MANAGE = "data_governance.manage"
    AUDIT_READ = "audit.read"


_ALL = frozenset(Permission)

ROLE_PERMISSIONS: dict[MembershipRole, frozenset[Permission]] = {
    MembershipRole.OWNER: _ALL,
    MembershipRole.ADMIN: _ALL,
    MembershipRole.EXECUTIVE: frozenset(
        {
            Permission.ORGANIZATION_READ,
            Permission.MEMBERSHIP_READ,
            Permission.RESOURCE_READ,
            Permission.NATIVE_CHAT_WRITE,
            Permission.AI_USE,
            Permission.AGENT_USE,
            Permission.AUDIT_READ,
        }
    ),
    MembershipRole.MANAGER: frozenset(
        {
            Permission.ORGANIZATION_READ,
            Permission.MEMBERSHIP_READ,
            Permission.RESOURCE_READ,
            Permission.RESOURCE_WRITE,
            Permission.NATIVE_CHAT_WRITE,
            Permission.AI_USE,
            Permission.AGENT_USE,
        }
    ),
    MembershipRole.MEMBER: frozenset(
        {
            Permission.ORGANIZATION_READ,
            Permission.MEMBERSHIP_READ,
            Permission.RESOURCE_READ,
            Permission.RESOURCE_WRITE,
            Permission.NATIVE_CHAT_WRITE,
            Permission.AI_USE,
            Permission.AGENT_USE,
        }
    ),
    MembershipRole.GUEST: frozenset(
        {
            Permission.ORGANIZATION_READ,
            Permission.RESOURCE_READ,
        }
    ),
}


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: MembershipRole


def role_has_permission(role: MembershipRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]


def authorize_organization(
    *,
    db: Session,
    organization_id: uuid.UUID,
    user: User,
    permission: Permission,
) -> AuthorizationContext:
    bind_organization_context(organization_id)
    if user.status != "active":
        audit_authorization_decision(
            allowed=False,
            organization_id=organization_id,
            actor_user_id=user.id,
            permission=permission.value,
            reason="inactive_user",
            db=db,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user.id,
        )
    )
    if membership is None:
        audit_authorization_decision(
            allowed=False,
            organization_id=organization_id,
            actor_user_id=user.id,
            permission=permission.value,
            reason="not_a_member",
            db=db,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    if not role_has_permission(membership.role, permission):
        audit_authorization_decision(
            allowed=False,
            organization_id=organization_id,
            actor_user_id=user.id,
            permission=permission.value,
            reason="role_denied",
            db=db,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    audit_authorization_decision(
        allowed=True,
        organization_id=organization_id,
        actor_user_id=user.id,
        permission=permission.value,
        reason="role_allowed",
        db=db,
    )
    return AuthorizationContext(
        organization_id=organization_id,
        user_id=user.id,
        role=membership.role,
    )


def require_organization_permission(permission: Permission):
    def dependency(
        organization_id: uuid.UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> AuthorizationContext:
        return authorize_organization(
            db=db,
            organization_id=organization_id,
            user=current_user,
            permission=permission,
        )

    return dependency


def _allowed_grant_levels(permission: Permission) -> tuple[ResourceAccessLevel, ...]:
    if permission == Permission.RESOURCE_READ:
        return (ResourceAccessLevel.READ, ResourceAccessLevel.WRITE)
    if permission == Permission.RESOURCE_WRITE:
        return (ResourceAccessLevel.WRITE,)
    raise ValueError("Resource ACL can only guard resource read/write permissions")


def authorize_resource(
    *,
    db: Session,
    organization_id: uuid.UUID,
    user: User,
    permission: Permission,
    resource_type: str,
    resource_id: str,
    restricted: bool = True,
) -> AuthorizationContext:
    context = authorize_organization(
        db=db,
        organization_id=organization_id,
        user=user,
        permission=permission,
    )
    if not restricted:
        return context

    grant = db.scalar(
        select(ResourceGrant.id)
        .where(
            ResourceGrant.organization_id == organization_id,
            ResourceGrant.resource_type == resource_type,
            ResourceGrant.resource_id == resource_id,
            ResourceGrant.user_id == user.id,
            ResourceGrant.access.in_(_allowed_grant_levels(permission)),
        )
        .limit(1)
    )
    if grant is None:
        audit_authorization_decision(
            allowed=False,
            organization_id=organization_id,
            actor_user_id=user.id,
            permission=permission.value,
            reason="missing_resource_grant",
            resource_type=resource_type,
            resource_id=resource_id,
            db=db,
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    audit_authorization_decision(
        allowed=True,
        organization_id=organization_id,
        actor_user_id=user.id,
        permission=permission.value,
        reason="resource_grant_allowed",
        resource_type=resource_type,
        resource_id=resource_id,
        db=db,
    )
    return context


def require_resource_permission(
    permission: Permission,
    *,
    restricted: bool = True,
    resource_type_param: str = "resource_type",
    resource_id_param: str = "resource_id",
):
    def dependency(
        request: Request,
        organization_id: uuid.UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> AuthorizationContext:
        resource_type = request.path_params.get(resource_type_param)
        resource_id = request.path_params.get(resource_id_param)
        if not isinstance(resource_type, str) or not isinstance(resource_id, str):
            raise RuntimeError(
                "Resource permission dependency is missing configured path parameters"
            )
        return authorize_resource(
            db=db,
            organization_id=organization_id,
            user=current_user,
            permission=permission,
            resource_type=resource_type,
            resource_id=resource_id,
            restricted=restricted,
        )

    return dependency
