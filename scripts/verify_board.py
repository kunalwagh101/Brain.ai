#!/usr/bin/env python3
"""Verify Brain delivery state from repository artifacts only.

Standard-library only by design.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "PRODUCT_BACKLOG.md"
BOARD = ROOT / "BOARD.md"
DOD = ROOT / "DEFINITION_OF_DONE.md"
TRACE = ROOT / "TRACEABILITY.md"

VALID_STATES = {
    "BACKLOG",
    "READY",
    "IN_PROGRESS",
    "IN_REVIEW",
    "BLOCKED",
    "DONE",
    "DEFERRED",
}
STORY_RE = re.compile(r"\*\*(S-\d{2}\.\d{2}\.\d{2})\b")
ANY_ID_RE = re.compile(r"\b(?:E-\d{2}|F-\d{2}\.\d{2}|S-\d{2}\.\d{2}\.\d{2})\b")
BOARD_RE = re.compile(
    r"^(BACKLOG|READY|IN_PROGRESS|IN_REVIEW|BLOCKED|DONE|DEFERRED)\s*\|\s*"
    r"(S-\d{2}\.\d{2}\.\d{2})\s*\|\s*(F-\d{2}\.\d{2})\s*\|\s*(.+)$"
)
EVIDENCE_RE = re.compile(
    r"EVIDENCE\s+(S-\d{2}\.\d{2}\.\d{2})\n"
    r"tests:\s*(.+)\n"
    r"command:\s*(.+)\n"
    r"result:\s*(.+)\n"
    r"code:\s*(.+)\n"
    r"commit:\s*(.+)",
    re.MULTILINE,
)
BAD_CODE_RE = re.compile(r"TODO|FIXME|NotImplemented|raise\s+NotImplementedError|^\s*pass\s*(?:#.*)?$", re.MULTILINE)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def read_required(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        fail(errors, f"missing required artifact: {path.relative_to(ROOT)}")
        return ""
    return path.read_text(encoding="utf-8")


def parse_story_ids(backlog: str) -> set[str]:
    return set(STORY_RE.findall(backlog))


def parse_board(board: str, errors: list[str]) -> dict[str, tuple[str, str, str]]:
    rows: dict[str, tuple[str, str, str]] = {}
    for line_no, line in enumerate(board.splitlines(), 1):
        match = BOARD_RE.match(line.strip())
        if not match:
            continue
        state, story, feature, note = match.groups()
        if story in rows:
            fail(errors, f"BOARD.md:{line_no}: duplicate story {story}")
        rows[story] = (state, feature, note)
    return rows


def verify_coverage(backlog: str, all_ids: set[str], errors: list[str]) -> int:
    marker = "## Requirements -> Backlog coverage"
    if marker not in backlog:
        fail(errors, "PRODUCT_BACKLOG.md: missing requirements coverage table")
        return 0
    section = backlog.split(marker, 1)[1].split("## Out of scope", 1)[0]
    requirements = 0
    for line in section.splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Requirement |" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        requirements += 1
        ids = set(ANY_ID_RE.findall(cells[1]))
        if not ids:
            fail(errors, f"coverage row has no backlog ID: {cells[0]}")
        missing = ids - all_ids
        if missing:
            fail(errors, f"coverage row '{cells[0]}' references unknown IDs: {sorted(missing)}")
    if requirements == 0:
        fail(errors, "requirements coverage table contains no requirements")
    return requirements


def path_from_evidence(value: str) -> tuple[Path, int | None, int | None]:
    raw = value.strip().split()[0]
    match = re.match(r"(.+?):(\d+)(?:-(\d+))?$", raw)
    if match:
        path, start, end = match.groups()
        return ROOT / path, int(start), int(end or start)
    return ROOT / raw, None, None


def test_file_from_nodeid(nodeid: str) -> Path:
    return ROOT / nodeid.strip().split("::", 1)[0]


def verify_done(
    done: set[str], backlog: str, board: str, trace: str, errors: list[str]
) -> tuple[int, int]:
    combined = "\n".join((backlog, board, trace))
    evidence = {match.group(1): match.groups()[1:] for match in EVIDENCE_RE.finditer(combined)}
    tested = 0
    total = len(done)
    command_environment = os.environ.copy()
    local_venv_bin = ROOT / ".venv" / "bin"
    if local_venv_bin.is_dir():
        command_environment["PATH"] = os.pathsep.join(
            (str(local_venv_bin), command_environment.get("PATH", ""))
        )

    for story in sorted(done):
        block = evidence.get(story)
        if not block:
            fail(errors, f"DONE {story} has no evidence block")
            continue
        tests, command, result, code, commit = [item.strip() for item in block]
        if not tests or tests.lower() == "pending":
            fail(errors, f"DONE {story} evidence has no named test")
        else:
            test_path = test_file_from_nodeid(tests)
            if not test_path.is_file():
                fail(errors, f"DONE {story} names missing test file: {test_path.relative_to(ROOT)}")
            else:
                tested += 1

        code_path, start, end = path_from_evidence(code)
        if not code_path.is_file():
            fail(errors, f"DONE {story} names missing code file: {code_path.relative_to(ROOT)}")
        else:
            lines = code_path.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = lines[(start - 1 if start else 0) : (end if end else len(lines))]
            snippet = "\n".join(selected)
            if BAD_CODE_RE.search(snippet):
                fail(errors, f"DONE {story} code evidence contains TODO/FIXME/stub markers")

        if not commit or commit.startswith("<"):
            fail(errors, f"DONE {story} evidence has no concrete commit SHA")
        if "passed" not in result.lower():
            fail(errors, f"DONE {story} evidence result does not claim a passing run")

        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                shell=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=command_environment,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired:
            fail(errors, f"DONE {story} test command timed out: {command}")
            continue
        if completed.returncode != 0:
            tail = "\n".join(completed.stdout.splitlines()[-20:])
            fail(errors, f"DONE {story} named test command failed:\n{tail}")

    return tested, total


def main() -> int:
    errors: list[str] = []
    backlog = read_required(BACKLOG, errors)
    board_text = read_required(BOARD, errors)
    read_required(DOD, errors)
    trace = read_required(TRACE, errors)

    stories = parse_story_ids(backlog)
    if not stories:
        fail(errors, "PRODUCT_BACKLOG.md contains no story headings")

    epics = set(re.findall(r"\bE-\d{2}\b", backlog))
    features = set(re.findall(r"\bF-\d{2}\.\d{2}\b", backlog))
    all_ids = stories | epics | features

    board = parse_board(board_text, errors)
    board_ids = set(board)

    missing_from_board = stories - board_ids
    unknown_on_board = board_ids - stories
    if missing_from_board:
        fail(errors, f"stories missing from board: {sorted(missing_from_board)}")
    if unknown_on_board:
        fail(errors, f"board contains stories missing from backlog: {sorted(unknown_on_board)}")

    states = Counter(state for state, _, _ in board.values())
    if states["IN_PROGRESS"] > 2:
        fail(errors, f"WIP violation: IN_PROGRESS={states['IN_PROGRESS']} > 2")

    oq_text = (ROOT / "OPEN_QUESTIONS.md").read_text(encoding="utf-8") if (ROOT / "OPEN_QUESTIONS.md").is_file() else ""
    for story, (state, _, note) in board.items():
        if state == "BLOCKED":
            oqs = re.findall(r"OQ-\d{3}", note)
            if not oqs and "external" not in note.lower():
                fail(errors, f"BLOCKED {story} lacks OQ/external dependency")
            for oq in oqs:
                if oq not in oq_text:
                    fail(errors, f"BLOCKED {story} references missing {oq}")

    requirement_count = verify_coverage(backlog, all_ids, errors)
    done = {story for story, (state, _, _) in board.items() if state == "DONE"}
    tested_done, total_done = verify_done(done, backlog, board_text, trace, errors)

    trace_ids = set(re.findall(r"\|\s*(S-\d{2}\.\d{2}\.\d{2})\s*\|", trace))
    missing_trace = stories - trace_ids
    if missing_trace:
        fail(errors, f"stories missing from TRACEABILITY.md: {sorted(missing_trace)}")

    print("Brain delivery verifier")
    print("-----------------------")
    for state in VALID_STATES:
        print(f"{state}: {states[state]}")
    coverage = 100.0 if total_done == 0 else tested_done / total_done * 100
    print(f"requirements mapped: {requirement_count}")
    print(f"DONE stories with named test files: {tested_done}/{total_done} ({coverage:.1f}%)")
    not_built = sorted(stories - done)
    print("not built yet:")
    for story in not_built:
        print(f"- {story}: {board.get(story, ('MISSING', '', ''))[0]}")

    if errors:
        print("\nFAILURES:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("\nPASS: repository delivery state is internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
