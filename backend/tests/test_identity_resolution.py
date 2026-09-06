from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.identity_resolution import (
    observe_canonical_actor,
    resolve_identity_manually,
    unresolve_identity_manually,
)
from app.main import app
from app.models import (
    CanonicalEvent,
    IdentityResolutionHistory,
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    RawEventStatus,
    SourceIdentity,
    SourceIdentityObservation,
    SourceIdentityState,
    User,
)


def _seed_org(
    db: Session,
    slug: str,
    *,
    owner_role: MembershipRole = MembershipRole.OWNER,
) -> tuple[Organization, User, IntegrationConnection]:
    organization = Organization(name=slug.title(), slug=slug)
    owner = User(email=f"owner-{slug}@example.com")
    db.add_all([organization, owner])
    db.flush()
    db.add(Membership(organization_id=organization.id, user_id=owner.id, role=owner_role))
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id=f"T-{slug}",
        display_name=f"{slug} Slack",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.UNKNOWN,
        scopes=[],
        provider_metadata={},
        secret_ref="secret-ref",
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.commit()
    return organization, owner, connection


def _canonical_event(
    db: Session,
    *,
    organization: Organization,
    connection: IntegrationConnection,
    raw_suffix: str,
    actor_id: str,
    provider: str = "slack",
    actor_name: str | None = None,
) -> CanonicalEvent:
    raw = RawEvent(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        provider=provider,
        source_event_id=f"raw-{raw_suffix}",
        source_event_type="message",
        delivery_kind="webhook",
        content_type="application/json",
        payload_sha256="a" * 64,
        raw_payload=b"{}",
        source_visibility="public_channel",
        source_acl=[],
        processing_status=RawEventStatus.PROCESSED,
        processing_attempts=1,
    )
    db.add(raw)
    db.flush()
    event = CanonicalEvent(
        organization_id=organization.id,
        raw_event_id=raw.id,
        integration_connection_id=connection.id,
        schema_version=1,
        event_type="message.created",
        action="created",
        actor_type=f"{provider}_user",
        actor_external_id=actor_id,
        actor_display_name=actor_name,
        object_type="message",
        object_external_id=f"C1:{raw_suffix}",
        object_display_name=None,
        source_provider=provider,
        source_event_id=raw.source_event_id,
        source_event_type="message",
        occurred_at=datetime.now(UTC),
        source_visibility="public_channel",
        source_acl=[],
        provenance={"raw_event_id": str(raw.id)},
        event_metadata={},
    )
    db.add(event)
    db.commit()
    return event


def test_same_provider_actor_reuses_one_tenant_source_identity(db_session: Session) -> None:
    organization, _, connection = _seed_org(db_session, "identity-one")
    first = _canonical_event(
        db_session,
        organization=organization,
        connection=connection,
        raw_suffix="1",
        actor_id="U123",
    )
    second = _canonical_event(
        db_session,
        organization=organization,
        connection=connection,
        raw_suffix="2",
        actor_id="U123",
    )

    identity_one = observe_canonical_actor(db_session, first)
    identity_two = observe_canonical_actor(db_session, second)

    assert identity_one is not None
    assert identity_two is not None
    assert identity_one.id == identity_two.id
    assert db_session.scalar(select(func.count()).select_from(SourceIdentity)) == 1
    assert db_session.scalar(select(func.count()).select_from(SourceIdentityObservation)) == 2
    assert first.resolved_user_id is None
    assert identity_one.state == SourceIdentityState.UNRESOLVED


def test_unverified_email_never_auto_resolves(db_session: Session) -> None:
    organization, _, connection = _seed_org(db_session, "identity-unverified")
    member = User(email="person@example.com")
    db_session.add(member)
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
        )
    )
    db_session.commit()
    event = _canonical_event(
        db_session,
        organization=organization,
        connection=connection,
        raw_suffix="unverified",
        actor_id="U200",
    )

    identity = observe_canonical_actor(
        db_session,
        event,
        email="person@example.com",
        email_verified=False,
    )

    assert identity is not None
    assert identity.resolved_user_id is None
    assert identity.state == SourceIdentityState.UNRESOLVED
    assert db_session.query(IdentityResolutionHistory).count() == 0


def test_verified_exact_email_auto_resolves_only_same_org_member(db_session: Session) -> None:
    organization, _, connection = _seed_org(db_session, "identity-auto")
    member = User(email="verified@example.com")
    db_session.add(member)
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=member.id,
            role=MembershipRole.MEMBER,
        )
    )
    db_session.commit()
    event = _canonical_event(
        db_session,
        organization=organization,
        connection=connection,
        raw_suffix="auto",
        actor_id="U300",
    )

    identity = observe_canonical_actor(
        db_session,
        event,
        email=" Verified@Example.com ",
        email_verified=True,
        evidence={"provider_verified": True},
    )

    assert identity is not None
    assert identity.resolved_user_id == member.id
    assert identity.state == SourceIdentityState.RESOLVED
    assert identity.resolution_method == "verified_email"
    db_session.refresh(event)
    assert event.resolved_user_id == member.id
    history = db_session.query(IdentityResolutionHistory).one()
    assert history.action == "auto_resolve"
    assert history.actor_user_id is None


def test_verified_email_does_not_cross_tenant_boundary(db_session: Session) -> None:
    organization, _, connection = _seed_org(db_session, "identity-target")
    other_org, _, _ = _seed_org(db_session, "identity-other")
    other_user = User(email="other-only@example.com")
    db_session.add(other_user)
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=other_org.id,
            user_id=other_user.id,
            role=MembershipRole.MEMBER,
        )
    )
    db_session.commit()
    event = _canonical_event(
        db_session,
        organization=organization,
        connection=connection,
        raw_suffix="cross",
        actor_id="U400",
    )

    identity = observe_canonical_actor(
        db_session,
        event,
        email="other-only@example.com",
        email_verified=True,
    )

    assert identity is not None
    assert identity.resolved_user_id is None
    assert identity.state == SourceIdentityState.UNRESOLVED


def test_manual_resolution_reassign_and_unresolve_are_audited(db_session: Session) -> None:
    organization, owner, connection = _seed_org(db_session, "identity-manual")
    first_user = User(email="first@example.com")
    second_user = User(email="second@example.com")
    db_session.add_all([first_user, second_user])
    db_session.flush()
    db_session.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=first_user.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=second_user.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    db_session.commit()
    event = _canonical_event(
        db_session,
        organization=organization,
        connection=connection,
        raw_suffix="manual",
        actor_id="U500",
    )
    identity = observe_canonical_actor(db_session, event)
    assert identity is not None

    resolve_identity_manually(
        db_session,
        identity,
        target_user_id=first_user.id,
        actor_user_id=owner.id,
        reason="confirmed by admin",
    )
    resolve_identity_manually(
        db_session,
        identity,
        target_user_id=second_user.id,
        actor_user_id=owner.id,
        reason="corrected account owner",
    )
    unresolve_identity_manually(
        db_session,
        identity,
        actor_user_id=owner.id,
        reason="account ownership uncertain",
    )

    db_session.refresh(event)
    assert identity.resolved_user_id is None
    assert identity.state == SourceIdentityState.UNRESOLVED
    assert event.resolved_user_id is None
    history = list(
        db_session.scalars(
            select(IdentityResolutionHistory).order_by(IdentityResolutionHistory.created_at)
        )
    )
    assert [item.action for item in history] == ["manual_resolve", "reassign", "unresolve"]
    assert history[0].new_user_id == first_user.id
    assert history[1].previous_user_id == first_user.id
    assert history[1].new_user_id == second_user.id
    assert history[2].previous_user_id == second_user.id
    assert all(item.actor_user_id == owner.id for item in history)


def test_member_cannot_manage_source_identities(client: TestClient, db_session: Session) -> None:
    organization, _, connection = _seed_org(
        db_session,
        "identity-member",
        owner_role=MembershipRole.MEMBER,
    )
    member = db_session.scalar(
        select(User).join(Membership).where(Membership.organization_id == organization.id)
    )
    assert member is not None
    event = _canonical_event(
        db_session,
        organization=organization,
        connection=connection,
        raw_suffix="api-member",
        actor_id="U600",
    )
    identity = observe_canonical_actor(db_session, event)
    assert identity is not None
    app.dependency_overrides[get_current_user] = lambda: member

    response = client.get(f"/api/v1/organizations/{organization.id}/source-identities")

    assert response.status_code == 403


def test_owner_can_reconcile_existing_canonical_actor(
    client: TestClient,
    db_session: Session,
) -> None:
    organization, owner, connection = _seed_org(db_session, "identity-reconcile")
    event = _canonical_event(
        db_session,
        organization=organization,
        connection=connection,
        raw_suffix="reconcile",
        actor_id="U700",
    )
    assert event.source_identity_id is None
    app.dependency_overrides[get_current_user] = lambda: owner

    response = client.post(
        f"/api/v1/organizations/{organization.id}/source-identities/reconcile",
        json={"limit": 100},
    )

    assert response.status_code == 200
    assert response.json() == {"processed": 1, "remaining": 0}
    db_session.refresh(event)
    assert event.source_identity_id is not None
    assert db_session.query(SourceIdentity).count() == 1
