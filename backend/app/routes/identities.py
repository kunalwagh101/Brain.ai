import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.identity_resolution import (
    IdentityResolutionError,
    reconcile_source_identities,
    resolve_identity_manually,
    unresolve_identity_manually,
)
from app.models import IdentityResolutionHistory, SourceIdentity, SourceIdentityState
from app.permissions import AuthorizationContext, Permission, require_organization_permission
from app.schemas import (
    IdentityReconcileRead,
    IdentityReconcileRequest,
    IdentityResolutionHistoryRead,
    SourceIdentityRead,
    SourceIdentityResolveRequest,
    SourceIdentityUnresolveRequest,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/source-identities",
    tags=["identity-resolution"],
)
_manage_identities = require_organization_permission(Permission.IDENTITY_MANAGE)


def _get_identity(
    db: Session,
    *,
    organization_id: uuid.UUID,
    identity_id: uuid.UUID,
) -> SourceIdentity:
    identity = db.scalar(
        select(SourceIdentity).where(
            SourceIdentity.id == identity_id,
            SourceIdentity.organization_id == organization_id,
        )
    )
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source identity not found",
        )
    return identity


@router.get("", response_model=list[SourceIdentityRead])
def list_source_identities(
    organization_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_identities)],
    db: Annotated[Session, Depends(get_db)],
    provider: str | None = None,
    identity_state: SourceIdentityState | None = None,
) -> list[SourceIdentity]:
    del authorization
    statement = select(SourceIdentity).where(SourceIdentity.organization_id == organization_id)
    if provider:
        statement = statement.where(SourceIdentity.provider == provider.strip().lower())
    if identity_state:
        statement = statement.where(SourceIdentity.state == identity_state)
    statement = statement.order_by(SourceIdentity.provider, SourceIdentity.external_id)
    return list(db.scalars(statement))


@router.get("/{identity_id}/history", response_model=list[IdentityResolutionHistoryRead])
def identity_history(
    organization_id: uuid.UUID,
    identity_id: uuid.UUID,
    authorization: Annotated[AuthorizationContext, Depends(_manage_identities)],
    db: Annotated[Session, Depends(get_db)],
) -> list[IdentityResolutionHistory]:
    del authorization
    _get_identity(db, organization_id=organization_id, identity_id=identity_id)
    return list(
        db.scalars(
            select(IdentityResolutionHistory)
            .where(IdentityResolutionHistory.source_identity_id == identity_id)
            .order_by(IdentityResolutionHistory.created_at, IdentityResolutionHistory.id)
        )
    )


@router.post("/{identity_id}/resolve", response_model=SourceIdentityRead)
def resolve_source_identity(
    organization_id: uuid.UUID,
    identity_id: uuid.UUID,
    payload: SourceIdentityResolveRequest,
    authorization: Annotated[AuthorizationContext, Depends(_manage_identities)],
    db: Annotated[Session, Depends(get_db)],
) -> SourceIdentity:
    identity = _get_identity(db, organization_id=organization_id, identity_id=identity_id)
    try:
        return resolve_identity_manually(
            db,
            identity,
            target_user_id=payload.user_id,
            actor_user_id=authorization.user_id,
            reason=payload.reason,
        )
    except IdentityResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{identity_id}/unresolve", response_model=SourceIdentityRead)
def unresolve_source_identity(
    organization_id: uuid.UUID,
    identity_id: uuid.UUID,
    payload: SourceIdentityUnresolveRequest,
    authorization: Annotated[AuthorizationContext, Depends(_manage_identities)],
    db: Annotated[Session, Depends(get_db)],
) -> SourceIdentity:
    identity = _get_identity(db, organization_id=organization_id, identity_id=identity_id)
    return unresolve_identity_manually(
        db,
        identity,
        actor_user_id=authorization.user_id,
        reason=payload.reason,
    )


@router.post("/reconcile", response_model=IdentityReconcileRead)
def reconcile_identities(
    organization_id: uuid.UUID,
    payload: IdentityReconcileRequest,
    authorization: Annotated[AuthorizationContext, Depends(_manage_identities)],
    db: Annotated[Session, Depends(get_db)],
) -> IdentityReconcileRead:
    del authorization
    processed, remaining = reconcile_source_identities(
        db,
        organization_id=organization_id,
        limit=payload.limit,
    )
    return IdentityReconcileRead(processed=processed, remaining=remaining)
