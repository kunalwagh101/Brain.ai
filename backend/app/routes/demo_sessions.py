"""Temporary staging login backed by the same users, memberships and APIs as Brain."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth import AuthPrincipal, get_current_principal
from app.config import get_settings
from app.database import get_db
from app.demo_session_models import DemoSession
from app.models import Membership, MembershipRole, Organization, User

router = APIRouter(prefix="/demo-sessions", tags=["demo-sessions"])
SESSION_LIFETIME = timedelta(hours=12)


class DemoSignup(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    model_config = {"extra": "forbid"}


class DemoSessionRead(BaseModel):
    access_token: str
    expires_at: datetime
    user_id: uuid.UUID


def demo_enabled() -> bool:
    settings = get_settings()
    return settings.environment.lower() == "staging" and settings.demo_signup_enabled


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def verify_demo_session(db: Session, token: str) -> DemoSession | None:
    if not demo_enabled() or not token.startswith("brdemo_") or len(token) > 128:
        return None
    session = db.scalar(select(DemoSession).where(DemoSession.token_hash == _token_hash(token)))
    if session is None or session.revoked_at is not None:
        return None
    expiry = (
        session.expires_at.replace(tzinfo=UTC)
        if session.expires_at.tzinfo is None
        else session.expires_at
    )
    return session if expiry > datetime.now(UTC) else None


@router.post("", response_model=DemoSessionRead, status_code=status.HTTP_201_CREATED)
def signup(
    payload: DemoSignup,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> DemoSessionRead:
    if not demo_enabled():
        raise HTTPException(status_code=404, detail="Demo signup is unavailable")
    name = " ".join(payload.name.split())
    if not name:
        raise HTTPException(status_code=422, detail="Enter a name")

    settings = get_settings()
    now = datetime.now(UTC)
    source = request.client.host if request.client else "unknown"
    source_hash = hmac.new(settings.app_secret.encode(), source.encode(), "sha256").hexdigest()
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        # Serialize the quota and insert across all instances, without Redis.
        db.execute(text("SELECT pg_advisory_xact_lock(1692301)"))
    since = now - timedelta(days=1)
    if (
        db.scalar(
            select(func.count()).select_from(DemoSession).where(DemoSession.created_at >= since)
        )
        or 0
    ) >= 100:
        raise HTTPException(status_code=429, detail="Demo signups are temporarily full")
    if (
        db.scalar(
            select(func.count())
            .select_from(DemoSession)
            .where(DemoSession.source_hash == source_hash, DemoSession.created_at >= since)
        )
        or 0
    ) >= 5:
        raise HTTPException(status_code=429, detail="Too many demo signups from this connection")

    identifier = uuid.uuid4().hex
    user = User(email=f"demo-{identifier}@example.invalid", display_name=name)
    organization = Organization(name=f"{name}'s demo", slug=f"demo-{identifier}")
    db.add_all([user, organization])
    db.flush()
    db.add(Membership(user_id=user.id, organization_id=organization.id, role=MembershipRole.OWNER))
    raw_token = f"brdemo_{secrets.token_urlsafe(32)}"
    db.add(
        DemoSession(
            user_id=user.id,
            organization_id=organization.id,
            token_hash=_token_hash(raw_token),
            source_hash=source_hash,
            expires_at=now + SESSION_LIFETIME,
        )
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return DemoSessionRead(
        access_token=raw_token, expires_at=now + SESSION_LIFETIME, user_id=user.id
    )


@router.delete("/current", status_code=204)
def signout(
    principal: Annotated[AuthPrincipal, Depends(get_current_principal)],
    db: Annotated[Session, Depends(get_db)],
):
    if principal.provider != "demo":
        raise HTTPException(status_code=403, detail="This is not a demo session")
    session = db.get(DemoSession, uuid.UUID(principal.subject))
    if session is not None:
        session.revoked_at = datetime.now(UTC)
        db.commit()
