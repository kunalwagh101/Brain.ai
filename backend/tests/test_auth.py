from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt import InvalidIssuerError, InvalidTokenError

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
        "client_id": "client_test",
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "urn:brain:user_email": "person@example.com",
        # Deliberately different from the subject email: Brain must not use the
        # actor/delegation claim to identify the signed-in subject.
        "act": {"sub": "impersonator@example.com"},
        "org_id": "org_workos_123",
        "role": "member",
        "permissions": ["project:read"],
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def _configure(monkeypatch, public_key, *, audience: str | None = None) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "workos_client_id", "client_test")
    monkeypatch.setattr(settings, "workos_audience", audience)
    monkeypatch.setattr(
        auth,
        "get_jwks_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _: SimpleNamespace(key=public_key)
        ),
    )


def test_verify_access_token_accepts_current_authkit_client_id_contract(
    monkeypatch, rsa_keys
) -> None:
    private_key, public_key = rsa_keys
    _configure(monkeypatch, public_key)

    principal = auth.verify_access_token(_token(private_key))

    assert principal.subject == "user_workos_123"
    assert principal.email == "person@example.com"
    assert principal.provider_organization_id == "org_workos_123"
    assert principal.permissions == ("project:read",)


def test_verify_access_token_does_not_use_actor_claim_as_subject_email(
    monkeypatch, rsa_keys
) -> None:
    private_key, public_key = rsa_keys
    _configure(monkeypatch, public_key)

    principal = auth.verify_access_token(_token(private_key))
    assert principal.email != "impersonator@example.com"


def test_verify_access_token_requires_brain_email_template_claim(
    monkeypatch, rsa_keys
) -> None:
    private_key, public_key = rsa_keys
    _configure(monkeypatch, public_key)

    with pytest.raises(InvalidTokenError):
        auth.verify_access_token(_token(private_key, **{"urn:brain:user_email": None}))


def test_verify_access_token_rejects_wrong_workos_client_id(monkeypatch, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    _configure(monkeypatch, public_key)

    with pytest.raises(InvalidTokenError):
        auth.verify_access_token(_token(private_key, client_id="client_attacker"))


def test_verify_access_token_accepts_legacy_audience_binding_without_client_id(
    monkeypatch, rsa_keys
) -> None:
    private_key, public_key = rsa_keys
    _configure(monkeypatch, public_key)

    principal = auth.verify_access_token(
        _token(private_key, client_id=None, aud="client_test")
    )
    assert principal.subject == "user_workos_123"


def test_verify_access_token_enforces_explicit_custom_audience(monkeypatch, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    _configure(monkeypatch, public_key, audience="brain-api")

    principal = auth.verify_access_token(_token(private_key, aud="brain-api"))
    assert principal.subject == "user_workos_123"

    with pytest.raises(InvalidTokenError):
        auth.verify_access_token(_token(private_key, aud="other-api"))


def test_verify_access_token_rejects_wrong_issuer(monkeypatch, rsa_keys) -> None:
    private_key, public_key = rsa_keys
    _configure(monkeypatch, public_key)

    with pytest.raises(InvalidIssuerError):
        auth.verify_access_token(_token(private_key, iss="https://attacker.example"))


def test_protected_route_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
