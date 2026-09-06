from app.models import Base, MembershipRole


def test_core_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "organizations",
        "users",
        "memberships",
        "external_identities",
    }


def test_membership_is_tenant_scoped() -> None:
    membership = Base.metadata.tables["memberships"]
    assert "organization_id" in membership.columns
    assert "user_id" in membership.columns


def test_external_identity_has_provider_subject_uniqueness() -> None:
    identity = Base.metadata.tables["external_identities"]
    constraints = {constraint.name for constraint in identity.constraints if constraint.name}
    assert "uq_external_identity_provider_subject" in constraints
    assert "user_id" in identity.columns


def test_supported_roles_are_explicit() -> None:
    assert {role.value for role in MembershipRole} == {
        "owner",
        "admin",
        "executive",
        "manager",
        "member",
        "guest",
    }
