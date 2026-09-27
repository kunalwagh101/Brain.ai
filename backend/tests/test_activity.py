import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.activity_models import ActivityNotification
from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User


def _seed(db: Session, suffix: str):
    organization = Organization(
        name=f"Activity {suffix}",
        slug=f"activity-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    owner = User(
        email=f"activity-owner-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Owner",
    )
    member = User(
        email=f"activity-member-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Member",
    )
    third = User(
        email=f"activity-third-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Third",
    )
    db.add_all([organization, owner, member, third])
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
                user_id=third.id,
                role=MembershipRole.MEMBER,
            ),
        ]
    )
    db.commit()
    return organization, owner, member, third


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _channel(client, organization, owner, visibility="organization"):
    _as(owner)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={"name": f"activity-{uuid.uuid4().hex[:7]}", "visibility": visibility},
    )
    assert response.status_code == 201
    return response.json()


def _root(client, organization, channel_id, user, body, key):
    _as(user)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages",
        headers={"Idempotency-Key": key},
        json={"body": body},
    )
    assert response.status_code == 201
    return response.json()


def test_activity_materializes_mentions_threads_reactions_and_dms_without_body_copy(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "core")
    channel = _channel(client, organization, owner)
    root = _root(
        client,
        organization,
        channel["id"],
        owner,
        f"unique-private-ish-channel-text @{member.email}",
        "activity-root",
    )

    _as(member)
    reply = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/replies",
        headers={"Idempotency-Key": "activity-reply"},
        json={"body": "reply-unique-text"},
    )
    assert reply.status_code == 201
    reaction = client.put(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{root['id']}/reaction",
        json={"reaction": "👍"},
    )
    assert reaction.status_code == 200

    conversation = client.post(
        f"/api/v1/organizations/{organization.id}/direct-messages",
        json={"target_email": owner.email},
    )
    assert conversation.status_code == 201
    dm_id = conversation.json()["id"]
    dm = client.post(
        f"/api/v1/organizations/{organization.id}/direct-messages/{dm_id}/messages",
        headers={"Idempotency-Key": "activity-dm"},
        json={"body": "dm-body-must-not-be-copied"},
    )
    assert dm.status_code == 201

    _as(owner)
    activity = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert activity.status_code == 200
    payload = activity.json()
    kinds = {item["kind"] for item in payload["items"]}
    assert {"thread_reply", "reaction", "direct_message"}.issubset(kinds)
    serialized = activity.text
    assert "reply-unique-text" not in serialized
    assert "dm-body-must-not-be-copied" not in serialized
    assert "unique-private-ish-channel-text" not in serialized

    first_count = db_session.scalar(
        select(func.count()).select_from(ActivityNotification).where(
            ActivityNotification.organization_id == organization.id,
            ActivityNotification.recipient_user_id == owner.id,
        )
    )
    again = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert again.status_code == 200
    second_count = db_session.scalar(
        select(func.count()).select_from(ActivityNotification).where(
            ActivityNotification.organization_id == organization.id,
            ActivityNotification.recipient_user_id == owner.id,
        )
    )
    assert second_count == first_count

    _as(member)
    member_activity = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert member_activity.status_code == 200
    assert any(item["kind"] == "mention" for item in member_activity.json()["items"])


def test_activity_read_state_is_recipient_scoped(db_session: Session, client) -> None:
    organization, owner, member, third = _seed(db_session, "read")
    channel = _channel(client, organization, owner)
    _root(
        client,
        organization,
        channel["id"],
        owner,
        f"Please inspect @{member.email}",
        "activity-read-root",
    )

    _as(member)
    summary = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert summary.status_code == 200
    assert summary.json()["unread_count"] == 1
    notification_id = summary.json()["items"][0]["id"]

    _as(third)
    forged = client.post(
        f"/api/v1/organizations/{organization.id}/activity/{notification_id}/read"
    )
    assert forged.status_code == 204

    _as(member)
    still_unread = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert still_unread.json()["unread_count"] == 1
    marked = client.post(
        f"/api/v1/organizations/{organization.id}/activity/{notification_id}/read"
    )
    assert marked.status_code == 204
    after = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert after.json()["unread_count"] == 0


def test_restricted_channel_revocation_hides_existing_activity(
    db_session: Session,
    client,
) -> None:
    organization, owner, member, _ = _seed(db_session, "revoke")
    channel = _channel(client, organization, owner, visibility="restricted")
    _as(owner)
    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/{channel['id']}/members",
        json={"email": member.email, "access": "write"},
    )
    assert invited.status_code == 201
    _root(
        client,
        organization,
        channel["id"],
        owner,
        f"Restricted mention @{member.email}",
        "activity-restricted-root",
    )

    _as(member)
    before = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert before.status_code == 200
    assert before.json()["unread_count"] == 1
    assert before.json()["items"][0]["kind"] == "mention"

    _as(owner)
    revoked = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{member.id}"
    )
    assert revoked.status_code == 204

    _as(member)
    after = client.get(f"/api/v1/organizations/{organization.id}/activity")
    assert after.status_code == 200
    assert after.json()["unread_count"] == 0
    assert after.json()["items"] == []
