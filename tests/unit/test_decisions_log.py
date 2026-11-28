"""The decisions log: one file per ruling, so no two PRs write the same file (#1225)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs" / "decisions.md"
FOLDER = ROOT / "docs" / "decisions"
# the last day a ruling went into docs/decisions.md; later ones go into docs/decisions/
LAST_ARCHIVED = "2026-11-28"
DATED = re.compile(r"(\d{4}-\d{2}-\d{2}) \(#\d+")
NAME = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})-(?P<issue>\d+)(?:-\d+)?\.md")


def test_no_new_ruling_goes_into_the_archive() -> None:
    late = [
        line[:40]
        for line in ARCHIVE.read_text(encoding="utf-8").splitlines()
        if (dated := DATED.match(line)) and dated[1] > LAST_ARCHIVED
    ]
    assert late == [], f"a new ruling goes into docs/decisions/<date>-<issue>.md: {late}"


def test_each_ruling_file_holds_one_dated_line_of_its_issue() -> None:
    files = sorted(p for p in FOLDER.iterdir() if p.name != "README.md")
    assert files, "docs/decisions/ holds the rulings since 2026-11-29"
    for path in files:
        name = NAME.fullmatch(path.name)
        assert name is not None, f"{path.name}: name it <YYYY-MM-DD>-<issue>.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1, f"{path.name}: one ruling, one line"
        assert lines[0].startswith(f"{name['date']} (#{name['issue']}"), (
            f"{path.name}: the line starts with its date and issue, as the name does"
        )


def test_the_archive_points_to_the_folder() -> None:
    assert "docs/decisions/" in ARCHIVE.read_text(encoding="utf-8").splitlines()[0]
