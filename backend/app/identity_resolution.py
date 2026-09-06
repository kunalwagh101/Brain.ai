import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    CanonicalEvent,
    IdentityResolutionHistory,
    Membership,
    SourceIdentity,
    SourceIdentityObservation,
    SourceIdentityState,
    User,
)

PERSON_ACTOR_TYPES = frozenset({"slack_user", "github_user"})


class IdentityResolutionError(ValueError):
    """Raised when a requested identity resolution would be unsafe."""


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized or "@" not in normalized or len(normalized) > 320:
        return None
    return normalized


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _active_member_by_email(
    db: Session,
    *,
    organization_id: uuid.UUID,
    email: str,
) -> User | None:
    return db.scalar(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.organization_id == organization_id,
            User.email == email,
            User.status == "active",
        )
        .limit(1)
    )


def _active_member_by_id(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
) -> User | None:
    return db.scalar(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(
            Membership.organization_id == organization_id,
            User.id == user_id,
            User.status == "active",
        )
        .limit(1)
    )


def _history(
    db: Session,
    identity: SourceIdentity,
    *,
    previous_user_id: uuid.UUID | None,
    new_user_id: uuid.UUID | None,
    action: str,
    method: str,
    actor_user_id: uuid.UUID | None,
    evidence: dict[str, object] | None = None,
) -> None:
    db.add(
        IdentityResolutionHistory(
            organization_id=identity.organization_id,
            source_identity_id=identity.id,
            previous_user_id=previous_user_id,
            new_user_id=new_user_id,
            action=action,
            method=method,
            actor_user_id=actor_user_id,
            evidence=evidence or {},
        )
    )


def _apply_resolution_to_events(db: Session, identity: SourceIdentity) -> None:
    db.execute(
        update(CanonicalEvent)
        .where(CanonicalEvent.source_identity_id == identity.id)
        .values(resolved_user_id=identity.resolved_user_id)
    )


def _get_or_create_identity(
    db: Session,
    event: CanonicalEvent,
    *,
    observed_at: datetime,
) -> SourceIdentity:
    identity = db.scalar(
        select(SourceIdentity).where(
            SourceIdentity.organization_id == event.organization_id,
            SourceIdentity.provider == event.source_provider,
            SourceIdentity.external_id == event.actor_external_id,
        )
    )
    if identity is not None:
        return identity

    identity = SourceIdentity(
        organization_id=event.organization_id,
        provider=event.source_provider,
        external_id=str(event.actor_external_id),
        display_name=event.actor_display_name,
        email=None,
        email_verified=False,
        state=SourceIdentityState.UNRESOLVED,
        resolved_user_id=None,
        resolution_method=None,
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )
    try:
        with db.begin_nested():
            db.add(identity)
            db.flush()
    except IntegrityError:
        identity = db.scalar(
            select(SourceIdentity).where(
                SourceIdentity.organization_id == event.organization_id,
                SourceIdentity.provider == event.source_provider,
                SourceIdentity.external_id == event.actor_external_id,
            )
        )
        if identity is None:
            raise
    return identity


def observe_canonical_actor(
    db: Session,
    event: CanonicalEvent,
    *,
    email: str | None = None,
    email_verified: bool = False,
    evidence: dict[str, object] | None = None,
) -> SourceIdentity | None:
    if event.actor_type not in PERSON_ACTOR_TYPES or not event.actor_external_id:
        return None

    observed_at = _utc_datetime(event.occurred_at or event.created_at or datetime.now(UTC))
    identity = _get_or_create_identity(db, event, observed_at=observed_at)
    event.source_identity_id = identity.id

    if event.actor_display_name:
        identity.display_name = event.actor_display_name
    if observed_at < _utc_datetime(identity.first_seen_at):
        identity.first_seen_at = observed_at
    if observed_at > _utc_datetime(identity.last_seen_at):
        identity.last_seen_at = observed_at

    normalized_email = normalize_email(email)
    observation = db.scalar(
        select(SourceIdentityObservation).where(
            SourceIdentityObservation.canonical_event_id == event.id
        )
    )
    if observation is None:
        observation = SourceIdentityObservation(
            source_identity_id=identity.id,
            canonical_event_id=event.id,
            display_name=event.actor_display_name,
            email=normalized_email,
            email_verified=bool(email_verified and normalized_email),
            evidence=evidence or {"source_event_id": event.source_event_id},
            observed_at=observed_at,
        )
        try:
            with db.begin_nested():
                db.add(observation)
                db.flush()
        except IntegrityError:
            pass

    verified_email = normalized_email if email_verified else None
    if verified_email:
        if identity.email_verified and identity.email and identity.email != verified_email:
            previous = identity.resolved_user_id
            identity.email = None
            identity.email_verified = False
            identity.resolved_user_id = None
            identity.resolution_method = None
            identity.state = SourceIdentityState.REVIEW_REQUIRED
            _history(
                db,
                identity,
                previous_user_id=previous,
                new_user_id=None,
                action="conflict_clear",
                method="verified_email_conflict",
                actor_user_id=None,
                evidence={"canonical_event_id": str(event.id)},
            )
        elif identity.state != SourceIdentityState.REVIEW_REQUIRED:
            identity.email = verified_email
            identity.email_verified = True
            member = _active_member_by_email(
                db,
                organization_id=identity.organization_id,
                email=verified_email,
            )
            if member is not None and identity.resolved_user_id is None:
                identity.resolved_user_id = member.id
                identity.state = SourceIdentityState.RESOLVED
                identity.resolution_method = "verified_email"
                _history(
                    db,
                    identity,
                    previous_user_id=None,
                    new_user_id=member.id,
                    action="auto_resolve",
                    method="verified_email",
                    actor_user_id=None,
                    evidence={"canonical_event_id": str(event.id), "email": verified_email},
                )
    elif normalized_email and not identity.email_verified:
        identity.email = normalized_email

    event.resolved_user_id = identity.resolved_user_id
    _apply_resolution_to_events(db, identity)
    db.commit()
    db.refresh(identity)
    db.refresh(event)
    return identity


def resolve_identity_manually(
    db: Session,
    identity: SourceIdentity,
    *,
    target_user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> SourceIdentity:
    member = _active_member_by_id(
        db,
        organization_id=identity.organization_id,
        user_id=target_user_id,
    )
    if member is None:
        raise IdentityResolutionError("Target user must be an active organization member")
    if identity.resolved_user_id == member.id and identity.state == SourceIdentityState.RESOLVED:
        return identity

    previous = identity.resolved_user_id
    identity.resolved_user_id = member.id
    identity.state = SourceIdentityState.RESOLVED
    identity.resolution_method = "manual"
    _history(
        db,
        identity,
        previous_user_id=previous,
        new_user_id=member.id,
        action="manual_resolve" if previous is None else "reassign",
        method="manual",
        actor_user_id=actor_user_id,
        evidence={"reason": reason.strip()[:500] if reason else None},
    )
    _apply_resolution_to_events(db, identity)
    db.commit()
    db.refresh(identity)
    return identity


def unresolve_identity_manually(
    db: Session,
    identity: SourceIdentity,
    *,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> SourceIdentity:
    if identity.resolved_user_id is None and identity.state == SourceIdentityState.UNRESOLVED:
        return identity
    previous = identity.resolved_user_id
    identity.resolved_user_id = None
    identity.state = SourceIdentityState.UNRESOLVED
    identity.resolution_method = None
    _history(
        db,
        identity,
        previous_user_id=previous,
        new_user_id=None,
        action="unresolve",
        method="manual",
        actor_user_id=actor_user_id,
        evidence={"reason": reason.strip()[:500] if reason else None},
    )
    _apply_resolution_to_events(db, identity)
    db.commit()
    db.refresh(identity)
    return identity


def reconcile_source_identities(
    db: Session,
    *,
    organization_id: uuid.UUID,
    limit: int,
) -> tuple[int, int]:
    events = list(
        db.scalars(
            select(CanonicalEvent)
            .where(
                CanonicalEvent.organization_id == organization_id,
                CanonicalEvent.source_identity_id.is_(None),
                CanonicalEvent.actor_external_id.is_not(None),
                CanonicalEvent.actor_type.in_(PERSON_ACTOR_TYPES),
            )
            .order_by(CanonicalEvent.created_at, CanonicalEvent.id)
            .limit(limit)
        )
    )
    processed = 0
    for event in events:
        if observe_canonical_actor(db, event) is not None:
            processed += 1
    remaining = db.scalar(
        select(func.count())
        .select_from(CanonicalEvent)
        .where(
            CanonicalEvent.organization_id == organization_id,
            CanonicalEvent.source_identity_id.is_(None),
            CanonicalEvent.actor_external_id.is_not(None),
            CanonicalEvent.actor_type.in_(PERSON_ACTOR_TYPES),
        )
    )
    return processed, int(remaining or 0)
