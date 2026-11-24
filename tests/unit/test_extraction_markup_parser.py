"""Broken markup reads the same on every Python version (#175, D-777).

The standard library's `html.parser` changed its handling of broken markup in CPython
security releases, twice: 3.12.12/3.13.6 and again 3.12.16/3.13.18 (measured on nine
interpreters, plans/extraction-batch-b14-plan.md). The readers use a copy of CPython 3.13.18's
parser (`sci2audio.extraction.htmlparser`), so these rows give the same `Content` on every
Python. On CI's 3.12.16 the stdlib parser happens to give the same rows, so the rows alone
would not catch a return to it: the import checks below do.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from sci2audio.extraction import epub, htmlparser, markup

pytestmark = pytest.mark.timeout(60)

EXTRACTION = Path(markup.__file__).parent


def lines_after_a(text: str) -> list[list[str]]:
    """The runs of each line `PageReader` reads from `<p>A</p>` + `text`, after the "A"."""
    reader = markup.PageReader(1, "c1.xhtml", markup.Anchors())
    reader.read("<p>A</p>" + text)
    first, *rest = reader.page().lines
    assert first.text == "A"
    return [[run.text for run in line.runs] for line in rest]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # the eight rows of #175
        pytest.param("<!-- x\n\ny", [], id="unclosed comment"),
        pytest.param("<a href", [], id="start tag cut at the end"),
        pytest.param("<![CDATA[x", [["x"]], id="unclosed CDATA"),
        pytest.param("<!x", [], id="bogus declaration"),
        pytest.param("<!--->B", [["B"]], id="comment <!--->"),
        pytest.param("<!-- a --!>B", [["B"]], id="comment closed by --!>"),
        pytest.param("<textarea><b>x</b></textarea>", [["<b>x</b>"]], id="textarea"),
        pytest.param("<a b='x>B", [], id="unclosed attribute quote"),
        # more rows that differ between patch levels
        pytest.param("<title><b>x</b></title>B", [["<b>x</b>", "B"]], id="title"),
        pytest.param("</p", [], id="end tag cut at the end"),
        pytest.param("<?x", [], id="unclosed processing instruction"),
        pytest.param("<!-->B", [["B"]], id="comment <!-->"),
        pytest.param("<!DOCTYPE x", [], id="unclosed doctype"),
        pytest.param("<plaintext><b>x</b>", [["<b>x</b>"]], id="plaintext"),
        pytest.param("<xmp><b>x</b></xmp>B", [["<b>x</b>", "B"]], id="xmp"),
    ],
)
def test_broken_markup_reads_as_cpython_3_13_18_reads_it(
    text: str, expected: list[list[str]]
) -> None:
    assert lines_after_a(text) == expected


def test_the_readers_use_the_copied_parser() -> None:
    assert issubclass(markup.PageReader, htmlparser.HTMLParser)
    assert issubclass(epub._NavReader, htmlparser.HTMLParser)


def imported_modules(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


@pytest.mark.parametrize("path", sorted(EXTRACTION.glob("*.py")), ids=lambda path: path.name)
def test_no_reader_imports_the_standard_library_parser(path: Path) -> None:
    assert not imported_modules(path) & {"html.parser", "_markupbase"}


def test_the_copy_names_its_source_and_keeps_the_psf_notice() -> None:
    text = (EXTRACTION / "htmlparser.py").read_text(encoding="utf-8")
    head = text[:6000]
    assert "Copied from CPython 3.13.18" in head
    assert "Copyright (c) 2001-2024 Python Software Foundation; All Rights Reserved" in head
    assert "PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2" in head
    assert "Summary of the changes made to Python" in head
    # it needs only these, identical from 3.12.10 to 3.13.18; mutmut adds its own import to
    # the files it mutates, which is not the copy's
    imported = imported_modules(EXTRACTION / "htmlparser.py")
    assert {name for name in imported if name.split(".")[0] != "mutmut"} == {
        "re",
        "html",
        "html.entities",
    }


def test_a_line_ended_by_a_flush_does_not_continue_unless_it_says_so() -> None:
    """`continued` is for a <br> or a line feed in <pre>; the end of a block ends the
    element too (#632)."""
    reader = markup.PageReader(1, "c1.xhtml", markup.Anchors())
    reader.feed("one")
    reader.flush()
    assert reader.continues is False
    reader.feed(" two")
    reader.flush(continued=True)
    assert reader.continues is True


def test_a_flush_that_finds_no_text_keeps_a_continuation_only_if_told_to() -> None:
    reader = markup.PageReader(1, "c1.xhtml", markup.Anchors())
    reader.continues = True
    reader.flush(continued=True)
    assert reader.continues is True
    reader.flush()
    assert reader.continues is False
