import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.native_conversation_models import NativeMessageSave


def _as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _seed(db: Session, suffix: str):
    organization = Organization(
        name=f"Save {suffix}",
        slug=f"save-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    other_organization = Organization(
        name=f"Other Save {suffix}",
        slug=f"other-save-{suffix}-{uuid.uuid4().hex[:6]}",
    )
    owner = User(
        email=f"save-owner-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Save Owner",
    )
    member = User(
        email=f"save-member-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Save Member",
    )
    other_owner = User(
        email=f"save-other-{suffix}-{uuid.uuid4().hex[:6]}@example.com",
        display_name="Other Save Owner",
    )
    db.add_all([organization, other_organization, owner, member, other_owner])
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
                organization_id=other_organization.id,
                user_id=other_owner.id,
                role=MembershipRole.OWNER,
            ),
        ]
    )
    db.commit()
    return organization, other_organization, owner, member, other_owner


def _channel(client, organization, actor, visibility="organization"):
    _as(actor)
    response = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels",
        json={
            "name": f"saved-{uuid.uuid4().hex[:7]}",
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


def _save(client, organization, channel_id, message_id, actor, active=True):
    _as(actor)
    return client.request(
        "PUT" if active else "DELETE",
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel_id}/messages/{message_id}/saved",
    )


def _saved(client, organization, actor):
    _as(actor)
    return client.get(
        f"/api/v1/organizations/{organization.id}/native-conversation/saved"
    )


def test_saved_messages_are_private_idempotent_and_newest_first(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, member, _ = _seed(db_session, "private")
    channel = _channel(client, organization, owner)
    first = _message(
        client,
        organization,
        channel["id"],
        owner,
        "First personal follow-up.",
        "save-first",
    )
    second = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Second personal follow-up.",
        "save-second",
    )

    first_save = _save(client, organization, channel["id"], first["id"], owner)
    repeated = _save(client, organization, channel["id"], first["id"], owner)
    second_save = _save(client, organization, channel["id"], second["id"], owner)
    assert first_save.status_code == 200
    assert repeated.status_code == 200
    assert second_save.status_code == 200
    assert repeated.json()["save_id"] == first_save.json()["save_id"]

    count = db_session.scalar(
        select(func.count())
        .select_from(NativeMessageSave)
        .where(
            NativeMessageSave.organization_id == organization.id,
            NativeMessageSave.user_id == owner.id,
        )
    )
    assert count == 2

    mine = _saved(client, organization, owner)
    assert mine.status_code == 200
    assert [item["message"]["id"] for item in mine.json()] == [
        second["id"],
        first["id"],
    ]

    someone_else = _saved(client, organization, member)
    assert someone_else.status_code == 200
    assert someone_else.json() == []


def test_read_only_restricted_member_can_save_and_revoke_hides_without_deleting_reference(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, member, _ = _seed(db_session, "revoke")
    channel = _channel(client, organization, owner, visibility="restricted")
    message = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Private channel follow-up.",
        "save-revoke-message",
    )

    _as(owner)
    invited = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members",
        json={"email": member.email, "access": "read"},
    )
    assert invited.status_code == 201

    saved = _save(
        client,
        organization,
        channel["id"],
        message["id"],
        member,
    )
    assert saved.status_code == 200
    save_id = saved.json()["save_id"]

    _as(owner)
    removed = client.delete(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members/{member.id}"
    )
    assert removed.status_code == 204

    hidden = _saved(client, organization, member)
    assert hidden.status_code == 200
    assert hidden.json() == []
    assert db_session.get(NativeMessageSave, uuid.UUID(save_id)) is not None

    _as(owner)
    restored = client.post(
        f"/api/v1/organizations/{organization.id}/native-channels/"
        f"{channel['id']}/members",
        json={"email": member.email, "access": "read"},
    )
    assert restored.status_code in {200, 201}

    visible_again = _saved(client, organization, member)
    assert visible_again.status_code == 200
    assert visible_again.json()[0]["save_id"] == save_id


def test_thread_reply_save_and_edit_preserve_reference(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, _, _ = _seed(db_session, "thread")
    channel = _channel(client, organization, owner)
    root = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Thread root.",
        "save-thread-root",
    )
    reply = _reply(
        client,
        organization,
        channel["id"],
        root["id"],
        owner,
        "Remember this reply.",
        "save-thread-reply",
    )

    saved = _save(client, organization, channel["id"], reply["id"], owner)
    assert saved.status_code == 200
    save_id = saved.json()["save_id"]
    assert saved.json()["message"]["thread_root_id"] == root["id"]

    _as(owner)
    edited = client.patch(
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{reply['id']}",
        json={
            "body": "Remember this edited reply.",
            "expected_revision": reply["revision"],
        },
    )
    assert edited.status_code == 200

    listed = _saved(client, organization, owner)
    assert listed.status_code == 200
    assert listed.json()[0]["save_id"] == save_id
    assert listed.json()[0]["message"]["body"] == "Remember this edited reply."


def test_retraction_removes_all_personal_save_references(
    db_session: Session,
    client,
) -> None:
    organization, _, owner, member, _ = _seed(db_session, "retract")
    channel = _channel(client, organization, owner)
    message = _message(
        client,
        organization,
        channel["id"],
        owner,
        "Shared message saved personally.",
        "save-retract",
    )

    assert _save(
        client,
        organization,
        channel["id"],
        message["id"],
        owner,
    ).status_code == 200
    assert _save(
        client,
        organization,
        channel["id"],
        message["id"],
        member,
    ).status_code == 200

    _as(owner)
    retracted = client.request(
        "DELETE",
        f"/api/v1/organizations/{organization.id}/native-conversation/"
        f"channels/{channel['id']}/messages/{message['id']}",
        json={"expected_revision": message["revision"]},
    )
    assert retracted.status_code == 200

    count = db_session.scalar(
        select(func.count())
        .select_from(NativeMessageSave)
        .where(NativeMessageSave.message_id == uuid.UUID(message["id"]))
    )
    assert count == 0
    assert _saved(client, organization, owner).json() == []
    assert _saved(client, organization, member).json() == []


def test_wrong_channel_cross_tenant_and_unsave_are_fail_closed_and_idempotent(
    db_session: Session,
    client,
) -> None:
    organization, other_organization, owner, _, other_owner = _seed(
        db_session,
        "scope",
    )
    channel_a = _channel(client, organization, owner)
    channel_b = _channel(client, organization, owner)
    other_channel = _channel(client, other_organization, other_owner)
    message = _message(
        client,
        organization,
        channel_a["id"],
        owner,
        "Scoped personal save.",
        "save-scope",
    )

    wrong_channel = _save(
        client,
        organization,
        channel_b["id"],
        message["id"],
        owner,
    )
    cross_tenant = _save(
        client,
        other_organization,
        other_channel["id"],
        message["id"],
        other_owner,
    )
    assert wrong_channel.status_code == 404
    assert cross_tenant.status_code == 404

    assert _save(
        client,
        organization,
        channel_a["id"],
        message["id"],
        owner,
    ).status_code == 200
    assert _save(
        client,
        organization,
        channel_a["id"],
        message["id"],
        owner,
        active=False,
    ).status_code == 204
    assert _save(
        client,
        organization,
        channel_a["id"],
        message["id"],
        owner,
        active=False,
    ).status_code == 204
