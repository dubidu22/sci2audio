"""Measuring helpers that the furniture finder, the reading order and the build share."""

from __future__ import annotations

from collections import Counter
from statistics import median

from sci2audio.core import Box, Content, Drawing, Picture, TextLine


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


def line_size(line: TextLine) -> float:
    """The size of a line's letters (the middle run size, by runs)."""
    return median(run.size for run in line.runs)
