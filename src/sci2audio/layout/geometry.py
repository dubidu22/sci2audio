"""Measuring helpers that the furniture finder, the reading order and the build share."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from statistics import median

from sci2audio.core import Box, Content, Drawing, Page, Picture, TextLine, TextRun
from sci2audio.layout.settings import LayoutSettings


def boxed(item: TextLine | Picture | Drawing) -> Box:
    """The item's box; layout measures only items that have one."""
    if item.box is None:
        raise ValueError(f"item {item.id!r} has no position")
    return item.box


def union(boxes: list[Box]) -> Box:
    return Box(
        min(b.x0 for b in boxes),
        min(b.y0 for b in boxes),
        max(b.x1 for b in boxes),
        max(b.y1 for b in boxes),
    )


def holds(outer: Box, inner: Box) -> bool:
    """True if the inner box lies wholly inside the outer one (edges may touch)."""
    return (
        outer.x0 <= inner.x0
        and inner.x1 <= outer.x1
        and outer.y0 <= inner.y0
        and inner.y1 <= outer.y1
    )


def minor(boxes: Sequence[Box], mark: float, width: float) -> bool:
    """True for graphics read as one that are lines only, each at most `width` thick (a
    rule, a frame, arrows, a fraction bar), or no taller than `mark` together (an icon): a
    loose line or mark (D-90, D-92), not a figure."""
    box = union(list(boxes))
    return box.y1 - box.y0 <= mark or all(min(b.x1 - b.x0, b.y1 - b.y0) <= width for b in boxes)


def same_row(a: Box, b: Box, overlap: float) -> bool:
    """True if the boxes overlap vertically by `overlap` of the lower one's height."""
    shared = min(a.y1, b.y1) - max(a.y0, b.y0)
    return shared > overlap * min(a.y1 - a.y0, b.y1 - b.y0)


def rows(lines: list[TextLine], overlap: float) -> list[list[TextLine]]:
    """Lines grouped by baseline, top to bottom, each row left to right."""
    found: list[list[TextLine]] = []
    for line in sorted((li for li in lines if li.box), key=lambda li: boxed(li).y0):
        if found and same_row(boxed(found[-1][-1]), boxed(line), overlap):
            found[-1].append(line)
        else:
            found.append([line])
    return [sorted(row, key=lambda li: boxed(li).x0) for row in found]


def text_area(lines: list[TextLine], share: float) -> tuple[float, float]:
    """Left and right edge of most of the text (`share` of the lines on each side left out)."""
    boxes = [line.box for line in lines if line.box]
    if not boxes:
        return 0.0, 0.0
    lefts = sorted(box.x0 for box in boxes)
    rights = sorted(box.x1 for box in boxes)
    cut = int(len(boxes) * share)
    return lefts[cut], rights[len(rights) - 1 - cut]


def body_size(content: Content) -> float:
    """The font size most of the text is set in (0 if the file has no sizes)."""
    sizes: Counter[float] = Counter()
    for page in content.pages:
        for line in page.lines:
            for run in line.runs:
                sizes[run.size] += len(run.text)
    return sizes.most_common(1)[0][0] if sizes else 0.0


def letter_size(runs: Iterable[TextRun]) -> float:
    """The size most of the letters have: a footnote mark or a subscript doesn't change it
    (0 if there are no letters)."""
    letters: dict[float, int] = {}
    for run in runs:
        letters[run.size] = letters.get(run.size, 0) + len(run.text.strip())
    return max(letters, key=lambda size: letters[size]) if letters else 0.0


def separators(
    pieces: Sequence[TextLine],
    size: float,
    word_space: float,
    stack_reach: float,
    bars: Sequence[Box] = (),
    bar: float = 0.15,
    bar_reach: float = 0.6,
) -> list[str]:
    """What stands before each piece of one printed line, left to right: a space where the
    white after the letters so far (a subscript may stand under the end of the piece before
    it) is at least `word_space` em of `size`, else nothing, as the page prints a mark or a
    script set close to its neighbour. A piece that starts more than `stack_reach` em back,
    under earlier letters, is out of its place and keeps a space, so no words run together.
    A digit that starts back under a digit (a fraction 1/2 set as 1 over 2) keeps a space,
    so the two never read as one number (review M2 of #128). Pieces without a position, or a
    line without sizes, keep a space (#36, D-274 to D-277). A piece that starts under one
    of the `bars` drawn below the piece before it is a fraction's denominator under its
    numerator and keeps a space ("eℏ 2me", not "eℏ2me"; #202, D-575): `bar` and `bar_reach`
    are `LayoutSettings.fraction_bar` and `fraction_reach`."""
    out = [""] * min(len(pieces), 1)
    reach: float | None = None
    for k, piece in enumerate(pieces):
        if k:
            gap = None if piece.box is None or reach is None else piece.box.x0 - reach
            near = gap is not None and -stack_reach * size <= gap < word_space * size
            stacked_digits = (
                gap is not None
                and gap < 0
                and pieces[k - 1].text[-1:].isdigit()
                and piece.text[:1].isdigit()
            )
            under = near and any(
                fraction_bar(drawn, pieces[k - 1], piece, size, bar, bar_reach) for drawn in bars
            )
            out.append("" if near and not stacked_digits and not under else " ")
        if piece.box is not None:
            reach = piece.box.x1 if reach is None else max(reach, piece.box.x1)
    return out


def fraction_bar(
    drawn: Box, upper: TextLine, lower: TextLine, size: float, thickness: float, reach: float
) -> bool:
    """True if the drawing is a fraction bar between the end of `upper` and the start of
    `lower`: at most `thickness` em of `size` thick and three times as wide; the letters of
    `upper` it stands under (its runs, or the whole piece where runs have no box) all above
    it and the first letters of `lower` below it, each overlapping it across, their middles
    on either side of it and their edges within `reach` em (#202, D-575). The same measure
    keeps PDFium's space inside one extracted line (extraction `FRACTION_BAR`)."""
    thick = drawn.y1 - drawn.y0
    if thick > thickness * size or drawn.x1 - drawn.x0 < 3 * thick:
        return False
    tops = [b for b in _letter_boxes(upper) if min(b.x1, drawn.x1) > max(b.x0, drawn.x0)]
    bottoms = _letter_boxes(lower)[:1]
    if not tops or not bottoms or min(bottoms[0].x1, drawn.x1) <= max(bottoms[0].x0, drawn.x0):
        return False
    bottom = bottoms[0]
    above = all((b.y0 + b.y1) / 2 < drawn.y0 and drawn.y0 - b.y1 <= reach * size for b in tops)
    below = drawn.y1 < (bottom.y0 + bottom.y1) / 2 and bottom.y0 - drawn.y1 <= reach * size
    return above and below


@dataclass(frozen=True)
class Bars:
    """A page's drawings that could be fraction bars: at most `thickest` points thick and
    three times as wide, sorted by their top, so finding those that meet a printed line
    costs no more on a page of a million drawings (#185)."""

    boxes: tuple[Box, ...] = ()
    tops: tuple[float, ...] = ()
    thickest: float = 0.0

    @staticmethod
    def of(drawings: Iterable[Box], thickest: float) -> Bars:
        thin = sorted(
            (b for b in drawings if b.y1 - b.y0 <= thickest and b.x1 - b.x0 >= 3 * (b.y1 - b.y0)),
            key=lambda b: b.y0,
        )
        return Bars(tuple(thin), tuple(b.y0 for b in thin), thickest)

    def meeting(self, box: Box) -> tuple[Box, ...]:
        """The bars that overlap or touch the box."""
        near = self.boxes[
            bisect_left(self.tops, box.y0 - self.thickest) : bisect_right(self.tops, box.y1)
        ]
        return tuple(b for b in near if b.x0 <= box.x1 and box.x0 <= b.x1 and b.y1 >= box.y0)


def page_bars(page: Page, settings: LayoutSettings) -> Bars:
    """The page's possible fraction bars: no thicker than `fraction_bar` em of its largest
    letters (#202)."""
    largest = max((run.size for line in page.lines for run in line.runs), default=0.0)
    return Bars.of((d.box for d in page.drawings), settings.fraction_bar * largest)


def _letter_boxes(piece: TextLine) -> list[Box]:
    """The boxes of the piece's runs that hold letters, in order; the piece's own box when
    its runs have none (no boxes at all for a piece without a position)."""
    boxes = [run.box for run in piece.runs if run.box is not None and run.text.strip()]
    return boxes or ([piece.box] if piece.box is not None else [])


def line_size(line: TextLine) -> float:
    """The size of a line's letters (the middle run size, by runs)."""
    return median(run.size for run in line.runs)
