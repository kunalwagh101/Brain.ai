from app.models import Base, MembershipRole


def test_core_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {"organizations", "users", "memberships"}


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
