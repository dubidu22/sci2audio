"""Whether a PDF's text can be read aloud (#442 part B, #187; policy D-762, D-772): the
pages `extraction.legibility` finds unreadable stop the audiobook when they hold more than
half of the document's characters, and are named in a warning otherwise. PDF only. The
pages whose letters were recognised from their shapes are named too (#618, AC-442.9)."""

from __future__ import annotations

import pytest
from core_strategies import contents
from hypothesis import event, given
from hypothesis import strategies as st
from pdf_maker import Text, glyph_number_pdf, image_only_pdf, joined_pdf, make_pdf, twin_pdf

from sci2audio.app.readability import (
    Unreadable,
    page_ranges,
    pages_named,
    picture_pages,
    picture_warning,
    recovered_pages,
    recovered_warning,
    stop_message,
    unreadable,
    warning,
)
from sci2audio.core import (
    Box,
    Content,
    Drawing,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.extraction import legibility, read_pdf
from sci2audio.extraction.legibility import MIN_LETTERS

DASH = "\N{EN DASH}"
GERMAN = [
    "Das Buch wurde in einer Zeit geschrieben, in der die Arbeit in den Quartieren",
    "neu gedacht werden musste. Die Menschen, die dort leben, kennen ihre Nachbarn,",
]


def page(number: int, characters: int, unmapped: int = 0) -> Page:
    """A page of `characters` letters ("aa" is no rare pair), `unmapped` of them from
    a font with no Unicode source."""
    line = TextLine(f"p{number}-l1", (TextRun("a" * characters),))
    return Page(number, lines=(line,), unmapped=unmapped)


def pdf(*pages: Page, kind: SourceFormat = SourceFormat.PDF) -> Content:
    return Content(Source("book.pdf", kind), pages)


def glyph_page(number: int, characters: int) -> Page:
    """A page that is all glyph numbers: unreadable by its count."""
    return page(number, characters, unmapped=characters)


# ---- the policy ------------------------------------------------------------------------------


def test_a_readable_pdf_has_nothing_to_say() -> None:
    assert unreadable(pdf(page(1, 300), page(2, 300))) is None


def test_exactly_half_of_the_characters_warns_and_one_more_stops() -> None:
    """D-762: more than half stops; half is a warning only."""
    half = unreadable(pdf(glyph_page(1, 300), page(2, 300)))
    assert half == Unreadable((1,), stops=False)
    more = unreadable(pdf(glyph_page(1, 301), page(2, 300)))
    assert more == Unreadable((1,), stops=True)


def test_the_share_counts_characters_not_pages() -> None:
    """Two short unreadable pages beside one long readable page: a warning; one long
    unreadable page beside two short ones: a stop."""
    few = unreadable(pdf(glyph_page(1, 50), glyph_page(2, 50), page(3, 500)))
    assert few == Unreadable((1, 2), stops=False)
    most = unreadable(pdf(page(1, 50), glyph_page(2, 500), page(3, 50)))
    assert most == Unreadable((2,), stops=True)


def test_a_page_is_named_by_any_of_the_three_measures() -> None:
    """The text check counts too (AC-442.2), not only the font count: private-use letters."""
    broken = Page(1, lines=(TextLine("p1-l1", (TextRun(chr(0xE000) * 60),)),))
    assert legibility(pdf(broken))[0].unreadable
    assert unreadable(pdf(broken, page(2, 10))) == Unreadable((1,), stops=True)


@pytest.mark.parametrize("kind", [SourceFormat.EPUB, SourceFormat.MARKDOWN, SourceFormat.TEXT])
def test_only_a_pdf_is_judged(kind: SourceFormat) -> None:
    """D-772: other formats give their own letters and have no printed pages."""
    assert unreadable(pdf(glyph_page(1, 300), kind=kind)) is None


def test_an_empty_pdf_never_stops() -> None:
    assert unreadable(pdf(Page(1), Page(2))) is None


def test_an_unreadable_names_at_least_one_page() -> None:
    with pytest.raises(ValueError, match="at least one page"):
        Unreadable((), stops=False)


@given(contents())
def test_the_verdict_never_fails_and_names_only_unreadable_pages(content: Content) -> None:
    found = unreadable(content)
    measured = legibility(content)
    bad = [m.number for m in measured if m.unreadable]
    if content.source.format is not SourceFormat.PDF or not bad:
        assert found is None
        return
    assert found is not None
    assert list(found.pages) == bad
    total = sum(m.characters for m in measured)
    held = sum(m.characters for m in measured if m.unreadable)
    assert found.stops is (2 * held > total)


# a page `legibility` reads as readable, or as unreadable by either of two measures: the
# glyph-number count, or the foreign letters (U+FFFD, private use); `contents()` alone never
# makes an unreadable page (#577)
_PAGES = st.one_of(
    st.tuples(st.just("readable"), st.integers(1, 400)),
    st.tuples(st.just("glyphs"), st.integers(1, 400)),
    st.tuples(st.just("foreign"), st.integers(MIN_LETTERS, 400), st.sampled_from("\ufffd\ue000")),
)


@st.composite
def mixed_pdfs(draw: st.DrawFn) -> Content:
    """A PDF of readable and unreadable pages, at least one unreadable, of any sizes."""
    kinds = draw(st.lists(_PAGES, min_size=1, max_size=8))
    if all(kind[0] == "readable" for kind in kinds):
        kinds.insert(draw(st.integers(0, len(kinds))), ("glyphs", draw(st.integers(1, 400))))
    pages = []
    for number, (kind, count, *char) in enumerate(kinds, start=1):
        if kind == "readable":
            pages.append(page(number, count))
        elif kind == "glyphs":
            pages.append(glyph_page(number, count))
        else:
            line = TextLine(f"p{number}-l1", (TextRun(char[0] * count),))
            pages.append(Page(number, lines=(line,)))
    return pdf(*pages)


@given(mixed_pdfs())
def test_the_verdict_on_pdfs_with_unreadable_pages(content: Content) -> None:
    measured = legibility(content)
    bad = {m.number for m in measured if m.unreadable}
    assert bad  # every example reaches the unreadable branch
    found = unreadable(content)
    assert found is not None
    assert set(found.pages) == bad
    assert set(found.pages) <= {p.number for p in content.pages}
    assert list(found.pages) == sorted(found.pages)
    total = sum(p.characters for p in content.pages)
    held = sum(p.characters for p in content.pages if p.number in bad)
    assert found.stops is (2 * held > total)
    event("stops" if found.stops else "warns")


# ---- on PDF files ----------------------------------------------------------------------------


def test_a_pdf_of_glyph_numbers_stops() -> None:
    """The #442 file's kind: a CID font with Identity-H, no ToUnicode, no cmap, no post."""
    content = read_pdf(glyph_number_pdf(GERMAN), "gemeinwesenarbeit.pdf")
    assert unreadable(content) == Unreadable((1,), stops=True)


def test_the_same_pdf_with_its_unicode_map_is_readable() -> None:
    content = read_pdf(glyph_number_pdf(GERMAN, to_unicode=True), "gemeinwesenarbeit.pdf")
    assert unreadable(content) is None


def test_a_glyph_number_page_among_longer_plain_pages_is_a_warning() -> None:
    plain = make_pdf(
        [Text("A plain line of English text that reads well.", 72, 100 + 14 * k) for k in range(8)]
    )
    content = read_pdf(joined_pdf(plain, glyph_number_pdf(GERMAN), plain), "mixed.pdf")
    assert [p.unmapped > 0 for p in content.pages] == [False, True, False]
    assert unreadable(content) == Unreadable((2,), stops=False)


# ---- the words -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pages", "written"),
    [
        ([4], "4"),
        ([4, 5], "4, 5"),
        ([1, 2, 3], f"1{DASH}3"),
        ([7, 1, 3, 2, 9, 10], f"1{DASH}3, 7, 9, 10"),
        ([1, 2, 3, 4, 6, 7, 8, 12], f"1{DASH}4, 6{DASH}8, 12"),
        ([2, 2, 3], "2, 3"),
        ([], ""),
    ],
)
def test_pages_are_written_as_ranges(pages: list[int], written: str) -> None:
    assert page_ranges(pages) == written


def test_the_messages_name_the_pages() -> None:
    assert pages_named([3]) == "page 3"
    assert pages_named([1, 2, 3]) == f"pages 1{DASH}3"
    stop = Unreadable((1, 2, 3), stops=True)
    assert stop_message("book.pdf", stop) == (
        f"book.pdf: the text of pages 1{DASH}3 cannot be read: the PDF's fonts give glyph "
        "numbers or wrong letters there, so the voice would read nonsense; no audiobook is "
        "made from it"
    )
    assert f"pages 1{DASH}3" in warning(stop)
    assert "no audiobook is made" in warning(stop)
    partly = warning(Unreadable((4,), stops=False))
    assert partly.startswith("The text of page 4 cannot be read")
    assert "Leave the chapters on those pages out." in partly


# ---- pages of pictures only (#186) -------------------------------------------------------------


def picture_page(number: int, *lines: str) -> Page:
    """A page holding one picture and `lines` of text."""
    text = tuple(TextLine(f"p{number}-l{k}", (TextRun(line),)) for k, line in enumerate(lines))
    return Page(number, lines=text, pictures=(Picture(f"p{number}-i1"),))


def test_a_page_of_pictures_only_is_named_and_a_blank_page_is_not() -> None:
    content = pdf(page(1, 300), picture_page(2), Page(3), picture_page(4, "A caption."))
    assert picture_pages(content) == (2,)


def test_a_line_of_white_space_only_is_no_text() -> None:
    assert picture_pages(pdf(page(1, 300), picture_page(2, " ", "\t"))) == (2,)


def test_a_page_of_drawings_only_is_not_named() -> None:
    """A scan is a picture; a page of vector lines only is a chart or a rule, not a scan."""
    drawn = Page(2, drawings=(Drawing("p2-d1", Box(0, 0, 10, 10)),))
    assert picture_pages(pdf(page(1, 300), drawn)) == ()


@pytest.mark.parametrize("kind", [SourceFormat.EPUB, SourceFormat.MARKDOWN, SourceFormat.TEXT])
def test_only_a_pdf_has_pages_of_pictures(kind: SourceFormat) -> None:
    """An EPUB's file holding one picture is a cover or a plate, not a scan (D-772)."""
    assert picture_pages(pdf(page(1, 300), picture_page(2), kind=kind)) == ()


def test_a_scanned_page_among_text_pages_of_a_real_pdf() -> None:
    """Extraction gives a scan without a text layer no lines; a scan with recognised text
    (invisible, as text recognition lays it over the picture) has its text."""
    plain = make_pdf([Text("A plain line of English text that reads well.", 72, 100)])
    data = joined_pdf(plain, image_only_pdf(), make_pdf([]), image_only_pdf(ocr_text="Hi"))
    assert picture_pages(read_pdf(data, "scans.pdf")) == (2,)


def boxed_page(number: int, *boxes: Box) -> Page:
    """A US Letter page holding pictures at `boxes` and no text."""
    pictures = tuple(Picture(f"p{number}-i{k}", box) for k, box in enumerate(boxes))
    return Page(number, width=612, height=792, pictures=pictures)


def test_a_page_with_only_a_small_logo_is_not_named() -> None:
    """#605: a publisher's logo on an otherwise blank back page is no scan."""
    logo = boxed_page(2, Box(256, 700, 356, 740))
    assert picture_pages(pdf(page(1, 300), logo)) == ()


def test_a_page_with_a_full_page_picture_is_named() -> None:
    assert picture_pages(pdf(page(1, 300), boxed_page(2, Box(0, 0, 612, 792)))) == (2,)


def test_pictures_count_together_and_their_overlap_once() -> None:
    """Two pictures that cover 60 % of the page together are a scan; one picture of 40 %
    laid twice over itself is not."""
    top, bottom = Box(0, 0, 612, 238), Box(0, 238, 612, 475)
    assert picture_pages(pdf(page(1, 300), boxed_page(2, top, bottom))) == (2,)
    same = Box(0, 0, 612, 317)
    assert picture_pages(pdf(page(1, 300), boxed_page(2, same, same))) == ()


def test_a_picture_beyond_the_page_counts_only_on_it() -> None:
    """A small picture whose box runs far off the page covers only the part on it."""
    off = boxed_page(2, Box(500, 700, 5000, 5000))
    assert picture_pages(pdf(page(1, 300), off)) == ()
    before = boxed_page(2, Box(-5000, -5000, 100, 100))  # starts left of and above it
    assert picture_pages(pdf(page(1, 300), before)) == ()


def test_a_picture_without_a_box_or_a_page_without_a_size_still_counts_as_a_scan() -> None:
    unboxed = Page(2, width=612, height=792, pictures=(Picture("p2-i1"),))
    small_and_unboxed = Page(
        3, width=612, height=792, pictures=(Picture("p3-i0", Box(0, 0, 10, 10)), Picture("p3-i1"))
    )
    unsized = Page(4, pictures=(Picture("p4-i1", Box(0, 0, 10, 10)),))
    assert picture_pages(pdf(page(1, 300), unboxed, small_and_unboxed, unsized)) == (2, 3, 4)


def test_many_small_pictures_are_measured_by_their_sum() -> None:
    """Above the pictures whose overlaps are worked out, their areas are summed: tiles
    that fill 60 % of the page are a scan, scattered tiles that fill 5 % are not."""
    tiles = [
        Box(x * 6.12, y * 7.92, (x + 1) * 6.12, (y + 1) * 7.92)
        for x in range(100)
        for y in range(100)
        if (x + y) % 20 == 0
    ]
    assert len(tiles) > 400
    assert picture_pages(pdf(page(1, 300), boxed_page(2, *tiles))) == ()
    filled = [
        Box(x * 6.12, y * 7.92, (x + 1) * 6.12, (y + 1) * 7.92)
        for x in range(100)
        for y in range(100)
        if y < 60
    ]
    assert picture_pages(pdf(page(1, 300), boxed_page(2, *filled))) == (2,)


def test_above_the_measured_pictures_overlaps_count_as_often_as_they_are_laid() -> None:
    """401 copies of one picture covering 1 % of the page sum to 401 %: named, although
    worked out with their overlap they would cover 1 %."""
    same = Box(0, 0, 61.2, 79.2)
    assert picture_pages(pdf(page(1, 300), boxed_page(2, *[same] * 401))) == (2,)
    assert picture_pages(pdf(page(1, 300), boxed_page(2, *[same] * 400))) == ()


def test_the_picture_warning_names_the_pages() -> None:
    assert picture_warning([7]) == (
        "Page 7 holds no text, only pictures (a scanned page?), so nothing on it is read."
    )
    assert picture_warning([12, 13, 14, 15, 16, 17, 18, 20]) == (
        f"Pages 12{DASH}18, 20 hold no text, only pictures (scanned pages?), so nothing on "
        "them is read."
    )


@given(contents())
def test_the_pages_of_pictures_are_those_with_a_picture_and_no_text(content: Content) -> None:
    named = picture_pages(content)
    if content.source.format is not SourceFormat.PDF:
        assert named == ()
        return
    only_pictures = tuple(
        p.number
        for p in content.pages
        if p.pictures and all(not line.text.strip() for line in p.lines)
    )
    unmeasured = tuple(
        p.number
        for p in content.pages
        if p.number in only_pictures
        and (not p.width or not p.height or any(pic.box is None for pic in p.pictures))
    )
    event(f"named {min(len(named), 2)}")
    event(f"left out {min(len(only_pictures) - len(named), 2)}")
    assert set(unmeasured) <= set(named) <= set(only_pictures)
    assert named == tuple(sorted(named, key=only_pictures.index))


# ---- pages read from the shapes of their letters (#618, AC-442.9) --------------------------

ENGLISH = [
    "The book was written in 1980, at a time when the work in the neighbourhoods had to be",
    "thought anew (see pages 12-14). The people who live there know what is missing: 3/4 of",
]


def test_the_pages_whose_letters_were_recognised_are_named() -> None:
    """A page of an Office font that lost its maps, between plain pages: its letters are
    recognised (PR 1 of #618), and it is the page named; the plain pages are not."""
    plain = make_pdf(
        [Text("A plain line of English text that reads well.", 72, 100 + 14 * k) for k in range(8)]
    )
    data = joined_pdf(plain, twin_pdf(ENGLISH), plain, twin_pdf(ENGLISH, "arial"))
    content = read_pdf(data, "twins.pdf")
    assert [p.recovered > 0 for p in content.pages] == [False, True, False, True]
    assert recovered_pages(content) == (2, 4)
    assert unreadable(content) is None  # recognised, so voiced


def test_a_page_counts_once_any_of_its_characters_was_recognised() -> None:
    recognised = Page(2, lines=page(2, 300).lines, unmapped=300, recovered=1)
    assert recovered_pages(pdf(page(1, 300), recognised, page(3, 300))) == (2,)
    assert recovered_pages(pdf(page(1, 300), glyph_page(2, 300))) == ()


@pytest.mark.parametrize("kind", [SourceFormat.EPUB, SourceFormat.MARKDOWN, SourceFormat.TEXT])
def test_only_a_pdf_names_recognised_pages(kind: SourceFormat) -> None:
    """As `unreadable` (D-772): only a PDF's page is a printed page."""
    recognised = Page(1, lines=page(1, 300).lines, unmapped=300, recovered=300)
    assert recovered_pages(pdf(recognised, kind=kind)) == ()


def test_the_recognised_warning_names_the_pages_and_says_it_may_be_wrong() -> None:
    assert recovered_warning([2]) == (
        "The text of page 2 was recognised from the shapes of its letters: the PDF's fonts "
        "give glyph numbers there instead of letters. The recognised text may hold mistakes."
    )
    assert recovered_warning([3, 1, 2, 7]).startswith(
        f"The text of pages 1{DASH}3, 7 was recognised from the shapes of its letters"
    )
