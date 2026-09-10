from app.database import sqlalchemy_database_url


def test_postgresql_url_uses_installed_psycopg3_driver() -> None:
    assert sqlalchemy_database_url(
        "postgresql://user:pass@db.internal:5432/brain"
    ) == "postgresql+psycopg://user:pass@db.internal:5432/brain"


def test_legacy_postgres_url_uses_installed_psycopg3_driver() -> None:
    assert sqlalchemy_database_url(
        "postgres://user:pass@db.internal:5432/brain"
    ) == "postgresql+psycopg://user:pass@db.internal:5432/brain"


def test_explicit_sqlalchemy_driver_is_preserved() -> None:
    value = "postgresql+psycopg://user:pass@localhost:5432/brain"
    assert sqlalchemy_database_url(value) == value
