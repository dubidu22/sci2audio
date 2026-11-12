"""Page furniture: text on a page that belongs to the page, not to the reading (D-63, TP-01).

Running heads and footers, page numbers, line numbers, side stamps and a printed table of
contents are found line by line, before the reading order, so they never split or join the
text around them. Lines at the top or bottom edge count only if they stand apart from the
body (white between, or smaller letters), so a heading or the last line of a page stays
text. Furniture still becomes blocks (kind `furniture`), so nothing is lost; a text step
removes them from the listening script with a marked edit.
"""

from __future__ import annotations

import re
from collections import defaultdict
from statistics import median

from sci2audio.core import Box, Content, FurnitureRole, Page, TextLine
from sci2audio.layout.geometry import body_size, boxed, line_size, rows, text_area
from sci2audio.layout.settings import LayoutSettings

PAGE_NUMBER = FurnitureRole.PAGE_NUMBER
RUNNING_HEAD = FurnitureRole.RUNNING_HEAD
FOOTER = FurnitureRole.FOOTER
SIDE_STAMP = FurnitureRole.SIDE_STAMP
LINE_NUMBER = FurnitureRole.LINE_NUMBER
CONTENTS = FurnitureRole.CONTENTS
SIDEBAR = FurnitureRole.SIDEBAR

_ROMAN = r"(?=[ivxlcdm])m{0,4}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
_PAGE_NUMBER = re.compile(
    r"^(?:page\s+)?[(\[\-\u2013\u2014]?\s*(?P<label>\d{1,4}|" + _ROMAN + r")\s*[)\]\-\u2013\u2014]?"
    r"(?:\s*(?:of|/)\s*\d{1,4})?$",
    re.IGNORECASE,
)
_CONTENTS_TITLE = {"contents", "tableofcontents"}
_LEADER = re.compile(r"(?:\.\s?){4,}\s*\d{1,4}$|(?:…\s?){2,}\s*\d{1,4}$")


def page_label(text: str) -> str:
    """The page label a page-number line prints: "39" in "- 39 -" or "Page 39 of 40"."""
    found = _PAGE_NUMBER.match(text.strip())
    return found.group("label") if found else text.strip()


Heads = dict[tuple[str, str], list[tuple[int, float]]]  # (band, shape) -> (page, height)


def find_furniture(content: Content, settings: LayoutSettings) -> dict[str, FurnitureRole]:
    """The furniture kind of every line that is furniture, by line id."""
    size = body_size(content) or settings.body_size
    pages = [page for page in content.pages if page.height and page.width]
    heads = _running_heads(pages, size, settings)
    counted = _counted(pages, settings)
    found: dict[str, FurnitureRole] = {}
    for page in pages:
        found.update(_Page(page, size, settings).furniture(heads, counted))
    return found


def _counted(pages: list[Page], settings: LayoutSettings) -> set[str]:
    """Numbers at the outer end of a top or bottom row that go up with the page, as page
    numbers do: one on each of at least `repeat_pages` pages, at the same end of the same
    band, each the page's number plus the same offset (a page number set beside a footer)."""
    seen: dict[tuple[str, int, int], list[str]] = defaultdict(list)
    for page in pages:
        edge = [li for li in page.lines if li.box and _band(li.box, page, settings)]
        for row in rows(edge, settings.row_overlap):
            for side, line in ((0, row[0]), (1, row[-1])):
                text = line.text.strip()
                if text.isdigit() and len(text) <= 4:
                    band = _band(boxed(line), page, settings)
                    seen[band, side, int(text) - page.number].append(line.id)
    return {
        line_id for ids in seen.values() if len(ids) >= settings.repeat_pages for line_id in ids
    }


def _band(box: Box, page: Page, settings: LayoutSettings) -> str:
    height = page.height or 0.0
    if box.y1 <= settings.edge_band * height:
        return "top"
    if box.y0 >= (1 - settings.edge_band) * height:
        return "bottom"
    return ""


def _shape(text: str) -> str:
    """The line with numbers and spacing evened out, to recognise a running head."""
    return re.sub(r"\d+", "#", re.sub(r"\s+", "", text.casefold()))


def _running_heads(pages: list[Page], size: float, settings: LayoutSettings) -> Heads:
    """Where edge lines no larger than body text stand, by band and shape."""
    seen: Heads = defaultdict(list)
    for page in pages:
        for line in page.lines:
            band = _band(line.box, page, settings) if line.box else ""
            if band and line_size(line) <= settings.head_size * size:
                seen[band, _shape(line.text)].append((page.number, boxed(line).y0))
    return seen


def _repeated(places: list[tuple[int, float]], y: float, drift: float) -> int:
    """On how many pages the same shape stands at this height, give or take `drift`."""
    return len({number for number, other in places if abs(other - y) <= drift})


class _Page:
    """One page's lines, measured once for the furniture rules."""

    def __init__(self, page: Page, size: float, settings: LayoutSettings) -> None:
        self.page, self.size, self.settings = page, size, settings
        self.lines = [line for line in page.lines if line.box]
        self.stamps = {line.id for line in self.lines if self._is_stamp(line)}
        flat = [line for line in self.lines if line.id not in self.stamps]
        self.rows = rows(flat, settings.row_overlap)
        self.alone = {row[0].id for row in self.rows if len(row) == 1}
        self.graphics = [g.box for g in (*page.pictures, *page.drawings) if g.box]
        self.apart = self._apart()

    def furniture(self, heads: Heads, counted: set[str]) -> dict[str, FurnitureRole]:
        found = dict.fromkeys(self.stamps, SIDE_STAMP)
        settings, height = self.settings, self.page.height or 0.0
        for line in self.lines:
            if line.id in found:
                continue
            box, text = boxed(line), line.text.strip()
            band = _band(box, self.page, settings)
            loose = line_size(line) < settings.small * self.size or line.id in self.apart
            places = heads.get((band, _shape(text)), [])
            drift = settings.head_drift * self.size
            if band and (line.id in counted or self._is_page_number(line)):
                found[line.id] = PAGE_NUMBER
            elif loose and _repeated(places, box.y0, drift) >= settings.repeat_pages:
                found[line.id] = RUNNING_HEAD
            elif box.y0 >= (1 - settings.footer_band) * height and loose:
                found[line.id] = FOOTER
        body = [line for line in self.lines if line.id not in found]
        found.update(_line_numbers(body, settings))
        found.update(_contents([line for line in body if line.id not in found], settings))
        return found

    def _is_stamp(self, line: TextLine) -> bool:
        """Turned text in the side margin, as tall as a good part of the page (arXiv)."""
        box, settings = boxed(line), self.settings
        width, height = self.page.width or 0.0, self.page.height or 0.0
        in_margin = (
            box.x1 < settings.margin_band * width or box.x0 > (1 - settings.margin_band) * width
        )
        return (
            in_margin
            and box.y1 - box.y0 > settings.stamp_ratio * (box.x1 - box.x0)
            and box.y1 - box.y0 >= settings.stamp_height * height
            and len(line.text.strip()) >= settings.stamp_letters
        )

    def _is_page_number(self, line: TextLine) -> bool:
        """Alone on its row, a number, not large, and no graphic beside it (an axis tick)."""
        box, settings = boxed(line), self.settings
        reach = settings.graphic_clear * self.size
        near = any(
            g.x0 - reach < box.x1
            and box.x0 < g.x1 + reach
            and g.y0 - reach < box.y1
            and box.y0 < g.y1 + reach
            and not _inside(box, g)
            for g in self.graphics
        )
        return (
            line.id in self.alone
            and bool(_PAGE_NUMBER.match(line.text.strip()))
            and line_size(line) <= settings.head_size * self.size
            and not near
        )

    def _apart(self) -> set[str]:
        """Lines in the top or bottom band with white of `apart` em between them and the body.

        The body is the other rows of text and any graphic that holds no text (a plot whose
        tick labels stand in the band is not apart from it).
        """
        settings, height = self.settings, self.page.height or 0.0
        boxes = [boxed(line) for line in self.lines]
        parts = [([boxed(li) for li in row], [li.id for li in row]) for row in self.rows]
        parts += [([g], []) for g in self.graphics if not any(_inside(b, g) for b in boxes)]
        found: set[str] = set()
        for ordered, inside in (
            (
                sorted(parts, key=lambda part: min(b.y0 for b in part[0])),
                lambda b: b.y1 <= settings.edge_band * height,
            ),
            (
                sorted(parts, key=lambda part: -max(b.y1 for b in part[0])),
                lambda b: b.y0 >= (1 - settings.edge_band) * height,
            ),
        ):
            for i, (part, _) in enumerate(ordered):
                if not all(inside(box) for box in part):
                    break
                after = ordered[i + 1][0] if i + 1 < len(ordered) else None
                if after is None or _white(part, after) >= settings.apart * self.size:
                    found.update(line for _, ids in ordered[: i + 1] for line in ids)
        return found


def _inside(box: Box, outer: Box) -> bool:
    return outer.x0 <= box.x0 and box.x1 <= outer.x1 and outer.y0 <= box.y0 and box.y1 <= outer.y1


def _white(a: list[Box], b: list[Box]) -> float:
    """The white between two groups of boxes, one above the other."""
    return max(
        min(x.y0 for x in b) - max(x.y1 for x in a), min(x.y0 for x in a) - max(x.y1 for x in b)
    )


def _line_numbers(lines: list[TextLine], settings: LayoutSettings) -> dict[str, FurnitureRole]:
    """Bare numbers beside the text, as in a draft with numbered lines."""
    words = [line for line in lines if not line.text.strip().isdigit()]
    left, right = text_area(words, settings.edge_share)
    beside = [
        line
        for line in lines
        if line.text.strip().isdigit() and (boxed(line).x1 <= left or boxed(line).x0 >= right)
    ]
    if len(beside) < settings.line_numbers:
        return {}
    return {line.id: LINE_NUMBER for line in beside}


def _contents(lines: list[TextLine], settings: LayoutSettings) -> dict[str, FurnitureRole]:
    """A printed table of contents: its title and the entries under it with their pages."""
    found: dict[str, FurnitureRole] = {}
    _, right = text_area(lines, settings.edge_share)
    size = median(run.size for line in lines for run in line.runs) if lines else 0.0
    reach = settings.contents_reach * max(size, 1.0)
    page_rows = rows(lines, settings.row_overlap)
    for start, row in enumerate(page_rows):
        if len(row) == 1 and re.sub(r"\W", "", row[0].text.casefold()) in _CONTENTS_TITLE:
            entries = _entries(page_rows[start + 1 :], right - reach)
            if entries:
                found.update({line.id: CONTENTS for line in row})
                found.update({line.id: CONTENTS for line in entries})
    return found


def _entries(page_rows: list[list[TextLine]], edge: float) -> list[TextLine]:
    """Rows that end in a page number at the right edge (or after dot leaders)."""

    def is_entry(row: list[TextLine]) -> bool:
        last = row[-1]
        ends_with_page = _PAGE_NUMBER.match(last.text.strip()) and len(row) > 1
        return bool(ends_with_page and boxed(last).x1 >= edge) or bool(
            _LEADER.search(" ".join(line.text for line in row))
        )

    entries: list[TextLine] = []
    pending: list[TextLine] = []  # a title wrapped onto the next row, before its page number
    for row in page_rows:
        if is_entry(row):
            entries += pending + row
            pending = []
        elif not pending and entries:
            pending = row
        else:
            break
    return entries
