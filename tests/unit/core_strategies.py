"""Hypothesis strategies for the core objects, shared by the core tests."""

from itertools import pairwise

from hypothesis import strategies as st

from sci2audio.core import (
    AudioChunk,
    Block,
    BlockKind,
    Document,
    Edit,
    EditKind,
    Metadata,
    Origin,
    Region,
    Section,
    Source,
    SourceFormat,
    Span,
)

names = st.text(st.characters(exclude_characters="/\\"), min_size=1, max_size=12)
words = st.text(max_size=12)
coords = st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False)


@st.composite
def regions(draw: st.DrawFn, length: int) -> tuple[Region, ...]:
    starts = sorted(draw(st.sets(st.integers(0, length), max_size=3)) | {0})
    out = []
    for start in starts:
        x0, x1 = sorted((draw(coords), draw(coords)))
        y0, y1 = sorted((draw(coords), draw(coords)))
        out.append(Region(draw(st.integers(1, 500)), x0, y0, x1, y1, start))
    return tuple(out)


@st.composite
def blocks(draw: st.DrawFn) -> Block:
    text = draw(st.text(max_size=40))
    origin = draw(
        st.one_of(
            st.builds(Origin),
            st.builds(Origin, regions=regions(len(text))),
            st.builds(Origin, chapter=st.integers(1, 50)),
            st.builds(Origin, line=st.integers(1, 5000)),
        )
    )
    return Block(draw(st.sampled_from(BlockKind)), text, origin)


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
    body = tuple(draw(st.lists(blocks(), max_size=6)))
    return Document(
        source=Source(
            draw(names),
            draw(st.sampled_from(SourceFormat)),
            draw(st.text("0123456789abcdef", max_size=8)),
        ),
        language=draw(st.sampled_from(["en", "en-GB", "de"])),
        blocks=body,
        metadata=draw(
            st.builds(Metadata, title=words, authors=st.lists(words, max_size=3).map(tuple))
        ),
        sections=draw(sections(0, len(body), 1, 2)),
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
    return Edit(
        span,
        kind,
        reason="test reason",
        step=draw(st.sampled_from(["s1", "s2"])),
        replacement=replacement,
    )


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
