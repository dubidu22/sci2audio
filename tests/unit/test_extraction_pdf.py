"""PDF extraction on small made-up PDFs (Issue #23, D-63, D-65).

Extraction records what the PDF holds and decides nothing; each test shows one thing it must
record faithfully. Broken and hostile PDFs are in `test_extraction_pdf_broken.py` (#5).
"""

import math
import threading
import unicodedata
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pdf_maker import (
    HEIGHT,
    Mark,
    Rect,
    Text,
    cropped,
    in_form,
    make_pdf,
    one_page_pdf,
    outlined_pdf,
    raw_pdf,
    spread,
    stream,
    turned,
    width,
)

from sci2audio.core import Content, Metadata, OutlineEntry, Page, SourceFormat
from sci2audio.extraction import extract_pdf, read_pdf
from sci2audio.extraction.pdf import (
    _GENERATED,
    _SPACE,
    OUTLINE_DEPTH,
    _accents_onto_letters,
    _Char,
    _char_text,
    _Line,
    _style,
)

pytestmark = pytest.mark.timeout(60)


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
    """#128: the next printed line of a paragraph starts back under the line
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
    """#128: a fraction 1/2 set as numerator over denominator must not read
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


def _fraction(
    numerator: str, denominator: str, back: float, bar: float | None, size: int = 7
) -> bytes:
    """ "so B = " in 10 point, then in `size` point the numerator raised 3.5 pt and the
    denominator 7.5 pt under it, `back` pt further left, both in one text object as TeX
    writes them; `bar` is the height of the rule drawn between them (None: no rule)."""
    rule = b"104.5 601.6 10 %.1f re f " % bar if bar is not None else b""
    content = (
        b"BT /F1 10 Tf 72 600 Td (so B = ) Tj ET "
        b"BT /F1 %d Tf 105 603.5 Td (%s) Tj %.1f -7.5 Td (%s) Tj ET "
        % (size, numerator.encode(), -back, denominator.encode())
        + rule
        + b"BT /F1 10 Tf 118 600 Td (then more) Tj ET"
    )
    return one_page_pdf(content)


@pytest.mark.parametrize(
    ("numerator", "denominator", "back", "bar", "printed", "size"),
    [
        ("1", "h", 0.2, 0.4, "so B = 1 h then more", 7),  # Liu p2: 1 over h-bar
        # TeX keeps the rule's thickness when it sets a fraction smaller: liu's 0.8 pt bar
        # over 5 pt letters is 0.16 em (#323)
        ("1", "h", 0.2, 0.8, "so B = 1 h", 5),  # "then" is over 1 em of 5 pt away: a new line
        ("eE", "h", -2.0, 0.4, "so B = eE h then more", 7),  # Liu p3: eE over h-bar
        ("1", "h", 0.2, None, "so B = 1h then more", 7),  # no rule: a script stack, as before
        ("1", "h", 0.2, 3.0, "so B = 1h then more", 7),  # a rule 3 pt thick is no fraction bar
    ],
)
def test_a_fraction_over_its_bar_keeps_its_space(
    numerator: str, denominator: str, back: float, bar: float | None, printed: str, size: int
) -> None:
    """#202: an inline fraction stored in one line, numerator then denominator, must not
    read as one word ("1h"). The denominator starts back under the numerator, so their
    letters touch along the line; the space PDFium adds between them stays when a fraction
    bar is drawn between the two (D-575), and only then: a superscript over a subscript has
    no bar and stays joined (D-277)."""
    assert lines_of(_fraction(numerator, denominator, back, bar, size))[0] == printed


def test_an_underlined_word_keeps_a_subscript_after_it_joined() -> None:
    """#323: a subscript stored right after an underlined word, tucked
    0.5 pt back under its last letter, stands below the word's baseline but above no bar:
    the underline is under the word, not between the word and the subscript."""
    end = 72 + width("word")
    content = (
        b"BT /F1 10 Tf 72 600 Td (word) Tj ET "
        b"72 598.1 %.2f 0.4 re f "
        % (end - 72)
        + b"BT /F1 7 Tf %.2f 597.5 Td (q) Tj ET " % (end - 0.5)
        + b"BT /F1 10 Tf %.2f 600 Td (then) Tj ET" % (end + 6)
    )
    assert lines_of(one_page_pdf(content)) == ["wordq then"]


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


def test_positions_are_taken_from_the_corner_of_an_offset_crop_box() -> None:
    """#458: a page cut from a larger sheet (crop box 100..500 across, 100..700 up, on a
    600 x 800 sheet) is 400 x 600 and every item on it lies inside it, measured from the
    crop box's top left corner, not the sheet's."""
    sheet = make_pdf([Text("A running head", 120, 120), Rect(120, 130, 380, 131)])
    page = read_pdf(cropped(sheet, (100, 100, 500, 700)), "cut.pdf").pages[0]
    assert (page.width, page.height) == (400, 600)
    (line,) = page.lines
    (rule,) = page.drawings
    assert line.box is not None
    assert rule.box is not None
    for box in (line.box, *(run.box for run in line.runs if run.box), rule.box):
        assert 0 <= box.x0 < box.x1 <= page.width
        assert 0 <= box.y0 <= box.y1 <= page.height
    assert 19.5 < line.box.x0 < 20.5  # x 120 on the sheet, the crop box starts at 100
    assert 5 < line.box.y0 < line.box.y1 < 25  # baseline 120 down the sheet, 20 down the page
    assert (rule.box.x0, rule.box.y0, rule.box.x1, rule.box.y1) == (20, 30, 280, 31)


def test_what_the_crop_box_cuts_off_the_sheet_is_not_read() -> None:
    """One page of a spread: the other page's text and drawings lie on the sheet but outside
    the crop box, so they are not printed (#458). Text outside the sheet itself is kept,
    as before."""
    sheet = make_pdf(
        [
            Text("The page kept", 340, 100),
            Text("The page cut off", 40, 100),
            Rect(40, 110, 200, 111),
            Text("Past the sheet", 620, 100),
        ]
    )
    page = read_pdf(cropped(sheet, (300, 0, 600, 800)), "spread.pdf").pages[0]
    assert [line.text for line in page.lines] == ["The page kept", "Past the sheet"]
    assert page.drawings == ()


def test_a_page_with_its_own_crop_box_at_the_origin_reads_as_before() -> None:
    sheet = make_pdf([Text("near the top", 50, 40), Rect(50, 300, 250, 301)])
    before = read_pdf(sheet, "m.pdf")
    after = read_pdf(cropped(sheet, (0, 0, 600, 800), media=(0, 0, 600, 800)), "m.pdf")
    assert after.pages == before.pages


def test_a_crop_box_cuts_off_the_sheet_also_when_the_media_box_is_inherited() -> None:
    """#543: a spread cut into two pages by their crop boxes, with the one media box on the
    /Pages node: each page reads only its half. Text outside the sheet itself is kept."""
    texts = [
        Text("The left page", 72, 80),
        Text("The right page", 672, 80),
        Text("Past the sheet", 1250, 80),
    ]
    for inherited in (True, False):
        content = read_pdf(spread(texts, inherited=inherited), "spread.pdf")
        assert [[line.text for line in page.lines] for page in content.pages] == [
            ["The left page", "Past the sheet"],
            ["The right page", "Past the sheet"],
        ], inherited
        right = content.pages[1].lines[0].box
        assert right is not None
        assert 71.5 < right.x0 < 72.5  # from the right page's own corner


def _boxes(page: Page) -> list[tuple[float, ...]]:
    boxes = []
    for line in page.lines:
        for box in (line.box, *(run.box for run in line.runs)):
            assert box is not None
            boxes.append((box.x0, box.y0, box.x1, box.y1))
    boxes += [(d.box.x0, d.box.y0, d.box.x1, d.box.y1) for d in page.drawings]
    return boxes


@pytest.mark.parametrize("turn", [90, 180, 270])
def test_a_turned_page_is_read_as_shown(turn: int) -> None:
    """#537: a page stored unturned and shown through /Rotate reads like the same page set
    upright: same size, same lines in the same order, positions inside the page as shown,
    and text that reads left to right when shown at angle 0, so its letters join into lines
    (a side stamp turned on the shown page stays turned)."""
    items: list[Text | Rect] = [
        Text("First row of the page", 72, 80),
        Text("Second row of the page", 72, 100),
        Rect(72, 110, 300, 111),
        Text("A side stamp", 560, 600, turned=True),
    ]
    upright = read_pdf(make_pdf(items), "upright.pdf").pages[0]
    page = read_pdf(turned(make_pdf(items), turn), "turned.pdf").pages[0]
    assert page.width is not None
    assert page.height is not None
    assert (page.width, page.height) == (upright.width, upright.height)
    assert [line.text for line in page.lines] == [line.text for line in upright.lines]
    assert [len(line.runs) for line in page.lines] == [len(line.runs) for line in upright.lines]
    got, want = _boxes(page), _boxes(upright)
    assert len(got) == len(want)
    for box, expected in zip(got, want, strict=True):
        assert box == pytest.approx(expected, abs=0.01)
        assert 0 <= box[0] <= box[2] <= page.width
        assert 0 <= box[1] <= box[3] <= page.height


@pytest.mark.parametrize("turn", [0, 90, 270])
def test_slightly_skewed_words_on_either_side_of_level_read_as_one_line(turn: int) -> None:
    """Words skewed by +0.2, -0.2 and +0.2 degrees (a scan's text layer) stand at angles
    either side of 0 and 2π: they are one line, upright and on a turned page, where text
    that reads left to right sits at 0 (#559)."""

    def word(x: float, deg: float, text: bytes) -> bytes:
        cos, sin = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        return b"BT /F1 12 Tf %.6f %.6f %.6f %.6f %g 700 Tm (%s) Tj ET\n" % (
            cos,
            sin,
            -sin,
            cos,
            x,
            text,
        )

    data = one_page_pdf(
        word(72, 0.2, b"Alpha") + word(110, -0.2, b"Beta") + word(140, 0.2, b"Gamma")
    )
    page = read_pdf(turned(data, turn) if turn else data, "skewed.pdf").pages[0]
    assert [line.text for line in page.lines] == ["Alpha Beta Gamma"]


def test_a_landscape_table_turned_into_a_portrait_paper_reads_its_rows_in_order() -> None:
    """#537 end to end: a landscape page (800 x 600 as shown) stored on portrait paper with
    /Rotate 90, holding a table: layout reads it exactly as the same page set upright, its
    rows from top to bottom."""
    from sci2audio.core import to_data
    from sci2audio.layout import build_document

    rows = [("Sample", "Width", "Depth")] + [
        (f"Probe {n}", f"{n}.5 mm", f"{n}0 m") for n in range(1, 9)
    ]
    content = b"".join(
        b"BT /F1 11 Tf %d %d Td (%s) Tj ET\n" % (x, 520 - 20 * k, cell.encode())
        for k, row in enumerate(rows)
        for x, cell in zip((80, 330, 580), row, strict=True)
    )
    landscape = one_page_pdf(content, media_box=b"[0 0 800 600]")
    shown = build_document(read_pdf(landscape, "table.pdf"))
    document = build_document(read_pdf(turned(landscape, 90), "table.pdf"))
    assert to_data(document.blocks) == to_data(shown.blocks)
    text = "\n".join(block.text for block in document.blocks)
    places = [text.index(f"Probe {n}") for n in range(1, 9)]
    assert places == sorted(places)


def test_drawings_inside_a_form_get_page_positions() -> None:
    # The rectangle sits at x 100..300, y 100..200 on its own page; the form halves it and
    # moves it 10 pt right and 20 pt up (PDF space): 60..160 across, 430..480 down. The
    # caption is there because a PDF without any text is refused (D-393).
    data = in_form(
        make_pdf([Rect(100, 100, 300, 200), Text("A caption", 100, 230)]), scale=0.5, dx=10, dy=20
    )
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

    # a child list that points back at an ancestor (#133)
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


def test_metadata_is_recorded_as_the_file_gives_it() -> None:
    # PDFium can't write an Info dictionary or /Lang, so the file is written object by object.
    data = raw_pdf(
        {
            1: b"<< /Type /Catalog /Pages 2 0 R /Lang (en-GB) >>",
            2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200]"
            b" /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            4: stream(b"BT /F1 12 Tf 20 150 Td (A made-up paper) Tj ET"),
            5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            6: b"<< /Title (A Made-Up Paper) /Author (Lovelace, Ada; Babbage, Charles)"
            b" /CreationDate (D:20240305120000Z) >>",
        },
        trailer=b"/Info 6 0 R",
    )
    assert read_pdf(data, "m.pdf").metadata == Metadata(
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


def test_a_journal_cut_from_bigger_sheets_reads_on_across_its_heads_and_notes() -> None:
    """#458 end to end: pages cut from the top of bigger sheets (crop box 90..510 across,
    300..800 up: 420 x 500), each with a ruled running head that prints the page number
    in its line, and a note under a short rule in the page's lower half. Measured from the
    sheet's corner the note rule would stand at the top of the page and be no footnote
    rule; from the crop box's corner the note is a footnote, the heads are page furniture
    and the sentence across the page break is one paragraph."""
    from sci2audio.core import BlockKind
    from sci2audio.layout import build_document

    full = "words set in the running text of this page fill the line"
    pages = []
    for n in range(1, 5):
        printed = n + 60
        head = f"Tests in Print \u00b7 {printed}" if n % 2 else f"{printed} \u00b7 Journal of Tests"
        rows = [full] * 18  # the last row is full and ends inside a sentence
        if n > 1:
            rows[0] = "across the page break and ends here. " + full
        x = 90 + 40
        items: list[Text | Rect] = [Text(head, x, 40), Rect(x, 43, x + 320, 43.6)]
        items += [Text(row, x, 70 + 12 * k) for k, row in enumerate(rows)]
        items += [Rect(x, 300, x + 100, 300.4), Text(str(n), x, 312, size=6)]
        items += [Text(f"A note on page {n} in small letters.", x + 5, 312, size=8)]
        pages.append(items)
    data = cropped(make_pdf(*pages), (90, 300, 510, 800))
    document = build_document(read_pdf(data, "journal.pdf"))
    heads = [b.text for b in document.blocks if b.kind is BlockKind.FURNITURE]
    assert heads == [
        "Tests in Print \u00b7 61",
        "62 \u00b7 Journal of Tests",
        "Tests in Print \u00b7 63",
        "64 \u00b7 Journal of Tests",
    ]
    notes = [(b.label, b.text) for b in document.blocks if b.kind is BlockKind.FOOTNOTE]
    assert [label for label, _ in notes] == ["1", "2", "3", "4"]
    assert any(
        f"{full}\nacross the page break" in b.text and b.kind is BlockKind.PARAGRAPH
        for b in document.blocks
    )


# Spacing accents drawn as glyphs of their own (#125)


def advance(text: str) -> float:
    """How far the text moves the pen: `width` measures the ink, so measure between bars."""
    return width(f"|{text}|") - width("||") if text else 0.0


def over(word: str, k: int, accent: str, x: float, y: float) -> Text:
    """The accent drawn over letter `k` of `word`, set from x."""
    middle = x + advance(word[:k]) + advance(word[k]) / 2
    return Text(accent, middle - advance(accent) / 2, y)


def test_an_accent_stored_after_its_word_goes_onto_its_letter() -> None:
    """Chi p6: the acute over the "c" of "Marasovic," is stored after the next word."""
    data = make_pdf(
        [
            Text("Ana Marasovic, Swabha", 50, 100),
            over("Ana Marasovic, Swabha", 12, "\u00b4", 50, 100),
        ]
    )
    assert lines_of(data) == ["Ana Marasović, Swabha"]


def _chars_at(text: str, x: float, top: float, step: float = 5.0) -> _Line:
    """A line of characters `step` wide from x, 12 pt high from `top` (PDFium's loose boxes
    of a 10 pt font)."""
    style = ("NimbusRomNo9L-Regu", 10.0, False, False)
    line = _Line()
    for k, letter in enumerate(text):
        x0, x1 = x + k * step, x + (k + 1) * step
        line.add(_Char(letter, style, (x0, top, x1, top + 12), 0.0, x0, x1, top, top + 12), None)
    return line


def test_an_accent_goes_onto_its_own_line_not_the_one_under_it() -> None:
    """Chi p6: the accent over the "c" of "Marasovic," is stored after "Swabha", and the line
    stored right after it, one line pitch down, has a letter under it too ("Doug"), its box
    touching the accent's; the accent goes onto the line it overlaps, its own."""
    lines = [
        _chars_at("Marasovic,", 435, 72.6),
        _chars_at("Swabha", 492, 72.6),
        _chars_at("\u00b4", 474, 72.5, step=3.4),
        _chars_at("Doug", 465, 84.6),
    ]
    assert _accents_onto_letters(lines) == {2}
    assert [c.text for c in lines[0].chars][8] == "\u0107"
    assert "".join(c.text for c in lines[3].chars) == "Doug"


def test_an_accent_stored_before_its_word_goes_onto_its_letter() -> None:
    """Stored even before the line above (PDFium hands an accent stored right before its own
    line over inside that line, which leaves it for the text step)."""
    data = make_pdf(
        [
            over("Marasovic,", 8, "\u00b4", 50, 100),
            Text("Above", 50, 80),
            Text("Marasovic,", 50, 100),
        ]
    )
    assert lines_of(data) == ["Above", "Marasović,"]


def test_an_accent_with_no_letter_under_it_stays_as_it_is() -> None:
    data = make_pdf(
        [Text("Marasovic,", 50, 100), Text("\u00b4", 200, 100), Text("\u00a8", 50, 140)]
    )
    assert lines_of(data) == ["Marasovic,", "\u00b4", "\u00a8"]


def test_an_accent_inside_a_line_is_left_for_the_text_step() -> None:
    """A TeX accent stored in reading order, before its letter ("Garcia" with the acute set
    before the "i"), is the #65 text step's to join."""
    assert lines_of(make_pdf([Text("Garc\u00b4ia", 50, 100)])) == ["Garc\u00b4ia"]


def test_an_accent_put_onto_its_letter_leaves_the_other_ids_as_numbered() -> None:
    data = make_pdf(
        [
            Text("Marasovic, Swabha", 50, 100),
            over("Marasovic, Swabha", 8, "\u00b4", 50, 100),
            Text("Swayamdipta", 50, 130),
        ]
    )
    found = read_pdf(data, "made.pdf").pages[0].lines
    assert [(line.id, line.text) for line in found] == [
        ("p1-l1", "Marasović, Swabha"),
        ("p1-l3", "Swayamdipta"),
    ]


COMBINING = {
    "\u00b4": "\u0301",
    "`": "\u0300",
    "\u02c6": "\u0302",
    "\u02dc": "\u0303",
    "\u00a8": "\u0308",
    "\u00af": "\u0304",
    "\u00b8": "\u0327",
}


@given(
    st.text("abcdeilmnorsuyzACENOSUZ", min_size=2, max_size=8),
    st.data(),
    st.sampled_from(sorted(COMBINING)),
    st.none() | st.sampled_from(sorted(COMBINING)),
    st.booleans(),
)
@settings(max_examples=30, deadline=None)
def test_an_accent_stored_apart_is_never_a_line_of_its_own(
    word: str, data: st.DataObject, accent: str, second: str | None, first: bool
) -> None:
    """The accent, now and then with a second one stacked on the same letter, is drawn over
    a letter of a word and stored before or after the printed line: it never comes out as a
    line of its own; it goes onto that letter, or, where PDFium hands it over inside the
    line, stays there for the text step. No letter and no accent is lost."""
    k = data.draw(st.integers(0, len(word) - 1))
    start = 50 + width("stored") + 3
    printed = [Text("stored", 50, 100), Text(word, start, 100)]
    printed.append(Text("stored", start + width(word) + 3, 100))
    # the same accent twice in one place PDFium takes for a glyph drawn twice and keeps once
    drawn = [accent] if second in (None, accent) else [accent, second]
    accented = [over(word, k, mark, start, 100) for mark in drawn]
    found = lines_of(make_pdf([*accented, *printed] if first else [*printed, *accented]))
    assert not any(set(text) <= set(COMBINING) for text in found)
    # PDFium's generated spaces around the word vary with where the accent is stored
    read = unicodedata.normalize("NFD", "".join("".join(found).split()))
    marks = set(COMBINING) | set(COMBINING.values())
    assert "".join(c for c in read if c not in marks) == f"stored{word}stored"
    for mark in set(drawn):
        assert read.count(mark) + read.count(COMBINING[mark]) == drawn.count(mark)
    if len(drawn) == 1 and accent not in read:
        composed = word[: k + 1] + COMBINING[accent] + word[k + 1 :]
        assert read == unicodedata.normalize("NFD", f"stored{composed}stored")


def test_two_accents_stacked_on_one_letter_both_go_onto_it() -> None:
    """#671: a circumflex and an acute drawn as glyphs of their own over the
    "e" of "Nguyen" ("Nguyễn" set as "ê" with a second accent). The circumflex is no letter
    for the acute to go onto, though `isalpha` holds for it (category Lm): in either stored
    order both go onto the "e", in the order they are stored, and the page loses neither."""
    for marks in (("\u02c6", "\u00b4"), ("\u00b4", "\u02c6")):
        lines = [
            _chars_at("Nguyen", 100, 72.6),
            _chars_at(marks[0], 120, 72.4, step=5.0),
            _chars_at(marks[1], 120, 72.5, step=5.0),
        ]
        assert _accents_onto_letters(lines) == {1, 2}
        expected = "e" + "".join({"\u02c6": "\u0302", "\u00b4": "\u0301"}[m] for m in marks)
        assert lines[0].chars[4].text == unicodedata.normalize("NFC", expected)
