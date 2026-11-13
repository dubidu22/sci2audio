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
    column_snap: float = 1.0  # em: column edges this close in two bands are one column's
    column_spread: float = 0.25  # a column reaches as far as this share of its lines do

    # Counting a page's columns
    column_text: float = 0.2  # a band counts if it holds this share of the page's text ...
    column_fill: float = 0.5  # ... and a column has this share of its letters in full lines
    full_line: float = 0.8  # a line this wide of its column fills it
    one_half: float = 0.9  # a page with this share of its lines in one half of the text area
    one_half_slack: float = 0.1  # (lines may reach this share of the text width past the middle)
    #                               follows the document's columns

    # Paragraphs
    size_change: float = 0.08  # lines whose sizes differ by this share are in different styles
    bold_share: float = 0.8  # a line with this share of its letters bold is set in bold
    short_line: float = 1.5  # em: a line ending this far before its text's edge ends a paragraph
    fill_slack: float = 0.7  # em: a line starting and ending this close to its column's edges
    #                           fills it (running text)
    align: float = 0.3  # em: lines ending this close together share an edge
    indent: float = 0.7  # em: a line starting this much further in than the lines before it
    paragraph_space: float = 0.4  # em: this much more white than the usual line spacing
    #                                between two lines ends a paragraph
    line_pitch: float = 1.2  # sizes: the line pitch to assume when no two lines show it
    same_size: float = 0.01  # lines whose sizes differ by less than this share are the same
    #                          size (to measure the line pitch, and in heading styles)

    # Joining the pieces of one printed line (#36, D-274 to D-280)
    word_space: float = 0.15  # em: white this wide after a line's letters before its next
    #                           piece is a space (extraction's SPACE, D-275)
    stack_reach: float = 2.0  # em: a piece starting further back than this under the
    #                           letters before it is out of its place and keeps a space (D-277)

    # Footnotes
    footnote_rule_height: float = 1.5  # points: a footnote rule is at most this thick, ...
    footnote_band: float = 0.5  # ... starts below this share of the page's height, ...
    footnote_reach: float = 2.0  # em: ... starts this close to the left edge of a column ...
    footnote_rule_width: float = 2.0  # em: ... is at least this wide ...
    footnote_rule_share: float = 0.5  # ... and at most this share of the column

    # Tables, figures and algorithms (placeholders)
    caption_reach: float = 2.0  # em: a table or figure stands this close to its caption, ...
    float_gap: float = 1.0  # em: ... its rows and pieces this close to each other
    line_width: float = 1.0  # em: a drawing at most this thick is a line (a rule, an arrow)
    mark_height: float = 2.0  # em: a graphic no caption names at most this tall is a mark
    #                            (an icon), not a figure

    # Display formulas (placeholders)
    formula_indent: float = 2.0  # em: a display line starts this far in from its column's
    #                              left edge, or further
    number_reach: float = 0.5  # em: an equation number ends this close to its column's
    #                            right edge
    math_share: float = 0.4  # a display line without a number is a formula if this share of
    #                          its letters is set in a math font or is a math symbol
    # the fonts that set mathematics (names start so; a subset prefix like "ABCDEF+" is left out)
    math_fonts: tuple[str, ...] = (
        "CMMI",
        "CMSY",
        "CMEX",
        "CMBSY",
        "MSAM",
        "MSBM",
        "EUFM",
        "RSFS",
        "STIXMath",
        "STIXTwoMath",
        "Symbol",
        "CambriaMath",
        "Cambria-Math",
        "LatinModernMath",
    )
    # Headings and sections
    heading_lines: int = 3  # a heading has at most this many lines ...
    heading_words: int = 20  # ... and words, ...
    heading_letters: int = 2  # ... and at least this many letters (not a bold table number)
    heading_bold: float = 0.95  # a block with this share of its main-size letters bold is bold
    heading_repeats: int = 2  # a document numbers its headings if this many have a number
    #                           (letters count if this many distinct ones do); without
    #                           numbers, a heading style is used this often
    # whole texts of headings that may stand in any bold or larger style. English only (v1.0):
    # papers in another language need their own list, passed in with that job's settings
    section_names: tuple[str, ...] = (
        "Abstract",
        "Summary",
        "Acknowledgements",
        "Acknowledgments",
        "References",
        "Bibliography",
        "Appendix",
        "Appendices",
    )
