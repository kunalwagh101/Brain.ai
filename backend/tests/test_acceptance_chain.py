import sys

import run_acceptance_chain as acceptance


EXPECTED_STORY_ORDER = [
    "S-05.01.01",
    "S-02.04.01",
    "S-05.02.01",
    "S-04.02.01",
    "S-07.01.01",
    "S-07.02.01",
]


def test_acceptance_chain_preserves_dependency_order() -> None:
    assert [stage.story for stage in acceptance.STAGES] == EXPECTED_STORY_ORDER
    assert acceptance.STAGES[0].name == "Permission-Aware Retrieval"
    assert acceptance.STAGES[-1].name == "Executive Overview"


def test_postgres_mode_requires_explicit_test_database_url(monkeypatch) -> None:
    monkeypatch.delenv("BRAIN_TEST_DATABASE_URL", raising=False)
    assert acceptance._database_mode() == "portable"

    monkeypatch.setenv(
        "BRAIN_TEST_DATABASE_URL",
        "postgresql://brain:brain@example.invalid:5432/brain",
    )
    assert acceptance._database_mode() == "postgresql"


def test_require_postgres_fails_closed_without_database_url(monkeypatch) -> None:
    monkeypatch.delenv("BRAIN_TEST_DATABASE_URL", raising=False)
    monkeypatch.setattr(sys, "argv", ["run_acceptance_chain.py", "--require-postgres"])

    assert acceptance.main() == 2
