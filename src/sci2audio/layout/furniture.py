"""Page furniture: text on a page that belongs to the page, not to the reading (D-63, TP-01).

Running heads and footers, page numbers, line numbers, side stamps and a printed table of
contents are found line by line, before the reading order, so they never split or join the
text around them. They still become blocks (kind `furniture`), so nothing is lost; a text step
removes them from the listening script with a marked edit.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import median

from sci2audio.core import Box, Content, Drawing, Page, Picture, TextLine
from sci2audio.layout.settings import LayoutSettings

PAGE_NUMBER = "page-number"
RUNNING_HEAD = "running-head"
FOOTER = "footer"
SIDE_STAMP = "side-stamp"
LINE_NUMBER = "line-number"
CONTENTS = "contents"
SIDEBAR = "sidebar"

_PAGE_NUMBER = re.compile(
    r"^(?:page\s+)?[(\[\-\u2013\u2014]?\s*(?:\d{1,4}|[ivxlcdm]{1,7})\s*[)\]\-\u2013\u2014]?"
    r"(?:\s*(?:of|/)\s*\d{1,4})?$",
    re.IGNORECASE,
)
_CONTENTS_TITLE = {"contents", "tableofcontents"}
_LEADER = re.compile(r"(?:\.\s?){4,}\s*\d{1,4}$|(?:…\s?){2,}\s*\d{1,4}$")


def find_furniture(content: Content, settings: LayoutSettings) -> dict[str, str]:
    """The furniture kind of every line that is furniture, by line id."""
    found: dict[str, str] = {}
    pages = [page for page in content.pages if page.height and page.width]
    repeated = _repeated_shapes(pages, settings)
    for page in pages:
        found.update(_on_page(page, repeated, settings))
    return found


def boxed(item: TextLine | Picture | Drawing) -> Box:
    """The item's box; layout measures only items that have one."""
    if item.box is None:
        raise ValueError(f"item {item.id!r} has no position")
    return item.box


def text_area(lines: list[TextLine], share: float = 0.05) -> tuple[float, float]:
    """Left and right edge of most of the text (`share` of the lines on each side left out)."""
    boxes = [line.box for line in lines if line.box]
    if not boxes:
        return 0.0, 0.0
    lefts = sorted(box.x0 for box in boxes)
    rights = sorted(box.x1 for box in boxes)
    cut = int(len(boxes) * share)
    return lefts[cut], rights[len(rights) - 1 - cut]


def rows(lines: list[TextLine]) -> list[list[TextLine]]:
    """Lines grouped by baseline, top to bottom, each row left to right."""
    found: list[list[TextLine]] = []
    for line in sorted((li for li in lines if li.box), key=lambda li: boxed(li).y0):
        if found and _same_row(boxed(found[-1][-1]), boxed(line)):
            found[-1].append(line)
        else:
            found.append([line])
    return [sorted(row, key=lambda li: boxed(li).x0) for row in found]


def _same_row(a: Box, b: Box) -> bool:
    overlap = min(a.y1, b.y1) - max(a.y0, b.y0)
    return overlap > 0.5 * min(a.y1 - a.y0, b.y1 - b.y0)


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


def _repeated_shapes(pages: list[Page], settings: LayoutSettings) -> set[tuple[str, str]]:
    seen: defaultdict[tuple[str, str], set[int]] = defaultdict(set)
    for page in pages:
        for line in page.lines:
            if line.box and (band := _band(line.box, page, settings)):
                seen[band, _shape(line.text)].add(page.number)
    return {key for key, numbers in seen.items() if len(numbers) >= settings.repeat_pages}


def _on_page(
    page: Page, repeated: set[tuple[str, str]], settings: LayoutSettings
) -> dict[str, str]:
    width, height = page.width or 0.0, page.height or 0.0
    lines = [line for line in page.lines if line.box]
    found: dict[str, str] = {}
    alone = {row[0].id for row in rows(lines) if len(row) == 1}
    for line in lines:
        box, text = boxed(line), line.text.strip()
        tall = box.y1 - box.y0 > 3 * (box.x1 - box.x0)
        in_margin = (
            box.x1 < settings.margin_band * width or box.x0 > (1 - settings.margin_band) * width
        )
        band = _band(box, page, settings)
        if tall and in_margin and len(text) >= 8:
            found[line.id] = SIDE_STAMP
        elif band and line.id in alone and _PAGE_NUMBER.match(text):
            found[line.id] = PAGE_NUMBER
        elif band and (band, _shape(text)) in repeated:
            found[line.id] = RUNNING_HEAD
        elif box.y0 >= (1 - settings.footer_band) * height:
            found[line.id] = FOOTER
    body = [line for line in lines if line.id not in found]
    found.update(_line_numbers(body, settings))
    found.update(_contents([line for line in body if line.id not in found]))
    return found


def _line_numbers(lines: list[TextLine], settings: LayoutSettings) -> dict[str, str]:
    """Bare numbers beside the text, as in a draft with numbered lines."""
    words = [line for line in lines if not line.text.strip().isdigit()]
    left, right = text_area(words)
    beside = [
        line
        for line in lines
        if line.box
        and line.text.strip().isdigit()
        and (line.box.x1 <= left or line.box.x0 >= right)
    ]
    if len(beside) < settings.line_numbers:
        return {}
    return {line.id: LINE_NUMBER for line in beside}


def _contents(lines: list[TextLine]) -> dict[str, str]:
    """A printed table of contents: its title and the entries under it with their pages."""
    found: dict[str, str] = {}
    _, right = text_area(lines)
    size = median(run.size for line in lines for run in line.runs) if lines else 0.0
    page_rows = rows(lines)
    for start, row in enumerate(page_rows):
        if len(row) == 1 and re.sub(r"\W", "", row[0].text.casefold()) in _CONTENTS_TITLE:
            entries = _entries(page_rows[start + 1 :], right, max(size, 1.0))
            if entries:
                found.update({line.id: CONTENTS for line in row})
                found.update({line.id: CONTENTS for line in entries})
    return found


def _entries(page_rows: list[list[TextLine]], right: float, size: float) -> list[TextLine]:
    def is_entry(row: list[TextLine]) -> bool:
        last = row[-1]
        ends_with_page = _PAGE_NUMBER.match(last.text.strip()) and len(row) > 1
        return bool(ends_with_page and boxed(last).x1 >= right - 2 * size) or bool(
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


def body_size(content: Content) -> float:
    """The font size most of the text is set in."""
    sizes: Counter[float] = Counter()
    for page in content.pages:
        for line in page.lines:
            for run in line.runs:
                sizes[run.size] += len(run.text)
    return sizes.most_common(1)[0][0] if sizes else 0.0
