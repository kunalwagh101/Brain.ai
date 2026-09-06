import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Settings, get_settings

SLACK_OAUTH_SCOPES = (
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
)
OAUTH_STATE_TTL_SECONDS = 600


class SlackConfigurationError(RuntimeError):
    pass


class SlackAPIError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code[:128] or "unknown_error"
        super().__init__(f"Slack API request failed: {self.code}")


class SlackTransportError(RuntimeError):
    pass


def require_slack_oauth_configuration(settings: Settings) -> None:
    if not settings.slack_client_id or not settings.slack_client_secret or not settings.slack_redirect_uri:
        raise SlackConfigurationError("Slack OAuth is not configured")


def require_slack_signing_secret(settings: Settings) -> str:
    if not settings.slack_signing_secret:
        raise SlackConfigurationError("Slack request signing is not configured")
    return settings.slack_signing_secret


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def create_oauth_state(
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    secret: str,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "organization_id": str(organization_id),
        "user_id": str(user_id),
        "expires_at": int(issued_at.timestamp()) + OAUTH_STATE_TTL_SECONDS,
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    signature = _b64encode(hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest())
    return f"{encoded}.{signature}"


def verify_oauth_state(
    state: str,
    *,
    secret: str,
    now: datetime | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        encoded, supplied_signature = state.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid Slack OAuth state") from exc

    expected_signature = _b64encode(
        hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(expected_signature, supplied_signature):
        raise ValueError("Invalid Slack OAuth state")

    try:
        payload = json.loads(_b64decode(encoded))
        expires_at = int(payload["expires_at"])
        organization_id = uuid.UUID(payload["organization_id"])
        user_id = uuid.UUID(payload["user_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid Slack OAuth state") from exc

    current = int((now or datetime.now(UTC)).timestamp())
    if expires_at < current:
        raise ValueError("Expired Slack OAuth state")
    return organization_id, user_id


def verify_slack_request(
    raw_body: bytes,
    *,
    timestamp: str,
    signature: str,
    signing_secret: str,
    now_epoch: float | None = None,
) -> bool:
    try:
        request_timestamp = int(timestamp)
    except (TypeError, ValueError):
        return False

    current = now_epoch if now_epoch is not None else time.time()
    if abs(current - request_timestamp) > 300:
        return False

    basestring = b"v0:" + timestamp.encode() + b":" + raw_body
    expected = "v0=" + hmac.new(
        signing_secret.encode(), basestring, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


class SlackAPIClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_authorization_url(self, state: str) -> str:
        require_slack_oauth_configuration(self._settings)
        query = urlencode(
            {
                "client_id": self._settings.slack_client_id,
                "scope": ",".join(SLACK_OAUTH_SCOPES),
                "redirect_uri": self._settings.slack_redirect_uri,
                "state": state,
            }
        )
        return f"https://slack.com/oauth/v2/authorize?{query}"

    def exchange_code(self, code: str) -> dict[str, object]:
        require_slack_oauth_configuration(self._settings)
        body = urlencode(
            {
                "client_id": self._settings.slack_client_id,
                "client_secret": self._settings.slack_client_secret,
                "code": code,
                "redirect_uri": self._settings.slack_redirect_uri,
            }
        ).encode()
        request = Request(
            "https://slack.com/api/oauth.v2.access",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        return self._send(request)

    def list_channels(self, token: str, *, cursor: str | None = None) -> dict[str, object]:
        params: dict[str, object] = {
            "types": "public_channel,private_channel",
            "exclude_archived": "true",
            "limit": 200,
        }
        if cursor:
            params["cursor"] = cursor
        return self._api_get("conversations.list", token, params)

    def conversation_info(self, token: str, channel_id: str) -> dict[str, object]:
        return self._api_get("conversations.info", token, {"channel": channel_id})

    def conversation_members(self, token: str, channel_id: str) -> list[str]:
        members: list[str] = []
        cursor: str | None = None
        for _ in range(100):
            params: dict[str, object] = {"channel": channel_id, "limit": 200}
            if cursor:
                params["cursor"] = cursor
            payload = self._api_get("conversations.members", token, params)
            page = payload.get("members")
            if not isinstance(page, list) or not all(isinstance(item, str) for item in page):
                raise SlackAPIError("invalid_members_response")
            members.extend(page)
            cursor = self._next_cursor(payload)
            if not cursor:
                return list(dict.fromkeys(members))
        raise SlackAPIError("members_pagination_limit")

    def history(
        self,
        token: str,
        channel_id: str,
        *,
        cursor: str | None,
        limit: int,
    ) -> dict[str, object]:
        params: dict[str, object] = {"channel": channel_id, "limit": min(max(limit, 1), 15)}
        if cursor:
            params["cursor"] = cursor
        return self._api_get("conversations.history", token, params)

    @staticmethod
    def _next_cursor(payload: dict[str, object]) -> str | None:
        metadata = payload.get("response_metadata")
        if not isinstance(metadata, dict):
            return None
        cursor = metadata.get("next_cursor")
        return cursor if isinstance(cursor, str) and cursor else None

    def _api_get(
        self,
        method: str,
        token: str,
        params: dict[str, object],
    ) -> dict[str, object]:
        url = f"https://slack.com/api/{method}?{urlencode(params)}"
        request = Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
        return self._send(request)

    @staticmethod
    def _send(request: Request) -> dict[str, object]:
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed Slack HTTPS URLs only
                raw = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise SlackTransportError("Slack transport request failed") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SlackTransportError("Slack returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise SlackTransportError("Slack returned an invalid response")
        if payload.get("ok") is not True:
            code = payload.get("error")
            raise SlackAPIError(code if isinstance(code, str) else "unknown_error")
        return payload


@lru_cache
def get_slack_api_client() -> SlackAPIClient:
    return SlackAPIClient(get_settings())
