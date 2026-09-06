from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import InvalidIssuerError

from app import auth
from app.config import get_settings


@pytest.fixture
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _token(private_key, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": "user_workos_123",
        "iss": "https://api.workos.com",
        "aud": "client_test",
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "act": {"sub": "person@example.com"},
        "org_id": "org_workos_123",
        "role": "member",
        "permissions": ["project:read"],
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def test_verify_access_token_validates_signature_and_claims(monkeypatch, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    settings = get_settings()
    monkeypatch.setattr(settings, "workos_client_id", "client_test")
    monkeypatch.setattr(settings, "workos_audience", "client_test")
    monkeypatch.setattr(
        auth,
        "get_jwks_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=public_key)
        ),
    )

    principal = auth.verify_access_token(_token(private_key))

    assert principal.subject == "user_workos_123"
    assert principal.email == "person@example.com"
    assert principal.provider_organization_id == "org_workos_123"
    assert principal.permissions == ("project:read",)


def test_verify_access_token_rejects_wrong_issuer(monkeypatch, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    settings = get_settings()
    monkeypatch.setattr(settings, "workos_client_id", "client_test")
    monkeypatch.setattr(settings, "workos_audience", "client_test")
    monkeypatch.setattr(
        auth,
        "get_jwks_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=public_key)
        ),
    )

    with pytest.raises(InvalidIssuerError):
        auth.verify_access_token(_token(private_key, iss="https://attacker.example"))


def test_protected_route_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
