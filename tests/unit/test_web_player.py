"""The read-along player's data and routes (#78, OU-02; D-294 to D-303).

Part one builds the page's view from hand-made documents and read-along data; part two
runs a real audio job with the fake voice and real ffmpeg (a few seconds, allowed in the
fast tier) and checks the page, the audiobook file route and the path checks (D-295).
"""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import itertools
import json
import os
import re
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from audio_fakes import FakeVoice
from hypothesis import given
from hypothesis import strategies as st
from pdf_maker import Text, make_pdf
from web_helpers import (
    book_folder,
    events,
    make_config,
    offline,  # noqa: F401 - fixture
    paper_bytes,
    program,
    upload,
)

from sci2audio import __version__
from sci2audio.app import JobRunner
from sci2audio.core import (
    Block,
    BlockKind,
    Box,
    Document,
    Edit,
    EditKind,
    Page,
    Part,
    Section,
    Span,
    TextLine,
    TextRun,
)
from sci2audio.extraction import extract_pdf
from sci2audio.layout import build_document
from sci2audio.output import ReadAlong
from sci2audio.output.readalong import ChapterTimes, ChunkTimes, to_json
from sci2audio.testing.documents import make_document
from sci2audio.textprep import BUILT_IN_STEPS, Category, Stage, StepContext, TextStep, unspoken
from sci2audio.voices import EngineError
from sci2audio.web import create_app, player, tasks
from sci2audio.web.player import (
    MAX_INDENT,
    AudioRecord,
    PlayerError,
    bare_name,
    build_view,
    indented,
    joined_hyphens,
    read_audio_record,
    sentence_starts,
    shown,
)
from sci2audio.web.project import PROJECT
from sci2audio.web.security import PERMISSIONS_POLICY

# ---- the view, from hand-made data ------------------------------------------------------


def record(**changes: Any) -> AudioRecord:
    values: dict[str, Any] = {
        "voice": "af_heart",
        "switched_off": frozenset({"footnote-texts"}),
        "duration": 10.0,
        "chunks": 0,
        "m4b": "Book.m4b",
        "mp3s": ("Book - 01 One.mp3",),
        "readalong": "Book.readalong.json",
    }
    values.update(changes)
    return AudioRecord(**values)


def readalong(
    spans: Sequence[tuple[int, int, int]],
    chapters: Sequence[tuple[str, int]] = (("One", 0),),
    chapter_of: Sequence[int] | None = None,
    joins: Sequence[int] = (),
) -> ReadAlong:
    """Chunks one second apart; `chapters` as (title, first chunk); the chunks numbered in
    `joins` go on with the sentence of the chunk before them (#480)."""
    owners = list(chapter_of) if chapter_of is not None else [0] * len(spans)
    chunks = tuple(
        ChunkTimes(owners[n], float(n), n + 0.5, Span(*span), n in joins)
        for n, span in enumerate(spans)
    )
    times = tuple(
        ChapterTimes(title, f"Book - {n + 1:02d} {title}.mp3", float(first), 99.0, first)
        for n, (title, first) in enumerate(chapters)
    )
    return ReadAlong(24000, float(len(spans)), "Book.m4b", times, chunks)


def on_pages(document: Document, pages: Sequence[int], labels: Sequence[str] = ()) -> Document:
    """The document with block n's lines on page `pages[n]`."""
    lines: dict[int, list[Any]] = {}
    items = {line.id: line for line in document.content.pages[0].lines}
    for number, block in enumerate(document.blocks):
        for part in block.parts:
            lines.setdefault(pages[number], []).append(items[part.item])
    count = max(pages)
    content = dataclasses.replace(
        document.content,
        pages=tuple(Page(n, tuple(lines.get(n, ()))) for n in range(1, count + 1)),
    )
    return dataclasses.replace(document, content=content, page_labels=tuple(labels))


def texts(view: player.PlayerView) -> list[str]:
    out = []
    for chapter in view.chapters:
        blocks = ([chapter.title_block] if chapter.title_block else []) + chapter.blocks
        out += ["".join(p.text for p in b.pieces) or b.notice for b in blocks]
    return out


def test_every_chunk_is_one_element_around_exactly_its_text() -> None:
    document = make_document(
        [("heading", "1 One"), ("paragraph", "First sentence. Second (Smith 2020) one.")]
    )
    data = readalong([(0, 0, 5), (1, 0, 15), (1, 16, 40)])
    view = build_view(document, record(chunks=3), data)
    (chapter,) = view.chapters
    assert chapter.title_block is not None
    assert chapter.title_block.heading == 2
    pieces = chapter.blocks[0].pieces
    assert [(p.text, p.element, p.chunk) for p in pieces] == [
        ("First sentence.", "s1", 1),
        (" ", None, None),
        ("Second (Smith 2020) one.", "s2", 2),
    ]
    assert [c[3] for c in view.chunks] == ["s0", "s1", "s2"]
    assert view.mode == "mp3"
    data = view.data("0123456789abcdef")
    assert data["document"] == "0123456789abcdef"
    assert data["chapters"][0]["file"] == "Book - 01 One.mp3"


CUT = "Before it. A long sentence, cut at its comma, and once more here. After it."


def test_the_pieces_of_a_cut_sentence_are_one_element() -> None:
    """#480 (D-730): the pieces of one cut sentence are one element on the page, with the
    text between them; each piece stays its own chunk with its own times."""
    document = make_document([("paragraph", CUT)])
    spans = [(0, 0, 10), (0, 11, 27), (0, 28, 45), (0, 46, 65), (0, 66, 75)]
    view = build_view(document, record(chunks=5), readalong(spans, joins=(2, 3)))
    pieces = view.chapters[0].blocks[0].pieces
    assert [(p.text, p.element, p.chunk) for p in pieces] == [
        ("Before it.", "s0", 0),
        (" ", None, None),
        ("A long sentence, cut at its comma, and once more here.", "s1", 1),
        (" ", None, None),
        ("After it.", "s4", 4),
    ]
    assert [c[3] for c in view.chunks] == ["s0", "s1", "s1", "s1", "s4"]
    assert [c[:2] for c in view.chunks] == [(float(n), n + 0.5) for n in range(5)]
    # the player steps by sentence: each chunk's sentence, by its first piece
    assert view.data("d")["sentences"] == [0, 1, 1, 1, 4]
    assert [list(c) for c in view.chunks] == view.data("d")["chunks"]
    # an audiobook made before #480 has no joins: one element per piece, as before
    old = build_view(document, record(chunks=5), readalong(spans))
    assert [c[3] for c in old.chunks] == ["s0", "s1", "s2", "s3", "s4"]
    assert old.data("d")["sentences"] == [0, 1, 2, 3, 4]
    assert [p.text for p in old.chapters[0].blocks[0].pieces if p.element] == [
        "Before it.",
        "A long sentence,",
        "cut at its comma,",
        "and once more here.",
        "After it.",
    ]


def test_a_join_never_crosses_a_block_or_follows_an_empty_span() -> None:
    """A `joins` the page can't follow (a hand-made or broken file) starts a sentence."""
    document = make_document([("paragraph", "One, two."), ("paragraph", "Three, four.")])
    # chunk 2 says it joins chunk 1, which lies in the block before
    data = readalong([(0, 0, 4), (0, 5, 9), (1, 0, 6), (1, 7, 12)], joins=(1, 2, 3))
    view = build_view(document, record(chunks=4), data)
    assert [c[3] for c in view.chunks] == ["s0", "s0", "s2", "s2"]
    # chunk 2 joins chunk 1, whose span is empty (a pause or a notice read at a point)
    document = make_document([("paragraph", "One two, three four.")])
    data = readalong([(0, 0, 8), (0, 8, 8), (0, 9, 20)], joins=(2,))
    view = build_view(document, record(chunks=3), data)
    assert [c[3] for c in view.chunks] == ["s0", "s0", "s2"]
    assert view.sentences == [0, 1, 2]


def test_a_join_follows_only_the_chunk_the_page_draws_just_before_it() -> None:
    """A hand-made file whose chunk order is not the text's: chunk 2 says it joins chunk 1,
    but chunk 0's words stand between them. The page, the markers and the player group the
    chunks by one rule (`sentence_starts`), so none of them joins these."""
    document = make_document([("paragraph", "One, two, three.")])
    data = readalong([(0, 5, 9), (0, 0, 4), (0, 10, 16)], joins=(2,))
    view = build_view(document, record(chunks=3), data)
    assert [c[3] for c in view.chunks] == ["s0", "s1", "s2"]
    assert sentence_starts(data, document) == view.sentences == [0, 1, 2]
    # chunk 1 overlaps chunk 0, so the page skips it (it shares chunk 0's element) and draws
    # chunk 2 right after chunk 0: chunk 2's join to chunk 1 can't be shown, and is ignored
    document = make_document([("paragraph", "One two three, four five six.")])
    data = readalong([(0, 0, 13), (0, 4, 9), (0, 14, 29)], joins=(2,))
    view = build_view(document, record(chunks=3), data)
    assert [c[3] for c in view.chunks] == ["s0", "s0", "s2"]
    assert sentence_starts(data, document) == view.sentences == [0, 1, 2]
    # in text order, the same join is followed
    document = make_document([("paragraph", "One, two, three.")])
    data = readalong([(0, 0, 4), (0, 5, 9), (0, 10, 16)], joins=(2,))
    view = build_view(document, record(chunks=3), data)
    assert [c[3] for c in view.chunks] == ["s0", "s1", "s1"]
    assert sentence_starts(data, document) == view.sentences == [0, 1, 1]


def test_an_old_chunk_with_nothing_to_speak_is_never_a_sentence() -> None:
    """#652 (4): a read-along made before the fix has a chunk for a block of only "-" and
    one for a dash after a question. The page draws no sentence for them, never makes the
    block the read element, and they are pieces of the sentence before them, so Previous,
    Next and the highlight step over them as over an empty span."""
    document = make_document(
        [
            ("paragraph", "- First item?"),
            ("paragraph", "-"),
            ("paragraph", "Second item? \u2013"),
            ("paragraph", "Third item."),
        ]
    )
    data = readalong([(0, 0, 13), (1, 0, 1), (2, 0, 12), (2, 13, 14), (3, 0, 11)])
    view = build_view(document, record(chunks=5), data)
    assert [c[3] for c in view.chunks] == ["s0", "s0", "s2", "s2", "s4"]
    assert sentence_starts(data, document) == view.sentences == [0, 0, 2, 2, 4]
    dash = view.chapters[0].blocks[1]
    assert not dash.read
    assert dash.element is None
    assert [p.element for p in dash.pieces] == [None]
    assert [p.text for p in view.chapters[0].blocks[2].pieces if p.element] == ["Second item?"]


def test_a_chunk_with_nothing_to_speak_that_opens_a_chapter_leads_the_sentence_after_it() -> None:
    """#652 (4): with no sentence before it in its chapter, the chunk goes with the sentence
    after it; a sentence of another chapter is never its sentence."""
    document = make_document(
        [("paragraph", "One."), ("paragraph", "\u2022"), ("paragraph", "Two.")],
        sections=[Section("One", 1, 0, 1), Section("Two", 1, 1, 3)],
    )
    data = readalong([(0, 0, 4), (1, 0, 1), (2, 0, 4)], (("One", 0), ("Two", 1)), [0, 1, 1])
    view = build_view(document, record(chunks=3), data)
    assert [c[3] for c in view.chunks] == ["s0", "s2", "s2"]
    assert sentence_starts(data, document) == view.sentences == [0, 1, 1]
    # a run of them opens the chapter (#652): all lead the sentence after them, so
    # Next from "One." goes to the run's start and never to a chunk with no element
    document = make_document(
        [("paragraph", "One."), ("paragraph", "-"), ("paragraph", "\u2022"), ("paragraph", "Two.")],
        sections=[Section("One", 1, 0, 1), Section("Two", 1, 1, 4)],
    )
    data = readalong(
        [(0, 0, 4), (1, 0, 1), (2, 0, 1), (3, 0, 4)], (("One", 0), ("Two", 1)), [0, 1, 1, 1]
    )
    view = build_view(document, record(chunks=4), data)
    assert [c[3] for c in view.chunks] == ["s0", "s3", "s3", "s3"]
    assert sentence_starts(data, document) == view.sentences == [0, 1, 1, 1]
    # in one block: the bullet before the item's words
    document = make_document([("paragraph", "\u2022\nItem one.")])
    data = readalong([(0, 0, 1), (0, 2, 11)])
    view = build_view(document, record(chunks=2), data)
    assert [c[3] for c in view.chunks] == ["s1", "s1"]
    assert sentence_starts(data, document) == view.sentences == [0, 0]


@pytest.mark.parametrize(
    ("blocks", "spans"),
    [
        # the marker opens the item's block, after a sentence of another block
        (["Intro.", "•\nItem one."], [(0, 0, 6), (1, 0, 1), (1, 2, 11)]),
        # the marker stands between two sentences of one block
        (["Intro. • Item one."], [(0, 0, 6), (0, 7, 8), (0, 9, 18)]),
    ],
)
def test_a_marker_in_mid_chapter_belongs_to_the_item_it_leads(
    blocks: list[str], spans: list[tuple[int, int, int]]
) -> None:
    """#869: a silent chunk followed in its block by the sentence it opens leads that
    sentence (the cutter's rule since #855), for the highlight and for Previous, Next and
    the markers alike: it is never highlighted with one sentence and counted with another."""
    document = make_document([("paragraph", text) for text in blocks])
    data = readalong(spans)
    view = build_view(document, record(chunks=3), data)
    assert [c[3] for c in view.chunks] == ["s0", "s2", "s2"]
    assert sentence_starts(data, document) == view.sentences == [0, 1, 1]
    assert [p.text for b in view.chapters[0].blocks for p in b.pieces if p.element] == [
        "Intro.",
        "Item one.",
    ]


def test_a_notice_read_for_printed_brackets_is_still_a_sentence() -> None:
    """#652: a placeholder's chunk reads its notice, so printed text of only brackets in a
    code block is no chunk with nothing to speak."""
    document = make_document([("paragraph", "Run this:"), ("code", "{ }")])
    data = readalong([(0, 0, 9), (1, 0, 3)])
    view = build_view(document, record(chunks=2), data)
    assert [c[3] for c in view.chunks] == ["s0", "b1"]
    assert sentence_starts(data, document) == view.sentences == [0, 1]


def test_an_empty_span_belongs_to_the_sentence_before_it_or_its_block() -> None:
    document = make_document([("paragraph", "Long one. Then"), ("figure", "")])
    data = readalong([(0, 0, 9), (0, 9, 9), (1, 0, 0)])
    view = build_view(
        document, record(chunks=3, switched_off=frozenset({"tables-and-figures"})), data
    )
    assert [c[3] for c in view.chunks] == ["s0", "s0", "b1"]
    figure = view.chapters[0].blocks[1]
    assert figure.element == "b1"
    assert figure.chunk == 2
    assert figure.read


def test_furniture_is_left_out_and_printed_pages_are_marked() -> None:
    document = make_document(
        [
            ("paragraph", "On page one."),
            ("furniture", "39"),
            ("paragraph", "On page two."),
            ("paragraph", "Still page two."),
        ]
    )
    document = on_pages(document, [1, 1, 2, 2], ["38", "39"])
    data = readalong([(0, 0, 12), (2, 0, 12), (3, 0, 15)])
    view = build_view(document, record(chunks=3), data)
    blocks = view.chapters[0].blocks
    assert [b.index for b in blocks] == [0, 2, 3]
    assert [b.page for b in blocks] == ["38", "39", ""]


def test_pages_without_a_printed_label_use_the_page_number() -> None:
    document = on_pages(make_document([("paragraph", "A."), ("paragraph", "B.")]), [1, 2])
    view = build_view(document, record(chunks=2), readalong([(0, 0, 2), (1, 0, 2)]))
    assert [b.page for b in view.chapters[0].blocks] == ["1", "2"]


def test_a_placeholder_shows_the_notice_the_audiobook_reads() -> None:
    blocks = [
        ("paragraph", "See the table."),
        ("table", "a b\n1 2"),
        Block(BlockKind.CAPTION, "Table 2: Results.", describes=1, label="Table 2"),
        Block(BlockKind.FORMULA, "x = y (3)", label="3"),
    ]
    document = make_document(blocks)
    data = readalong([(0, 0, 14), (1, 0, 7), (2, 0, 17), (3, 0, 9)])
    view = build_view(document, record(chunks=4), data)
    table, caption, formula = view.chapters[0].blocks[1:]
    assert table.notice == "Table 2 is skipped."
    assert table.printed == "a b 1 2"
    assert table.element == "b1"
    assert view.chunks[1][3] == "b1"
    assert caption.notice == ""
    assert caption.pieces[0].element == "s2"
    assert formula.notice.startswith("Formula 3")
    # switched off, the formula was read as printed: its text is the sentence
    off = build_view(document, record(chunks=4, switched_off=frozenset({"formulas"})), data)
    formula = off.chapters[0].blocks[3]
    assert formula.notice == ""
    assert formula.pieces[0].text == "x = y (3)"


def test_a_code_block_shows_its_notice_and_its_code_with_its_line_breaks() -> None:
    """#280, D-546: the notice is the sentence; the code is shown open, line breaks kept."""
    code = 'import seaborn as sns\ng = sns.relplot(\ng.savefig("paper_demo.pdf")'
    document = make_document([("paragraph", "Run this:"), ("code", code)])
    data = readalong([(0, 0, 9), (1, 0, len(code))])
    view = build_view(document, record(chunks=2), data)
    block = view.chapters[0].blocks[1]
    assert (block.notice, block.code, block.printed) == ("A code block is skipped.", code, "")
    assert block.element == "b1"
    assert view.chunks[1][3] == "b1"
    off = build_view(document, record(chunks=2, switched_off=frozenset({"code"})), data)
    block = off.chapters[0].blocks[1]
    assert (block.notice, block.code) == ("", "")
    assert block.pieces[0].text == " ".join(code.split("\n"))


CHAR = 5.25  # points: one character of a 10 point typewriter font


def boxed(document: Document, indents: Sequence[int], left: float = 166.86) -> Document:
    """The document with a box for each line of page 1, `indents[k]` characters in for its
    k-th line, one line pitch apart, as a PDF gives them."""
    page = document.content.pages[0]
    lines = tuple(
        dataclasses.replace(
            line,
            box=Box(
                left + CHAR * indent,
                100 + 12 * k,
                left + CHAR * (indent + len(line.text)),
                110 + 12 * k,
            ),
        )
        for k, (line, indent) in enumerate(zip(page.lines, indents, strict=True))
    )
    content = dataclasses.replace(document.content, pages=(dataclasses.replace(page, lines=lines),))
    return dataclasses.replace(document, content=content)


SEABORN = ["g = sns.relplot(", 'data=fmri, kind="line",', 'x="timepoint", y="signal",', ")"]


def test_a_pdf_code_block_is_shown_with_its_printed_indent() -> None:
    """#282: a PDF line holds no leading spaces; the view indents each line by its left
    edge against the block's leftmost line, in characters of the font. The block's text,
    and so the script, stays as printed."""
    code = "\n".join(SEABORN)
    document = boxed(make_document([("code", code)]), [0, 4, 4, 0])
    view = build_view(document, record(chunks=1), readalong([(0, 0, len(code))]))
    shown_code = view.chapters[0].blocks[0].code
    assert shown_code.split("\n") == [
        "g = sns.relplot(",
        '    data=fmri, kind="line",',
        '    x="timepoint", y="signal",',
        ")",
    ]
    assert document.blocks[0].text == code


def test_a_code_block_without_line_boxes_keeps_its_own_spaces() -> None:
    """EPUB, Markdown and text code: its text holds its indent already."""
    code = "def f():\n    return 1"
    document = make_document([("code", code)])
    view = build_view(document, record(chunks=1), readalong([(0, 0, len(code))]))
    assert view.chapters[0].blocks[0].code == code


def test_the_indent_is_measured_on_each_page_and_capped() -> None:
    """A listing over a page break (#283) is measured against its leftmost line on each
    page (odd and even pages have other margins); a line is never drawn more than
    `MAX_INDENT` characters in."""
    block = Block(
        BlockKind.CODE,
        "a(\nb\nc(\nd\ne",
        tuple(Part(f"l{k}", start) for k, start in enumerate([0, 3, 5, 8, 10])),
    )
    lefts = [(1, 100.0), (1, 110.5), (2, 60.0), (2, 70.5), (2, 60.0 + CHAR * 90)]
    texts = ["a(", "b", "c(", "d", "e"]
    lines = {
        f"l{k}": (page, TextLine(f"l{k}", (TextRun(text),), Box(x0, 0, x0 + CHAR * len(text), 10)))
        for k, ((page, x0), text) in enumerate(zip(lefts, texts, strict=True))
    }
    assert indented(block, lines).split("\n") == ["a(", "  b", "c(", "  d", " " * MAX_INDENT + "e"]


def _line(key: str, text: str, x0: float, width: float | None = None) -> TextLine:
    return TextLine(key, (TextRun(text),), Box(x0, 0, x0 + (width or CHAR * len(text)), 10))


def _body(page: int, left: float, count: int = 5) -> list[TextLine]:
    """Running text on a page, its column `left` points from the page's edge."""
    return [_line(f"p{page}-{k}", "Running text.", left, width=400) for k in range(count)]


def test_a_later_page_part_of_only_indented_lines_keeps_its_indent() -> None:
    """#612: a listing's part on a later page made only of indented lines is measured
    against the first page's leftmost line, shifted by the two pages' text-column edges
    (here page 2's column stands 18 points further right), not drawn flush."""
    block = Block(
        BlockKind.CODE, "\n".join(SEABORN[:3]), (Part("a", 0), Part("b", 17), Part("c", 41))
    )
    code = {
        "a": (1, _line("a", SEABORN[0], 72.0)),
        "b": (2, _line("b", SEABORN[1], 90.0 + 4 * CHAR)),
        "c": (2, _line("c", SEABORN[2], 90.0 + 4 * CHAR)),
    }
    pages = {
        1: [*_body(1, 72.0), code["a"][1]],
        2: [code["b"][1], code["c"][1], *_body(2, 90.0)],
    }
    assert indented(block, code, pages).split("\n") == [
        SEABORN[0],
        "    " + SEABORN[1],
        "    " + SEABORN[2],
    ]
    assert block.text == "\n".join(SEABORN[:3])  # the text, and so the script, as printed


def test_a_later_page_part_is_never_measured_right_of_its_own_leftmost_line() -> None:
    """#612: where the column edges would put the reference right of the part's leftmost
    line, that line is the reference: no line is drawn left of the block's edge. Page 1's
    code stands 10 points right of its column (72), page 2's flush with its column (90),
    so the shifted reference (100) lies right of page 2's leftmost code line (90)."""
    block = Block(BlockKind.CODE, "f(\nx\ny", (Part("a", 0), Part("b", 3), Part("c", 5)))
    code = {
        "a": (1, _line("a", "f(", 82.0)),
        "b": (2, _line("b", "x", 90.0 + 2 * CHAR)),
        "c": (2, _line("c", "y", 90.0)),
    }
    pages = {1: [*_body(1, 72.0), code["a"][1]], 2: [code["b"][1], code["c"][1], *_body(2, 90.0)]}
    assert indented(block, code, pages).split("\n") == ["f(", "  x", "y"]


def test_one_line_set_wider_does_not_change_the_character_width() -> None:
    """The width is the median over the block's lines: one line whose box is wider than
    its letters (a wide glyph, a box padded by the PDF) leaves the others' indent."""
    block = Block(BlockKind.CODE, "f(\nx\ny", (Part("a", 0), Part("b", 3), Part("c", 5)))
    boxes = {"a": (0.0, "f(", 2), "b": (4 * CHAR, "x", 1), "c": (0.0, "y", 4)}
    lines = {
        key: (1, TextLine(key, (TextRun(text),), Box(x0, 0, x0 + CHAR * chars, 10)))
        for key, (x0, text, chars) in boxes.items()
    }
    assert indented(block, lines).split("\n") == ["f(", "    x", "y"]


def test_seaborn_shows_its_four_argument_lines_indented() -> None:
    """AC-282.2: the seaborn paper's listing on page 2, as the corpus PDF prints it."""
    paper = (
        Path(__file__).resolve().parents[1] / "corpus" / "papers" / "joss2021-waskom-seaborn.pdf"
    )
    document = build_document(extract_pdf(paper))
    (block,) = [b for b in document.blocks if b.kind is BlockKind.CODE]
    shown_lines = indented(block, player._code_lines(document)).split("\n")
    assert [line for line in shown_lines if line.startswith(" ")] == [
        '    data=fmri, kind="line",',
        '    x="timepoint", y="signal",',
        '    hue="event", style="event", col="region",',
        "    height=3.5, aspect=.8,",
    ]
    assert [line.strip() for line in shown_lines] == block.text.split("\n")


def test_chapters_not_in_the_audiobook_are_not_shown() -> None:
    document = make_document(
        [
            ("heading", "Intro"),
            ("paragraph", "Text."),
            ("heading", "References"),
            ("paragraph", "R."),
        ],
        sections=(Section("Intro", 1, 0, 2), Section("References", 1, 2, 4)),
    )
    view = build_view(document, record(chunks=2), readalong([(0, 0, 5), (1, 0, 5)]))
    assert [c.title for c in view.chapters] == ["One"]  # and nothing names the others (#472)
    assert not hasattr(view, "left_out")


def test_heading_levels_follow_the_sections() -> None:
    document = make_document(
        [("heading", "1 A"), ("heading", "1.1 B"), ("paragraph", "x."), ("heading", "Loose")],
        sections=(Section("1 A", 1, 0, 4, (Section("1.1 B", 2, 1, 4),)),),
    )
    data = readalong([(0, 0, 3), (1, 0, 5), (2, 0, 2), (3, 0, 5)])
    view = build_view(document, record(chunks=4), data)
    chapter = view.chapters[0]
    assert chapter.title_block is not None
    assert chapter.title_block.heading == 2
    assert [b.heading for b in chapter.blocks] == [3, 0, 4]


class _Mover(TextStep):
    """Reads block 3 (a footnote) at position 10 of block 1 (#213)."""

    id = "places"
    languages = ("*",)
    category = Category.FOOTNOTES
    stage = Stage.MOVE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        to = Span(1, 10, 10)
        return [Edit(Span(3, 0, 9), EditKind.MOVE, "read at its mark", self.id, to=to)]


def test_a_moved_footnote_shows_after_the_block_it_is_read_in() -> None:
    """#213 (plan Q8): the note shows where the voice reads it, in the mark's chapter; the
    page it starts is marked on the next block printed there."""
    document = make_document(
        [
            ("heading", "1 One"),
            ("paragraph", "It works.1 It holds."),
            ("heading", "2 Two"),
            Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
            ("paragraph", "More."),
        ],
        sections=[Section("1 One", 1, 0, 2), Section("2 Two", 1, 2, 5)],
    )
    document = on_pages(document, [1, 1, 1, 2, 2])
    spans = [(0, 0, 5), (1, 0, 9), (3, 0, 9), (1, 11, 20), (2, 0, 5), (4, 0, 5)]
    data = readalong(spans, (("One", 0), ("Two", 4)), [0, 0, 0, 0, 1, 1])
    steps = [*BUILT_IN_STEPS, _Mover()]
    view = build_view(document, record(chunks=6), data, steps)
    one, two = view.chapters
    assert [b.index for b in one.blocks] == [1, 3]
    assert [b.index for b in two.blocks] == [4]
    assert [(b.page, b.heading) for b in one.blocks] == [("", 0), ("", 0)]
    assert two.blocks[0].page == "2"  # the note no longer starts page 2: the next block does
    assert [c[3] for c in view.chunks] == ["s0", "s1", "s2", "s3", "s4", "s5"]
    assert texts(view) == ["1 One", "It works.1 It holds.", "1 A note.", "2 Two", "More."]
    # without the move, the note stays where it is printed
    plain = build_view(document, record(chunks=6), data)
    assert [b.index for b in plain.chapters[1].blocks] == [3, 4]


def test_an_audiobook_read_with_notes_where_printed_shows_them_there() -> None:
    """The page is built by today's steps, the audio may be older. A read-along
    that reads the note where it is printed (before #213) shows it there, in its printed
    chapter, although today's steps would move it."""
    document = make_document(
        [
            ("heading", "1 One"),
            ("paragraph", "It works.1 It holds."),
            ("heading", "2 Two"),
            Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
            ("paragraph", "More."),
        ],
        sections=[Section("1 One", 1, 0, 2), Section("2 Two", 1, 2, 5)],
    )
    document = on_pages(document, [1, 1, 1, 2, 2])
    spans = [(0, 0, 5), (1, 0, 9), (1, 11, 20), (2, 0, 5), (3, 0, 9), (4, 0, 5)]
    data = readalong(spans, (("One", 0), ("Two", 3)), [0, 0, 0, 1, 1, 1])
    view = build_view(document, record(chunks=6), data, [*BUILT_IN_STEPS, _Mover()])
    one, two = view.chapters
    assert [b.index for b in one.blocks] == [1]
    assert [b.index for b in two.blocks] == [3, 4]
    assert two.blocks[0].page == "2"
    assert [c[3] for c in view.chunks] == ["s0", "s1", "s2", "s3", "s4", "s5"]


class _ToTheStart(TextStep):
    """Reads block 1 (a footnote) at the start of block 2, the next chapter's heading."""

    id = "places"
    languages = ("*",)
    category = Category.FOOTNOTES
    stage = Stage.MOVE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return [Edit(Span(1, 0, 9), EditKind.MOVE, "test", self.id, to=Span(2, 0, 0))]


def test_a_chapter_that_starts_with_a_moved_block_is_the_chapter_it_is_read_in() -> None:
    """The chapter is found from where its first piece is read, not from where
    that piece is printed."""
    document = make_document(
        [
            ("heading", "1 One"),
            Block(BlockKind.FOOTNOTE, "1 A note.", label="1"),
            ("heading", "2 Two"),
            ("paragraph", "More."),
        ],
        sections=[Section("1 One", 1, 0, 2), Section("2 Two", 1, 2, 4)],
    )
    spans = [(0, 0, 5), (1, 0, 9), (2, 0, 5), (3, 0, 5)]
    data = readalong(spans, (("One", 0), ("Two", 1)), [0, 1, 1, 1])
    view = build_view(document, record(chunks=4), data, [*BUILT_IN_STEPS, _ToTheStart()])
    one, two = view.chapters
    assert (one.title_block and one.title_block.index, [b.index for b in one.blocks]) == (0, [])
    assert two.title_block is not None
    assert (two.title_block.index, [b.index for b in two.blocks]) == (2, [1, 3])


class _Together(TextStep):
    """Reads the footnotes `notes` at one position `to`."""

    id = "places"
    languages = ("*",)
    category = Category.FOOTNOTES
    stage = Stage.MOVE

    def __init__(self, notes: Sequence[int], to: Span) -> None:
        self.notes, self.to = notes, to

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return [Edit(Span(n, 0, 9), EditKind.MOVE, "test", self.id, to=self.to) for n in self.notes]


def _notes_paper(notes: int) -> Document:
    """Chapter One: a heading and "It works.1 It holds."; chapter Two: a heading, `notes`
    footnotes printed together and "More."."""
    blocks: list = [
        ("heading", "1 One"),
        ("paragraph", "It works.1 It holds."),
        ("heading", "2 Two"),
    ]
    blocks += [Block(BlockKind.FOOTNOTE, f"{n} A note.", label=str(n)) for n in range(1, notes + 1)]
    blocks.append(("paragraph", "More."))
    return make_document(
        blocks, sections=[Section("1 One", 1, 0, 2), Section("2 Two", 1, 2, 4 + notes)]
    )


@pytest.mark.parametrize("notes", [2, 3])
@pytest.mark.parametrize("at", [10, 0], ids=["mid-block", "at-the-start"])
def test_notes_read_together_at_one_position_all_show_where_they_are_read(
    notes: int, at: int
) -> None:
    """The voice reads the target, note 1, note 2, ..., the rest of the target;
    every note of that stretch is shown in the target's chapter, after the target."""
    document = _notes_paper(notes)
    moved = list(range(3, 3 + notes))
    head = [(1, 0, 9)] if at else []
    tail = [(1, 11, 20)] if at else [(1, 0, 20)]
    spans = [(0, 0, 5), *head, *[(n, 0, 9) for n in moved], *tail, (2, 0, 5), (3 + notes, 0, 5)]
    two = len(spans) - 2
    data = readalong(spans, (("One", 0), ("Two", two)), [0] * two + [1, 1])
    steps = [*BUILT_IN_STEPS, _Together(moved, Span(1, at, at))]
    view = build_view(document, record(chunks=len(spans)), data, steps)
    one, two_view = view.chapters
    assert [b.index for b in one.blocks] == [1, *moved]
    assert [b.index for b in two_view.blocks] == [3 + notes]


def test_notes_printed_together_and_read_there_stay_where_printed() -> None:
    """An old-style read-along reads two notes together where they are printed,
    under a heading that does not hold their marks: they stay there."""
    document = _notes_paper(2)
    spans = [(0, 0, 5), (1, 0, 20), (2, 0, 5), (3, 0, 9), (4, 0, 9), (5, 0, 5)]
    data = readalong(spans, (("One", 0), ("Two", 2)), [0, 0, 1, 1, 1, 1])
    steps = [*BUILT_IN_STEPS, _Together([3, 4], Span(1, 10, 10))]
    view = build_view(document, record(chunks=6), data, steps)
    assert [[b.index for b in c.blocks] for c in view.chapters] == [[1], [3, 4, 5]]


def test_a_block_with_nothing_read_says_so() -> None:
    document = make_document([("paragraph", "Read."), ("paragraph", "Removed by a step.")])
    view = build_view(document, record(chunks=1), readalong([(0, 0, 5)]))
    removed = view.chapters[0].blocks[1]
    assert not removed.read
    assert removed.pieces[0].text == "Removed by a step."


def test_a_span_outside_its_block_is_refused() -> None:
    document = make_document([("paragraph", "Short.")])
    with pytest.raises(PlayerError) as caught:
        build_view(document, record(chunks=1), readalong([(0, 0, 60)]))
    assert caught.value.key == "listen.mismatch"
    with pytest.raises(PlayerError):
        build_view(document, record(chunks=1), readalong([(4, 0, 1)]))


def test_line_breaks_show_as_spaces_and_hyphenated_words_join() -> None:
    assert shown("exam-\nple and\nmore") == "exam-ple and more"
    assert shown("exam-\nple and\nmore", joined=frozenset({4})) == "example and more"
    assert (
        shown("exam-\nple", 0, 5, frozenset({4})) + shown("exam-\nple", 5, None, {4}) == "example"
    )


def test_a_word_the_hyphen_step_joined_shows_joined_and_a_kept_hyphen_as_printed() -> None:
    """#286: the read-along shows what the line-end-hyphens step decided, as the voice reads
    it ("contributing"), and keeps a hyphen the step kept ("COVID-19"), also when a
    sentence's piece ends between the hyphen and the line break."""
    text = "asking questions, and con-\ntributing code during COVID-\n19."
    document = make_document([("paragraph", text)])
    cut = text.index("-") + 1  # one piece ends right after the joined word's hyphen
    data = readalong([(0, 0, cut), (0, cut, len(text))])
    view = build_view(document, record(chunks=2), data)
    pieces = [p.text for p in view.chapters[0].blocks[0].pieces]
    assert pieces == ["asking questions, and con", "tributing code during COVID-19."]
    assert joined_hyphens(document, frozenset()) == {0: frozenset({text.index("-")})}
    # characters and hyphenation switched off: the voice read it as printed, and so it shows
    off = build_view(document, record(chunks=2, switched_off=frozenset({"characters"})), data)
    assert "".join(p.text for p in off.chapters[0].blocks[0].pieces) == (
        "asking questions, and con-tributing code during COVID-19."
    )


def test_a_word_joined_at_the_cut_of_a_cut_sentence_shows_joined() -> None:
    """#480 (plans/480-c2-tests.md item 5): the voice's cut falls right after a line-end
    hyphen the hyphen step joined; the joined sentence shows the word joined."""
    text = "asking questions, and con-\ntributing code during COVID-\n19."
    document = make_document([("paragraph", text)])
    cut = text.index("-") + 1
    data = readalong([(0, 0, cut), (0, cut, len(text))], joins=(1,))
    view = build_view(document, record(chunks=2), data)
    pieces = [(p.text, p.element) for p in view.chapters[0].blocks[0].pieces]
    assert pieces == [("asking questions, and contributing code during COVID-19.", "s0")]


@pytest.mark.parametrize(
    "text",
    [
        "See https://www.data-\nbase.org/x for more.",
        "See www.mypack-\nage.org for more.",
        "Code at github.com/foo/sea-\nborn today.",
    ],
)
def test_a_hyphen_in_a_link_at_a_line_end_shows_as_printed(text: str) -> None:
    """#290: the links step wins over the join, so the voice never joined it
    and the address shows with its printed hyphen."""
    document = make_document([("paragraph", text)])
    view = build_view(document, record(chunks=1), readalong([(0, 0, len(text))]))
    assert view.chapters[0].blocks[0].pieces[0].text == text.replace("-\n", "-")
    assert joined_hyphens(document, frozenset()) == {}


def test_a_join_inside_a_removed_reference_list_is_not_shown_as_joined() -> None:
    """#290: the reference-list step removes the whole block first, so the
    line-end-hyphens join there is set aside and the text shows as printed."""
    document = make_document(
        [("heading", "References"), ("paragraph", "Doe, J. (2020). A con-\ntributing study.")],
        sections=(Section("References", 1, 0, 2),),
    )
    assert joined_hyphens(document, frozenset()) == {}


@st.composite
def blocks_and_spans(draw: st.DrawFn) -> tuple[Document, list[tuple[int, int, int]]]:
    words = st.text(alphabet="ab -.\n", min_size=1, max_size=30).filter(
        lambda t: t.strip() and not t.startswith("\n")
    )
    texts = draw(st.lists(words, min_size=1, max_size=5))
    spans = []
    for number, text in enumerate(texts):
        cuts = sorted(draw(st.sets(st.integers(0, len(text)), max_size=6)))
        for start, end in itertools.pairwise(cuts):
            spans.append((number, start, end))
        if draw(st.booleans()):
            at = draw(st.integers(0, len(text)))
            spans.append((number, at, at))
    spans.sort(key=lambda s: (s[0], s[1], s[2]))
    if not spans:
        spans = [(0, 0, 0)]
    return make_document([("paragraph", t) for t in texts]), spans


@given(blocks_and_spans(), st.data())
def test_nothing_is_lost_or_doubled_and_every_chunk_has_one_element(
    case: tuple[Document, list[tuple[int, int, int]]], data: st.DataObject
) -> None:
    document, spans = case
    joins = data.draw(st.sets(st.integers(0, len(spans) - 1)))  # #480: any joins at all
    view = build_view(document, record(chunks=len(spans)), readalong(spans, joins=joins))
    shown_blocks = view.chapters[0].blocks
    joined = joined_hyphens(document, frozenset())
    assert ["".join(p.text for p in b.pieces) for b in shown_blocks] == [
        shown(b.text, joined=joined.get(n, frozenset())) for n, b in enumerate(document.blocks)
    ]
    # a chunk whose text says nothing (#652) is drawn as an empty span is
    silent = [
        start < end and unspoken(document.blocks[block].text[start:end])
        for block, start, end in spans
    ]
    ids = {p.element for b in shown_blocks for p in b.pieces if p.element}
    ids |= {b.element for b in shown_blocks if b.element}
    # a silent chunk takes a neighbour's element; only with none to take it has none
    elements = [chunk[3] for chunk in view.chunks]
    assert all(
        element in ids or (silent[n] and not any(elements)) for n, element in enumerate(elements)
    )
    # the model of #480: a chunk with text that joins the chunk before it, in the same block
    # and with text too, is that chunk's sentence; every other chunk with text is its own
    wanted: list[str] = []
    for number, (block, start, end) in enumerate(spans):
        if silent[number]:
            wanted.append("silent")
            continue
        before = spans[number - 1] if number else None
        follows = (
            number in joins
            and start < end
            and before is not None
            and before[0] == block
            and before[1] < before[2]
            and not silent[number - 1]
        )
        wanted.append(wanted[-1] if follows else f"s{number}")
    elements = [chunk[3] for chunk in view.chunks]
    for number, (block, start, end) in enumerate(spans):
        if start >= end or silent[number]:
            continue
        assert elements[number] == wanted[number]
        if wanted[number] != f"s{number}":
            continue
        # a sentence's element runs from its first piece to the end of its last
        last = number
        while last + 1 < len(spans) and wanted[last + 1] == wanted[number]:
            last += 1
        piece = next(p for b in shown_blocks for p in b.pieces if p.element == f"s{number}")
        text = document.blocks[block].text
        assert piece.text == shown(text, start, spans[last][2], joined.get(block, frozenset()))
    # the player's and the markers' sentences are the page's
    if not any(silent):
        assert view.sentences == [int(w.removeprefix("s")) for w in wanted]
        return
    # a silent chunk followed in its block by a chunk with text (or by one that leads in
    # turn) leads that chunk's sentence, with its element (#869); any other is a piece of
    # the sentence before it; a run of them that opens the chapter (one chapter here) leads
    # the chunk after it (#652); the chunks drawn group as the page draws them. The spans
    # here are in text order and never overlap, so "the chunk the page draws next in the
    # block" is the next chunk.
    leads = [False] * len(spans)
    for number in reversed(range(len(spans) - 1)):
        block, start, end = spans[number + 1]
        leads[number] = (
            silent[number]
            and block == spans[number][0]
            and (leads[number + 1] or (start < end and not silent[number + 1]))
        )
    sentences = view.sentences
    leading = True  # every chunk so far is silent
    for number in range(len(spans)):
        if number and (leading or leads[number - 1] or (silent[number] and not leads[number])):
            assert sentences[number] == sentences[number - 1]
        elif leads[number]:
            assert sentences[number] == number
        if leads[number]:
            led = next(n for n in range(number, len(spans)) if not leads[n])
            assert elements[number] == elements[led]
        leading = leading and silent[number]
    drawn = [n for n, (_, start, end) in enumerate(spans) if start < end and not silent[n]]
    pairs = {(sentences[n], wanted[n]) for n in drawn}
    assert len(pairs) == len({a for a, _ in pairs}) == len({b for _, b in pairs})


def test_bare_names() -> None:
    for good in ("Book.m4b", "Book - 01 Intro.mp3", "a..b.mp3"):
        assert bare_name(good)
    for bad in ("", ".", "..", "../x.mp3", "a/b.mp3", "a\\b.mp3", "C:x.mp3", "x\x00.mp3", None, 3):
        assert not bare_name(bad)


# ---- the routes, after a real audio job --------------------------------------------------

pytestmark = pytest.mark.usefixtures("offline")


def server(tmp_path: Path, voice: FakeVoice | None = None) -> tuple[Any, Any]:
    voice = voice or FakeVoice()
    config = make_config(tmp_path)
    app = create_app(config, voice=lambda models_dir: voice.source())
    return program(app, config), config


def make(
    client: Any, data: bytes = b"", name: str = "paper.pdf", **settings: Any
) -> dict[str, Any]:
    doc = upload(client, data or paper_bytes(), name)
    body = {"kind": "audio", "document": doc["id"], "settings": settings}
    job = client.post("/api/v1/jobs", json=body).json()
    final = json.loads(events(client, job["id"])[-1][1])
    return {"doc": doc, "job": final}


def player_data(page: str) -> dict[str, Any]:
    found = re.search(
        r'<script id="player-data" type="application/json">(.*?)</script>', page, re.S
    )
    assert found is not None
    return json.loads(found[1])


def work_of(config: Any, document: str) -> Path:
    return config.work_root / document


def test_the_listen_page_after_an_audio_job(tmp_path: Path) -> None:
    client, _config = server(tmp_path)
    made = make(client)
    assert made["job"]["state"] == "done", made["job"]
    doc = made["doc"]["id"]
    page = client.get(f"/documents/{doc}/listen")
    assert page.status_code == 200
    text = page.text
    assert "Listen: paper.pdf" in text
    assert "read by a synthetic voice (Heart)" in text
    assert "Not in this audiobook" not in text  # the chapters left out go unnamed (#472)
    assert '<script src="/static/player.js" defer></script>' in text
    data = player_data(text)
    assert data["mode"] == "mp3"
    assert [c["title"] for c in data["chapters"]] == ["Introduction", "Methods"]
    for start, end, chapter, element in data["chunks"]:
        assert f'id="{element}"' in text
        assert start <= end
        assert chapter in (0, 1)
    # the citation the voice left out is struck in its sentence (#392, D-704b)
    sentence = (
        r'<span class="s" id="s\d+" data-chunk="\d+">'
        r'Things happen<s class="cut"> \(Smith, 2020\)</s>'
        r'<span class="visually-hidden"> \(not read\)</span> and more\.'
    )
    assert re.search(sentence + "</span>", text)
    # the other pages link here
    assert f'href="/documents/{doc}/listen"' in client.get(f"/documents/{doc}").text
    assert f'href="/documents/{doc}/listen"' in client.get("/").text
    assert f'href="/documents/{doc}/listen"' in client.get(f"/jobs/{made['job']['id']}").text


def test_the_audiobook_route_serves_only_its_own_files(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    base = f"/api/v1/documents/{doc}/audiobook"
    names = [f["name"] for f in made["job"]["files"]]
    for name in names:
        answer = client.get(f"{base}/{name}")
        assert answer.status_code == 200, name
        assert answer.content == (book_folder(config.output_folder) / name).read_bytes()
    mp3 = next(n for n in names if n.endswith(".mp3"))
    assert client.get(f"{base}/{mp3}").headers["content-type"] == "audio/mpeg"
    part = client.get(f"{base}/{mp3}", headers={"Range": "bytes=0-9"})
    assert part.status_code == 206
    assert len(part.content) == 10
    # the player's audio carries the page-wide headers too (#172)
    assert part.headers["permissions-policy"] == PERMISSIONS_POLICY
    assert part.headers["cross-origin-embedder-policy"] == "require-corp"
    saved = client.get(f"{base}/{mp3}?download=true")
    assert saved.headers["content-disposition"].startswith("attachment")
    (book_folder(config.output_folder) / "other.mp3").write_bytes(b"x")
    for wrong in ("other.mp3", "..%2Fsettings.json", "%2E%2E", "audio.json", "document.json"):
        assert client.get(f"{base}/{wrong}").status_code == 404, wrong
    assert client.get(f"/api/v1/documents/0123456789abcdef/audiobook/{mp3}").status_code == 404
    other = make(client, make_pdf([Text("Another one.", 72, 100)]), "other.pdf")
    assert client.get(f"/api/v1/documents/{other['doc']['id']}/audiobook/{mp3}").status_code == 404
    (book_folder(config.output_folder) / mp3).unlink()
    assert client.get(f"{base}/{mp3}").status_code == 404


def test_the_record_finds_a_folder_the_saved_settings_dont_name(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    made = make(client, output_folder=str(elsewhere))
    doc = made["doc"]["id"]
    record_file = work_of(config, doc) / player.RECORD
    stored = json.loads(record_file.read_text(encoding="utf-8"))
    assert stored == {
        "format": "sci2audio-web-audiobook",
        "version": 1,
        "document": doc,
        "folder": str(book_folder(elsewhere.absolute())),
    }
    assert client.get(f"/documents/{doc}/listen").text.count('class="s"') > 0
    record_file.unlink()
    (work_of(config, doc) / PROJECT).unlink()  # without both, saved and default hold nothing
    page = client.get(f"/documents/{doc}/listen").text
    assert "The audiobook files are no longer in" in page
    assert "player-data" not in page


@pytest.mark.parametrize(
    "change",
    [
        {"folder": "relative/folder"},
        {"document": "0123456789abcdef"},
        {"format": "something-else"},
        {"version": 2},
        {"folder": 42},
    ],
)
def test_a_record_that_is_not_ours_is_ignored(tmp_path: Path, change: dict[str, Any]) -> None:
    client, config = server(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    made = make(client, output_folder=str(elsewhere))
    doc = made["doc"]["id"]
    record_file = work_of(config, doc) / player.RECORD
    stored = json.loads(record_file.read_text(encoding="utf-8"))
    record_file.write_text(json.dumps({**stored, **change}), encoding="utf-8")
    (work_of(config, doc) / PROJECT).unlink()  # the project's own folders would find it
    assert "The audiobook files are no longer in" in client.get(f"/documents/{doc}/listen").text


def test_the_project_record_finds_the_audiobook_without_the_player_s_record(
    tmp_path: Path,
) -> None:
    """D-749: the project's own audiobook folders are looked in after the recorded one."""
    client, config = server(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    made = make(client, output_folder=str(elsewhere))
    doc = made["doc"]["id"]
    (work_of(config, doc) / player.RECORD).unlink()
    assert client.get(f"/documents/{doc}/listen").text.count('class="s"') > 0


def test_files_of_another_audiobook_under_the_same_names_are_refused(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    names = {f["name"] for f in made["job"]["files"]}
    readalong_name = next(n for n in names if n.endswith(".readalong.json"))
    path = book_folder(config.output_folder) / readalong_name
    data = json.loads(path.read_text(encoding="utf-8"))
    data["duration"] += 5
    path.write_text(json.dumps(data), encoding="utf-8")
    page = client.get(f"/documents/{doc}/listen").text
    assert "now belong to another audiobook" in page
    mp3 = next(n for n in names if n.endswith(".mp3"))
    assert client.get(f"/api/v1/documents/{doc}/audiobook/{mp3}").status_code == 404


def test_a_read_along_that_does_not_fit_the_document_is_refused(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    name = next(f["name"] for f in made["job"]["files"] if f["name"].endswith(".readalong.json"))
    path = book_folder(config.output_folder) / name
    data = json.loads(path.read_text(encoding="utf-8"))
    data["chunks"][0]["end_char"] = 10_000
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "does not fit this document" in client.get(f"/documents/{doc}/listen").text


def test_a_record_of_another_file_is_refused(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    audio = work_of(config, doc) / "audio.json"
    data = json.loads(audio.read_text(encoding="utf-8"))
    data["source"]["sha256"] = "f" * 64
    audio.write_text(json.dumps(data), encoding="utf-8")
    assert (
        "The record of this audiobook can&#39;t be read"
        in client.get(f"/documents/{doc}/listen").text
    )


@pytest.mark.parametrize("name", ["../escape.mp3", "sub/x.mp3", "C:x.mp3"])
def test_file_names_with_a_folder_part_are_refused(tmp_path: Path, name: str) -> None:
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    audio = work_of(config, doc) / "audio.json"
    data = json.loads(audio.read_text(encoding="utf-8"))
    data["files"]["mp3"][0] = name
    audio.write_text(json.dumps(data), encoding="utf-8")
    assert (
        "The record of this audiobook can&#39;t be read"
        in client.get(f"/documents/{doc}/listen").text
    )


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need extra rights")
def test_a_link_out_of_the_folder_is_not_followed(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    made = make(client)
    doc = made["doc"]["id"]
    mp3 = next(f["name"] for f in made["job"]["files"] if f["name"].endswith(".mp3"))
    secret = tmp_path / "secret.mp3"
    secret.write_bytes(b"not yours")
    (book_folder(config.output_folder) / mp3).unlink()
    os.symlink(secret, book_folder(config.output_folder) / mp3)
    assert client.get(f"/api/v1/documents/{doc}/audiobook/{mp3}").status_code == 404
    assert "no longer in" in client.get(f"/documents/{doc}/listen").text


def test_no_audiobook_yet(tmp_path: Path) -> None:
    client, _ = server(tmp_path)
    doc = upload(client, paper_bytes(), "paper.pdf")
    page = client.get(f"/documents/{doc['id']}/listen")
    assert page.status_code == 200
    assert "There is no audiobook of this document yet." in page.text
    assert "player.js" not in page.text
    assert client.get("/documents/0123456789abcdef/listen").status_code == 404


def test_a_failed_job_writes_no_record(tmp_path: Path) -> None:
    voice = FakeVoice()
    voice.fail_to_make = EngineError("broken")
    client, config = server(tmp_path, voice)
    made = make(client)
    assert made["job"]["state"] == "failed"
    assert not (work_of(config, made["doc"]["id"]) / player.RECORD).exists()


def test_a_full_disk_while_noting_the_folder_leaves_the_job_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full(*args: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(tasks, "write_record", full)
    client, config = server(tmp_path)
    made = make(client)
    assert made["job"]["state"] == "done"
    doc = made["doc"]["id"]
    assert not (work_of(config, doc) / player.RECORD).exists()
    # the default output folder is the fallback (D-295)
    assert "player-data" in client.get(f"/documents/{doc}/listen").text


def test_text_from_the_file_is_escaped(tmp_path: Path) -> None:
    client, _ = server(tmp_path)
    made = make(
        client, make_pdf([Text("Bold <script>alert(1)</script> claims.", 72, 100)]), "x.pdf"
    )
    page = client.get(f"/documents/{made['doc']['id']}/listen").text
    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;alert(1)" in page


def settle(path: Path, ns: int | None = None) -> int:
    """Give the file a time long enough ago that the caches keep it (`RACY_NS`)."""
    ns = time.time_ns() - 10 * player.RACY_NS if ns is None else ns
    os.utime(path, ns=(ns, ns))
    return ns


def test_the_readalong_file_is_read_once_per_version(tmp_path: Path) -> None:
    path = tmp_path / "Book.readalong.json"
    path.write_text(to_json(readalong([(0, 0, 1)])), encoding="utf-8")
    settle(path)
    first = player.load_readalong(path)
    assert player.load_readalong(path) is first
    path.write_text(to_json(readalong([(0, 0, 1), (0, 1, 2)])), encoding="utf-8")
    os.utime(path, ns=(1, 1))
    assert len(player.load_readalong(path).chunks) == 2


def same_size_texts() -> tuple[bytes, bytes]:
    """Two read-along files of the same size in bytes (written as bytes, so Windows adds
    no carriage returns)."""
    first = to_json(readalong([(0, 0, 1)])).encode()
    second = to_json(readalong([(0, 0, 2)])).encode()
    assert first != second
    assert len(first) == len(second)
    return first, second


def test_a_readalong_file_made_again_with_the_same_size_and_time_is_read_again(
    tmp_path: Path,
) -> None:
    """#407: the audio job replaces the file whole; where the clock gives the new file the
    old one's time (Windows) and it has the same size, its new identity tells them apart."""
    path = tmp_path / "Book.readalong.json"
    first, second = same_size_texts()
    path.write_bytes(first)
    seen = settle(path)
    assert player.load_readalong(path).chunks[0].span == Span(0, 0, 1)
    new = tmp_path / "Book.readalong.json.new"
    new.write_bytes(second)
    os.replace(new, path)  # as write_texts does: a new file in the old one's place
    settle(path, seen)
    assert os.stat(path).st_size == len(first)
    assert player.load_readalong(path).chunks[0].span == Span(0, 0, 2)


def test_a_fresh_readalong_file_rewritten_in_place_is_read_again(tmp_path: Path) -> None:
    """A rewrite in place keeps the identity, and within one clock tick the time and size
    too: a file changed in the last two seconds is read each time (#407, as #403)."""
    path = tmp_path / "Book.readalong.json"
    first, second = same_size_texts()
    path.write_bytes(first)
    seen = os.stat(path).st_mtime_ns
    assert player.load_readalong(path).chunks[0].span == Span(0, 0, 1)
    assert player.audiobook_stamp(path) == hashlib.sha256(first).hexdigest()[:16]
    with path.open("r+b") as stream:  # in place: the same inode
        stream.write(second)
    os.utime(path, ns=(seen, seen))
    assert player.load_readalong(path).chunks[0].span == Span(0, 0, 2)
    # the stamp asked for before the rewrite is not kept for the new bytes (#601)
    assert player.audiobook_stamp(path) == hashlib.sha256(second).hexdigest()[:16]


def test_a_broken_document_record_is_named(tmp_path: Path) -> None:
    client, config = server(tmp_path)
    doc = make(client)["doc"]["id"]
    (work_of(config, doc) / "document.json").write_text("{", encoding="utf-8")
    assert (
        "The record of this audiobook can&#39;t be read"
        in client.get(f"/documents/{doc}/listen").text
    )


# ---- the steps the audiobook was made with (#666) ---------------------------------------


def said_parts(view: player.PlayerView) -> list[tuple[str, str]]:
    return [
        (part.text, part.said)
        for chapter in view.chapters
        for block in chapter.blocks
        for piece in block.pieces
        for part in piece.parts
        if part.mark == "said"
    ]


def test_the_read_along_uses_the_plugin_steps_it_is_given() -> None:
    from web_helpers import AMPERSAND_TEXT, plugin_steps

    document = make_document([("paragraph", AMPERSAND_TEXT)])
    data = readalong([(0, 0, len(AMPERSAND_TEXT))])
    made = record(chunks=1, made_with=__version__)
    assert said_parts(build_view(document, made, data, plugin_steps())) == [("&", "and")]
    assert said_parts(build_view(document, made, data)) == []


def test_joined_hyphens_takes_the_steps_it_is_given() -> None:
    text = "asking questions, and con-\ntributing code."
    document = make_document([("paragraph", text)])
    assert joined_hyphens(document, frozenset()) == {0: frozenset({text.index("-")})}
    assert joined_hyphens(document, frozenset(), steps=()) == {}


def plugin_server(tmp_path: Path) -> tuple[Any, Any]:
    from web_helpers import plugin_steps

    voice = FakeVoice()
    config = make_config(tmp_path)
    app = create_app(
        config, runner=JobRunner(plugin_steps()), voice=lambda models_dir: voice.source()
    )
    return program(app, config), config


def ampersand_pdf() -> bytes:
    from web_helpers import AMPERSAND_TEXT

    return make_pdf([Text(AMPERSAND_TEXT, 72, 100, size=11)])


def test_the_listen_page_uses_the_servers_plugin_steps(tmp_path: Path) -> None:
    client, _ = plugin_server(tmp_path)
    made = make(client, ampersand_pdf(), "salt.pdf")
    assert made["job"]["state"] == "done", made["job"]
    page = client.get(f"/documents/{made['doc']['id']}/listen").text
    assert '<span class="said"' in page
    assert "and" in page[page.index('<span class="said"') :].split(">", 1)[0]


def test_an_audiobook_made_without_plugins_shows_no_plugin_edits(tmp_path: Path) -> None:
    client, config = plugin_server(tmp_path)
    made = make(client, ampersand_pdf(), "salt.pdf")
    doc = made["doc"]["id"]
    record_file = work_of(config, doc) / "audio.json"
    data = json.loads(record_file.read_text(encoding="utf-8"))
    data["settings"]["plugins"] = False  # as `sci2audio convert --no-plugins` records it
    data.pop("plugins", None)
    record_file.write_text(json.dumps(data), encoding="utf-8")
    page = client.get(f"/documents/{doc}/listen").text
    assert '<span class="said"' not in page


def test_a_record_without_a_plugin_list_uses_the_built_in_steps(tmp_path: Path) -> None:
    """No released record was made with a plugin: a record without the list (#669) names
    none (D-852)."""
    client, config = server(tmp_path)
    made = make(client)
    work = work_of(config, made["doc"]["id"])
    assert read_audio_record(work, made["doc"]["id"]).plugins == frozenset()
    data = json.loads((work / "audio.json").read_text(encoding="utf-8"))
    data["plugins"] = [{"step": "ampersand-and", "distribution": "x", "version": "1"}]
    (work / "audio.json").write_text(json.dumps(data), encoding="utf-8")
    assert read_audio_record(work, made["doc"]["id"]).plugins == frozenset({"ampersand-and"})
    data["plugins"] = "not a list"
    (work / "audio.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(PlayerError):
        read_audio_record(work, made["doc"]["id"])


def test_a_plugin_installed_after_the_audiobook_shows_no_edit(tmp_path: Path) -> None:
    """#696: a book made without the plugin, opened by a server
    that has it, shows only what the voice said."""
    from web_helpers import plugin_steps

    voice = FakeVoice()
    config = make_config(tmp_path)
    before = create_app(config, voice=lambda models_dir: voice.source())
    made = make(program(before, config), ampersand_pdf(), "salt.pdf")
    assert made["job"]["state"] == "done", made["job"]
    after = create_app(
        config, runner=JobRunner(plugin_steps()), voice=lambda models_dir: voice.source()
    )
    page = program(after, config).get(f"/documents/{made['doc']['id']}/listen").text
    assert "Salt &amp; pepper" in page
    assert '<span class="said"' not in page
