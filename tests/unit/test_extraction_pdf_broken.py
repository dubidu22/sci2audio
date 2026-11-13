"""Broken and hostile PDFs: each must give a clear `ExtractionError` naming the file, never
a traceback or a hang (Issue #5, PDF part; D-65 for #23's first cases).

Moved here from `test_extraction_pdf.py` unchanged; the cases added by #5 follow them.
"""

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pdf_maker import Mark, Rect, Text, make_pdf, outlined_pdf

from sci2audio.core import Content
from sci2audio.extraction import ExtractionError, extract_pdf, read_pdf

pytestmark = pytest.mark.timeout(60)

TESTS = Path(__file__).resolve().parents[1]
FIXTURES = TESTS / "fixtures"
BROKEN = FIXTURES / "broken"
PAPER = TESTS / "corpus" / "papers" / "acl2023-hardt-ellipsis.pdf"
EPUB = TESTS / "corpus" / "epub" / "wells-the-time-machine.epub"


# Broken files: a clear message naming the file, never a traceback or a hang (#5).


@pytest.mark.parametrize(
    ("data", "message"),
    [
        pytest.param(b"", "the file is empty", id="empty"),
        pytest.param(b"Just some words, no PDF at all.", "not a PDF", id="plain-text"),
        pytest.param(EPUB.read_bytes(), "not a PDF", id="epub-named-pdf"),
        pytest.param(PAPER.read_bytes()[:1000], "damaged", id="truncated-start"),
        pytest.param(PAPER.read_bytes()[: PAPER.stat().st_size // 2], "damaged", id="half"),
        pytest.param(
            (BROKEN / "password-protected.pdf").read_bytes(), "password-protected", id="password"
        ),
        # PDFium refuses to open a PDF without pages, so it reads as damaged; the "has no
        # pages" check in read_pdf only guards against a PDFium that opens one.
        pytest.param(make_pdf(), "damaged", id="zero-pages-refused-by-pdfium"),
    ],
)
def test_broken_files_fail_with_a_clear_message(data: bytes, message: str) -> None:
    with pytest.raises(ExtractionError, match=message) as error:
        read_pdf(data, "broken.pdf")
    assert str(error.value).startswith("broken.pdf: ")


def test_a_missing_file_fails_with_a_clear_message(tmp_path: Path) -> None:
    with pytest.raises(ExtractionError, match=r"^gone\.pdf: cannot be opened"):
        extract_pdf(tmp_path / "gone.pdf")


SMALL = make_pdf(
    [Text("A heading", 50, 60, font="Helvetica-Bold", size=14), Text("Body text", 50, 100)],
    [Rect(50, 300, 250, 301), Text("arXiv stamp", 20, 600, turned=True)],
)


def outcome(data: bytes, name: str) -> Content | str:
    """The content, or the message of the ExtractionError (any other exception fails the test)."""
    try:
        return read_pdf(data, name)
    except ExtractionError as error:
        return str(error)


@settings(deadline=None)
@given(st.binary(max_size=2000))
def test_any_bytes_give_content_or_a_clear_error(data: bytes) -> None:
    result = outcome(data, "random.pdf")
    assert isinstance(result, Content) or result.startswith("random.pdf: ")


@settings(deadline=None)
@given(
    st.integers(0, len(SMALL)),
    st.lists(st.tuples(st.integers(0, len(SMALL) - 1), st.integers(0, 255)), max_size=20),
)
def test_a_damaged_pdf_gives_content_or_a_clear_error(
    keep: int, changes: list[tuple[int, int]]
) -> None:
    data = bytearray(SMALL[:keep] if keep < len(SMALL) // 2 else SMALL)
    for position, value in changes:
        if position < len(data):
            data[position] = value
    result = outcome(bytes(data), "damaged.pdf")
    assert (isinstance(result, Content) and result.pages) or result.startswith("damaged.pdf: ")


OUTLINED = outlined_pdf(2, (Mark("1 Intro", 1, (Mark("1.1 Part", 2, goto=True),)), Mark("End")))


@settings(deadline=None)
@given(st.lists(st.tuples(st.integers(0, len(OUTLINED) - 1), st.integers(0, 255)), max_size=20))
def test_a_damaged_outline_gives_content_or_a_clear_error(changes: list[tuple[int, int]]) -> None:
    """Bytes changed anywhere, bookmarks included: an outline is read as far as it can be,
    and every entry still fits the content (D-268)."""
    data = bytearray(OUTLINED)
    for position, value in changes:
        data[position] = value
    result = outcome(bytes(data), "damaged.pdf")
    assert isinstance(result, Content) or result.startswith("damaged.pdf: ")
