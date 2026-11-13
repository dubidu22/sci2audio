"""Markdown and text extraction on the own samples: the ground truth and the golden files
(#74, D-348, D-349).

Extraction decides nothing, so the truth files are checked only for what must be *recorded*:
each heading as a line tagged with its level, each note in a line with the endnote role and
its mark linked to it, the tables, pictures and formulas, and the verbatim sentences in the
lines' text. Paragraphs, sections and placeholders are the layout stage's work (#75).

The variants of the samples (other line ends, byte order marks, UTF-16, Windows-1252) are
built here from the stored bytes and must give the same lines (D-345, D-348).

The golden files show each page's items in stored order: every line in full with its runs'
tags and style, every picture with its path and alternative text. Accept a wanted change
with `uv run pytest --snapshot-update` and explain the diff in the PR.
"""

import codecs
import tomllib
from functools import cache
from pathlib import Path

import pytest
from content_description import describe
from syrupy.assertion import SnapshotAssertion

from sci2audio.core import Content, Metadata, TextLine
from sci2audio.extraction import extract_markdown, extract_text, read_markdown, read_text

pytestmark = pytest.mark.timeout(60)

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
MARKDOWN = CORPUS / "markdown" / "sci2audio-sample-note.md"
TEXT = CORPUS / "text" / "sci2audio-sample-plain.txt"


@cache
def markdown() -> Content:
    return extract_markdown(MARKDOWN)


@cache
def text() -> Content:
    return extract_text(TEXT)


def truth(sample: Path) -> dict:
    return tomllib.loads((CORPUS / "truth" / f"{sample.stem}.toml").read_text(encoding="utf-8"))


def lines(content: Content) -> tuple[TextLine, ...]:
    return content.pages[0].lines


def tagged(content: Content, tag: str) -> list[TextLine]:
    return [line for line in lines(content) if any(tag in run.tags for run in line.runs)]


def joined(content: Content) -> str:
    """The lines' text, each element's lines joined by a space and elements by a newline."""
    out: list[str] = []
    for line in lines(content):
        continues = "br" in line.runs[0].tags and out
        out.append((out.pop() + " " if continues else "") + line.text)
    return "\n".join(out)


# ---- the Markdown sample -----------------------------------------------------------------


def test_markdown_metadata_from_the_front_matter() -> None:
    assert markdown().metadata == Metadata(
        title=truth(MARKDOWN)["title"],
        authors=("A. Example", "B. Sample"),
        date="2026-11-13",
        identifier="10.0000/sci2audio.sample",
        language="en-GB",
    )
    assert markdown().outline == ()
    assert (markdown().source.encoding, markdown().source.encoding_guessed) == ("utf-8", False)


def test_markdown_headings_are_lines_tagged_with_their_level() -> None:
    found = [
        {"level": int(tag[1]), "text": line.text}
        for line in lines(markdown())
        for tag in line.runs[0].tags[:1]
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}
    ]
    assert found == truth(MARKDOWN)["headings"]


def test_markdown_notes_carry_the_endnote_role_and_their_marks_link_to_them() -> None:
    notes = tagged(markdown(), "role:doc-endnote")
    expected = truth(MARKDOWN)["footnotes"]
    assert [line.text for line in notes] == [note["text"] for note in expected]
    marks = [
        (run.text, run.tags[-1])
        for line in lines(markdown())
        for run in line.runs
        if "role:doc-noteref" in run.tags
    ]
    by_mark = {note["mark"]: f"link:{line.id}" for note, line in zip(expected, notes, strict=True)}
    assert marks == [("1", by_mark["1"]), ("2", by_mark["2"]), ("2", by_mark["2"])]


def test_markdown_tables_pictures_and_formulas() -> None:
    expected = truth(MARKDOWN)
    starts = [
        line for line in lines(markdown()) if line.runs[0].tags[:3] == ("table", "thead", "tr")
    ]
    assert len({line.runs[0].tags[:1] for line in starts}) == expected["tables"]
    assert [picture.alt for picture in markdown().pages[0].pictures] == expected["figures"]
    formulas = [
        {"display": run.tags[-2] == "div", "text": run.text}
        for line in lines(markdown())
        for run in line.runs
        if "role:math" in run.tags
    ]
    assert formulas == expected["formulas"]


def test_markdown_verbatim_sentences_are_in_the_lines() -> None:
    text_of_lines = joined(markdown())
    for entry in truth(MARKDOWN)["verbatim"]:
        assert entry["text"] in text_of_lines, entry


def test_markdown_golden_file(snapshot: SnapshotAssertion) -> None:
    assert describe(markdown()) == snapshot


# ---- the text sample ---------------------------------------------------------------------


def test_text_lines_and_paragraphs() -> None:
    content = text()
    assert content.metadata == Metadata()
    assert content.outline == ()
    assert lines(content)[0].text == truth(TEXT)["title"]
    paragraphs = [line for line in lines(content) if line.runs[0].tags == ("p",)]
    assert len(paragraphs) == 8  # the paragraphs between blank lines (one ends at a line of spaces)
    assert all(len(line.runs) == 1 for line in lines(content))


def test_text_verbatim_sentences_are_in_the_lines() -> None:
    text_of_lines = joined(text())
    for entry in truth(TEXT)["verbatim"]:
        sentence = entry["text"]
        if entry["where"] == "hyphenation":  # recorded as printed: the hyphen ends the line
            sentence = sentence.replace("example", "exam- ple")
        assert sentence in text_of_lines, entry


def test_text_golden_file(snapshot: SnapshotAssertion) -> None:
    assert describe(text()) == snapshot


# ---- variants: line ends and encodings (D-345) -------------------------------------------


def variants(data: bytes) -> dict[str, bytes]:
    words = data.decode("utf-8")
    crlf = words.replace("\n", "\r\n")
    return {
        "crlf": crlf.encode(),
        "cr": words.replace("\n", "\r").encode(),
        "utf-8 mark": codecs.BOM_UTF8 + data,
        "utf-16 le": codecs.BOM_UTF16_LE + crlf.encode("utf-16-le"),
        "utf-16 be": codecs.BOM_UTF16_BE + words.encode("utf-16-be"),
        "windows-1252": words.encode("cp1252"),
    }


@pytest.mark.parametrize("sample", [MARKDOWN, TEXT], ids=["markdown", "text"])
@pytest.mark.parametrize(
    "variant", ["crlf", "cr", "utf-8 mark", "utf-16 le", "utf-16 be", "windows-1252"]
)
def test_every_variant_gives_the_same_lines(sample: Path, variant: str) -> None:
    read = read_markdown if sample.suffix == ".md" else read_text
    stored = read(sample.read_bytes(), sample.name)
    content = read(variants(sample.read_bytes())[variant], sample.name)
    assert content.pages == stored.pages
    assert content.metadata == stored.metadata
    assert content.source.encoding_guessed == (variant == "windows-1252")
