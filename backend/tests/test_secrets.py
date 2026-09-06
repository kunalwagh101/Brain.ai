import json
import uuid

import pytest
from botocore.exceptions import ClientError

from app.secrets import AWSSecretsManagerStore, SecretStoreError


class FakeAWSSecretsClient:
    def __init__(self) -> None:
        self.created: dict[str, object] | None = None
        self.deleted: dict[str, object] | None = None
        self.loaded_secret = '{"access_token":"secret"}'
        self.fail_create = False

    def create_secret(self, **kwargs):
        if self.fail_create:
            raise ClientError(
                {"Error": {"Code": "InternalServiceError", "Message": "boom"}},
                "CreateSecret",
            )
        self.created = kwargs
        return {"ARN": "arn:aws:secretsmanager:us-east-1:123:secret:brain-test"}

    def get_secret_value(self, **kwargs):
        return {"SecretString": self.loaded_secret}

    def delete_secret(self, **kwargs):
        self.deleted = kwargs
        return {"ARN": kwargs["SecretId"]}


def test_aws_secret_store_serializes_only_secret_payload() -> None:
    client = FakeAWSSecretsClient()
    store = AWSSecretsManagerStore(client, prefix="brain", environment="test")
    organization_id = uuid.uuid4()
    connection_id = uuid.uuid4()

    reference = store.store_connection_secret(
        organization_id=organization_id,
        connection_id=connection_id,
        provider="slack",
        credentials={"refresh_token": "r1", "access_token": "a1"},
    )

    assert reference.startswith("arn:aws:secretsmanager:")
    assert client.created is not None
    assert client.created["Name"].endswith(f"/{organization_id}/slack/{connection_id}")
    assert json.loads(client.created["SecretString"]) == {
        "access_token": "a1",
        "refresh_token": "r1",
    }


def test_aws_secret_store_loads_valid_json_object() -> None:
    store = AWSSecretsManagerStore(FakeAWSSecretsClient(), prefix="brain", environment="test")

    assert store.load_connection_secret("arn:one") == {"access_token": "secret"}


def test_aws_secret_store_schedules_recoverable_deletion() -> None:
    client = FakeAWSSecretsClient()
    store = AWSSecretsManagerStore(client, prefix="brain", environment="test")

    store.schedule_delete("arn:one")

    assert client.deleted == {"SecretId": "arn:one", "RecoveryWindowInDays": 7}


def test_aws_secret_store_maps_provider_failure_without_leaking_secret() -> None:
    client = FakeAWSSecretsClient()
    client.fail_create = True
    store = AWSSecretsManagerStore(client, prefix="brain", environment="test")

    with pytest.raises(SecretStoreError) as exc:
        store.store_connection_secret(
            organization_id=uuid.uuid4(),
            connection_id=uuid.uuid4(),
            provider="slack",
            credentials={"access_token": "must-not-leak"},
        )

    assert "must-not-leak" not in str(exc.value)
