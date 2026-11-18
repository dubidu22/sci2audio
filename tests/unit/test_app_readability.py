"""Whether a PDF's text can be read aloud (#442 part B, #187; policy D-762, D-772): the
pages `extraction.legibility` finds unreadable stop the audiobook when they hold more than
half of the document's characters, and are named in a warning otherwise. PDF only."""

from __future__ import annotations

import pytest
from core_strategies import contents
from hypothesis import given
from pdf_maker import Text, glyph_number_pdf, joined_pdf, make_pdf

from sci2audio.app.readability import (
    Unreadable,
    page_ranges,
    pages_named,
    stop_message,
    unreadable,
    warning,
)
from sci2audio.core import Content, Page, Source, SourceFormat, TextLine, TextRun
from sci2audio.extraction import legibility, read_pdf

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
