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
    assert acceptance.STAGES[0].name == "Authentication + Permission-Aware Retrieval"
    assert acceptance.STAGES[-1].name == "Executive Overview"


def test_first_gate_includes_auth_permission_and_retrieval_contracts() -> None:
    first_gate_tests = set(acceptance.STAGES[0].tests)
    assert "tests/test_auth.py" in first_gate_tests
    assert "tests/test_permissions.py" in first_gate_tests
    assert "tests/test_organizations.py" in first_gate_tests
    assert "tests/test_search.py" in first_gate_tests
    assert "tests/test_search_evaluation.py" in first_gate_tests
    assert "tests/test_search_contract.py" in first_gate_tests


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
