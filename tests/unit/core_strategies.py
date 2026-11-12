"""Hypothesis strategies for the core objects, shared by the core tests."""

from collections.abc import Callable

from hypothesis import strategies as st

from sci2audio.core import (
    Box,
    Content,
    Drawing,
    Metadata,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)

names = st.text(st.characters(exclude_characters="/\\"), min_size=1, max_size=12)
words = st.text(max_size=12)
coords = st.floats(min_value=0, max_value=2000, allow_nan=False, allow_infinity=False)


@st.composite
def boxes(draw: st.DrawFn) -> Box:
    x0, x1 = sorted((draw(coords), draw(coords)))
    y0, y1 = sorted((draw(coords), draw(coords)))
    return Box(x0, y0, x1, y1)


runs = st.builds(
    TextRun,
    text=st.text(min_size=1, max_size=15),
    font=st.sampled_from(["", "Times-Roman", "Helvetica-Bold"]),
    size=st.floats(0, 72),
    bold=st.booleans(),
    italic=st.booleans(),
    box=st.none() | boxes(),
    tags=st.lists(st.sampled_from(["h1", "h2", "li", "em", "p"]), max_size=2).map(tuple),
)


@st.composite
def pages(draw: st.DrawFn, number: int, ids: Callable[[], str]) -> Page:
    """A page whose item ids come from `ids`, which hands out a fresh id per call."""
    size = draw(st.none() | st.tuples(st.floats(1, 5000), st.floats(1, 5000)))
    return Page(
        number=number,
        lines=tuple(
            TextLine(
                ids(),
                tuple(draw(st.lists(runs, min_size=1, max_size=3))),
                draw(st.none() | boxes()),
            )
            for _ in range(draw(st.integers(0, 4)))
        ),
        pictures=tuple(
            Picture(ids(), draw(st.none() | boxes()), draw(words))
            for _ in range(draw(st.integers(0, 2)))
        ),
        drawings=tuple(Drawing(ids(), draw(boxes())) for _ in range(draw(st.integers(0, 2)))),
        width=size[0] if size else None,
        height=size[1] if size else None,
    )


@st.composite
def contents(draw: st.DrawFn) -> Content:
    counter = iter(range(10_000))

    def ids() -> str:
        return f"i{next(counter)}"

    return Content(
        source=Source(
            draw(names),
            draw(st.sampled_from(SourceFormat)),
            draw(st.text("0123456789abcdef", max_size=8)),
        ),
        pages=tuple(draw(pages(n, ids)) for n in range(1, draw(st.integers(0, 3)) + 1)),
        metadata=draw(
            st.builds(
                Metadata,
                title=words,
                authors=st.lists(words, max_size=3).map(tuple),
                language=st.sampled_from(["", "en", "en-GB"]),
            )
        ),
    )
