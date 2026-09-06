import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import jwt

from app.config import Settings, get_settings
from app.secrets import SecretStore, SecretStoreError, get_secret_store

GITHUB_API_VERSION = "2026-03-10"
GITHUB_STATE_TTL_SECONDS = 600
GITHUB_SELECTION_TTL_SECONDS = 600


class GitHubConfigurationError(RuntimeError):
    """Raised when the GitHub App is not fully configured."""


class GitHubAPIError(RuntimeError):
    """Raised when GitHub rejects an authenticated API request."""

    def __init__(self, code: str, status_code: int = 502) -> None:
        self.code = (code or "github_api_error")[:128]
        self.status_code = status_code
        super().__init__(self.code)


class GitHubTransportError(RuntimeError):
    """Raised when GitHub cannot be reached or returns invalid data."""


@dataclass(frozen=True, slots=True)
class GitHubAppCredentials:
    private_key_pem: str
    client_secret: str
    webhook_secret: str


def require_github_configuration(settings: Settings) -> None:
    required = (
        settings.github_app_id,
        settings.github_app_slug,
        settings.github_client_id,
        settings.github_callback_url,
        settings.github_app_secret_ref,
    )
    if not all(required):
        raise GitHubConfigurationError("GitHub App is not configured")


def load_github_credentials(settings: Settings, store: SecretStore) -> GitHubAppCredentials:
    require_github_configuration(settings)
    assert settings.github_app_secret_ref is not None
    try:
        values = store.load_connection_secret(settings.github_app_secret_ref)
    except SecretStoreError as exc:
        raise GitHubConfigurationError("GitHub App credentials are unavailable") from exc

    private_key = values.get("private_key_pem")
    client_secret = values.get("client_secret")
    webhook_secret = values.get("webhook_secret")
    if not private_key or not client_secret or not webhook_secret:
        raise GitHubConfigurationError("GitHub App credential secret is incomplete")
    return GitHubAppCredentials(
        private_key_pem=private_key.replace("\\n", "\n"),
        client_secret=client_secret,
        webhook_secret=webhook_secret,
    )


def verify_github_webhook(raw_body: bytes, *, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def _signed_payload(
    payload: dict[str, object],
    *,
    purpose: str,
    secret: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    body = dict(payload)
    body["purpose"] = purpose
    body["expires_at"] = int(issued.timestamp()) + ttl_seconds
    encoded = _b64encode(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64encode(hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def _verify_signed_payload(
    token: str,
    *,
    purpose: str,
    secret: str,
    now: datetime | None = None,
) -> dict[str, object]:
    try:
        encoded, supplied_signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid GitHub state") from exc
    expected_signature = _b64encode(
        hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected_signature, supplied_signature):
        raise ValueError("Invalid GitHub state")
    try:
        payload = json.loads(_b64decode(encoded))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid GitHub state") from exc
    if not isinstance(payload, dict) or payload.get("purpose") != purpose:
        raise ValueError("Invalid GitHub state")
    expires_at = payload.get("expires_at")
    if not isinstance(expires_at, int):
        raise ValueError("Invalid GitHub state")
    current = int((now or datetime.now(UTC)).timestamp())
    if expires_at < current:
        raise ValueError("Expired GitHub state")
    return payload


def create_install_state(
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    secret: str,
    now: datetime | None = None,
) -> str:
    return _signed_payload(
        {
            "organization_id": str(organization_id),
            "user_id": str(user_id),
        },
        purpose="github_install",
        secret=secret,
        ttl_seconds=GITHUB_STATE_TTL_SECONDS,
        now=now,
    )


def verify_install_state(
    token: str,
    *,
    secret: str,
    now: datetime | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    payload = _verify_signed_payload(
        token,
        purpose="github_install",
        secret=secret,
        now=now,
    )
    try:
        return uuid.UUID(str(payload["organization_id"])), uuid.UUID(str(payload["user_id"]))
    except (KeyError, ValueError) as exc:
        raise ValueError("Invalid GitHub state") from exc


def create_selection_token(
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    installation: dict[str, object],
    secret: str,
) -> str:
    account = installation.get("account")
    if not isinstance(account, dict):
        raise ValueError("GitHub installation has no account")
    installation_id = installation.get("id")
    account_id = account.get("id")
    account_login = account.get("login")
    if not isinstance(installation_id, int) or not isinstance(account_id, int):
        raise ValueError("GitHub installation identifiers are invalid")
    if not isinstance(account_login, str) or not account_login:
        raise ValueError("GitHub installation account is invalid")
    return _signed_payload(
        {
            "organization_id": str(organization_id),
            "user_id": str(user_id),
            "installation_id": installation_id,
            "account_id": account_id,
            "account_login": account_login,
            "target_type": str(installation.get("target_type") or "Unknown"),
            "repository_selection": str(installation.get("repository_selection") or "selected"),
        },
        purpose="github_installation_selection",
        secret=secret,
        ttl_seconds=GITHUB_SELECTION_TTL_SECONDS,
    )


def verify_selection_token(token: str, *, secret: str) -> dict[str, object]:
    return _verify_signed_payload(
        token,
        purpose="github_installation_selection",
        secret=secret,
    )


class GitHubAPIClient:
    def __init__(self, settings: Settings, store: SecretStore) -> None:
        self._settings = settings
        self._store = store

    def installation_url(self, state: str) -> str:
        require_github_configuration(self._settings)
        assert self._settings.github_app_slug is not None
        return (
            f"https://github.com/apps/{self._settings.github_app_slug}/installations/new?"
            f"{urlencode({'state': state})}"
        )

    def exchange_user_code(self, code: str) -> str:
        credentials = load_github_credentials(self._settings, self._store)
        assert self._settings.github_client_id is not None
        assert self._settings.github_callback_url is not None
        body = urlencode(
            {
                "client_id": self._settings.github_client_id,
                "client_secret": credentials.client_secret,
                "code": code,
                "redirect_uri": self._settings.github_callback_url,
            }
        ).encode()
        request = Request(
            "https://github.com/login/oauth/access_token",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        payload = self._send(request)
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            error = payload.get("error")
            raise GitHubAPIError(str(error or "oauth_token_missing"), 400)
        return token

    def list_user_installations(self, user_token: str) -> list[dict[str, object]]:
        payload = self._api_get(
            "https://api.github.com/user/installations?per_page=100",
            user_token,
        )
        installations = payload.get("installations")
        if not isinstance(installations, list):
            raise GitHubTransportError("GitHub returned invalid installation data")
        return [item for item in installations if isinstance(item, dict)]

    def get_app_installation(self, installation_id: int) -> dict[str, object]:
        token = self._app_jwt()
        return self._api_get(
            f"https://api.github.com/app/installations/{installation_id}",
            token,
        )

    def create_installation_token(self, installation_id: int) -> str:
        token = self._app_jwt()
        request = Request(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            data=b"{}",
            headers=self._headers(token, content_type="application/json"),
            method="POST",
        )
        payload = self._send(request)
        installation_token = payload.get("token")
        if not isinstance(installation_token, str) or not installation_token:
            raise GitHubTransportError("GitHub returned no installation token")
        return installation_token

    def list_installation_repositories(self, token: str) -> list[dict[str, object]]:
        repositories: list[dict[str, object]] = []
        for page in range(1, 101):
            payload = self._api_get(
                "https://api.github.com/installation/repositories?"
                f"per_page=100&page={page}",
                token,
            )
            items = payload.get("repositories")
            if not isinstance(items, list):
                raise GitHubTransportError("GitHub returned invalid repository data")
            page_items = [item for item in items if isinstance(item, dict)]
            repositories.extend(page_items)
            if len(page_items) < 100:
                repositories.sort(key=lambda item: int(item.get("id") or 0))
                return repositories
        raise GitHubAPIError("repository_pagination_limit")

    def list_resource_page(
        self,
        token: str,
        full_name: str,
        resource: str,
        *,
        page: int,
        per_page: int,
    ) -> list[dict[str, object]]:
        endpoints = {
            "commits": "commits",
            "pull_requests": "pulls?state=all",
            "issues": "issues?state=all",
            "deployments": "deployments",
        }
        endpoint = endpoints.get(resource)
        if endpoint is None:
            raise ValueError("Unsupported GitHub backfill resource")
        separator = "&" if "?" in endpoint else "?"
        url = (
            f"https://api.github.com/repos/{full_name}/{endpoint}{separator}"
            f"per_page={per_page}&page={page}"
        )
        payload = self._api_get_list(url, token)
        if resource == "issues":
            payload = [item for item in payload if "pull_request" not in item]
        return payload

    def _app_jwt(self) -> str:
        credentials = load_github_credentials(self._settings, self._store)
        assert self._settings.github_app_id is not None
        now = int(time.time())
        encoded = jwt.encode(
            {
                "iat": now - 60,
                "exp": now + 540,
                "iss": self._settings.github_app_id,
            },
            credentials.private_key_pem,
            algorithm="RS256",
        )
        return str(encoded)

    @staticmethod
    def _headers(token: str, *, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "Brain-GitHub-Connector",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _api_get(self, url: str, token: str) -> dict[str, object]:
        request = Request(url, headers=self._headers(token), method="GET")
        payload = self._send(request)
        if not isinstance(payload, dict):
            raise GitHubTransportError("GitHub returned an invalid object")
        return payload

    def _api_get_list(self, url: str, token: str) -> list[dict[str, object]]:
        request = Request(url, headers=self._headers(token), method="GET")
        payload = self._send(request)
        if not isinstance(payload, list):
            raise GitHubTransportError("GitHub returned an invalid list")
        return [item for item in payload if isinstance(item, dict)]

    @staticmethod
    def _send(request: Request) -> object:
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed GitHub URLs only
                raw = response.read()
        except HTTPError as exc:
            status = int(exc.code)
            raise GitHubAPIError(f"http_{status}", status) from exc
        except (URLError, TimeoutError) as exc:
            raise GitHubTransportError("GitHub transport request failed") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GitHubTransportError("GitHub returned invalid JSON") from exc


def get_github_api_client() -> GitHubAPIClient:
    return GitHubAPIClient(get_settings(), get_secret_store())
