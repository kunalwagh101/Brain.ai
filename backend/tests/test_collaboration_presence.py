import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.collaboration_presence_models import (
    CollaborationPresenceLease,
    CollaborationTypingLease,
)
from app.data_governance_models import SecurityAuditEvent
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _seed(db: Session, suffix: str):
    organization = Organization(
        name=f"Presence {suffix}",
        slug=f"presence-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    owner = User(
        email=f"presence-owner-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Presence Owner",
    )
    member = User(
        email=f"presence-member-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Presence Member",
    )
    admin = User(
        email=f"presence-admin-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Presence Admin",
    )
    guest = User(
        email=f"presence-guest-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Presence Guest",
    )
    db.add_all([organization, owner, member, admin, guest])
    db.flush()
    db.add_all(
        [
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role=MembershipRole.OWNER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=member.id,
                role=MembershipRole.MEMBER,
            ),
            Membership(
                organization_id=organization.id,
                user_id=admin.id,
                role=MembershipRole.ADMIN,
            ),
            Membership(
                organization_id=organization.id,
                user_id=guest.id,
                role=MembershipRole.GUEST,
            ),
        ]
    )
    db.commit()
    return organization, owner, member, admin, guest


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _heartbeat(client, organization, user):
    _as(user)
    return client.post(
        f"/api/v1/organizations/{organization.id}/collaboration-presence/heartbeat"
    )


def _channel(client, organization, owner, *, visibility="organization"):
    _as(owner)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": f"presence-{uuid.uuid4().hex[:7]}",
            "visibility": visibility,
        },
    )
    assert response.status_code == 201
    return response.json()


def _context(client, organization, actor, kind, context_id):
    _as(actor)
    return client.get(
        f"/api/v1/organizations/{organization.id}/collaboration-presence/"
        f"{kind}/{context_id}"
    )


def _typing(client, organization, actor, kind, context_id, *, active=True):
    _as(actor)
    return client.request(
        "PUT" if active else "DELETE",
        f"/api/v1/organizations/{organization.id}/collaboration-presence/"
        f"{kind}/{context_id}/typing",
    )


def _invite(client, organization, owner, channel_id, target, access="write"):
    _as(owner)
    return client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel_id}/members",
        json={"email": target.email, "access": access},
    )


def _dm(client, organization, actor, target):
    _as(actor)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/direct-messages",
        json={"target_email": target.email},
    )
    assert response.status_code == 201
    return response.json()


def test_heartbeat_refreshes_one_lease_and_expired_rows_are_purged(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _, _ = _seed(db_session, "heartbeat")
    channel = _channel(client, organization, owner)

    first = _heartbeat(client, organization, owner)
    second = _heartbeat(client, organization, owner)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"online": True}

    count = db_session.scalar(
        select(func.count())
        .select_from(CollaborationPresenceLease)
        .where(
            CollaborationPresenceLease.organization_id == organization.id,
            CollaborationPresenceLease.user_id == owner.id,
        )
    )
    assert count == 1

    lease = db_session.scalar(
        select(CollaborationPresenceLease).where(
            CollaborationPresenceLease.organization_id == organization.id,
            CollaborationPresenceLease.user_id == owner.id,
        )
    )
    assert lease is not None
    lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    assert _heartbeat(client, organization, member).status_code == 200
    visible = _context(client, organization, member, "channel", channel["id"])
    assert visible.status_code == 200
    assert [item["user_id"] for item in visible.json()["online_users"]] == [str(member.id)]
    assert db_session.get(CollaborationPresenceLease, lease.id) is None


def test_restricted_channel_presence_and_typing_follow_live_membership(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _, _ = _seed(db_session, "restricted")
    channel = _channel(client, organization, owner, visibility="restricted")
    invited = _invite(client, organization, owner, channel["id"], member)
    assert invited.status_code == 201

    assert _heartbeat(client, organization, owner).status_code == 200
    assert _heartbeat(client, organization, member).status_code == 200
    started = _typing(
        client,
        organization,
        member,
        "channel",
        channel["id"],
    )
    repeated = _typing(
        client,
        organization,
        member,
        "channel",
        channel["id"],
    )
    assert started.status_code == 204
    assert repeated.status_code == 204

    typing_count = db_session.scalar(
        select(func.count())
        .select_from(CollaborationTypingLease)
        .where(
            CollaborationTypingLease.organization_id == organization.id,
            CollaborationTypingLease.native_channel_id == uuid.UUID(channel["id"]),
            CollaborationTypingLease.user_id == member.id,
        )
    )
    assert typing_count == 1

    before = _context(client, organization, owner, "channel", channel["id"])
    assert before.status_code == 200
    assert {item["user_id"] for item in before.json()["online_users"]} == {
        str(owner.id),
        str(member.id),
    }
    assert [item["user_id"] for item in before.json()["typing_users"]] == [
        str(member.id)
    ]

    _as(owner)
    removed = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{member.id}"
    )
    assert removed.status_code == 204

    after = _context(client, organization, owner, "channel", channel["id"])
    assert after.status_code == 200
    assert [item["user_id"] for item in after.json()["online_users"]] == [str(owner.id)]
    assert after.json()["typing_users"] == []

    denied = _context(client, organization, member, "channel", channel["id"])
    assert denied.status_code == 404


def test_dm_presence_and_typing_are_participant_only_even_for_admin(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, admin, _ = _seed(db_session, "dm")
    conversation = _dm(client, organization, owner, member)

    assert _heartbeat(client, organization, owner).status_code == 200
    assert _heartbeat(client, organization, member).status_code == 200
    assert _heartbeat(client, organization, admin).status_code == 200
    assert _typing(
        client,
        organization,
        member,
        "dm",
        conversation["id"],
    ).status_code == 204

    owner_view = _context(
        client,
        organization,
        owner,
        "dm",
        conversation["id"],
    )
    assert owner_view.status_code == 200
    assert [item["user_id"] for item in owner_view.json()["online_users"]] == [
        str(member.id)
    ]
    assert [item["user_id"] for item in owner_view.json()["typing_users"]] == [
        str(member.id)
    ]

    admin_view = _context(
        client,
        organization,
        admin,
        "dm",
        conversation["id"],
    )
    assert admin_view.status_code == 404
    admin_typing = _typing(
        client,
        organization,
        admin,
        "dm",
        conversation["id"],
    )
    assert admin_typing.status_code == 404


def test_expired_and_cleared_typing_never_appear(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _, _ = _seed(db_session, "typing-expiry")
    channel = _channel(client, organization, owner)
    assert _heartbeat(client, organization, member).status_code == 200
    assert _typing(
        client,
        organization,
        member,
        "channel",
        channel["id"],
    ).status_code == 204

    lease = db_session.scalar(
        select(CollaborationTypingLease).where(
            CollaborationTypingLease.organization_id == organization.id,
            CollaborationTypingLease.native_channel_id == uuid.UUID(channel["id"]),
            CollaborationTypingLease.user_id == member.id,
        )
    )
    assert lease is not None
    lease.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    expired = _context(client, organization, owner, "channel", channel["id"])
    assert expired.status_code == 200
    assert expired.json()["typing_users"] == []
    assert db_session.get(CollaborationTypingLease, lease.id) is not None

    assert _heartbeat(client, organization, owner).status_code == 200
    assert db_session.get(CollaborationTypingLease, lease.id) is None

    assert _typing(
        client,
        organization,
        member,
        "channel",
        channel["id"],
    ).status_code == 204
    assert _typing(
        client,
        organization,
        member,
        "channel",
        channel["id"],
        active=False,
    ).status_code == 204
    assert _typing(
        client,
        organization,
        member,
        "channel",
        channel["id"],
        active=False,
    ).status_code == 204
    assert db_session.scalar(
        select(func.count())
        .select_from(CollaborationTypingLease)
        .where(CollaborationTypingLease.organization_id == organization.id)
    ) == 0


def test_guest_cannot_publish_presence_or_typing(
    db_session: Session,
    client,
) -> None:
    organization, owner, _, _, guest = _seed(db_session, "guest")
    channel = _channel(client, organization, owner)

    heartbeat = _heartbeat(client, organization, guest)
    typing = _typing(
        client,
        organization,
        guest,
        "channel",
        channel["id"],
    )
    read = _context(client, organization, guest, "channel", channel["id"])

    assert heartbeat.status_code == 403
    assert typing.status_code == 403
    assert read.status_code == 403


def test_normal_presence_traffic_creates_no_security_audit_history(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _, _ = _seed(db_session, "no-audit")
    channel = _channel(client, organization, owner)
    baseline = db_session.scalar(
        select(func.count())
        .select_from(SecurityAuditEvent)
        .where(SecurityAuditEvent.organization_id == organization.id)
    ) or 0

    assert _heartbeat(client, organization, owner).status_code == 200
    assert _heartbeat(client, organization, member).status_code == 200
    assert _context(
        client,
        organization,
        owner,
        "channel",
        channel["id"],
    ).status_code == 200
    assert _typing(
        client,
        organization,
        member,
        "channel",
        channel["id"],
    ).status_code == 204
    assert _typing(
        client,
        organization,
        member,
        "channel",
        channel["id"],
        active=False,
    ).status_code == 204

    after = db_session.scalar(
        select(func.count())
        .select_from(SecurityAuditEvent)
        .where(SecurityAuditEvent.organization_id == organization.id)
    ) or 0
    assert after == baseline
