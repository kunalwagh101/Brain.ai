from sqlalchemy import UniqueConstraint

from app.models import Base, MembershipRole


def _unique_columns(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def test_core_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "organizations",
        "users",
        "memberships",
        "external_identities",
        "resource_grants",
        "integration_connections",
        "slack_channel_authorizations",
        "raw_events",
    }


def test_membership_is_tenant_scoped() -> None:
    membership = Base.metadata.tables["memberships"]
    assert "organization_id" in membership.columns
    assert "user_id" in membership.columns


def test_supported_roles_are_explicit() -> None:
    assert {role.value for role in MembershipRole} == {
        "owner",
        "admin",
        "executive",
        "manager",
        "member",
        "guest",
    }


def test_external_identity_provider_subject_is_unique() -> None:
    assert ("provider", "subject") in _unique_columns("external_identities")


def test_resource_grant_scope_is_unique() -> None:
    assert (
        "organization_id",
        "resource_type",
        "resource_id",
        "user_id",
        "access",
    ) in _unique_columns("resource_grants")


def test_integration_connection_is_unique_per_tenant_provider_account() -> None:
    connection = Base.metadata.tables["integration_connections"]
    assert (
        "organization_id",
        "provider",
        "external_account_id",
    ) in _unique_columns("integration_connections")
    assert "secret_ref" in connection.columns
    assert "sync_cursor" in connection.columns


def test_slack_channel_authorization_is_unique_per_connection_channel() -> None:
    assert (
        "integration_connection_id",
        "channel_id",
    ) in _unique_columns("slack_channel_authorizations")


def test_raw_event_idempotency_key_is_unique_per_connection() -> None:
    assert (
        "integration_connection_id",
        "source_event_id",
    ) in _unique_columns("raw_events")
