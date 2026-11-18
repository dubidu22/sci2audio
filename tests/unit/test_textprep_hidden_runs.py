"""Hidden runs and inline page-break markers are not read (#193, D-692).

A run tagged `hidden` or `aria-hidden`, or marked as a page break (`epub:pagebreak`,
`role:doc-pagebreak`), is removed by the inline step `hidden-runs` in the "Page furniture"
category, in a block of any kind but furniture and a placeholder whose notice is read; a
placeholder whose notice is switched off is read as printed, so its runs go too (#463). The
tags are the run's element stack (D-306), so a run inside a hidden element counts too.
"""

from collections.abc import Sequence

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    Edit,
    EditKind,
    FurnitureRole,
    Page,
    Part,
    Source,
    SourceFormat,
    Span,
    TextLine,
    TextRun,
    apply_edits,
)
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Category,
    HiddenRunStep,
    Stage,
    StepContext,
    run_steps,
    spoken_text,
)
from sci2audio.textprep.furniture import QUOTED, edits_around, read_around, removed_span

EN = StepContext("en")
HIDDEN = ("p", "span", "hidden")
PAGE_BREAK = ("p", "span", "#page-13", "epub:pagebreak", "role:doc-pagebreak")

Tagged = tuple[str, tuple[str, ...]]  # a run's text and its tags; () for a plain run


def tagged(*runs: str | Tagged, kind: BlockKind = BlockKind.PARAGRAPH, **block: str) -> Document:
    """A one-block document of these runs: strings are plain, (text, tags) are tagged."""
    text, ranges = "", []
    for run in runs:
        if isinstance(run, str):
            text += run
        else:
            ranges.append((len(text), len(text) + len(run[0]), run[1]))
            text += run[0]
    return make_document([Block(kind, text, **block)], tags={0: ranges})


def read(document: Document, switched_off: Sequence[Category] = ()) -> list[str]:
    """Each block's spoken text after all built-in steps."""
    run = run_steps(document, StepContext(document.language), switched_off=switched_off,
                    strict=True)  # fmt: skip
    return [
        spoken_text(p for p in run.script() if p.span.block == index)
        for index in range(len(document.blocks))
    ]


@pytest.mark.parametrize(
    ("runs", "spoken"),
    [
        (["Visible ", ("SECRET", HIDDEN), " text"], "Visible text"),
        (["after ", ("13", PAGE_BREAK), " mid"], "after mid"),
        (["a ", ("x", ("p", "span", "aria-hidden")), " b"], "a b"),
        (["a ", ("7", ("p", "span", "role:doc-pagebreak")), " b"], "a b"),
        (["a ", ("7", ("p", "span", "epub:pagebreak")), " b"], "a b"),
        (["text ", ("x", HIDDEN), "."], "text."),
        (["text ", ("x", HIDDEN), ", more ", ("y", HIDDEN), ")"], "text, more)"),
        ([("a ", HIDDEN), ("b", (*HIDDEN, "em")), " c"], "c"),
        (
            ["shown ", ("bonjour", ("p", "span", "lang:fr")), " ", ("on", ("span", "role:note"))],
            "shown bonjour on",
        ),
        (["ends hidden ", ("tail", HIDDEN)], "ends hidden"),
    ],
)
def test_hidden_runs_and_page_breaks_are_not_read(runs: list, spoken: str) -> None:
    assert read(tagged(*runs)) == [spoken]


def test_each_reason_names_what_is_removed() -> None:
    document = tagged("a ", ("SECRET  word", HIDDEN), " b ", ("13", PAGE_BREAK), " c")
    edits = HiddenRunStep().find(document, EN)
    hidden = 'hidden text "SECRET word" is not read (hidden in the file)'
    assert [(e.span, e.kind, e.reason) for e in edits] == [
        (Span(0, 2, 14), EditKind.REMOVE, hidden),
        (Span(0, 17, 19), EditKind.REMOVE, 'page-break marker "13" is not read'),
    ]


@pytest.mark.parametrize(
    "runs", [[("13", PAGE_BREAK), ("x", HIDDEN)], [("x", HIDDEN), ("13", PAGE_BREAK)]]
)
def test_hidden_runs_side_by_side_are_one_removal_and_hidden_wins_the_reason(runs: list) -> None:
    document = tagged("a ", *runs, " b")
    (edit,) = HiddenRunStep().find(document, EN)
    assert edit.span == Span(0, 2, 5)
    assert edit.reason.startswith("hidden text")


@pytest.mark.parametrize(
    "kind", [BlockKind.HEADING, BlockKind.LIST_ITEM, BlockKind.FOOTNOTE, BlockKind.CAPTION]
)
def test_hidden_runs_go_in_every_kind_of_text_block(kind: BlockKind) -> None:
    document = tagged("Shown", (" hidden", HIDDEN), " too", kind=kind)
    (edit,) = HiddenRunStep().find(document, EN)
    assert edit.span == Span(0, 6, 12)


def test_furniture_and_placeholders_read_by_their_notice_get_no_edit_of_this_step() -> None:
    furniture = make_document(
        [Block(BlockKind.FURNITURE, "Journal 12", role=FurnitureRole.RUNNING_HEAD)],
        tags={0: [(8, 10, HIDDEN)]},
    )
    assert HiddenRunStep().find(furniture, EN) == []
    for kind in (BlockKind.TABLE, BlockKind.FIGURE, BlockKind.FORMULA, BlockKind.CODE):
        assert HiddenRunStep().find(tagged("a ", ("b", HIDDEN), kind=kind), EN) == []


NOTICES = {
    BlockKind.TABLE: Category.TABLES_AND_FIGURES,
    BlockKind.FIGURE: Category.TABLES_AND_FIGURES,
    BlockKind.FORMULA: Category.FORMULAS,
    BlockKind.CODE: Category.CODE,
}


@pytest.mark.parametrize("kind", list(NOTICES))
@pytest.mark.parametrize("language", ["en", "de"])
def test_a_placeholder_whose_notice_is_off_loses_its_hidden_runs(
    kind: BlockKind, language: str
) -> None:
    """#463: with its notice switched off a placeholder is read as printed, so its hidden
    runs and page-break markers go as in any block; another category off changes nothing."""
    document = make_document(
        [Block(kind, "a 13 b SECRET c")],
        language,
        tags={0: [(2, 4, PAGE_BREAK), (7, 13, HIDDEN)]},
    )
    off = StepContext(language, switched_off=frozenset({NOTICES[kind]}))
    edits = HiddenRunStep().find(document, off)
    assert [edit.span for edit in edits] == [Span(0, 2, 4), Span(0, 7, 13)]
    others = frozenset(set(NOTICES.values()) - {NOTICES[kind]})
    assert HiddenRunStep().find(document, StepContext(language, switched_off=others)) == []
    assert read(document, switched_off=[NOTICES[kind]]) == ["a b c"]


@pytest.mark.parametrize("kind", list(NOTICES))
@pytest.mark.parametrize("on", [True, False])
def test_a_placeholder_in_a_language_without_notices_loses_its_hidden_runs(
    kind: BlockKind, on: bool
) -> None:
    """The notice steps read English and German only: in a French job every placeholder is
    read as printed, its category on or off, so its hidden runs go (#463)."""
    document = make_document(
        [Block(kind, "a 13 b SECRET c")],
        "fr",
        tags={0: [(2, 4, PAGE_BREAK), (7, 13, HIDDEN)]},
    )
    switched = [] if on else [NOTICES[kind]]
    context = StepContext("fr", switched_off=frozenset(switched))
    assert [edit.span for edit in HiddenRunStep().find(document, context)] == [
        Span(0, 2, 4),
        Span(0, 7, 13),
    ]
    assert read(document, switched_off=switched) == ["a b c"]


def test_a_hidden_run_of_white_space_only_gets_no_edit() -> None:
    assert HiddenRunStep().find(tagged("a", ("  ", HIDDEN), "b"), EN) == []


def test_a_pdf_without_tags_gets_no_edit() -> None:
    line = TextLine("l0", (TextRun("Visible ", size=10.0), TextRun("SECRET", size=10.0)))
    content = Content(Source("plain.pdf", SourceFormat.PDF), (Page(1, (line,)),))
    block = Block(BlockKind.PARAGRAPH, line.text, (Part("l0"),))
    document = Document(content=content, language="en", blocks=(block,))
    assert HiddenRunStep().find(document, EN) == []


def test_a_line_not_where_its_part_says_is_skipped() -> None:
    line = TextLine("l0", (TextRun("Other", tags=HIDDEN),))
    content = Content(Source("odd.epub", SourceFormat.EPUB), (Page(1, (line,)),))
    block = Block(BlockKind.PARAGRAPH, "Shown", (Part("l0"),))
    document = Document(content=content, language="en", blocks=(block,))
    assert HiddenRunStep().find(document, EN) == []


def test_the_page_furniture_switch_reads_hidden_runs() -> None:
    document = tagged("Visible ", ("SECRET", HIDDEN), " text")
    assert read(document, switched_off=[Category.PAGE_FURNITURE]) == ["Visible SECRET text"]


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_the_step_reads_every_language(language: str) -> None:
    document = make_document([(BlockKind.PARAGRAPH, "a b c")], language, tags={0: [(2, 3, HIDDEN)]})
    assert len(HiddenRunStep().find(document, StepContext(language))) == 1


def test_the_step_is_the_first_inline_step_so_a_link_inside_never_wins() -> None:
    inline = [step.id for step in BUILT_IN_STEPS if step.stage is Stage.INLINE]
    assert inline[0] == "hidden-runs"
    document = tagged("See ", ("https://example.org/x (Smith, 2019)", HIDDEN), " here.")
    assert read(document) == ["See here."]


@pytest.mark.parametrize(
    ("runs", "spoken"),
    [
        (["Visit https://x.org", ("\u2197", ("a", "aria-hidden")), " today."], "today."),
        (["See https://x.org/a", ("13", PAGE_BREAK), "b now."], "now."),  # inside the link
        (["As shown [12]", ("13", PAGE_BREAK), " before."], "As shown before."),
        (
            ["Shown in [1,", ("13", PAGE_BREAK), " 2] and more."],
            "Shown in references 1 and 2 and more.",
        ),
        (["Read (", ("x", HIDDEN), "https://x.org) now."], "Read now."),
        (["A", ("13", PAGE_BREAK), " b. See https://x.org now."], "A b. now."),  # before it
        (["As shown [12] here", ("13", PAGE_BREAK), " before."], "As shown here before."),
        # two removals that touch: the second takes the space before "]" (review round 2, S1)
        (["Shown [1, 2 ", ("x", HIDDEN), " ", ("y", HIDDEN), "] here."], "Shown here."),
    ],
)
def test_links_and_citations_read_the_text_without_hidden_runs(runs: list, spoken: str) -> None:
    assert read(tagged(*runs)) == [spoken]


def test_a_link_with_a_marker_inside_is_removed_in_pieces_beside_the_marker() -> None:
    document = tagged("See https://x.org/a", ("13", PAGE_BREAK), "b now.")
    run = run_steps(document, EN, strict=True)
    pieces = sorted((e.span.start, e.span.end, e.step) for e in run.accepted)
    assert pieces == [(0, 19, "links"), (19, 21, "hidden-runs"), (21, 23, "links")]


def test_a_replacement_split_by_a_marker_is_read_once() -> None:
    document = tagged("Shown in [1,", ("13", PAGE_BREAK), " 2] and more.")
    edits = [e for e in run_steps(document, EN, strict=True).accepted if e.step == "citations"]
    assert [(e.kind, e.replacement) for e in edits] == [
        (EditKind.REPLACE, "references 1 and 2"),
        (EditKind.REMOVE, ""),
    ]


def test_an_insertion_is_put_back_where_it_stands_in_the_printed_text() -> None:
    text, kept = read_around("ab13cd", [(2, 4)])
    assert (text, kept) == ("abcd", [0, 1, 4, 5, 6])
    inserts = [Edit(Span(0, at, at), EditKind.REPLACE, "r", "s", "X") for at in (2, 4)]
    placed = edits_around(inserts, kept, [(2, 4)])
    assert [(e.span.start, e.span.end, e.replacement) for e in placed] == [(4, 4, "X"), (6, 6, "X")]


@pytest.mark.parametrize(
    ("runs", "spoken"),
    [
        (["As shown [12]", ("13", PAGE_BREAK), " before."], "As shown [12]13 before."),
        (["Read (", ("x", HIDDEN), "https://x.org) now."], "Read (xhttps://x.org) now."),
    ],
)
def test_with_page_furniture_off_links_and_citations_read_the_runs(runs: list, spoken: str) -> None:
    assert read(tagged(*runs), switched_off=[Category.PAGE_FURNITURE]) == [spoken]


def test_a_long_hidden_text_is_quoted_in_part() -> None:
    hidden = " ".join(["word"] * 30)
    (edit,) = HiddenRunStep().find(tagged("a ", (hidden, HIDDEN), " b"), EN)
    quoted = edit.reason.split('"')[1]
    assert len(quoted) <= QUOTED
    assert quoted == hidden[: QUOTED - 1].rstrip() + "\u2026"
    one_more = "w" * (QUOTED + 1)
    (edit,) = HiddenRunStep().find(tagged("a ", (one_more, HIDDEN), " b"), EN)
    assert f'"{one_more[: QUOTED - 1]}\u2026"' in edit.reason
    spaced = "w" * (QUOTED - 2) + " " + "w" * 20  # the cut ends in a space, which goes
    (edit,) = HiddenRunStep().find(tagged("a ", (spaced, HIDDEN), " b"), EN)
    assert f'"{"w" * (QUOTED - 2)}\u2026"' in edit.reason
    short = "w" * QUOTED
    (edit,) = HiddenRunStep().find(tagged("a ", (short, HIDDEN), " b"), EN)
    assert f'"{short}"' in edit.reason


@pytest.mark.parametrize(
    ("text", "start", "end", "span"),
    [
        # white space on both sides: the white space before goes too, so the text reads as
        # it does without the run, "a b", which is what a second run reads (#445)
        ("a xy b", 2, 4, (1, 4)),
        ("a  xy  b", 1, 7, (1, 5)),  # the run's own white space is left out of it first
        ("a\nxy b", 2, 4, (1, 4)),  # a line break before: the space after is left
        ("a xy\nb", 2, 4, (1, 4)),  # a line break after: the line break is left
        ("axy b", 1, 3, (1, 3)),  # glued on the left: nothing more
        ("a xyb", 2, 4, (2, 4)),  # glued on the right: nothing more
        ("a xy.", 2, 4, (1, 4)),  # before a full stop the space before goes too
        ("a xy", 2, 4, (1, 4)),  # at the block's end too
        ("a \n xy)", 4, 6, (1, 6)),  # a line break is white space
        ("xy.", 0, 2, (0, 2)),
    ],
)
def test_removed_span(text: str, start: int, end: int, span: tuple[int, int]) -> None:
    assert removed_span(text, start, end) == span


def test_the_step_keeps_the_text_step_contract() -> None:
    check_text_step(HiddenRunStep(), allow_ask=False)


_PIECES = st.lists(
    st.tuples(st.text(alphabet="ab .,)", min_size=1, max_size=6), st.booleans()),
    min_size=1,
    max_size=8,
)


@given(_PIECES)
def test_any_text_reads_as_the_text_without_its_hidden_runs(pieces: list[tuple[str, bool]]) -> None:
    document = tagged(*((text, HIDDEN) if hidden else text for text, hidden in pieces))
    edits = HiddenRunStep().find(document, EN)
    spoken = spoken_text(apply_edits(document, edits))
    shown = "".join(text for text, hidden in pieces if not hidden)
    # the same characters but white space, which only goes beside a removal
    assert "".join(spoken.split()) == "".join(shown.split())
