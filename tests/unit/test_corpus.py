"""Rules for the shared sample corpus in tests/corpus/ (Issue #3, PE-03).

Every sample text must be listed in tests/corpus/LICENSES.md with an allowed
licence, and the corpus must stay small enough to live in the repository.
"""

import zipfile
from pathlib import Path

import pytest

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
LICENSES = CORPUS / "LICENSES.md"

# Files in tests/corpus/ that are not sample texts.
NOT_SAMPLES = {"LICENSES.md"}
TRUTH = CORPUS / "truth"  # hand-checked ground truth about the samples (Issue #16)

# SPDX identifiers (plus "public domain") allowed by .claude/rules/licences.md for texts.
ALLOWED_LICENCES = {
    "CC0-1.0",
    "CC-BY-2.0",
    "CC-BY-2.5",
    "CC-BY-3.0",
    "CC-BY-4.0",
    "public domain",
}

MAX_FILE_BYTES = 1_000_000  # no file over 1 MB
MAX_TOTAL_BYTES = 10_000_000  # whole corpus under 10 MB
MIN_PAPERS, MAX_PAPERS = 5, 10

REQUIRED_COLUMNS = ("File", "Title", "Authors", "Source", "Licence")


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def table_lines() -> list[str]:
    return [
        line
        for line in LICENSES.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("|")
    ]


def read_licence_table() -> list[dict[str, str]]:
    """Return the rows of the Markdown table in LICENSES.md as dicts."""
    header, _separator, *rows = table_lines()
    columns = split_row(header)
    return [dict(zip(columns, split_row(row), strict=True)) for row in rows]


def listed_file(row: dict[str, str]) -> str:
    return row["File"].strip("`")


def sample_files() -> list[Path]:
    return sorted(
        path
        for path in CORPUS.rglob("*")
        if path.is_file() and path.name not in NOT_SAMPLES and TRUTH not in path.parents
    )


def relative(path: Path) -> str:
    return path.relative_to(CORPUS).as_posix()


def test_table_has_required_columns() -> None:
    header = split_row(table_lines()[0])
    for column in REQUIRED_COLUMNS:
        assert column in header, f"LICENSES.md table lacks the column {column!r}"


def test_every_file_is_listed() -> None:
    listed = {listed_file(row) for row in read_licence_table()}
    unlisted = [relative(path) for path in sample_files() if relative(path) not in listed]
    assert not unlisted, f"Files missing from tests/corpus/LICENSES.md: {unlisted}"


def test_every_listed_file_exists() -> None:
    missing = [
        listed_file(row)
        for row in read_licence_table()
        if not (CORPUS / listed_file(row)).is_file()
    ]
    assert not missing, f"Listed in LICENSES.md but not in tests/corpus/: {missing}"


def test_every_row_is_complete() -> None:
    for row in read_licence_table():
        empty = [column for column in REQUIRED_COLUMNS if not row[column]]
        assert not empty, f"{listed_file(row)}: empty columns {empty}"


def test_only_allowed_licences() -> None:
    refused = {
        listed_file(row): row["Licence"]
        for row in read_licence_table()
        if row["Licence"] not in ALLOWED_LICENCES
    }
    assert not refused, f"Licences not allowed for sample texts: {refused}"


def test_no_file_over_limit() -> None:
    too_big = {
        relative(path): path.stat().st_size
        for path in sample_files()
        if path.stat().st_size > MAX_FILE_BYTES
    }
    assert not too_big, f"Files over {MAX_FILE_BYTES} bytes: {too_big}"


def test_total_size_under_limit() -> None:
    total = sum(path.stat().st_size for path in sample_files())
    assert total < MAX_TOTAL_BYTES, f"Corpus is {total} bytes, limit {MAX_TOTAL_BYTES}"


def test_corpus_has_papers_and_an_epub() -> None:
    papers = [path for path in sample_files() if path.suffix == ".pdf"]
    epubs = [path for path in sample_files() if path.suffix == ".epub"]
    assert MIN_PAPERS <= len(papers) <= MAX_PAPERS, f"{len(papers)} papers"
    assert epubs, "the corpus needs at least one public-domain EPUB"


@pytest.mark.parametrize("path", [p for p in sample_files() if p.suffix == ".pdf"], ids=relative)
def test_pdf_is_a_real_pdf(path: Path) -> None:
    # A failed download often saves an HTML error page under the .pdf name.
    assert path.read_bytes()[:5] == b"%PDF-"


@pytest.mark.parametrize("path", [p for p in sample_files() if p.suffix == ".epub"], ids=relative)
def test_epub_is_a_real_epub(path: Path) -> None:
    with zipfile.ZipFile(path) as epub:
        assert epub.namelist()[0] == "mimetype"
        assert epub.read("mimetype") == b"application/epub+zip"
