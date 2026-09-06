from sqlalchemy import UniqueConstraint

from app.models import Base, MembershipRole


def test_core_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "organizations",
        "users",
        "memberships",
        "external_identities",
        "resource_grants",
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
    identity = Base.metadata.tables["external_identities"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in identity.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("provider", "subject") in unique_columns


def test_resource_grant_scope_is_unique() -> None:
    grant = Base.metadata.tables["resource_grants"]
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in grant.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert (
        "organization_id",
        "resource_type",
        "resource_id",
        "user_id",
        "access",
    ) in unique_columns
