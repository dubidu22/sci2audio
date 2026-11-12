"""The thresholds layout works with, passed in for each job (no global state)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutSettings:
    """Every threshold the layout stage uses. Shares are of the page's width or height."""

    language: str = ""  # BCP 47 tag for the document; "" = the file's own, else "en"
    edge_band: float = 0.1  # top and bottom share of a page that holds heads and page numbers
    footer_band: float = 0.06  # bottom share that holds only furniture (venue, licence lines)
    margin_band: float = 0.12  # left and right share where side stamps stand
    repeat_pages: int = 2  # a line in the edge band repeated on this many pages is a running head
    wide: float = 0.55  # an item wider than this share of the text may span columns
    gutter: float = 0.8  # em: the narrowest white strip between two columns
    gutter_crossings: float = 0.1  # share of the narrow items that may cross a gutter
    column_items: int = 5  # a column holds at least this many items ...
    column_width: float = 0.25  # ... and this share of the text's width (not a margin of numbers)
    line_numbers: int = 5  # this many bare numbers beside the text are line numbers
    figure_reach: float = 2.0  # points: pictures and drawings this close form one figure
