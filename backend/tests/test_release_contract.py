import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_release_shell_scripts_have_valid_bash_syntax() -> None:
    for relative_path in (
        "scripts/postgres-backup.sh",
        "scripts/postgres-restore.sh",
    ):
        result = subprocess.run(
            ["bash", "-n", str(REPO_ROOT / relative_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr


def test_restore_refuses_without_explicit_destructive_confirmation() -> None:
    env = os.environ.copy()
    env.update(
        {
            "PGHOST": "127.0.0.1",
            "PGDATABASE": "disposable",
            "PGUSER": "brain",
            "RESTORE_FILE": "/tmp/does-not-need-to-exist.dump",
        }
    )
    env.pop("BRAIN_RESTORE_CONFIRM", None)
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/postgres-restore.sh")],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 64
    assert "Restore refused" in result.stderr


def test_release_gate_keeps_required_safety_exercises() -> None:
    workflow = (REPO_ROOT / ".github/workflows/release-gate.yml").read_text(
        encoding="utf-8"
    )
    required_fragments = (
        "ruff check app tests migrations",
        "pytest",
        "python scripts/verify_board.py",
        "alembic downgrade base",
        "alembic upgrade head",
        "scripts/postgres-backup.sh",
        "scripts/postgres-restore.sh",
        "BRAIN_RESTORE_CONFIRM=I_UNDERSTAND_THIS_REPLACES_DATABASE",
        "docker build --pull",
        "/health/ready",
        "release-manifest.json",
    )
    for fragment in required_fragments:
        assert fragment in workflow


def test_production_image_runs_as_non_root_user() -> None:
    dockerfile = (REPO_ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
    assert "USER brain" in dockerfile
    assert "CMD [\"uvicorn\"" in dockerfile


def test_docker_build_context_excludes_local_secret_and_backup_material() -> None:
    dockerignore = (REPO_ROOT / "backend/.dockerignore").read_text(encoding="utf-8")
    required_patterns = (".env", ".venv/", "*.dump", "*.dump.sha256", "*.sql")
    for pattern in required_patterns:
        assert pattern in dockerignore

