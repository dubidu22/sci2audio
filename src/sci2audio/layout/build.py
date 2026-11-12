"""Turn the extracted `Content` into the reading `Document` (D-63, Issue #21)."""

from __future__ import annotations

from statistics import median

from sci2audio.core import Block, BlockKind, Box, Content, Document, Page, Part, TextLine
from sci2audio.layout.furniture import SIDEBAR, find_furniture
from sci2audio.layout.geometry import body_size, boxed, text_area
from sci2audio.layout.order import Element, by_rows, figures, reading_order
from sci2audio.layout.settings import LayoutSettings


def build_document(content: Content, settings: LayoutSettings | None = None) -> Document:
    """The content in reading order: one block per line for now, furniture marked.

    Each page is read on its own: the furniture at its top edge first (running heads), then
    the text and figures in reading order, then the rest of its furniture (page numbers at
    the foot, footers, side stamps, a sidebar). Items without a position follow in the order
    the file stores them.
    """
    settings = settings or LayoutSettings()
    layout = _Layout(content, settings)
    blocks = [block for page in content.pages for block in layout.blocks(page)]
    language = settings.language or content.metadata.language or "en"
    return Document(content=content, language=language, blocks=tuple(blocks))


def columns_per_page(content: Content, settings: LayoutSettings | None = None) -> list[int]:
    """How many columns of text each page is set in (a sidebar doesn't count).

    A page whose text all stands in one half of a two-column document, as on a last page
    that ends in the left column, follows the document's columns.
    """
    layout = _Layout(content, settings or LayoutSettings())
    found = [layout.read(page)[1] for page in content.pages]
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

    def read(self, page: Page) -> tuple[list[Element], int, dict[str, str]]:
        """The page's text and figures in reading order, its columns, and its furniture."""
        lines = [line for line in page.lines if line.box and line.id not in self.furniture]
        sidebar = self._sidebar(lines)
        body = [Element(boxed(line), line) for line in lines if line.id not in sidebar]
        body += figures([*page.pictures, *page.drawings], self.settings.figure_reach)
        width = (self.right - self.left) or (page.width or 0.0)
        ordered, columns = reading_order(body, width, self.size, self.settings)
        return ordered, columns, self.furniture | sidebar

    def in_one_half(self, page: Page) -> bool:
        """True if nearly all the page's text lies in one half of the text area."""
        middle = (self.left + self.right) / 2
        slack = self.settings.one_half_slack * (self.right - self.left)  # a table may reach
        boxes = [line.box for line in page.lines if line.box and line.id not in self.furniture]
        left = sum(box.x1 <= middle + slack for box in boxes)
        right = sum(box.x0 >= middle - slack for box in boxes)
        return bool(boxes) and max(left, right) >= self.settings.one_half * len(boxes)

    def blocks(self, page: Page) -> list[Block]:
        ordered, _, furniture = self.read(page)
        edge = [Element(line.box, line) for line in page.lines if line.box and line.id in furniture]
        top = [e for e in edge if e.box.y1 <= self.settings.edge_band * (page.height or 0.0)]
        taken = {id(e) for e in top}
        overlap = self.settings.row_overlap
        ordered = by_rows(top, overlap) + ordered
        ordered += by_rows([e for e in edge if id(e) not in taken], overlap)
        nowhere = Box(0, 0, 0, 0)  # items without a position are placed after, never measured
        ordered += [Element(nowhere, line) for line in page.lines if not line.box]
        loose = [g for g in (*page.pictures, *page.drawings) if not g.box]
        ordered += [Element(nowhere, graphics=(g,)) for g in loose]
        return [_block(element, furniture) for element in ordered]

    def _sidebar(self, lines: list[TextLine]) -> dict[str, str]:
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


def _block(element: Element, furniture: dict[str, str]) -> Block:
    if element.line:
        kind = BlockKind.FURNITURE if element.line.id in furniture else BlockKind.PARAGRAPH
        return Block(kind, element.line.text, (Part(element.line.id),))
    return Block(BlockKind.FIGURE, "", tuple(Part(g.id) for g in element.graphics))
