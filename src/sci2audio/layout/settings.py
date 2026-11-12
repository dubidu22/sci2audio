"""The thresholds layout works with, passed in for each job (no global state)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutSettings:
    """Every threshold the layout stage uses.

    Shares are of the page's width or height unless a comment says otherwise; "em" is the
    body font size of the document.
    """

    language: str = ""  # BCP 47 tag for the document; "" = the file's own, else "en"
    body_size: float = 10.0  # points: the body size to assume when the file has no sizes
    row_overlap: float = 0.5  # boxes on one row overlap by this share of the lower one

    # Furniture
    edge_band: float = 0.1  # top and bottom share of a page that holds heads and page numbers
    footer_band: float = 0.06  # bottom share where venue and licence lines stand
    margin_band: float = 0.12  # left and right share where side stamps stand
    repeat_pages: int = 2  # a line in the edge band repeated on this many pages is a running head
    head_drift: float = 0.5  # em: ... at the same height on each of them, give or take this
    head_size: float = 1.05  # ... and set no larger than this times the body size
    small: float = 0.95  # an edge line set smaller than this times the body size, or ...
    apart: float = 1.0  # em: ... with this much white between it and the body, is furniture
    graphic_clear: float = 1.0  # em: a page number has no graphic this close (not an axis tick)
    stamp_ratio: float = 3.0  # a side stamp is this many times taller than wide, ...
    stamp_height: float = 0.25  # ... at least this share of the page tall ...
    stamp_letters: int = 8  # ... and holds at least this many characters
    edge_share: float = 0.05  # share of lines left out on each side to find the text's edges
    line_numbers: int = 5  # this many bare numbers beside the text are line numbers
    contents_reach: float = 2.0  # em: a contents entry's page number ends this close to the edge

    # Columns and reading order
    text_share: float = 0.1  # share of lines left out on each side to find the text area
    wide: float = 0.55  # an item wider than this share of the text may span columns
    gutter: float = 0.8  # em: the narrowest white strip between two columns
    gutter_crossings: float = 0.1  # share of the narrow items that may cross a gutter
    column_items: int = 5  # a column holds at least this many items ...
    column_width: float = 0.25  # ... and this share of the text's width (not a margin of numbers)
    frame_items: int = 1  # a wide graphic around this many items is a frame or background
    figure_reach: float = 2.0  # points: pictures and drawings this close form one figure

    # Counting a page's columns
    column_text: float = 0.2  # a band counts if it holds this share of the page's text ...
    column_fill: float = 0.5  # ... and a column has this share of its letters in full lines
    full_line: float = 0.8  # a line this wide of its column fills it
    one_half: float = 0.9  # a page with this share of its lines in one half of the text area
    one_half_slack: float = 0.1  # (lines may reach this share of the text width past the middle)
    #                               follows the document's columns
