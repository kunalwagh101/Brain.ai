import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Membership, MembershipRole, Organization, User
from app.schemas import MembershipCreate, MembershipRead, OrganizationCreate, OrganizationRead

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _membership_for(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
    return db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user_id,
        )
    )


def _require_member(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    membership = _membership_for(db, organization_id, user_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return membership


def _require_owner(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    membership = _require_member(db, organization_id, user_id)
    if membership.role != MembershipRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner role required")
    return membership


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Organization slug exists") from None
    db.refresh(organization)
    return organization


@router.get("/{organization_id}", response_model=OrganizationRead)
def read_organization(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    _require_member(db, organization_id, current_user.id)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Membership:
    _require_owner(db, organization_id, current_user.id)
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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Membership already exists") from None
    db.refresh(membership)
    return membership


@router.get("/{organization_id}/memberships", response_model=list[MembershipRead])
def list_memberships(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Membership]:
    _require_member(db, organization_id, current_user.id)
    return list(
        db.scalars(
            select(Membership)
            .where(Membership.organization_id == organization_id)
            .order_by(Membership.created_at, Membership.id)
        )
    )
