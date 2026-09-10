#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

PROVIDER_KEY = "openai"
PROVIDER_DISPLAY_NAME = "OpenAI"
PROVIDER_API_URL = "https://api.openai.com/v1/chat/completions"
ADAPTER_KIND = "openai_chat_completions"
MODEL_KEY = "gpt-5.6-terra"
MODEL_DISPLAY_NAME = "GPT-5.6 Terra"
MODEL_MAX_OUTPUT_TOKENS = 8_192
INPUT_NANO_USD_PER_TOKEN = 2_000
CACHED_INPUT_NANO_USD_PER_TOKEN = 200
OUTPUT_NANO_USD_PER_TOKEN = 12_000
RATE_SOURCE_LABEL = "OpenAI GPT-5.6 Terra pricing reviewed 2026-09-10"


class BootstrapError(RuntimeError):
    pass


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise BootstrapError(f"{name} is required")
    return value


def _validate_base_url(value: str, *, allow_http_localhost: bool) -> str:
    parsed = urlparse(value)
    if parsed.scheme == "https" and parsed.netloc:
        return value.rstrip("/")
    if (
        allow_http_localhost
        and parsed.scheme == "http"
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        return value.rstrip("/")
    raise BootstrapError(
        "Brain base URL must use HTTPS; HTTP is allowed only for explicit localhost use"
    )


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        raise BootstrapError(
            f"Brain returned non-JSON response for {response.request.method} "
            f"{response.request.url.path}: HTTP {response.status_code}"
        ) from exc


def _request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    expected: set[int],
    json_body: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
) -> Any:
    response = client.request(method, path, json=json_body, params=params)
    payload = _json(response) if response.content else None
    if response.status_code not in expected:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        raise BootstrapError(
            f"Brain request failed: {method} {path} -> HTTP {response.status_code}; "
            f"detail={detail!r}"
        )
    return payload


def _list(client: httpx.Client, path: str) -> list[dict[str, Any]]:
    payload = _request(client, "GET", path, expected={200})
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise BootstrapError(f"Expected list response from {path}")
    return payload


def _ensure_provider(
    client: httpx.Client,
    *,
    organization_id: str,
    openai_api_key: str,
) -> dict[str, Any]:
    path = f"/api/v1/organizations/{organization_id}/ai/providers"
    providers = _list(client, path)
    matching = [row for row in providers if row.get("provider_key") == PROVIDER_KEY]
    if len(matching) > 1:
        raise BootstrapError("Multiple OpenAI provider configurations exist unexpectedly")
    if matching:
        provider = matching[0]
        status = provider.get("status")
        if status == "disabled":
            provider = _request(
                client,
                "POST",
                f"{path}/{provider['id']}/status",
                expected={200},
                json_body={"enabled": True},
            )
        elif status != "enabled":
            raise BootstrapError(
                f"Existing OpenAI provider is in non-reenableable state: {status!r}"
            )
        if provider.get("api_url") != PROVIDER_API_URL:
            raise BootstrapError(
                "Existing OpenAI provider API URL differs from the approved Chat Completions URL; "
                "review it instead of silently replacing production configuration"
            )
        if provider.get("adapter_kind") != ADAPTER_KIND:
            raise BootstrapError(
                "Existing OpenAI provider adapter differs from the approved adapter contract"
            )
        return provider

    payload = _request(
        client,
        "POST",
        path,
        expected={201},
        json_body={
            "provider_key": PROVIDER_KEY,
            "display_name": PROVIDER_DISPLAY_NAME,
            "adapter_kind": ADAPTER_KIND,
            "api_url": PROVIDER_API_URL,
            "credentials": {"api_key": openai_api_key},
        },
    )
    if not isinstance(payload, dict):
        raise BootstrapError("Provider creation returned an invalid contract")
    return payload


def _ensure_model(
    client: httpx.Client,
    *,
    organization_id: str,
    provider_id: str,
) -> dict[str, Any]:
    path = f"/api/v1/organizations/{organization_id}/ai/providers/{provider_id}/models"
    models = _list(client, path)
    matching = [row for row in models if row.get("model_key") == MODEL_KEY]
    if len(matching) > 1:
        raise BootstrapError("Multiple GPT-5.6 Terra model configurations exist unexpectedly")
    if matching:
        model = matching[0]
        if not model.get("enabled"):
            model = _request(
                client,
                "POST",
                f"/api/v1/organizations/{organization_id}/ai/models/{model['id']}/status",
                expected={200},
                json_body={"enabled": True},
            )
        configured_max = model.get("max_output_tokens")
        if configured_max not in {None, MODEL_MAX_OUTPUT_TOKENS}:
            raise BootstrapError(
                "Existing Terra model has a different output ceiling. Review it instead of "
                "silently changing an audited runtime configuration."
            )
        return model

    payload = _request(
        client,
        "POST",
        path,
        expected={201},
        json_body={
            "model_key": MODEL_KEY,
            "display_name": MODEL_DISPLAY_NAME,
            "enabled": True,
            "max_output_tokens": MODEL_MAX_OUTPUT_TOKENS,
        },
    )
    if not isinstance(payload, dict):
        raise BootstrapError("Model creation returned an invalid contract")
    return payload


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _ensure_rate_card(
    client: httpx.Client,
    *,
    organization_id: str,
    provider_id: str,
    model_id: str,
) -> dict[str, Any]:
    path = f"/api/v1/organizations/{organization_id}/ai/rate-cards"
    cards = _list(client, f"{path}?model_configuration_id={model_id}")
    now = datetime.now(UTC)
    current: list[dict[str, Any]] = []
    future: list[dict[str, Any]] = []
    for card in cards:
        start = _parse_timestamp(card.get("effective_from"))
        end = _parse_timestamp(card.get("effective_to"))
        if start is None:
            raise BootstrapError("Existing rate card has an invalid effective_from timestamp")
        if start <= now and (end is None or now < end):
            current.append(card)
        elif start > now:
            future.append(card)

    if len(current) > 1:
        raise BootstrapError("Multiple rate cards are effective now; refuse ambiguous cost accounting")
    if current:
        card = current[0]
        if (
            int(card.get("input_nano_usd_per_token", -1)) != INPUT_NANO_USD_PER_TOKEN
            or int(card.get("cached_input_nano_usd_per_token", -1))
            != CACHED_INPUT_NANO_USD_PER_TOKEN
            or int(card.get("output_nano_usd_per_token", -1)) != OUTPUT_NANO_USD_PER_TOKEN
        ):
            raise BootstrapError(
                "The currently effective Terra rate card does not match the reviewed 2026-09-10 "
                "price, including cached input. Create a deliberate historical rate transition "
                "instead of overwriting it."
            )
        return card

    if future:
        raise BootstrapError(
            "A future Terra rate card already exists. Refuse to create an indefinite card that "
            "would overlap it; review the planned pricing window first."
        )

    effective_from = now - timedelta(minutes=5)
    payload = _request(
        client,
        "POST",
        path,
        expected={201},
        json_body={
            "provider_configuration_id": provider_id,
            "model_configuration_id": model_id,
            "input_nano_usd_per_token": INPUT_NANO_USD_PER_TOKEN,
            "cached_input_nano_usd_per_token": CACHED_INPUT_NANO_USD_PER_TOKEN,
            "output_nano_usd_per_token": OUTPUT_NANO_USD_PER_TOKEN,
            "source_label": RATE_SOURCE_LABEL,
            "effective_from": effective_from.isoformat(),
            "effective_to": None,
        },
    )
    if not isinstance(payload, dict):
        raise BootstrapError("Rate-card creation returned an invalid contract")
    return payload


def _required_int(payload: dict[str, Any], name: str) -> int:
    value = payload.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BootstrapError(f"Provider smoke returned invalid {name}")
    return value


def _compatibility_smoke(
    client: httpx.Client,
    *,
    organization_id: str,
    provider_id: str,
    model_id: str,
    rate_card_id: str,
) -> dict[str, Any]:
    payload = _request(
        client,
        "POST",
        f"/api/v1/organizations/{organization_id}/ai/invoke",
        expected={200},
        json_body={
            "provider_configuration_id": provider_id,
            "model_configuration_id": model_id,
            "input_text": "Return one short JSON object with key status and value ok.",
            "system_text": "This is a provider compatibility smoke test. Be concise.",
            "max_output_tokens": 64,
        },
    )
    if not isinstance(payload, dict) or not payload.get("request_id"):
        raise BootstrapError("Provider smoke returned an invalid AI invocation contract")

    request_id = str(payload["request_id"])
    cost = _request(
        client,
        "GET",
        f"/api/v1/organizations/{organization_id}/ai/requests/{request_id}/cost",
        expected={200},
    )
    if not isinstance(cost, dict):
        raise BootstrapError("Request-scoped cost endpoint returned an invalid contract")
    if str(cost.get("request_id")) != request_id:
        raise BootstrapError("Request-scoped cost endpoint returned the wrong request")
    if str(cost.get("rate_card_id")) != rate_card_id:
        raise BootstrapError("Smoke request was not priced by the reviewed Terra rate card")
    if cost.get("cost_status") != "calculated" or cost.get("unknown_reason") is not None:
        raise BootstrapError(
            "Smoke request did not produce exact cache-aware cost accounting"
        )

    input_tokens = _required_int(cost, "input_tokens")
    cached_input_tokens = _required_int(cost, "cached_input_tokens")
    output_tokens = _required_int(cost, "output_tokens")
    if cached_input_tokens > input_tokens:
        raise BootstrapError("Provider reported more cached tokens than total input tokens")

    expected_input_cost = (
        (input_tokens - cached_input_tokens) * INPUT_NANO_USD_PER_TOKEN
        + cached_input_tokens * CACHED_INPUT_NANO_USD_PER_TOKEN
    )
    expected_output_cost = output_tokens * OUTPUT_NANO_USD_PER_TOKEN
    expected_total_cost = expected_input_cost + expected_output_cost
    if cost.get("input_cost_nano_usd") != expected_input_cost:
        raise BootstrapError("Recorded input cost does not match provider token usage")
    if cost.get("output_cost_nano_usd") != expected_output_cost:
        raise BootstrapError("Recorded output cost does not match provider token usage")
    if cost.get("total_cost_nano_usd") != expected_total_cost:
        raise BootstrapError("Recorded total cost does not match the reviewed Terra rates")

    return {
        "request_id": request_id,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": payload.get("latency_ms"),
        "cost_nano_usd": expected_total_cost,
    }


def _run(args: argparse.Namespace) -> int:
    base_url = _validate_base_url(
        args.base_url,
        allow_http_localhost=args.allow_http_localhost,
    )
    token = _required_env("BRAIN_ADMIN_TOKEN")
    openai_api_key = _required_env("OPENAI_API_KEY")
    retention_mode = _required_env("BRAIN_OPENAI_RETENTION_MODE").lower()
    if retention_mode not in {"standard", "zdr"}:
        raise BootstrapError("BRAIN_OPENAI_RETENTION_MODE must be 'standard' or 'zdr'")
    if not args.confirm_customer_policy:
        raise BootstrapError(
            "Pass --confirm-customer-policy only after confirming the customer permits the selected "
            "OpenAI retention mode and API data sharing remains disabled"
        )

    with httpx.Client(
        base_url=base_url,
        headers=_headers(token),
        timeout=args.timeout_seconds,
        follow_redirects=False,
    ) as client:
        provider = _ensure_provider(
            client,
            organization_id=args.organization_id,
            openai_api_key=openai_api_key,
        )
        provider_id = str(provider["id"])
        model = _ensure_model(
            client,
            organization_id=args.organization_id,
            provider_id=provider_id,
        )
        model_id = str(model["id"])
        rate_card = _ensure_rate_card(
            client,
            organization_id=args.organization_id,
            provider_id=provider_id,
            model_id=model_id,
        )
        rate_card_id = str(rate_card["id"])
        smoke = _compatibility_smoke(
            client,
            organization_id=args.organization_id,
            provider_id=provider_id,
            model_id=model_id,
            rate_card_id=rate_card_id,
        )

    print("Ask Brain OpenAI staging bootstrap: PASS")
    print(f"provider_configuration_id={provider_id}")
    print(f"model_configuration_id={model_id}")
    print(f"rate_card_id={rate_card_id}")
    print(f"model={MODEL_KEY}")
    print(f"retention_mode_attested={retention_mode}")
    print(f"smoke_request_id={smoke['request_id']}")
    print(f"smoke_latency_ms={smoke['latency_ms']}")
    print(f"smoke_input_tokens={smoke['input_tokens']}")
    print(f"smoke_cached_input_tokens={smoke['cached_input_tokens']}")
    print(f"smoke_output_tokens={smoke['output_tokens']}")
    print(f"smoke_cost_nano_usd={smoke['cost_nano_usd']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Idempotently configure the approved OpenAI/Terra Ask Brain staging runtime, exact "
            "cache-aware rate card, and provider compatibility smoke"
        )
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    parser.add_argument("--confirm-customer-policy", action="store_true")
    parser.add_argument("--allow-http-localhost", action="store_true")
    args = parser.parse_args()
    if args.timeout_seconds <= 0 or args.timeout_seconds > 120:
        print("timeout_seconds must be >0 and <=120", file=sys.stderr)
        return 64
    try:
        return _run(args)
    except (BootstrapError, httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        print(f"Ask Brain staging bootstrap failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
