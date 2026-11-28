"""The decisions log: one file per ruling, so no two PRs write the same file (#1225)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs" / "decisions.md"
FOLDER = ROOT / "docs" / "decisions"
# the last day a ruling went into docs/decisions.md; later ones go into docs/decisions/
LAST_ARCHIVED = "2026-11-28"
DATED = re.compile(r"(\d{4}-\d{2}-\d{2}) \(#\d+")
NAME = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})-(?P<issue>\d+)(?:-\d+)?\.md")


def late_rulings(archive: str) -> list[str]:
    """The lines of `archive` that hold a ruling dated after `LAST_ARCHIVED`."""
    return [
        line[:40]
        for line in archive.splitlines()
        if (dated := DATED.match(line)) and dated[1] > LAST_ARCHIVED
    ]


def misfiled(name: str, text: str) -> str | None:
    """Why the ruling file `name` holding `text` is not as #1225 asks, or None."""
    named = NAME.fullmatch(name)
    if named is None:
        return f"{name}: name it <YYYY-MM-DD>-<issue>.md"
    lines = text.splitlines()
    if len(lines) != 1:
        return f"{name}: one ruling, one line"
    if not lines[0].startswith(f"{named['date']} (#{named['issue']}"):
        return f"{name}: the line starts with its date and issue, as the name does"
    return None


def test_no_new_ruling_goes_into_the_archive() -> None:
    late = late_rulings(ARCHIVE.read_text(encoding="utf-8"))
    assert late == [], f"a new ruling goes into docs/decisions/<date>-<issue>.md: {late}"


@pytest.mark.parametrize(
    "line",
    [
        "2026-11-29 (#1300): x",
        "2026-11-29 (D-920, #1302): x",
        "2026-11-29: x",
        "- 2026-11-29 (#1303): x",
        "2026-11-24 (#890): an old ruling; 2026-11-29 (#1304): one appended to it",
        "29 Nov 2026 (#1305): x",
    ],
)
def test_a_late_ruling_in_the_archive_is_found_in_any_shape(line: str) -> None:
    """#1261: not only a line that opens with `<date> (#N`."""
    archive = ARCHIVE.read_text(encoding="utf-8")
    assert late_rulings(f"{archive}{line}\n") != []


def test_each_ruling_file_holds_one_dated_line_of_its_issue() -> None:
    files = sorted(p for p in FOLDER.iterdir() if p.name != "README.md")
    assert files, "docs/decisions/ holds the rulings since 2026-11-29"
    for path in files:
        reason = misfiled(path.name, path.read_text(encoding="utf-8"))
        assert reason is None, reason


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("2026-11-28-12.md", "2026-11-28 (#1225): x\n"),  # another issue's number
        ("2026-11-28-1225.md", "2026-11-29 (#1225): x\n"),  # another day
        ("2026-13-45-1300.md", "2026-13-45 (#1300): x\n"),  # no such day
        ("2026-11-27-1300.md", "2026-11-27 (#1300): x\n"),  # a day the archive still held
    ],
)
def test_a_ruling_files_name_and_line_must_match_exactly(name: str, text: str) -> None:
    """#1261: the issue number and the date as the name gives them, and a real date."""
    assert misfiled(name, text) is not None, name


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("2026-11-29-1300.md", "2026-11-29 (#1300): x\n"),
        ("2026-11-29-1300-2.md", "2026-11-29 (#1300, ruled by Colin on 29 Nov 2026): x\n"),
        ("2026-11-29-1300.md", "2026-11-29 (#1300, #1301): x\n"),  # its own issue first
    ],
)
def test_a_ruling_file_of_its_day_and_issue_is_taken(name: str, text: str) -> None:
    assert misfiled(name, text) is None


def test_the_archive_points_to_the_folder() -> None:
    assert "docs/decisions/" in ARCHIVE.read_text(encoding="utf-8").splitlines()[0]
