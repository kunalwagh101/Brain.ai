import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.native_conversation_models import NativeMessagePin


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _seed(db: Session, suffix: str):
    organization = Organization(
        name=f"Pin {suffix}",
        slug=f"pin-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    other_organization = Organization(
        name=f"Other Pin {suffix}",
        slug=f"other-pin-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    owner = User(
        email=f"pin-owner-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Pin Owner",
    )
    member = User(
        email=f"pin-member-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Pin Member",
    )
    guest = User(
        email=f"pin-guest-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Pin Guest",
    )
    other_owner = User(
        email=f"pin-other-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Other Pin Owner",
    )
    db.add_all(
        [organization, other_organization, owner, member, guest, other_owner]
    )
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
                user_id=guest.id,
                role=MembershipRole.GUEST,
            ),
            Membership(
                organization_id=other_organization.id,
                user_id=other_owner.id,
                role=MembershipRole.OWNER,
            ),
        ]
    )
    db.commit()
    return organization, other_organization, owner, member, guest, other_owner


def _channel(client, organization, actor, visibility="organization"):
    _as(actor)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": f"pins-{uuid.uuid4().hex[:7]}",
            "visibility": visibility,
        },
    )
    assert response.status_code == 201
    return response.json()


def _message(client, organization, channel_id, actor, body, key):
    _as(actor)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages",
        headers={"Idempotency-Key": key},
        json={"body": body, "attachment_source_ids": []},
    )
    assert response.status_code == 201
    return response.json()


def _reply(client, organization, channel_id, root_id, actor, body, key):
    _as(actor)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages/{root_id}/replies",
        headers={"Idempotency-Key": key},
        json={"body": body, "attachment_source_ids": []},
    )
    assert response.status_code == 201
    return response.json()


def _pin(client, organization, channel_id, message_id, actor, active=True):
    _as(actor)
    return client.request(
        "PUT" if active else "DELETE",
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages/{message_id}/pin",
    )


def _pins(client, organization, channel_id, actor):
    _as(actor)
    return client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/pins"
    )


def test_pins_are_idempotent_newest_first_and_edits_preserve_reference(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _, _ = _seed(db_session, "idempotent")
    channel = _channel(client, organization, owner)
    first = _message(
        client,
        organization,
        channel["id"],
        owner,
        "First important message.",
        "pin-first",
    )
    second = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Second important message.",
        "pin-second",
    )

    first_pin = _pin(client, organization, channel["id"], first["id"], owner)
    repeated = _pin(client, organization, channel["id"], first["id"], owner)
    second_pin = _pin(client, organization, channel["id"], second["id"], owner)
    assert first_pin.status_code == 200
    assert repeated.status_code == 200
    assert second_pin.status_code == 200
    assert repeated.json()["pin_id"] == first_pin.json()["pin_id"]

    count = db_session.scalar(
        select(func.count())
        .select_from(NativeMessagePin)
        .where(
            NativeMessagePin.organization_id == organization.id,
            NativeMessagePin.channel_id == uuid.UUID(channel["id"]),
        )
    )
    assert count == 2

    listed = _pins(client, organization, channel["id"], owner)
    assert listed.status_code == 200
    assert [item["message"]["id"] for item in listed.json()] == [
        second["id"],
        first["id"],
    ]

    _as(owner)
    edited = client.patch(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{first['id']}",
        json={
            "body": "Edited important message.",
            "expected_revision": first["revision"],
        },
    )
    assert edited.status_code == 200

    listed_after_edit = _pins(client, organization, channel["id"], owner)
    first_after = next(
        item
        for item in listed_after_edit.json()
        if item["message"]["id"] == first["id"]
    )
    assert first_after["pin_id"] == first_pin.json()["pin_id"]
    assert first_after["message"]["body"] == "Edited important message."
    assert first_after["message"]["revision"] == first["revision"] + 1


def test_thread_reply_pin_materialises_existing_thread_context(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _, _ = _seed(db_session, "reply")
    channel = _channel(client, organization, owner)
    root = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Root message.",
        "pin-reply-root",
    )
    reply = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        owner,
        "Important reply.",
        "pin-reply-child",
    )

    pinned = _pin(client, organization, channel["id"], reply["id"], owner)
    assert pinned.status_code == 200
    listed = _pins(client, organization, channel["id"], owner)
    assert listed.status_code == 200
    assert listed.json()[0]["message"]["id"] == reply["id"]
    assert listed.json()[0]["message"]["thread_root_id"] == root["id"]


def test_read_only_member_can_list_but_cannot_mutate_and_revoke_hides(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, member, _, _ = _seed(db_session, "restricted")
    channel = _channel(client, organization, owner, visibility="restricted")
    message = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Restricted important message.",
        "pin-restricted-message",
    )
    assert _pin(
        client,
        organization,
        channel["id"],
        message["id"],
        owner,
    ).status_code == 200

    _as(owner)
    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invited.status_code == 201

    visible = _pins(client, organization, channel["id"], member)
    denied_pin = _pin(
        client,
        organization,
        channel["id"],
        message["id"],
        member,
    )
    denied_unpin = _pin(
        client,
        organization,
        channel["id"],
        message["id"],
        member,
        active=False,
    )
    assert visible.status_code == 200
    assert visible.json()[0]["message"]["id"] == message["id"]
    assert denied_pin.status_code == 404
    assert denied_unpin.status_code == 404

    _as(owner)
    removed = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{member.id}"
    )
    assert removed.status_code == 204
    hidden = _pins(client, organization, channel["id"], member)
    assert hidden.status_code == 404


def test_cross_channel_cross_tenant_and_guest_pin_mutations_fail_closed(
    db_session: Session,
    client,
) -> None:
    (
        organization,
        other_organization,
        owner,
        _,
        guest,
        other_owner,
    ) = _seed(db_session, "scope")
    channel_a = _channel(client, organization, owner)
    channel_b = _channel(client, organization, owner)
    other_channel = _channel(client, other_organization, other_owner)
    message = _message(
        client,
        organization,
        channel_a["id"],
        owner,
        "Scoped message.",
        "pin-scope-message",
    )

    wrong_channel = _pin(
        client,
        organization,
        channel_b["id"],
        message["id"],
        owner,
    )
    cross_tenant = _pin(
        client,
        other_organization,
        other_channel["id"],
        message["id"],
        other_owner,
    )
    guest_attempt = _pin(
        client,
        organization,
        channel_a["id"],
        message["id"],
        guest,
    )
    assert wrong_channel.status_code == 404
    assert cross_tenant.status_code == 404
    assert guest_attempt.status_code == 403


def test_retraction_removes_pin_in_same_lifecycle(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _, _ = _seed(db_session, "retract")
    channel = _channel(client, organization, owner)
    message = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Pinned then retracted.",
        "pin-retract-message",
    )
    assert _pin(
        client,
        organization,
        channel["id"],
        message["id"],
        owner,
    ).status_code == 200

    _as(owner)
    retracted = client.request(
        "DELETE",
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{message['id']}",
        json={"expected_revision": message["revision"]},
    )
    assert retracted.status_code == 200
    assert _pins(client, organization, channel["id"], owner).json() == []
    assert db_session.scalar(
        select(NativeMessagePin).where(
            NativeMessagePin.message_id == uuid.UUID(message["id"])
        )
    ) is None


def test_unpin_is_idempotent(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _, _ = _seed(db_session, "unpin")
    channel = _channel(client, organization, owner)
    message = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Unpin me.",
        "pin-unpin-message",
    )
    assert _pin(
        client,
        organization,
        channel["id"],
        message["id"],
        owner,
    ).status_code == 200
    assert _pin(
        client,
        organization,
        channel["id"],
        message["id"],
        owner,
        active=False,
    ).status_code == 204
    assert _pin(
        client,
        organization,
        channel["id"],
        message["id"],
        owner,
        active=False,
    ).status_code == 204
