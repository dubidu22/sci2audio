"""Whether a PDF's text can be read aloud: the app's decision on extraction's measures
(#442 part B, #187; policy D-762, docs/unreadable-pdf-text.md).

A PDF whose fonts lost every Unicode source gives the fonts' glyph numbers as text ("Das
Buch" reads "'DV %XFK"), and voicing it is minutes of nonsense. `extraction.legibility`
measures each page and says which are unreadable; this module decides what the jobs do:

- when the unreadable pages hold more than half of the document's characters (white space
  not counted), the audio job stops before the voice and writes nothing (`stops`);
- otherwise every unreadable page is named in a warning of the report.

PDF only (D-772): a page is a printed page only there; an EPUB's "page" is one of its files
and a text file is one page, and their text comes from the file's own letters, not from a
font.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise

from sci2audio.core import Box, Content, Page, SourceFormat
from sci2audio.extraction import legibility


@dataclass(frozen=True)
class Unreadable:
    """The pages whose text can't be read, and whether the document stops for them."""

    pages: tuple[int, ...]  # `Page.number`: 1 = the first page, as a PDF viewer counts
    stops: bool  # they hold more than half of the document's characters

    def __post_init__(self) -> None:
        if not self.pages:
            raise ValueError("an Unreadable names at least one page")


def unreadable(content: Content) -> Unreadable | None:
    """The unreadable pages of a PDF, or None when there are none (or it is no PDF)."""
    if content.source.format is not SourceFormat.PDF:
        return None
    measured = legibility(content)
    pages = tuple(page.number for page in measured if page.unreadable)
    if not pages:
        return None
    total = sum(page.characters for page in measured)
    bad = sum(page.characters for page in measured if page.unreadable)
    return Unreadable(pages, stops=2 * bad > total)


def pages_named(pages: Iterable[int]) -> str:
    """For the app's English messages: "page 4", or "pages " and the ranges."""
    numbers = set(pages)
    return f"{'page' if len(numbers) == 1 else 'pages'} {page_ranges(numbers)}"


def stop_message(name: str, found: Unreadable) -> str:
    """Why the audio job stops (UnreadableTextError), naming the pages."""
    return (
        f"{name}: the text of {pages_named(found.pages)} cannot be read: the PDF's fonts "
        "give glyph numbers or wrong letters there, so the voice would read nonsense; "
        "no audiobook is made from it"
    )


def warning(found: Unreadable) -> str:
    """The report's warning (#187), naming the pages."""
    where = pages_named(found.pages)
    if found.stops:
        return (
            f"The text of {where} cannot be read: the PDF's fonts give glyph "
            "numbers or wrong letters there. That is most of the document, so no audiobook is "
            "made from it."
        )
    return (
        f"The text of {where} cannot be read: the PDF's fonts give glyph numbers "
        "or wrong letters there, so the voice would read nonsense. Leave the chapters on "
        "those pages out."
    )


# A scan fills its page; a logo or an ornament on a blank page of a born-digital PDF covers
# a small part of it (#605). Below this share of the page, the pictures are no scan.
SCAN_COVER = 0.5
# Overlaps are worked out for this many pictures on a page at most (the work grows with the
# square); a page of more is measured by their summed areas, as if none overlapped.
_MEASURED_PICTURES = 400


def picture_pages(content: Content) -> tuple[int, ...]:
    """The pages of a PDF that hold pictures and no text (#186), the pictures covering at
    least `SCAN_COVER` of the page together (#605): a scanned page in a PDF whose other
    pages have text. A blank page (no text, no picture) is not one, and a line of white
    space only is no text. Vector drawings do not count: a scan is a picture. A picture
    without a box, or a page without a size, can't be measured and still counts as a scan.
    PDF only, as `unreadable` (D-772): an EPUB's page holding only a picture is a cover or
    a plate, not a scan."""
    if content.source.format is not SourceFormat.PDF:
        return ()
    return tuple(
        page.number
        for page in content.pages
        if page.pictures
        and not any(line.text.strip() for line in page.lines)
        and _covered(page) >= SCAN_COVER
    )


def _covered(page: Page) -> float:
    """The share of the page its pictures cover together, overlaps counted once; 1.0 when
    a picture has no box or the page no size, so that page still counts as a scan."""
    if not page.width or not page.height:
        return 1.0
    boxes: list[Box] = []
    for picture in page.pictures:
        if picture.box is None:
            return 1.0
        box = picture.box  # only the part on the page counts
        x0, y0 = max(box.x0, 0.0), max(box.y0, 0.0)
        x1, y1 = min(box.x1, page.width), min(box.y1, page.height)
        if x0 < x1 and y0 < y1:
            boxes.append(Box(x0, y0, x1, y1))
    page_area = page.width * page.height
    summed = sum((b.x1 - b.x0) * (b.y1 - b.y0) for b in boxes)
    if summed < SCAN_COVER * page_area or len(boxes) > _MEASURED_PICTURES:
        return summed / page_area  # their union is no larger than their sum
    return _union_area(boxes) / page_area


def _union_area(boxes: list[Box]) -> float:
    """The area the boxes cover together: summed over the strips between their edges."""
    xs = sorted({x for box in boxes for x in (box.x0, box.x1)})
    area = 0.0
    for left, right in pairwise(xs):
        spans = sorted((b.y0, b.y1) for b in boxes if b.x0 <= left and right <= b.x1)
        height, reached = 0.0, -math.inf
        for y0, y1 in spans:  # each span adds only what lies below the ones before it
            height += max(0.0, y1 - max(y0, reached))
            reached = max(reached, y1)
        area += (right - left) * height
    return area


def picture_warning(pages: Iterable[int]) -> str:
    """The report's warning for the pages that hold only pictures (#186), naming them."""
    numbers = set(pages)
    if len(numbers) == 1:
        return (
            f"Page {page_ranges(numbers)} holds no text, only pictures (a scanned page?), "
            "so nothing on it is read."
        )
    return (
        f"Pages {page_ranges(numbers)} hold no text, only pictures (scanned pages?), so "
        "nothing on them is read."
    )


def page_ranges(pages: Iterable[int]) -> str:
    """Page numbers as people write them, "1-3, 7" with an en dash: a run of three or more
    as a range, a run of two as "4, 5"."""
    numbers = sorted(set(pages))
    parts: list[str] = []
    start = 0
    for i in range(1, len(numbers) + 1):
        if i == len(numbers) or numbers[i] != numbers[i - 1] + 1:
            run = numbers[start:i]
            if len(run) >= 3:
                parts.append(f"{run[0]}\N{EN DASH}{run[-1]}")
            else:
                parts.extend(str(n) for n in run)
            start = i
    return ", ".join(parts)
