"""Test documents with pages and font sizes, for the footnote-mark rule (#64).

`make_document` (sci2audio.testing) puts every block on one page with no sizes. The mark
rule also looks at the page a note is printed on and at font sizes (PDF), so these tests
build such documents here: each block is one line of sized runs on a given page.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from hypothesis import strategies as st

from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    Page,
    Part,
    Section,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.testing import make_document


@dataclass(frozen=True)
class Line:
    """One block of one line: its kind, page, label and runs as (text, size)."""

    kind: BlockKind
    page: int
    runs: tuple[tuple[str, float], ...]
    label: str = ""


def sized_document(lines: Sequence[Line], language: str = "en") -> Document:
    """A PDF-like document: each line a block of its own on its page, runs with sizes."""
    pages: dict[int, list[TextLine]] = {}
    blocks = []
    for number, line in enumerate(lines):
        text_line = TextLine(f"l{number}", tuple(TextRun(t, size=s) for t, s in line.runs))
        pages.setdefault(line.page, []).append(text_line)
        blocks.append(Block(line.kind, text_line.text, (Part(text_line.id),), label=line.label))
    last = max(pages, default=0)
    content = Content(
        Source("sized.pdf", SourceFormat.PDF),
        tuple(Page(n, tuple(pages.get(n, ()))) for n in range(1, last + 1)),
    )
    return Document(content=content, language=language, blocks=tuple(blocks))


def body(page: int, *runs: tuple[str, float]) -> Line:
    return Line(BlockKind.PARAGRAPH, page, runs)


def note(page: int, label: str, text: str) -> Line:
    return Line(BlockKind.FOOTNOTE, page, ((label, 7.0), (text, 9.0)) if label else ((text, 9.0),),
                label)  # fmt: skip


# ---- a strategy for documents full of what #64 handles ----------------------------------

_WORDS = st.sampled_from(["noise", "N", "the", "x", "results", "|N |", "a", "Smith,", "end."])
_LABELS = st.sampled_from(["1", "2", "12", "\u2217", "†", "a"])  # \u2217: asterisk operator
_TITLES = st.sampled_from(
    ["References", "7 References", "BIBLIOGRAPHY", "8. Bibliography", "Results", "Notes"]
)
_CAPTION_LABELS = st.sampled_from(["Table 1", "Fig. 2", "Figure 3", "Algorithm 1", "Eq. 4"])


@st.composite
def rule_documents(draw: st.DrawFn) -> Document:
    """Documents with footnotes and their marks set as superscripts, placeholders with and
    without captions, formula numbers and reference sections, so the #64 steps have work to
    do in most examples (a density probe checks it)."""
    # always one mark the rule must remove and its note, whatever else is drawn, so every
    # example exercises the mark rule (#83 lesson: count what the examples really test)
    first = draw(_LABELS)
    blocks: list[Block] = [Block(BlockKind.PARAGRAPH, f"results{first}")]
    tags: dict[int, list[tuple[int, int, str]]] = {0: [(7, 7 + len(first), "sup")]}
    for _ in range(draw(st.integers(1, 8))):
        kind = draw(st.sampled_from([*BlockKind]))
        if kind is BlockKind.PARAGRAPH:
            text, ranges = "", []
            for _ in range(draw(st.integers(1, 5))):
                text += draw(_WORDS)
                if draw(st.booleans()):
                    label = draw(_LABELS)
                    ranges.append((len(text), len(text) + len(label), "sup"))
                    text += label
                text += draw(st.sampled_from([" ", " + ", "\n", ""]))
            tags[len(blocks)] = ranges
            blocks.append(Block(kind, text))
        elif kind is BlockKind.FOOTNOTE:
            label = draw(st.just("") | _LABELS)
            gap = draw(st.sampled_from(["", " ", "\n"]))
            blocks.append(Block(kind, f"{label}{gap}{draw(_WORDS)} note", label=label))
        elif kind is BlockKind.FORMULA:
            number = draw(st.sampled_from(["", "4", "16a"]))
            text = draw(st.sampled_from(["", "x = y", "E = mc2"])) + (
                f" ({number})" if number else ""
            )
            blocks.append(Block(kind, text, label=number))
        elif kind in (BlockKind.TABLE, BlockKind.FIGURE):
            blocks.append(Block(kind, draw(st.sampled_from(["", "a b\nc d"]))))
        elif kind is BlockKind.CAPTION:
            targets = [i for i, b in enumerate(blocks) if b.is_placeholder]
            label = draw(_CAPTION_LABELS)
            describes = draw(st.none() | st.sampled_from(targets)) if targets else None
            blocks.append(Block(kind, f"{label}: words.", describes=describes, label=label))
        elif kind is BlockKind.HEADING:
            blocks.append(Block(kind, draw(_TITLES)))
        else:
            blocks.append(Block(kind, draw(_WORDS)))
    blocks.append(Block(BlockKind.FOOTNOTE, f"{first} The note.", label=first))
    sections = []
    for index, block in enumerate(blocks):
        if block.kind is BlockKind.HEADING:
            if sections:
                last = sections[-1]
                sections[-1] = Section(last.title, 1, last.start, index)
            sections.append(Section(block.text, 1, index, len(blocks)))
    return make_document(
        blocks, draw(st.sampled_from(["en", "en-GB"])), tags=tags, sections=sections
    )
