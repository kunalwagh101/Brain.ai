import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db, sqlalchemy_database_url
from app.main import app
from app.models import Base


def _postgres_test_session(database_url: str):
    normalized_url = sqlalchemy_database_url(database_url)
    schema = f"brain_test_{uuid.uuid4().hex}"
    admin_engine = create_engine(normalized_url, pool_pre_ping=True)
    if admin_engine.dialect.name != "postgresql":
        admin_engine.dispose()
        raise RuntimeError("BRAIN_TEST_DATABASE_URL must point to PostgreSQL")

    schema_created = False
    try:
        with admin_engine.begin() as connection:
            vector_installed = connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
            if not vector_installed:
                raise RuntimeError(
                    "PostgreSQL acceptance database must have the vector extension installed"
                )
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            schema_created = True

        engine = create_engine(
            normalized_url,
            connect_args={"options": f"-csearch_path={schema},public"},
            pool_pre_ping=True,
        )
        try:
            with engine.connect() as connection:
                current_schema = connection.scalar(text("SELECT current_schema()"))
                if current_schema != schema:
                    raise RuntimeError("PostgreSQL test schema isolation was not activated")
            Base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            with factory() as session:
                yield session
        finally:
            engine.dispose()
    finally:
        if schema_created:
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def db_session() -> Session:
    database_url = os.getenv("BRAIN_TEST_DATABASE_URL", "").strip()
    if database_url:
        yield from _postgres_test_session(database_url)
        return

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
