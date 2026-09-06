import json
import urllib.error
import urllib.request
from typing import Protocol

from app.config import get_settings
from app.secrets import SecretStoreError, get_secret_store


class EmbeddingError(RuntimeError):
    pass


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str], *, model: str) -> list[list[float]]: ...


class HTTPEmbeddingClient:
    """Small provider-neutral embedding adapter.

    Contract: POST JSON {"model": <model>, "input": [<text>, ...]} and return either
    {"data": [{"embedding": [...]}, ...]} or {"embeddings": [[...], ...]}.
    This keeps Brain independent of a specific vendor SDK.
    """

    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: float,
        api_key: str | None = None,
    ) -> None:
        self._url = url
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key

    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        if not texts:
            return []
        body = json.dumps({"model": model, "input": texts}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(self._url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                raw = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise EmbeddingError("embedding_service_unavailable") from exc

        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EmbeddingError("embedding_response_invalid_json") from exc
        vectors = _parse_vectors(payload)
        if len(vectors) != len(texts):
            raise EmbeddingError("embedding_response_count_mismatch")
        if vectors and any(len(vector) != len(vectors[0]) for vector in vectors):
            raise EmbeddingError("embedding_dimension_mismatch")
        return vectors


def _parse_vectors(payload: object) -> list[list[float]]:
    if not isinstance(payload, dict):
        raise EmbeddingError("embedding_response_invalid_shape")
    direct = payload.get("embeddings")
    if isinstance(direct, list):
        return [_coerce_vector(item) for item in direct]
    data = payload.get("data")
    if isinstance(data, list):
        vectors: list[list[float]] = []
        for item in data:
            if not isinstance(item, dict):
                raise EmbeddingError("embedding_response_invalid_shape")
            vectors.append(_coerce_vector(item.get("embedding")))
        return vectors
    raise EmbeddingError("embedding_response_missing_vectors")


def _coerce_vector(value: object) -> list[float]:
    if not isinstance(value, list) or not value:
        raise EmbeddingError("embedding_response_invalid_vector")
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise EmbeddingError("embedding_response_invalid_vector") from exc


def build_embedding_client() -> tuple[EmbeddingClient | None, str | None]:
    settings = get_settings()
    if not settings.embedding_api_url or not settings.embedding_model:
        return None, None

    api_key: str | None = None
    if settings.embedding_secret_ref:
        try:
            secret = get_secret_store().load_connection_secret(settings.embedding_secret_ref)
        except SecretStoreError as exc:
            raise EmbeddingError("embedding_secret_unavailable") from exc
        api_key = secret.get("api_key")
        if not api_key:
            raise EmbeddingError("embedding_secret_missing_api_key")

    return (
        HTTPEmbeddingClient(
            url=settings.embedding_api_url,
            timeout_seconds=settings.embedding_timeout_seconds,
            api_key=api_key,
        ),
        settings.embedding_model,
    )
