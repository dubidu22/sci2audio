"""Format of the hand-checked ground truth in tests/corpus/truth/ (Issue #16, D-60).

Each corpus file has exactly one truth file, and every truth file follows the format documented in
tests/corpus/truth/README.md. These tests check the shape only; whether the values are right is
checked by hand against the PDF or EPUB.
"""

import tomllib
from pathlib import Path
from typing import Any

import pytest

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
TRUTH = CORPUS / "truth"

SAMPLE_SUFFIXES = {".pdf", ".epub"}
DRAFT_SOURCES = {"pdf", "epub", "latex", "markdown"}
VERBATIM_PLACES = {"plain", "column-break", "page-break", "hyphenation"}
FURNITURE_KINDS = {
    "running-head",
    "page-number",
    "line-number",
    "side-stamp",
    "footer",
    "sidebar",
    "contents",
}
COUNT_KEYS = {
    "footnotes",
    "tables",
    "figures",
    "algorithms",
    "numbered_formulas",
    "unnumbered_formulas",
}
REQUIRED_COUNTS = COUNT_KEYS - {"algorithms"}
MIN_VERBATIM, MAX_VERBATIM = 3, 5

COMMON_KEYS = {"file", "drafted_from", "title"}
PAPER_KEYS = COMMON_KEYS | {"pages", "columns", "headings", "counts", "verbatim", "furniture"}
EPUB_KEYS = COMMON_KEYS | {"chapters", "endnotes"}


def sample_files() -> list[Path]:
    return sorted(
        path
        for path in CORPUS.rglob("*")
        if path.is_file() and path.suffix in SAMPLE_SUFFIXES and TRUTH not in path.parents
    )


def truth_files() -> list[Path]:
    return sorted(TRUTH.glob("*.toml"))


def load(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def is_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() == value and value != ""


def is_count(value: object) -> bool:
    return type(value) is int and value >= 0


def check_pages(pages: object, last_page: int, where: str) -> None:
    assert isinstance(pages, list), f"{where}: pages must be a list"
    assert pages, f"{where}: pages must not be empty"
    for page in pages:
        assert type(page) is int, f"{where}: page {page!r} is not a whole number"
        assert 1 <= page <= last_page, f"{where}: page {page} outside 1..{last_page}"


def test_every_corpus_file_has_one_truth_file() -> None:
    expected = {path.stem for path in sample_files()}
    found = {path.stem for path in truth_files()}
    assert not expected - found, f"Corpus files without a truth file: {sorted(expected - found)}"
    assert not found - expected, f"Truth files without a corpus file: {sorted(found - expected)}"


@pytest.mark.parametrize("path", truth_files(), ids=lambda path: path.name)
def test_truth_file_names_its_corpus_file(path: Path) -> None:
    truth = load(path)
    assert is_text(truth.get("file")), "file must be a path below tests/corpus/"
    corpus_file = CORPUS / truth["file"]
    assert corpus_file.is_file(), f"{truth['file']} does not exist"
    assert corpus_file.stem == path.stem, f"{path.name} must be named after {truth['file']}"
    assert TRUTH not in corpus_file.parents


@pytest.mark.parametrize("path", truth_files(), ids=lambda path: path.name)
def test_truth_file_has_common_keys(path: Path) -> None:
    truth = load(path)
    assert is_text(truth.get("title")), "title must be non-empty text"
    sources = truth.get("drafted_from")
    assert isinstance(sources, list), "drafted_from must be a list"
    assert sources, "drafted_from must name at least one source"
    assert set(sources) <= DRAFT_SOURCES, f"unknown sources {set(sources) - DRAFT_SOURCES}"
    assert len(set(sources)) == len(sources), "drafted_from lists a source twice"


def truth_for(suffix: str) -> list[Path]:
    stems = {path.stem for path in sample_files() if path.suffix == suffix}
    return [path for path in truth_files() if path.stem in stems]


PAPERS = truth_for(".pdf")
EPUBS = truth_for(".epub")


@pytest.mark.parametrize("path", PAPERS, ids=lambda path: path.name)
def test_paper_truth_follows_format(path: Path) -> None:
    truth = load(path)
    assert set(truth) == PAPER_KEYS, (
        f"missing {sorted(PAPER_KEYS - set(truth))}, unknown {sorted(set(truth) - PAPER_KEYS)}"
    )
    assert "pdf" in truth["drafted_from"]

    pages = truth["pages"]
    assert type(pages) is int, "pages must be a whole number"
    assert pages >= 1, "pages must be at least 1"
    columns = truth["columns"]
    assert isinstance(columns, list), "columns must be a list"
    assert len(columns) == pages, "one columns entry per page"
    assert set(columns) <= {1, 2}, "columns per page must be 1 or 2"

    headings = truth["headings"]
    assert isinstance(headings, list), "headings must be a list (empty if the paper has none)"
    for heading in headings:
        assert set(heading) == {"level", "text"}, f"heading needs level and text: {heading}"
        assert heading["level"] in {1, 2, 3}, f"heading level must be 1 to 3: {heading}"
        assert is_text(heading["text"]), f"heading text must be non-empty: {heading}"

    counts = truth["counts"]
    assert set(counts) <= COUNT_KEYS, f"unknown counts {sorted(set(counts) - COUNT_KEYS)}"
    assert set(counts) >= REQUIRED_COUNTS, f"missing counts {sorted(REQUIRED_COUNTS - set(counts))}"
    for key, value in counts.items():
        assert is_count(value), f"counts.{key} must be a whole number from 0"

    verbatim = truth["verbatim"]
    assert MIN_VERBATIM <= len(verbatim) <= MAX_VERBATIM, f"{len(verbatim)} verbatim sentences"
    for entry in verbatim:
        assert set(entry) == {"where", "page", "text"}, f"verbatim needs where, page, text: {entry}"
        assert entry["where"] in VERBATIM_PLACES, f"unknown verbatim place {entry['where']!r}"
        check_pages([entry["page"]], pages, f"verbatim {entry['text'][:30]!r}")
        assert is_text(entry["text"]), "verbatim text must be non-empty, without outer spaces"
        assert "\n" not in entry["text"], "verbatim text is one line: line breaks become spaces"
        assert len(entry["text"].split()) >= 6, f"verbatim text too short: {entry['text']!r}"

    for entry in truth["furniture"]:
        assert set(entry) == {"kind", "pages", "text"}, (
            f"furniture needs kind, pages, text: {entry}"
        )
        assert entry["kind"] in FURNITURE_KINDS, f"unknown furniture kind {entry['kind']!r}"
        check_pages(entry["pages"], pages, f"furniture {entry['text']!r}")
        assert is_text(entry["text"]), "furniture text must be non-empty, without outer spaces"


@pytest.mark.parametrize("path", EPUBS, ids=lambda path: path.name)
def test_epub_truth_follows_format(path: Path) -> None:
    truth = load(path)
    assert set(truth) == EPUB_KEYS, (
        f"missing {sorted(EPUB_KEYS - set(truth))}, unknown {sorted(set(truth) - EPUB_KEYS)}"
    )
    assert "epub" in truth["drafted_from"]

    chapters = truth["chapters"]
    assert isinstance(chapters, list), "chapters must be a list"
    assert chapters, "chapters must not be empty"
    assert all(is_text(chapter) for chapter in chapters), "chapter titles must be non-empty"

    for note in truth["endnotes"]:
        assert set(note) == {"chapter", "text"}, f"endnote needs chapter and text: {note}"
        assert note["chapter"] in chapters, f"endnote names unknown chapter {note['chapter']!r}"
        assert is_text(note["text"]), "endnote text must be non-empty"
