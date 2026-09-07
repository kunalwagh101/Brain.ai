import json
import uuid
from functools import lru_cache
from typing import Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings


class SecretStoreError(RuntimeError):
    pass


class SecretStore(Protocol):
    def store_connection_secret(
        self,
        *,
        organization_id: uuid.UUID,
        connection_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str: ...

    def store_ai_provider_secret(
        self,
        *,
        organization_id: uuid.UUID,
        provider_configuration_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str: ...

    def load_connection_secret(self, reference: str) -> dict[str, str]: ...

    def schedule_delete(self, reference: str) -> None: ...


class AWSSecretsManagerStore:
    def __init__(self, client, *, prefix: str, environment: str) -> None:
        self._client = client
        self._prefix = prefix.strip("/")
        self._environment = environment

    def _name(
        self,
        *,
        organization_id: uuid.UUID,
        connection_id: uuid.UUID,
        provider: str,
    ) -> str:
        return (
            f"{self._prefix}/{self._environment}/integrations/"
            f"{organization_id}/{provider}/{connection_id}"
        )

    def _ai_provider_name(
        self,
        *,
        organization_id: uuid.UUID,
        provider_configuration_id: uuid.UUID,
        provider: str,
    ) -> str:
        return (
            f"{self._prefix}/{self._environment}/ai-providers/"
            f"{organization_id}/{provider}/{provider_configuration_id}"
        )

    def _create_secret(
        self,
        *,
        name: str,
        description: str,
        credentials: dict[str, str],
    ) -> str:
        try:
            response = self._client.create_secret(
                Name=name,
                Description=description,
                SecretString=json.dumps(credentials, separators=(",", ":"), sort_keys=True),
            )
        except (BotoCoreError, ClientError) as exc:
            raise SecretStoreError("Credential storage failed") from exc

        reference = response.get("ARN")
        if not isinstance(reference, str) or not reference:
            raise SecretStoreError("Credential storage returned no secret reference")
        return reference

    def store_connection_secret(
        self,
        *,
        organization_id: uuid.UUID,
        connection_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str:
        return self._create_secret(
            name=self._name(
                organization_id=organization_id,
                connection_id=connection_id,
                provider=provider,
            ),
            description="Brain external integration credential",
            credentials=credentials,
        )

    def store_ai_provider_secret(
        self,
        *,
        organization_id: uuid.UUID,
        provider_configuration_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str:
        return self._create_secret(
            name=self._ai_provider_name(
                organization_id=organization_id,
                provider_configuration_id=provider_configuration_id,
                provider=provider,
            ),
            description="Brain AI provider credential",
            credentials=credentials,
        )

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        try:
            response = self._client.get_secret_value(SecretId=reference)
        except (BotoCoreError, ClientError) as exc:
            raise SecretStoreError("Credential retrieval failed") from exc

        raw = response.get("SecretString")
        if not isinstance(raw, str):
            raise SecretStoreError("Credential secret is not a string payload")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SecretStoreError("Credential secret is not valid JSON") from exc
        if not isinstance(data, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in data.items()
        ):
            raise SecretStoreError("Credential secret has an invalid shape")
        return data

    def schedule_delete(self, reference: str) -> None:
        try:
            self._client.delete_secret(SecretId=reference, RecoveryWindowInDays=7)
        except (BotoCoreError, ClientError) as exc:
            raise SecretStoreError("Credential deletion failed") from exc


@lru_cache
def get_secret_store() -> SecretStore:
    settings = get_settings()
    client = boto3.client("secretsmanager", region_name=settings.aws_region)
    return AWSSecretsManagerStore(
        client,
        prefix=settings.secrets_prefix,
        environment=settings.environment,
    )
