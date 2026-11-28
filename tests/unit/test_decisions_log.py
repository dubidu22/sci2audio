"""The decisions log: one file per ruling, so no two PRs write the same file (#1225)."""

from __future__ import annotations

import datetime
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs" / "decisions.md"
FOLDER = ROOT / "docs" / "decisions"
# the last day a ruling went into docs/decisions.md; later ones go into docs/decisions/
LAST_ARCHIVED = datetime.date(2026, 11, 28)
# any date in a line, as the log writes it or in words: a late ruling may open a line, sit
# in a list item or be appended to an old ruling's line (#1261)
ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
WORDS_DATE = re.compile(
    r"\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d{4})\b"
)
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
NAME = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})-(?P<issue>\d+)(?:-\d+)?\.md")


def dates_in(line: str) -> list[datetime.date]:
    """The real dates `line` names; a shape that is no day (2026-13-45) is none."""
    found = [(int(y), int(m), int(d)) for y, m, d in ISO_DATE.findall(line)]
    found += [(int(y), MONTHS.index(m) + 1, int(d)) for d, m, y in WORDS_DATE.findall(line)]
    dates = []
    for year, month, day in found:
        try:
            dates.append(datetime.date(year, month, day))
        except ValueError:
            continue
    return dates


def late_rulings(archive: str) -> list[str]:
    """The lines of `archive` that name a day after `LAST_ARCHIVED`, its first line (the
    pointer to docs/decisions/, which names the day the folder starts) apart."""
    return [
        line[:60]
        for line in archive.splitlines()[1:]
        if any(day > LAST_ARCHIVED for day in dates_in(line))
    ]


def misfiled(name: str, text: str) -> str | None:
    """Why the ruling file `name` holding `text` is not as #1225 asks, or None."""
    named = NAME.fullmatch(name)
    if named is None:
        return f"{name}: name it <YYYY-MM-DD>-<issue>.md"
    try:
        day = datetime.date.fromisoformat(named["date"])
    except ValueError:
        return f"{name}: {named['date']} is no day"
    if day < LAST_ARCHIVED:
        return f"{name}: a ruling before {LAST_ARCHIVED} is in docs/decisions.md"
    lines = text.splitlines()
    if len(lines) != 1:
        return f"{name}: one ruling, one line"
    if re.match(rf"{named['date']} \(#{named['issue']}(?!\d)", lines[0]) is None:
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
