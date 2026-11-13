"""PDF extraction on small made-up PDFs and broken files (Issue #23, D-63, D-65).

Extraction records what the PDF holds and decides nothing; each test shows one thing it must
record faithfully, or one file it must refuse with a clear message.
"""

import threading
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pdf_maker import HEIGHT, Mark, Rect, Text, in_form, make_pdf, outlined_pdf, width

from sci2audio.core import Content, Metadata, OutlineEntry, SourceFormat
from sci2audio.extraction import ExtractionError, extract_pdf, read_pdf
from sci2audio.extraction.pdf import (
    _GENERATED,
    _SPACE,
    OUTLINE_DEPTH,
    _Char,
    _char_text,
    _Line,
    _style,
)

pytestmark = pytest.mark.timeout(60)

TESTS = Path(__file__).resolve().parents[1]
FIXTURES = TESTS / "fixtures"
BROKEN = FIXTURES / "broken"
PAPER = TESTS / "corpus" / "papers" / "acl2023-hardt-ellipsis.pdf"
EPUB = TESTS / "corpus" / "epub" / "wells-the-time-machine.epub"


def lines_of(data: bytes) -> list[str]:
    return [line.text for line in read_pdf(data, "made.pdf").pages[0].lines]


def test_two_columns_on_one_baseline_stay_two_lines() -> None:
    data = make_pdf([Text("end of a left line", 50, 100), Text("start of a right", 320, 100)])
    assert lines_of(data) == ["end of a left line", "start of a right"]


def test_lines_keep_the_order_the_file_stores_them_in() -> None:
    data = make_pdf([Text("stored first, lower", 50, 300), Text("stored second, higher", 50, 100)])
    assert lines_of(data) == ["stored first, lower", "stored second, higher"]


def test_runs_record_font_size_bold_and_italic() -> None:
    data = make_pdf(
        [
            Text("Heading", 50, 60, font="Helvetica-Bold", size=14),
            Text("leaning", 50, 100, font="Helvetica-Oblique"),
        ]
    )
    heading, leaning = (line.runs[0] for line in read_pdf(data, "made.pdf").pages[0].lines)
    assert (heading.font, heading.size, heading.bold, heading.italic) == (
        "Helvetica-Bold",
        14.0,
        True,
        False,
    )
    assert (leaning.size, leaning.bold, leaning.italic) == (10.0, False, True)


def test_a_raised_smaller_number_stays_in_its_line_as_its_own_run() -> None:
    data = make_pdf([Text("E = mc", 50, 200), Text("2", 81, 196, size=6)])
    (line,) = read_pdf(data, "made.pdf").pages[0].lines
    assert [(run.text, run.size) for run in line.runs] == [("E = mc", 10.0), ("2", 6.0)]


# Spaces PDFium adds itself (#36, D-274 to D-276)


def test_a_mark_set_close_between_a_word_and_a_full_stop_gets_no_space() -> None:
    """Arsiwalla p3 "qualia1.": PDFium adds a space where the baseline changes, however
    close the letters stand; the page prints none."""
    end = 100 + width("qualia")
    mark = end + 0.3 + width("1", size=7)
    data = make_pdf(
        [Text("qualia", 100, 100), Text("1", end + 0.3, 96, size=7), Text(".", mark + 0.5, 100)]
    )
    assert lines_of(data) == ["qualia1."]


def test_a_mark_after_a_word_space_keeps_the_space() -> None:
    """Hardt p3 "sets. 1": 5 pt of white stand before the mark."""
    end = 100 + width("sets.")
    assert lines_of(make_pdf([Text("sets.", 100, 100), Text("1", end + 5, 96, size=7)])) == [
        "sets. 1"
    ]


def test_a_subscript_then_a_word_after_a_word_space() -> None:
    end = 100 + width("x")
    after = end + 0.2 + width("i", size=7)
    data = make_pdf(
        [Text("x", 100, 100), Text("i", end + 0.2, 103, size=7), Text("is", after + 3, 100)]
    )
    assert lines_of(data) == ["xi is"]


def test_white_after_a_stacked_script_is_measured_from_the_row_s_letters() -> None:
    """Liu p2 "J^1st_0[n": the subscript "0", stored after the superscript, starts back
    under it and becomes a line of its own; the "[" after it stands close to the end of
    "1st", not 4 pt after the "0"."""
    j = 100 + width("J")
    end = j + width("1st", size=7)
    data = make_pdf(
        [
            Text("J", 100, 100),
            Text("1st", j, 96, size=7),
            Text("0", j, 103, size=7),
            Text("[n", end + 0.5, 100),
        ]
    )
    assert lines_of(data) == ["J1st", "0[n"]


@pytest.mark.parametrize("start", [100, 90])
@pytest.mark.parametrize("leading", [10.5, 11, 12])
def test_a_wrapped_line_keeps_the_spaces_after_its_scripts(start: float, leading: float) -> None:
    """Review M1 of #128: the next printed line of a paragraph starts back under the line
    above and, with tight leading, overlaps its loose boxes; it is no script stacked under
    that line, so its spaces are measured from its own letters ("word1 is", not "word1is")."""
    font = "Times-Roman"
    y = 100 + leading
    end = 100 + width("Then the word", font)
    mark = end + 0.3 + width("1", font, 7)
    data = make_pdf(
        [
            Text("A line of text set above the next one, ending in x", start, 100, font),
            Text(
                "2",
                start + width("A line of text set above the next one, ending in x", font),
                103,
                font,
                7,
            ),
            Text("Then the word", 100, y, font),
            Text("1", end + 0.3, y - 4, font, 7),
            Text("is next.", mark + 4, y, font),
        ]
    )
    assert lines_of(data)[-1] == "Then the word1 is next."


@pytest.mark.parametrize(
    ("numerator", "denominator", "after", "white", "printed"),
    [
        ("1", "2", "{L", 0.3, "j = 1 2{L"),  # Liu: j = 1/2 {L, v}
        ("3", "2", "at", 2.5, "j = 3 2 at"),  # Liu: v = 3/2 at
        ("1", "22", "t", 0.3, "j = 1 22t"),  # Liu: 1/22 sigma
    ],
)
def test_digits_of_a_stacked_fraction_keep_their_space(
    numerator: str, denominator: str, after: str, white: float, printed: str
) -> None:
    """Review M2 of #128: a fraction 1/2 set as numerator over denominator must not read
    "12" (twelve). The denominator starts back under the numerator, so their letters touch
    along the line; the space PDFium adds between two digits on different baselines stays."""
    x = 100 + width("j = ")
    top, bottom = width(numerator, size=7), width(denominator, size=7)
    wide = max(top, bottom)
    data = make_pdf(
        [
            Text("j = ", 100, 100),
            Text(numerator, x + (wide - top) / 2, 96, size=7),
            Text(denominator, x + (wide - bottom) / 2, 104, size=7),
            Text(after, x + wide + white, 100),
        ]
    )
    assert lines_of(data) == [printed]


def char(text: str, u0: float, u1: float, base: float = 100.0, size: float = 10.0) -> _Char:
    style = ("Times", size, False, False)
    return _Char(text, style, (u0, base - size, u1, base), 0.0, u0, u1, base - size, base, base)


@pytest.mark.parametrize(
    ("before", "after", "space", "spaced"),
    [
        (char("N", 0, 8), char("|", 7.9, 10), _GENERATED, False),  # touching: "|N|"
        (char("N", 0, 8), char("|", 7.9, 10), _SPACE, True),  # the file's own space stays
        (char("f", 0, 5), char("a", 5.3, 10), _GENERATED, True),  # "of a": f reaches over
        (char("1", 0, 4, 96, 7), char(".", 4.5, 7), _GENERATED, False),  # 0.05 em: script
        (char("1", 0, 4, 96, 7), char(".", 4.5, 7), _SPACE, True),  # a real space stays
        (char("2", 0, 4, 96, 7), char(")", 5.2, 8), _GENERATED, False),  # 0.12 em: fraction
        (char(".", 0, 3), char("1", 4.5, 8, 96, 7), _GENERATED, True),  # 0.15 em: kept
        (char("x", 0, 5), char("y", 6, 10), None, False),  # no space at all
    ],
)
def test_which_spaces_are_kept(
    before: _Char, after: _Char, space: str | None, spaced: bool
) -> None:
    line = _Line()
    line.add(before, None)
    line.add(after, space)
    assert (1 in line.spaces) is spaced


def test_text_turned_upwards_reads_as_one_line() -> None:
    data = make_pdf([Text("arXiv:1234.5678v1 [cs.CL]", 20, 600, size=20, turned=True)])
    (line,) = read_pdf(data, "made.pdf").pages[0].lines
    assert line.text == "arXiv:1234.5678v1 [cs.CL]"
    assert line.box is not None
    assert line.box.y1 - line.box.y0 > line.box.x1 - line.box.x0  # tall and narrow


def test_boxes_are_measured_from_the_top_left() -> None:
    page = read_pdf(make_pdf([Text("near the top", 50, 40), Rect(50, 300, 250, 301)]), "m.pdf")
    (line,) = page.pages[0].lines
    (rule,) = page.pages[0].drawings
    assert line.box is not None
    assert 25 < line.box.y0 < line.box.y1 < 45
    assert (rule.box.x0, rule.box.y0, rule.box.x1, rule.box.y1) == (50, 300, 250, 301)


def test_drawings_inside_a_form_get_page_positions() -> None:
    # The rectangle sits at x 100..300, y 100..200 on its own page; the form halves it and
    # moves it 10 pt right and 20 pt up (PDF space): 60..160 across, 430..480 down.
    data = in_form(make_pdf([Rect(100, 100, 300, 200)]), scale=0.5, dx=10, dy=20)
    (drawing,) = read_pdf(data, "form.pdf").pages[0].drawings
    box = drawing.box
    assert (box.x0, box.y0, box.x1, box.y1) == (60, 430, 160, 480)


def test_pages_ids_and_source_are_recorded(tmp_path: Path) -> None:
    file = tmp_path / "two pages.pdf"
    file.write_bytes(make_pdf([Text("one", 50, 100)], [Text("two", 50, 100), Rect(1, 2, 3, 4)]))
    content = extract_pdf(file)
    assert content.source.name == "two pages.pdf"
    assert content.source.format is SourceFormat.PDF
    assert len(content.source.sha256) == 64
    assert [(p.number, p.width, p.height) for p in content.pages] == [
        (1, 600, HEIGHT),
        (2, 600, HEIGHT),
    ]
    assert sorted(content.items()) == ["p1-l1", "p2-d1", "p2-l1"]


def test_extraction_is_deterministic() -> None:
    data = make_pdf([Text("same every time", 50, 100), Rect(10, 10, 20, 20)])
    assert read_pdf(data, "a.pdf") == read_pdf(data, "a.pdf")


def test_threads_reading_at_once_do_not_crash() -> None:
    # PDFium is not thread-safe (KB audit "PDFium thread-safety crash"): the lock must hold.
    data = make_pdf([Text(f"line {i}", 50, 20 + 12 * i) for i in range(40)])
    expected = read_pdf(data, "t.pdf")
    results: list[Content] = []

    def work() -> None:
        results.extend(read_pdf(data, "t.pdf") for _ in range(5))

    threads = [threading.Thread(target=work) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [expected] * 30


# The outline: bookmarks as stored, in the file's order, levels from 1 (#24, D-263 to D-268).


def test_bookmarks_keep_their_order_nesting_and_pages() -> None:
    data = outlined_pdf(
        3,
        (
            Mark("1 Introduction", 1, (Mark("1.1 Setup", 1), Mark("1.2 Data ", 2))),
            Mark("2 Results", 3, (Mark("2.1 Speed", 3, (Mark("Notes", 3),)),)),
            Mark("Appendix", 3),
        ),
    )
    assert read_pdf(data, "m.pdf").outline == (
        OutlineEntry("1 Introduction", 1, 1),
        OutlineEntry("1.1 Setup", 2, 1),
        OutlineEntry("1.2 Data ", 2, 2),  # the trailing space stays (D-266)
        OutlineEntry("2 Results", 1, 3),
        OutlineEntry("2.1 Speed", 2, 3),
        OutlineEntry("Notes", 3, 3),
        OutlineEntry("Appendix", 1, 3),
    )


def test_a_bookmark_target_may_be_a_goto_action_or_missing() -> None:
    data = outlined_pdf(
        2,
        (Mark("By action", 2, goto=True), Mark("No target"), Mark("Past the end", 7), Mark("", 1)),
    )
    assert read_pdf(data, "m.pdf").outline == (
        OutlineEntry("By action", 1, 2),
        OutlineEntry("No target", 1),
        OutlineEntry("Past the end", 1),  # points at a page the file does not have
        OutlineEntry("", 1, 1),  # an empty title is kept (D-266)
    )


def test_bookmark_titles_are_decoded_as_stored() -> None:
    data = outlined_pdf(
        1,
        (
            Mark("Über die Größe ∑ ✓"),  # UTF-16 with a byte-order mark
            Mark(b"Caf\xe9 \x8eQuoted\x8d"),  # PDFDocEncoding: é, ” and “
            Mark(b"\xfe\xff\xd8\x00\x00A"),  # UTF-16 with a lone surrogate
            Mark(b"A\x00B"),  # control characters: PDFium reads them as spaces
            Mark("x\ny\x01"),
        ),
    )
    titles = [entry.title for entry in read_pdf(data, "m.pdf").outline]
    assert titles == ["Über die Größe ∑ ✓", "Café ”Quoted“", "\ufffdA", "A B", "x y "]


def test_a_file_without_bookmarks_has_an_empty_outline() -> None:
    assert read_pdf(outlined_pdf(1, ()), "m.pdf").outline == ()
    assert read_pdf(make_pdf([Text("no outline", 50, 100)]), "m.pdf").outline == ()


def test_a_bookmark_loop_ends_and_the_pages_are_still_read() -> None:
    """A damaged outline gives what could be read and never fails the file (D-268)."""
    data = outlined_pdf(2, (Mark("a", 1, (Mark("b", 2),)), Mark("c", 2)), circular=True)
    content = read_pdf(data, "m.pdf")
    assert content.outline == (
        OutlineEntry("a", 1, 1),
        OutlineEntry("b", 2, 2),
        OutlineEntry("c", 1, 2),
    )
    assert [line.text for page in content.pages for line in page.lines] == ["Page 1", "Page 2"]

    # a child list that points back at an ancestor (review of #133, N3)
    data = outlined_pdf(2, (Mark("a", 1, (Mark("b", 2, loop=True),)), Mark("c", 2)))
    content = read_pdf(data, "m.pdf")
    assert content.outline == (
        OutlineEntry("a", 1, 1),
        OutlineEntry("b", 2, 2),
        OutlineEntry("c", 1, 2),
    )
    assert [line.text for page in content.pages for line in page.lines] == ["Page 1", "Page 2"]


def test_bookmarks_deeper_than_the_limit_are_left_out() -> None:
    """D-267: a real document stops long before; this bounds a hostile file."""
    mark = Mark("deepest", 1)
    for depth in range(OUTLINE_DEPTH, 0, -1):
        mark = Mark(f"level {depth}", 1, (mark,))
    levels = [entry.level for entry in read_pdf(outlined_pdf(1, (mark,)), "m.pdf").outline]
    assert levels == list(range(1, OUTLINE_DEPTH + 1))


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


def test_metadata_is_recorded_as_the_file_gives_it() -> None:
    # PDFium can't write an Info dictionary or /Lang, so this file is stored (fixtures/README.md).
    assert extract_pdf(FIXTURES / "metadata.pdf").metadata == Metadata(
        title="A Made-Up Paper",
        authors=("Lovelace, Ada; Babbage, Charles",),  # kept whole: any split is a guess
        date="2024-03-05",
        language="en-GB",
    )


@pytest.mark.parametrize(
    ("code", "hyphen", "text"),
    [
        pytest.param(ord("a"), False, "a", id="letter"),
        pytest.param(0, False, "\ufffd", id="no-unicode-mapping-is-kept-as-unknown"),
        pytest.param(0x110000, False, "\ufffd", id="beyond-unicode"),
        pytest.param(0x02, True, "-", id="pdfium-line-end-hyphen"),
        pytest.param(ord("-"), True, "-", id="printed-hyphen"),
        pytest.param(0xAD, True, "\u00ad", id="soft-hyphen-stays-soft"),
        pytest.param(ord(" "), False, None, id="space-separates-words"),
        pytest.param(0x07, False, None, id="control-code-separates-words"),
    ],
)
def test_character_codes(code: int, hyphen: bool, text: str | None) -> None:
    assert _char_text(code, hyphen) == text


@pytest.mark.parametrize(
    ("font", "weight", "flags", "bold", "italic"),
    [
        pytest.param("NimbusRomNo9L-Medi", 400, 0, True, False, id="urw-medi-is-bold"),
        pytest.param("Roboto-Medium", 500, 0, False, False, id="medium-is-not-bold"),
        pytest.param("HelveticaNeue-Medium", 500, 0, False, False, id="medium-again"),
        pytest.param("CMBX12", 545, 0, True, False, id="computer-modern-bold"),
        pytest.param("SomeFont", 700, 0, True, False, id="weight-700"),
        pytest.param("SomeFont", 400, 1 << 18, True, False, id="force-bold-flag"),
        pytest.param("SomeFont", 400, 1 << 6, False, True, id="italic-flag"),
        pytest.param("CMTI10", 400, 0, False, True, id="computer-modern-italic"),
        pytest.param("SFBX1095", 400, 0, True, False, id="cm-super-bold"),
        pytest.param("ABCDEF+ECBX1200", 400, 0, True, False, id="ec-bold-subset"),
        pytest.param("SFBI1000", 400, 0, True, True, id="cm-super-bold-italic"),
        pytest.param("SFTI1095", 400, 0, False, True, id="cm-super-italic"),
        pytest.param("SFSL1200", 400, 0, False, True, id="cm-super-slanted"),
        pytest.param("SFRM1095", 400, 0, False, False, id="cm-super-roman"),
        pytest.param("SFSX1200", 400, 0, True, False, id="cm-super-sans-bold"),
        pytest.param("SFBL1000", 400, 0, True, True, id="cm-super-bold-slanted"),
        pytest.param("SFSI1000", 400, 0, False, True, id="cm-super-sans-italic"),
        pytest.param("SFRB1000", 400, 0, True, False, id="cm-super-roman-bold"),
        pytest.param("SFCC1000", 400, 0, False, False, id="cm-super-caps-stays-plain"),
        pytest.param("SFUI1000", 400, 0, False, False, id="cm-super-upright-italic-is-plain"),
        pytest.param("SFProText-Regular", 400, 0, False, False, id="sf-pro-is-not-cm-super"),
        pytest.param("", 400, 0, False, False, id="unknown-font"),
    ],
)
def test_bold_and_italic(font: str, weight: int, flags: int, bold: bool, italic: bool) -> None:
    assert _style(font, weight, flags) == (bold, italic)


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
