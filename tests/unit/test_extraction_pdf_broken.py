"""Broken and hostile PDFs: each must give a clear `ExtractionError` naming the file, never
a traceback or a hang (Issue #5, PDF part; D-65 for #23's first cases, D-393 to D-398).

The first cases came from `test_extraction_pdf.py` (#23); #5 adds the files that are refused
with their exact messages (`broken_pdfs.py`, shared with the web tests), the limits, and the
damaged files PDFium repairs, which must still be read. Every file is written by the tests;
none is stored except the password-protected one.
"""

from functools import cache
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from broken_pdfs import ALL, COPY, CUT_SHORT, REFUSED, Refused
from hypothesis import given, settings
from hypothesis import strategies as st
from pdf_maker import (
    Mark,
    Rect,
    Text,
    dense_pdf,
    image_only_pdf,
    make_pdf,
    one_page_pdf,
    outlined_pdf,
    owner_locked_pdf,
    raw_pdf,
    stream,
    with_page_added,
)

from sci2audio.core import Content
from sci2audio.extraction import ExtractionError, extract_pdf, pdf, read_pdf

pytestmark = pytest.mark.timeout(60)

TESTS = Path(__file__).resolve().parents[1]
FIXTURES = TESTS / "fixtures"
BROKEN = FIXTURES / "broken"
CORPUS = TESTS / "corpus" / "papers"
PAPERS = sorted(CORPUS.glob("*.pdf"))
PAPER = CORPUS / "acl2023-hardt-ellipsis.pdf"
EPUB = TESTS / "corpus" / "epub" / "wells-the-time-machine.epub"


# Broken files: a clear message naming the file, never a traceback or a hang (#5).


@pytest.mark.parametrize(
    ("data", "message"),
    [
        pytest.param(b"", "the file is empty", id="empty"),
        pytest.param(b"Just some words, no PDF at all.", "not a PDF", id="plain-text"),
        pytest.param(EPUB.read_bytes(), "not a PDF", id="epub-named-pdf"),
        # A file that starts like a PDF but has no end is cut short (D-395); #23 said "damaged".
        pytest.param(PAPER.read_bytes()[:1000], "cut short", id="truncated-start"),
        pytest.param(PAPER.read_bytes()[: PAPER.stat().st_size // 2], "cut short", id="half"),
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


@pytest.mark.parametrize("case", REFUSED, ids=[case.id for case in REFUSED])
def test_refused_files_say_why(case: Refused) -> None:
    with pytest.raises(ExtractionError) as error:
        read_pdf(case.make(), "broken.pdf")
    assert str(error.value) == case.expected("broken.pdf")


def test_the_limits_are_the_decided_ones() -> None:
    """D-394, D-395: the tests below shrink the limits, so their values are pinned here."""
    assert (pdf.MAX_PAGES, pdf.MAX_PAGE_CHARS, pdf.MAX_CHARS) == (10_000, 100_000, 10_000_000)
    assert pdf.HEADER_ZONE == 1024


def test_a_page_over_the_character_limit_is_refused_before_it_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdf, "MAX_PAGE_CHARS", 1_100)
    content = read_pdf(dense_pdf(1, 1_000), "fits.pdf")
    assert sum(len(line.text) for line in content.pages[0].lines) == 1_000
    lines: list[int] = []
    monkeypatch.setattr(pdf, "_lines", lambda *args: lines.append(1))
    with pytest.raises(ExtractionError) as error:
        read_pdf(dense_pdf(1, 1_200), "big.pdf")
    assert str(error.value) == (
        "big.pdf: the PDF is too large or damaged (page 1 holds more than 1,100 characters)"
    )
    assert lines == []


def test_too_many_characters_in_all_are_refused_before_more_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdf, "MAX_CHARS", 2_500)
    read_pdf(dense_pdf(2, 1_200), "fits.pdf")
    with pytest.raises(ExtractionError) as error:
        read_pdf(dense_pdf(3, 1_200), "big.pdf")
    assert (
        str(error.value) == "big.pdf: the PDF is too large or damaged (more than 2,500 characters)"
    )


def pdfium_chars(data: bytes) -> int:
    """The characters PDFium counts on the file's first page, the line ends it adds included."""
    document = pdfium.PdfDocument(data)
    try:
        textpage = document[0].get_textpage()
        return textpage.count_chars()
    finally:
        document.close()


def test_a_page_exactly_at_the_character_limit_is_read_and_one_more_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review S4 of #188: the limit is pinned at its boundary, so `>=` for `>` fails."""
    data = dense_pdf(1, 1_000)
    count = pdfium_chars(data)
    monkeypatch.setattr(pdf, "MAX_PAGE_CHARS", count)
    read_pdf(data, "fits.pdf")
    monkeypatch.setattr(pdf, "MAX_PAGE_CHARS", count - 1)
    with pytest.raises(
        ExtractionError, match=rf"\(page 1 holds more than {count - 1:,} characters\)$"
    ):
        read_pdf(data, "big.pdf")


def test_exactly_the_characters_allowed_in_all_are_read_and_one_more_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = dense_pdf(2, 1_000)  # two pages sharing one content stream
    total = 2 * pdfium_chars(data)
    monkeypatch.setattr(pdf, "MAX_CHARS", total)
    read_pdf(data, "fits.pdf")
    monkeypatch.setattr(pdf, "MAX_CHARS", total - 1)
    with pytest.raises(ExtractionError, match=rf"\(more than {total - 1:,} characters\)$"):
        read_pdf(data, "big.pdf")


def test_too_many_pages_are_refused_before_any_page_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdf, "MAX_PAGES", 2)
    read_pdf(make_pdf([Text("one", 50, 50)], [Text("two", 50, 50)]), "fits.pdf")
    pages: list[int] = []
    monkeypatch.setattr(pdf, "_pages", lambda document, name: pages.append(1))
    with pytest.raises(ExtractionError, match=r"\(more than 2 pages\)$"):
        read_pdf(make_pdf(*([Text("page", 50, 50)],) * 3), "big.pdf")
    assert pages == []


HTML = b"<!DOCTYPE html><html><body>" + b"<p>Not found.</p>" * 300 + b"</body></html>"


def text_of(data: bytes) -> list[str]:
    return [line.text for page in read_pdf(data, "read.pdf").pages for line in page.lines]


@pytest.mark.parametrize(
    ("data", "lines"),
    [
        # a scan with a text layer from text recognition, laid over the picture invisibly
        pytest.param(image_only_pdf(ocr_text="Recognised words"), ["Recognised words"], id="ocr"),
        # owner restrictions that still allow reading out (D-396)
        pytest.param(
            owner_locked_pdf("A made-up paper", ALL & ~COPY),
            ["A made-up paper"],
            id="owner-forbids-copying-only",
        ),
        pytest.param(
            owner_locked_pdf("A made-up paper", ALL), ["A made-up paper"], id="owner-allows-all"
        ),
        pytest.param(
            owner_locked_pdf("A made-up paper", ALL, revision=2),
            ["A made-up paper"],
            id="owner-revision-2-allows-copying",
        ),
        # damage PDFium repairs: the file still ends with %%EOF, so nothing was cut (D-395)
        pytest.param(
            one_page_pdf().replace(b"0000000015 00000 n", b"0000009999 00000 n"),
            ["Hello world"],
            id="wrong-xref-offsets",
        ),
        pytest.param(one_page_pdf(xref=False), ["Hello world"], id="no-xref-table"),
        pytest.param(
            one_page_pdf().replace(b"startxref\n", b"startxref\n9"),
            ["Hello world"],
            id="wrong-startxref",
        ),
        pytest.param(one_page_pdf() + bytes(2048), ["Hello world"], id="junk-after-the-end"),
        # past PDFium's 4 KB window for startxref, so it rebuilds the table (review M1 of #188)
        pytest.param(one_page_pdf() + bytes(4096), ["Hello world"], id="4-kb-after-the-end"),
        pytest.param(one_page_pdf() + bytes(1 << 20), ["Hello world"], id="1-mb-after-the-end"),
        pytest.param(one_page_pdf() + HTML, ["Hello world"], id="web-page-after-the-end"),
        pytest.param(
            one_page_pdf().replace(b"/Count 1", b"/Count 1000000000"),
            ["Hello world"],
            id="page-count-lies",
        ),
        pytest.param(one_page_pdf(media_box=b"[0 0 0 0]"), ["Hello world"], id="empty-media-box"),
        pytest.param(one_page_pdf(media_box=b"[]"), ["Hello world"], id="no-media-box"),
        pytest.param(
            one_page_pdf(media_box=b"[0 0 1e40 -1e40]"), ["Hello world"], id="huge-media-box"
        ),
        pytest.param(one_page_pdf(page=b"/Rotate 90"), ["Hello world"], id="turned-page"),
        # a font whose glyph names PDFium doesn't know: read as the file maps it (D-402)
        pytest.param(
            one_page_pdf(
                b"BT /F1 12 Tf 72 720 Td (ABC) Tj ET",
                extra={
                    5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica"
                    b" /Encoding << /Differences [65 /g1 /g2 /g3] >> >>"
                },
            ),
            ["ABC"],
            id="unknown-glyph-names",
        ),
    ],
)
def test_damaged_files_pdfium_repairs_are_read(data: bytes, lines: list[str]) -> None:
    assert text_of(data) == lines


def nested_forms(levels: int) -> bytes:
    """Forms drawing the next form ten times, `levels` deep: 10 ** levels letters drawn."""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
        b" /Resources << /XObject << /X 100 0 R >> >> /Contents 4 0 R >>",
        4: stream(b"/X Do"),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for level in range(levels):
        if level == levels - 1:
            body, resources = b"BT /F1 1 Tf 0 0 Td (a) Tj ET", b"<< /Font << /F1 5 0 R >> >>"
        else:
            body = b" ".join([b"/X Do"] * 10)
            resources = b"<< /XObject << /X %d 0 R >> >>" % (101 + level)
        objects[100 + level] = stream(
            body, b"/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources " + resources
        )
    return raw_pdf(objects)


def test_forms_nested_deep_and_wide_are_read_quickly() -> None:
    """100,000 uses of one form, five levels deep: PDFium draws its letter once per place."""
    assert text_of(nested_forms(5)) == ["a"]


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


@settings(deadline=None)
@given(
    st.lists(st.one_of(st.none(), st.lists(st.integers(0, 7), max_size=3)), min_size=1, max_size=8),
    st.integers(-1, 10**9),
)
def test_any_page_tree_gives_content_or_a_clear_error(
    nodes: list[list[int] | None], count: int
) -> None:
    """Page trees of shared nodes, cycles, missing nodes and wrong counts: each node is a
    page (None) or names the nodes below it."""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [10 0 R] /Count %d >>" % count,
        4: stream(b"BT /F1 12 Tf 72 720 Td (Hello world) Tj ET"),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for i, kids in enumerate(nodes):
        if kids is None:
            objects[10 + i] = (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
                b" /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            )
        else:
            named = b" ".join(b"%d 0 R" % (10 + k) for k in kids)
            objects[10 + i] = b"<< /Type /Pages /Parent 2 0 R /Kids [%s] /Count %d >>" % (
                named,
                len(kids),
            )
    result = outcome(raw_pdf(objects), "tree.pdf")
    assert isinstance(result, Content) or result.startswith("tree.pdf: ")


# Cut short or whole: the decision looks at the last %%EOF and what follows it (D-395, as
# applied after review round 1 of #188, M1 and S1).

TAILS = {
    "4-kb-zeros": bytes(4096),
    "10-kb-zeros": bytes(10_000),
    "1-mb-zeros": bytes(1 << 20),
    "web-page": HTML,
}


@pytest.mark.parametrize("tail", TAILS.values(), ids=TAILS.keys())
@pytest.mark.parametrize("paper", PAPERS, ids=[paper.stem for paper in PAPERS])
def test_a_whole_corpus_paper_with_bytes_after_its_end_is_not_cut_short(
    paper: Path, tail: bytes
) -> None:
    """The decision only, on all seven papers: PDFium opens the file and the checks before
    any page is read pass. Past 4 KB of trailing bytes PDFium rebuilds the cross-reference
    table, which the first rule of D-395 took for a cut."""
    data = paper.read_bytes() + tail
    document = pdfium.PdfDocument(data)
    try:
        pdf._check(document, paper.name, data)
    finally:
        document.close()


@pytest.mark.parametrize("tail", TAILS.values(), ids=TAILS.keys())
def test_a_paper_with_bytes_after_its_end_reads_the_same_lines(tail: bytes) -> None:
    """The whole read, on the smallest paper, so the fast suite stays fast."""
    paper = CORPUS / "joss2021-waskom-seaborn.pdf"
    padded = read_pdf(paper.read_bytes() + tail, paper.name)
    assert padded.pages == smallest_paper_alone().pages


@cache
def smallest_paper_alone() -> Content:
    paper = CORPUS / "joss2021-waskom-seaborn.pdf"
    return read_pdf(paper.read_bytes(), paper.name)


def test_a_file_cut_inside_an_incremental_update_is_cut_short() -> None:
    """Review S1 of #188: the earlier revision's %%EOF and startxref are whole, so PDFium
    would read that revision, a page short, without a word."""
    original = make_pdf([Text("first page", 50, 50)])
    updated = with_page_added(original, "second page")
    assert text_of(updated) == ["first page", "second page"]
    for cut in (len(original) + 50, len(updated) - 30):
        with pytest.raises(ExtractionError) as error:
            read_pdf(updated[:cut], "update.pdf")
        assert str(error.value) == CUT_SHORT.format(name="update.pdf")


def test_a_corpus_paper_cut_inside_an_incremental_update_is_cut_short() -> None:
    paper = CORPUS / "joss2021-waskom-seaborn.pdf"
    original = paper.read_bytes()
    updated = with_page_added(original, "an added page")
    assert len(read_pdf(updated, paper.name).pages) == 5
    with pytest.raises(ExtractionError, match="cut short"):
        read_pdf(updated[: len(original) + 50], paper.name)


def test_a_file_without_any_eof_is_cut_short() -> None:
    """Without a %%EOF PDFium doesn't trust the cross-reference table and rebuilds it, so a
    whole file whose writer left %%EOF out can't be told from a cut one; both are refused."""
    whole = one_page_pdf()
    for data in (whole.replace(b"%%EOF", b""), whole[: whole.index(b"xref")]):
        with pytest.raises(ExtractionError) as error:
            read_pdf(data, "cut.pdf")
        assert str(error.value) == CUT_SHORT.format(name="cut.pdf")
