"""Grouping drawings into figures in time about linear in the drawings (#354).

Before #354, `order.figures` compared each drawing with every later one starting within
reach of its right edge: 20,000 rectangles at one spot took 54 s, a file of 5 pages of
100,000 rectangles (the most the reader allows, #185) 198 s of layout. The sweep in
`order.touching` gives the same groups (pinned against a plain all-pairs reference) and
grows about linearly in the drawings on a page, however they lie (pinned with
`assert_linear`, which times a page of n/8 drawings against one of n).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from linear_time import assert_linear

from sci2audio.core import Box, Content, Drawing, Page, Source, SourceFormat, TextLine, TextRun
from sci2audio.layout import build_document
from sci2audio.layout.order import figures, touching


def all_pairs(boxes: list[Box], reach: float) -> list[int]:
    """The plain reference: every pair compared, touching boxes in one group."""
    group = list(range(len(boxes)))

    def root(i: int) -> int:
        while group[i] != i:
            i = group[i]
        return i

    for i, a in enumerate(boxes):
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            near = b.x0 <= a.x1 + reach and a.x0 <= b.x1 + reach
            if near and b.y0 <= a.y1 + reach and a.y0 <= b.y1 + reach:
                group[root(i)] = root(j)
    return [root(i) for i in range(len(boxes))]


def partition(groups: list[int]) -> list[int]:
    """The groups numbered by first appearance, so two answers compare as partitions."""
    seen: dict[int, int] = {}
    return [seen.setdefault(g, len(seen)) for g in groups]


# coordinates on a coarse grid as often as not, so edges meet exactly and gaps equal reach
coordinate = st.one_of(st.integers(0, 40).map(float), st.floats(0, 60, allow_nan=False))
size = st.one_of(st.just(0.0), st.integers(0, 6).map(float), st.floats(0, 20, allow_nan=False))
boxes = st.lists(
    st.builds(lambda x, y, w, h: Box(x, y, x + w, y + h), coordinate, coordinate, size, size),
    max_size=60,
)


@given(boxes, st.sampled_from([0.0, 0.5, 2.0, 4.0]))
@example([Box(0, 0, 1, 1), Box(3, 0, 4, 1)], 2.0)  # exactly `reach` apart across: one group
@example([Box(0, 0, 1, 1), Box(0, 3, 1, 4)], 2.0)  # ... and down
@example([Box(0, 0, 1, 1), Box(3.5, 0, 4, 1)], 2.0)  # just past it: two
@example([Box(0, 0, 50, 0), Box(10, 0, 20, 0)], 0.0)  # flat lines on one height, no reach
def test_the_groups_are_those_of_comparing_every_pair(found: list[Box], reach: float) -> None:
    assert partition(touching(found, reach)) == partition(all_pairs(found, reach))


def test_figures_keep_the_order_of_their_first_graphic_and_of_their_graphics() -> None:
    drawn = [
        Drawing("b2", Box(100, 100, 110, 110)),
        Drawing("a1", Box(0, 0, 10, 10)),
        Drawing("b1", Box(111, 100, 120, 110)),  # touches b2 (1 pt apart)
        Drawing("a2", Box(11, 0, 20, 10)),  # touches a1
    ]
    found = figures([*drawn], 2.0)
    assert [[g.id for g in f.graphics] for f in found] == [["b2", "b1"], ["a1", "a2"]]
    assert found[0].box == Box(100, 100, 120, 110)


Layout = Callable[[int], list[Box]]
FAMILIES: dict[str, Layout] = {
    # every drawing at one spot (the quadratic case of #354: 54 s at 20,000)
    "one spot": lambda n: [Box(100, 100, 110, 110)] * n,
    # rules across the page, each touching the next (18 s at 20,000)
    "stacked rules": lambda n: [
        Box(50, 50 + k % 2000 * 0.35, 550, 50.1 + k % 2000 * 0.35) for k in range(n)
    ],
    # each a little right of the one before (14 s at 20,000)
    "staircase": lambda n: [Box(50 + k * 0.005, 100, 60 + k * 0.005, 110) for k in range(n)],
    # glyphs drawn as outlines: words in lines down the page
    "outlined text": lambda n: [
        Box(
            50 + k % 90 * 5.5, 50 + k // 90 * 12 % 700, 54.5 + k % 90 * 5.5, 58 + k // 90 * 12 % 700
        )
        for k in range(n)
    ],
    # page-tall rules side by side, all touching
    "tall rules": lambda n: [Box(50 + k % 500, 50, 50.3 + k % 500, 750) for k in range(n)],
    # marks too far apart to touch, each a figure of its own joined to the text before it
    # (`graphics._place` rebuilt that block once per mark: quadratic in the marks)
    "separate marks": lambda n: [
        Box(
            20 + k % 140 * 4,
            160 + k // 140 * 4 % 600,
            20.5 + k % 140 * 4,
            160.5 + k // 140 * 4 % 600,
        )
        for k in range(n)
    ],
    # 1 pt squares on a grid, as the reader's own limit test draws them (#185)
    "grid": lambda n: [
        Box(k % 600, k // 600 % 790, k % 600 + 1, k // 600 % 790 + 1) for k in range(n)
    ],
}


def page_of(found: list[Box], top: float = 600) -> Content:
    """One page with these drawings and ten lines of text from `top` down."""
    lines = tuple(
        TextLine(
            f"p1-l{k}",
            (TextRun(f"Running text, line {k}.", "Times", 10.0),),
            Box(72, top + 12 * k, 500, top + 10 + 12 * k),
        )
        for k in range(10)
    )
    drawn = tuple(Drawing(f"p1-d{k}", box) for k, box in enumerate(found))
    return Content(Source("test.pdf", SourceFormat.PDF), (Page(1, lines, (), drawn, 612, 792),))


@pytest.mark.parametrize("family", FAMILIES)
def test_a_page_of_drawings_is_laid_out_in_linear_time(family: str) -> None:
    top = 20 if family == "separate marks" else 600  # the marks then join the text above
    # rebuilding the text's block once per mark only shows from about 16,000 marks
    size = 24_000 if family == "separate marks" else 8_000
    pages = {n: page_of(FAMILIES[family](n), top) for n in (size // 8, size)}
    assert_linear(lambda n: build_document(pages[int(n)]), str, size)


@pytest.mark.benchmark
def test_benchmark_a_page_of_100_000_drawings(benchmark) -> None:  # type: ignore[no-untyped-def]
    """A page at the reader's limit (`MAX_PAGE_GRAPHICS`, 100,000 rectangles of 1 pt on a
    grid, all touching) lays out in under 15 s (#354; 198 s for five such pages before)."""
    page = page_of(FAMILIES["grid"](100_000))
    benchmark.pedantic(lambda: build_document(page), rounds=1, iterations=1)
    assert benchmark.stats.stats.max < 15
