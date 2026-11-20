"""`rebuilt_from_script` (D-577): the second-run document keeps each block's label while the
script still reads the label's words, as the script reads them, also when a step rewrote
them (#324, D-578)."""

from collections.abc import Sequence

import pytest

from sci2audio.core import (
    Block,
    BlockKind,
    Content,
    Document,
    Page,
    Part,
    ScriptPiece,
    Source,
    SourceFormat,
    Span,
    TextLine,
    TextRun,
)
from sci2audio.testing import make_document, rebuilt_from_script
from sci2audio.testing.documents import _run_tags
from sci2audio.textprep import StepContext, run_steps, spoken_text


def _figure_and_caption(caption: str, label: str, language: str = "en"):
    return make_document(
        [
            Block(BlockKind.FIGURE, "0 10 20"),
            Block(BlockKind.CAPTION, caption, describes=0, label=label),
        ],
        language,
    )


def _read(document) -> list[str]:
    script = run_steps(document, StepContext(document.language), strict=True).script()
    return [
        spoken_text([piece for piece in script if piece.span.block == index])
        for index in range(len(document.blocks))
    ]


def test_a_label_a_step_spelled_out_stays_and_names_the_figure_again() -> None:
    document = _figure_and_caption(
        "Abb. 1: Anwendungsfälle und Datenstrukturen.", "Abb. 1", language="de"
    )
    first = run_steps(document, StepContext("de"), strict=True)
    rebuilt = rebuilt_from_script(document, first.script())
    assert rebuilt.blocks[1].text == "Abbildung 1: Anwendungsfälle und Datenstrukturen."
    assert rebuilt.blocks[1].label == "Abbildung 1"
    assert (
        _read(rebuilt)
        == _read(document)
        == [
            "Abbildung 1 wird übersprungen.",
            "Abbildung 1: Anwendungsfälle und Datenstrukturen.",
        ]
    )


def test_a_label_read_as_printed_stays() -> None:
    document = _figure_and_caption("Figure 3. Response over time.", "Figure 3")
    first = run_steps(document, StepContext("en"), strict=True)
    assert rebuilt_from_script(document, first.script()).blocks[1].label == "Figure 3"


def test_a_label_whose_words_were_all_removed_goes() -> None:
    """The script reads only the caption's text after its label: no label is made up."""
    document = _figure_and_caption("Fig. 3. Response over time.", "Fig. 3")
    script = [ScriptPiece("Response over time.", Span(1, 8, 27))]
    assert rebuilt_from_script(document, script).blocks[1].label == ""


def test_a_label_covered_only_by_a_pause_goes() -> None:
    document = _figure_and_caption("Fig. 3. Response.", "Fig. 3")
    script = [ScriptPiece("", Span(1, 3, 3), pause=True), ScriptPiece("Response.", Span(1, 8, 17))]
    assert rebuilt_from_script(document, script).blocks[1].label == ""


def test_a_block_the_script_left_out_loses_its_label() -> None:
    document = _figure_and_caption("Fig. 3. Response.", "Fig. 3")
    script = [ScriptPiece("A figure is skipped.", Span(0, 0, 7))]
    rebuilt = rebuilt_from_script(document, script)
    assert (rebuilt.blocks[1].text, rebuilt.blocks[1].label) == ("", "")


def test_a_label_read_inside_a_longer_replacement_stays_only_where_the_new_text_prints_it() -> None:
    """A replacement that runs past the label's edge cannot be mapped: the label stays only
    if the new text still prints it, as before #324."""
    document = _figure_and_caption("Fig. 3. Response over time.", "Fig. 3")
    script = [ScriptPiece("The response over time.", Span(1, 0, 27))]
    assert rebuilt_from_script(document, script).blocks[1].label == ""
    script = [ScriptPiece("Fig. 3: the response over time.", Span(1, 0, 27))]
    assert rebuilt_from_script(document, script).blocks[1].label == "Fig. 3"


def test_a_label_partly_removed_keeps_what_is_read() -> None:
    document = _figure_and_caption("Fig. 3. Response.", "Fig. 3")
    script = [ScriptPiece("Figure", Span(1, 0, 4)), ScriptPiece(". Response.", Span(1, 6, 17))]
    rebuilt = rebuilt_from_script(document, script)
    assert (rebuilt.blocks[1].text, rebuilt.blocks[1].label) == ("Figure. Response.", "Figure")


@pytest.mark.parametrize(
    "kind", [BlockKind.FORMULA, BlockKind.TABLE, BlockKind.FIGURE, BlockKind.CODE]
)
def test_a_placeholder_comes_back_as_printed_with_its_label(kind: BlockKind) -> None:
    """A notice is made from the printed placeholder and its captions only, so the second
    run rebuilds the placeholder as printed and makes the same notice again (D-707), however
    the notice reads the label ("Formel 3 Punkt 2", #362)."""
    label = "3.2" if kind is BlockKind.FORMULA else ""  # only a formula carries its own
    document = make_document([Block(kind, "a = b (3.2)", label=label)], "de")
    first = run_steps(document, StepContext("de"), strict=True)
    rebuilt = rebuilt_from_script(document, first.script())
    assert (rebuilt.blocks[0].text, rebuilt.blocks[0].label) == ("a = b (3.2)", label)
    assert _read(rebuilt) == _read(document)


def test_a_placeholder_keeps_its_pictures_and_their_alt_text() -> None:
    document = make_document([Block(BlockKind.FIGURE, "")], pictures={0: ["A bar chart."]})
    script = [ScriptPiece("A figure is skipped. It shows: A bar chart.", Span(0, 0, 0))]
    rebuilt = rebuilt_from_script(document, script)
    assert [part.item for part in rebuilt.blocks[0].parts] == [
        part.item for part in document.blocks[0].parts
    ]
    assert _read(rebuilt) == _read(document) == ["A figure is skipped. It shows: A bar chart."]


def test_a_formula_notice_names_its_number_on_the_second_run_too() -> None:
    """nightly seed 555 of the runner's idempotence property: a formula labelled "0"."""
    document = make_document([Block(BlockKind.FORMULA, "0", label="0")])
    first = run_steps(document, StepContext("en"), strict=True)
    rebuilt = rebuilt_from_script(document, first.script())
    assert (rebuilt.blocks[0].text, rebuilt.blocks[0].label) == ("0", "0")
    assert _read(rebuilt) == _read(document) == ["Formula 0 is skipped."]


@pytest.mark.parametrize(
    ("text", "label", "language"),
    [("† Note.", "†", "en"), ("* Note.", "*", "en"), ("\u2217 Hinweis.", "\u2217", "de")],
)
def test_a_footnote_mark_is_not_mapped_into_its_introduction(
    text: str, label: str, language: str
) -> None:
    """The footnotes step replaces a note's mark with its introduction ("Footnote.",
    "Fußnote."): that is no label, so the rebuilt note has none (#353)."""
    document = make_document(
        [Block(BlockKind.PARAGRAPH, "Text."), Block(BlockKind.FOOTNOTE, text, label=label)],
        language,
    )
    first = run_steps(document, StepContext(language), strict=True)
    rebuilt = rebuilt_from_script(document, first.script())
    assert rebuilt.blocks[1].text != text  # the mark was read as an introduction
    assert rebuilt.blocks[1].label == ""


# ---- pictures (#191, D-692) ----------------------------------------------------------------


def test_make_document_puts_each_picture_on_its_block_s_page_after_its_text() -> None:
    from sci2audio.core import Picture

    document = make_document(
        [(BlockKind.PARAGRAPH, "Text."), (BlockKind.FIGURE, "0 10")],
        pictures={1: ["A chart", ""]},
        pages={1: 2},
    )
    items = document.content.items()
    figure = document.blocks[1]
    parts = [(part.item, part.start) for part in figure.parts]
    assert parts == [("b1l0", 0), ("b1p0", 4), ("b1p1", 4)]
    assert [items[item][1] for item, _ in parts[1:]] == [
        Picture("b1p0", alt="A chart"),
        Picture("b1p1", alt=""),
    ]
    assert {items[item][0].number for item, _ in parts} == {2}
    assert document.content.pages[0].pictures == ()


def test_the_rebuilt_document_keeps_each_block_s_alt_texts() -> None:
    from sci2audio.core import Picture

    document = make_document(
        [(BlockKind.FIGURE, ""), (BlockKind.PARAGRAPH, "Text."), (BlockKind.FIGURE, "")],
        pictures={0: ["A cat", "A dog"], 2: [""]},
    )
    script = run_steps(document, StepContext("en"), strict=True).script()
    rebuilt = rebuilt_from_script(document, script)
    items = rebuilt.content.items()

    def alts(block: int) -> list[str]:
        found = [items[part.item][1] for part in rebuilt.blocks[block].parts]
        return [item.alt for item in found if isinstance(item, Picture)]

    assert [alts(0), alts(1), alts(2)] == [["A cat", "A dog"], [], [""]]
    assert _read(rebuilt) == _read(document)


def _tagged_runs(document, index: int) -> list[tuple[str, tuple[str, ...]]]:
    items = document.content.items()
    return [
        (run.text, run.tags)
        for part in document.blocks[index].parts
        for run in items[part.item][1].runs
        if run.tags
    ]


def test_a_placeholder_back_as_printed_keeps_its_tagged_runs_and_one_read_does_not() -> None:
    """#463: a placeholder rebuilt as printed keeps its hidden and page-break runs, so a
    second run sees them again; one in `own_output` comes back as read, without tags."""
    hidden, page_break = ("span", "hidden"), ("span", "epub:pagebreak")
    document = make_document(
        [(BlockKind.TABLE, "a 13 b SECRET c"), (BlockKind.CODE, "x 13 y")],
        tags={0: [(2, 4, page_break), (7, 13, hidden)], 1: [(2, 4, page_break)]},
    )
    script = run_steps(document, StepContext("en"), strict=True).script()
    rebuilt = rebuilt_from_script(document, script, own_output=[1])
    assert rebuilt.blocks[0].text == "a 13 b SECRET c"
    assert _tagged_runs(rebuilt, 0) == [("13", page_break), ("SECRET", hidden)]
    assert _tagged_runs(rebuilt, 1) == []


def _placeholders(*blocks: tuple[str, Sequence[tuple[TextLine, int]]]) -> Document:
    """Tables of this text, each made of these lines at these starts in its text."""
    lines = [line for _, parts in blocks for line, _ in parts]
    content = Content(Source("t.epub", SourceFormat.EPUB), (Page(1, tuple(lines)),))
    made = tuple(
        Block(BlockKind.TABLE, text, tuple(Part(line.id, start) for line, start in parts))
        for text, parts in blocks
    )
    return Document(content=content, language="en", blocks=made)


def _rebuilt(document: Document) -> Document:
    script = run_steps(document, StepContext("en"), strict=True).script()
    return rebuilt_from_script(document, script)


def test_a_tagged_run_across_a_line_break_keeps_its_tag_on_each_line() -> None:
    """A tagged range may not cross a line break, so a run holding one is cut there; a run
    of a part that goes back over a range before it is left out (#484, the
    shape the nightly seeds found: overlapping parts and a run "0\n" tagged "h1")."""
    h1, h2 = ("h1",), ("h2",)
    document = _placeholders(
        ("ab\ncd", [(TextLine("l0", (TextRun("ab\ncd", tags=h1),)), 0)]),
        (
            "0\n00\n",
            [
                (TextLine("l1", (TextRun("0\n"), TextRun("00", tags=h2))), 0),
                (TextLine("l2", (TextRun("0\n", tags=h1),)), 0),
            ],
        ),
    )
    rebuilt = _rebuilt(document)
    assert [block.text for block in rebuilt.blocks] == ["ab\ncd", "0\n00\n"]
    assert _tagged_runs(rebuilt, 0) == [("ab", h1), ("cd", h1)]
    assert _tagged_runs(rebuilt, 1) == [("00", h2)]


def test_a_tagged_run_ending_in_a_line_break_gives_no_empty_range() -> None:
    """Cut at its line break, "a\n" leaves an empty piece after it, which gets no range.
    `make_document` would pass over an empty range at a line's edge, so the helper's own
    ranges are checked too (#484)."""
    lines = [TextLine("l0", (TextRun("a\n", tags=("hidden",)),)), TextLine("l1", (TextRun("b"),))]
    document = _placeholders(("a\nb", [(lines[0], 0), (lines[1], 2)]))
    assert _run_tags(document.blocks[0], document.content.items()) == [(0, 1, ("hidden",))]
    assert _tagged_runs(_rebuilt(document), 0) == [("a", ("hidden",))]


def test_a_line_not_where_its_part_says_gives_no_tag() -> None:
    """The "never point at other text" guard, as in `HiddenRunStep`."""
    line = TextLine("l0", (TextRun("Other", tags=("hidden",)),))
    rebuilt = _rebuilt(_placeholders(("Shown", [(line, 0)])))
    assert rebuilt.blocks[0].text == "Shown"
    assert _tagged_runs(rebuilt, 0) == []
