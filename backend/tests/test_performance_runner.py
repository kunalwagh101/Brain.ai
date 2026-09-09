import asyncio
import os
import runpy
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "scripts/run-performance-benchmark.py"


def _runner_namespace() -> dict[str, object]:
    return runpy.run_path(str(RUNNER_PATH), run_name="brain_performance_runner")


def test_benchmark_runner_has_valid_python_syntax() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    compile(source, str(RUNNER_PATH), "exec")


def test_missing_placeholder_fails_without_echoing_secret_value(monkeypatch) -> None:
    namespace = _runner_namespace()
    expand = namespace["_expand"]
    error_type = namespace["BenchmarkConfigurationError"]
    monkeypatch.delenv("BRAIN_PERF_MISSING_VALUE", raising=False)

    with pytest.raises(error_type) as exc_info:
        expand("${BRAIN_PERF_MISSING_VALUE}")

    assert "BRAIN_PERF_MISSING_VALUE" in str(exc_info.value)


def test_bearer_token_is_used_only_as_authorization_header(monkeypatch) -> None:
    namespace = _runner_namespace()
    headers = namespace["_headers"]
    monkeypatch.setenv("BRAIN_PERF_TEST_TOKEN", "benchmark-secret-value")

    result = headers({"auth_env": "BRAIN_PERF_TEST_TOKEN"})

    assert result["Authorization"] == "Bearer benchmark-secret-value"
    assert result["Accept"] == "application/json"


def test_cost_delta_marks_unknown_cost_incomplete() -> None:
    namespace = _runner_namespace()
    cost_delta = namespace["_cost_delta"]

    result = cost_delta(
        {
            "total_cost_nano_usd": 1_000,
            "known_cost_requests": 5,
            "unknown_cost_requests": 0,
        },
        {
            "total_cost_nano_usd": 3_000,
            "known_cost_requests": 7,
            "unknown_cost_requests": 1,
        },
    )

    assert result == {
        "total_cost_nano_usd": 2_000,
        "known_cost_requests": 2,
        "unknown_cost_requests": 1,
        "exact_cost_complete": False,
    }


def test_http_runner_uses_aggregate_status_without_response_body() -> None:
    namespace = _runner_namespace()
    single_request = namespace["_single_request"]
    seen_request_bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_request_bodies.append(request.content)
        return httpx.Response(200, json={"sensitive": "never-returned-by-runner"})

    async def exercise() -> tuple[float, bool, int | None, str | None]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://benchmark.example",
            transport=transport,
        ) as client:
            return await single_request(
                client,
                asyncio.Semaphore(1),
                method="POST",
                path="/probe",
                headers={"Authorization": "Bearer hidden"},
                query=None,
                body={"prompt": "test-only"},
                expected_statuses={200},
                timeout_seconds=1,
            )

    elapsed_ms, succeeded, status_code, error_code = asyncio.run(exercise())
    assert elapsed_ms >= 0
    assert succeeded is True
    assert status_code == 200
    assert error_code is None
    assert seen_request_bodies


def test_runner_source_does_not_emit_response_or_authorization_content() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "response.text" not in source
    assert "response.content" not in source
    assert '"Authorization": headers' not in source
    assert "output_text" not in source
    assert os.path.basename(str(RUNNER_PATH)) == "run-performance-benchmark.py"
