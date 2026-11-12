"""Hypothesis strategies for the core objects, shared by the core tests."""

from collections.abc import Callable
from itertools import pairwise

from hypothesis import strategies as st

from sci2audio.core import (
    LABELLED_KINDS,
    AudioChunk,
    Block,
    BlockKind,
    Box,
    Content,
    Document,
    Drawing,
    Edit,
    EditKind,
    FurnitureRole,
    Metadata,
    Page,
    Part,
    Picture,
    Section,
    Source,
    SourceFormat,
    Span,
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


@st.composite
def sections(draw: st.DrawFn, start: int, end: int, level: int, depth: int) -> tuple[Section, ...]:
    """A valid section tree over blocks start..end: cut the range, maybe nest one level more."""
    cuts = sorted(draw(st.lists(st.integers(start, end), max_size=4)))
    out = []
    for a, b in pairwise(cuts):
        children = draw(sections(a, b, level + 1, depth - 1)) if depth > 0 else ()
        out.append(Section(draw(words), level, a, b, children))
    return tuple(out)


@st.composite
def documents(draw: st.DrawFn) -> Document:
    """Content laid out like the layout stage would: every item in exactly one block."""
    content = draw(contents())
    items = draw(st.permutations([item for _, item in content.items().values()]))
    cuts = sorted([*draw(st.lists(st.integers(0, len(items)), max_size=6)), 0, len(items)])
    blocks = []
    for a, b in pairwise(cuts):
        if a == b:
            continue
        text, parts = "", []
        for item in items[a:b]:
            parts.append(Part(item.id, len(text)))
            if isinstance(item, TextLine):
                text += ("\n" if text else "") + item.text
                parts[-1] = Part(item.id, len(text) - len(item.text))
        kind = draw(st.sampled_from(BlockKind))
        role = draw(st.none() | st.sampled_from(FurnitureRole))
        role = role if kind is BlockKind.FURNITURE else None
        words_in = text.split()
        label = draw(st.just("") | st.sampled_from(words_in)) if words_in else ""
        label = label if kind in LABELLED_KINDS else ""
        blocks.append(Block(kind, text, tuple(parts), role=role, label=label))
    labels = st.tuples(*(st.sampled_from(["", "1", "39", "xii"]) for _ in content.pages))
    return Document(
        content=content,
        language=draw(st.sampled_from(["en", "en-GB", "de"])),
        blocks=tuple(blocks),
        sections=draw(sections(0, len(blocks), 1, 2)),
        page_labels=draw(st.just(()) | labels),
    )


@st.composite
def spans_in(draw: st.DrawFn, document: Document) -> Span:
    """A span inside one of the document's blocks (the document needs at least one block)."""
    index = draw(st.integers(0, len(document.blocks) - 1))
    length = len(document.blocks[index].text)
    start = draw(st.integers(0, length))
    return Span(index, start, draw(st.integers(start, length)))


@st.composite
def edits_on(draw: st.DrawFn, span: Span) -> Edit:
    """Any edit whose kind fits the span."""
    empty = span.start == span.end
    kinds = [EditKind.REPLACE, EditKind.ASK, EditKind.PAUSE if empty else EditKind.REMOVE]
    kind = draw(st.sampled_from(kinds))
    replacement = ""
    if kind is EditKind.REPLACE:
        replacement = draw(st.text(min_size=1, max_size=10))
    elif kind is EditKind.ASK:
        replacement = draw(st.text(max_size=10))
    step = draw(st.sampled_from(["s1", "s2"]))
    return Edit(span, kind, reason="test reason", step=step, replacement=replacement)


def chunks_in(document: Document) -> st.SearchStrategy[AudioChunk]:
    files = st.from_regex(r"\A[a-z0-9]{1,8}(/[a-z0-9]{1,8})?\.wav\Z")
    return st.builds(AudioChunk, spans_in(document), files, st.floats(0, 3600))


def overlaps(a: Span, b: Span) -> bool:
    """The overlap rule, written independently of the code under test."""
    if a.block != b.block:
        return False
    if a.start == a.end == b.start == b.end:
        return True
    return a.start < b.end and b.start < a.end
