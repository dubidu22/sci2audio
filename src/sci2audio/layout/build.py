"""Turn the extracted `Content` into the reading `Document` (D-63, Issue #21)."""

from __future__ import annotations

from statistics import median

from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    FurnitureRole,
    Page,
    Part,
    TextLine,
)
from sci2audio.layout.furniture import PAGE_NUMBER, SIDEBAR, find_furniture, page_label
from sci2audio.layout.geometry import body_size, boxed, text_area
from sci2audio.layout.headings import find_headings
from sci2audio.layout.order import Element, Reading, by_rows, figures, reading_order
from sci2audio.layout.paragraphs import Held, Unit, make_row, paragraphs, rows_of, split_cells
from sci2audio.layout.settings import LayoutSettings


def build_document(content: Content, settings: LayoutSettings | None = None) -> Document:
    """The content in reading order as paragraphs, figures and furniture.

    Each page is read on its own: the furniture at its top edge first (running heads), then
    the text and figures in reading order, then the rest of its furniture (page numbers at
    the foot, footers, side stamps, a sidebar). Items without a position follow in the order
    the file stores them. The text lines are then joined into paragraphs, which may run on
    across columns and pages (`paragraphs`).
    """
    settings = settings or LayoutSettings()
    layout = _Layout(content, settings)
    units = [unit for page in content.pages for unit in layout.units(page)]
    blocks, sections = find_headings(paragraphs(units, settings), content, layout.size, settings)
    language = settings.language or content.metadata.language or "en"
    labels = tuple(layout.label(page) for page in content.pages)
    return Document(
        content=content,
        language=language,
        blocks=tuple(blocks),
        sections=sections,
        page_labels=labels,
    )


def columns_per_page(content: Content, settings: LayoutSettings | None = None) -> list[int]:
    """How many columns of text each page is set in (a sidebar doesn't count).

    A page whose text all stands in one half of a two-column document, as on a last page
    that ends in the left column, follows the document's columns.
    """
    layout = _Layout(content, settings or LayoutSettings())
    found = [layout.read(page)[0].columns for page in content.pages]
    if 2 not in found:
        return found
    return [
        2 if count == 1 and layout.in_one_half(page) else count
        for count, page in zip(found, content.pages, strict=True)
    ]


class _Layout:
    """What layout knows about the whole document while it reads one page after another."""

    def __init__(self, content: Content, settings: LayoutSettings) -> None:
        self.settings = settings
        self.furniture = find_furniture(content, settings)
        self.size = body_size(content) or settings.body_size
        lines = [
            line
            for page in content.pages
            for line in page.lines
            if line.box and line.id not in self.furniture
        ]
        self.left, self.right = text_area(lines, settings.text_share)

    def read(self, page: Page) -> tuple[Reading, dict[str, FurnitureRole]]:
        """The page's text and figures in reading order, and its furniture."""
        lines = [line for line in page.lines if line.box and line.id not in self.furniture]
        sidebar = self._sidebar(lines)
        body = [Element(boxed(line), line) for line in lines if line.id not in sidebar]
        body += figures([*page.pictures, *page.drawings], self.settings.figure_reach)
        # the text area found over the document may leave out a short column of this page
        boxes = [e.box for e in body if e.line]
        spread = max(b.x1 for b in boxes) - min(b.x0 for b in boxes) if boxes else 0.0
        width = max(self.right - self.left, spread) or (page.width or 0.0)
        return reading_order(body, width, self.size, self.settings), self.furniture | sidebar

    def label(self, page: Page) -> str:
        """The page label the page prints in its page number, or "" if it prints none."""
        numbers = [li for li in page.lines if self.furniture.get(li.id) == PAGE_NUMBER]
        return page_label(numbers[0].text) if numbers else ""

    def in_one_half(self, page: Page) -> bool:
        """True if nearly all the page's text lies in one half of the text area."""
        middle = (self.left + self.right) / 2
        slack = self.settings.one_half_slack * (self.right - self.left)  # a table may reach
        boxes = [line.box for line in page.lines if line.box and line.id not in self.furniture]
        left = sum(box.x1 <= middle + slack for box in boxes)
        right = sum(box.x0 >= middle - slack for box in boxes)
        return bool(boxes) and max(left, right) >= self.settings.one_half * len(boxes)

    def units(self, page: Page) -> list[Unit]:
        """The page's printed lines of text, figures and furniture, in reading order."""
        reading, furniture = self.read(page)
        edges = self._edges(reading)
        edge = [Element(line.box, line) for line in page.lines if line.box and line.id in furniture]
        top = [e for e in edge if e.box.y1 <= self.settings.edge_band * (page.height or 0.0)]
        taken = {id(e) for e in top}
        overlap = self.settings.row_overlap
        units: list[Unit] = [Held(_block(e, furniture)) for e in by_rows(top, overlap)]
        groups = split_cells(rows_of(reading.ordered, edges, self.settings), edges)
        for group in groups:
            if group[0].line is None:
                units += [Held(_block(e, furniture)) for e in group]
            else:
                units.append(make_row(group, edges[id(group[0])], page.number, self.settings))
        rest = by_rows([e for e in edge if id(e) not in taken], overlap)
        units += [Held(_block(e, furniture)) for e in rest]
        # items without a position: a line is a paragraph of its own, a graphic a figure
        units += [
            Held(Block(BlockKind.PARAGRAPH, li.text, (Part(li.id),)))
            for li in page.lines
            if not li.box
        ]
        loose = [g for g in (*page.pictures, *page.drawings) if not g.box]
        units += [Held(Block(BlockKind.FIGURE, "", (Part(g.id),))) for g in loose]
        return units

    def _edges(self, reading: Reading) -> dict[int, tuple[float, float]]:
        """The left and right edge of the column each element is read in.

        Each band finds its own gutters, so one column's edges differ a little from band to
        band: edges this close to a column's edges found before are that column's. Elements
        read across the page take the text area's edges, unless they lie inside one column
        the page has elsewhere (a band too short to find its columns in).
        """
        reach = self.settings.column_snap * self.size
        columns: list[tuple[float, float]] = []

        def snapped(left: float, right: float) -> tuple[float, float]:
            for column in columns:
                if abs(column[0] - left) <= reach and abs(column[1] - right) <= reach:
                    return column
            columns.append((left, right))
            return columns[-1]

        found: dict[int, tuple[float, float]] = {}
        for key, (left, right) in reading.sides.items():
            found[key] = snapped(
                self.left if left is None else left, self.right if right is None else right
            )
        for element in reading.ordered:
            if id(element) in found:
                continue
            box = element.box
            inside = [c for c in columns if c[0] - reach <= box.x0 and box.x1 <= c[1] + reach]
            found[id(element)] = inside[0] if len(inside) == 1 else snapped(self.left, self.right)
        # a gutter may begin inside a column's longest lines (it allows a few to cross it):
        # the column reaches as far as a share of its lines do
        spread = {}
        for column in columns:
            members = [e.box for e in reading.ordered if e.line and found[id(e)] == column]
            if members:
                k = int(len(members) * self.settings.column_spread)
                lefts = sorted(box.x0 for box in members)
                rights = sorted((box.x1 for box in members), reverse=True)
                spread[column] = (min(column[0], lefts[k]), max(column[1], rights[k]))
        return {key: spread.get(column, column) for key, column in found.items()}

    def _sidebar(self, lines: list[TextLine]) -> dict[str, FurnitureRole]:
        """Lines beside the document's text area, in smaller letters (the JOSS metadata)."""
        beside = [
            line
            for line in lines
            if line.box and (line.box.x1 <= self.left or line.box.x0 >= self.right)
        ]
        sizes = [run.size for line in beside for run in line.runs]
        if len(beside) < self.settings.column_items or median(sizes) >= self.size:
            return {}
        return {line.id: SIDEBAR for line in beside}


def _block(element: Element, furniture: dict[str, FurnitureRole]) -> Block:
    if element.line:
        role = furniture.get(element.line.id)
        kind = BlockKind.FURNITURE if role else BlockKind.PARAGRAPH
        return Block(kind, element.line.text, (Part(element.line.id),), role=role)
    return Block(BlockKind.FIGURE, "", tuple(Part(g.id) for g in element.graphics))
