"""Formulas, tables and figures are read as a short notice (FX-01, FX-02, #64, Q3, D-145),
and the reference list is not read (TP-06, D-146)."""

import pytest
from hypothesis import given
from textprep_documents import rule_documents

from sci2audio.core import Block, BlockKind, Document, EditKind, Section, Span
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import (
    REFERENCE_TITLES,
    Category,
    FormulaNoticeStep,
    ReferenceListStep,
    StepContext,
    TableFigureNoticeStep,
    run_steps,
    spoken_text,
    wording_for,
)

EN = StepContext("en")


def read(document: Document, **switches: object) -> list[str]:
    run = run_steps(document, StepContext(document.language), strict=True, **switches)
    return [
        spoken_text(p for p in run.script() if p.span.block == index)
        for index in range(len(document.blocks))
    ]


def caption(label: str, describes: int, rest: str = ": What it shows.") -> Block:
    return Block(BlockKind.CAPTION, label + rest, describes=describes, label=label)


# ---- notices -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("blocks", "notice"),
    [
        ([(BlockKind.TABLE, "a b\nc d"), caption("Table 2", 0)], "Table 2 is skipped."),
        ([caption("Figure 1", 1), (BlockKind.FIGURE, "")], "Figure 1 is skipped."),
        ([(BlockKind.FIGURE, "x"), caption("Fig. 3", 0, ". Shown.")], "Figure 3 is skipped."),
        ([(BlockKind.FIGURE, "x"), caption("Figs. 3", 0)], "Figures 3 is skipped."),
        ([(BlockKind.TABLE, "x"), caption("Tab. 4", 0)], "Table 4 is skipped."),
        ([(BlockKind.FIGURE, "x"), caption("Algorithm 5", 0)], "Algorithm 5 is skipped."),
        ([(BlockKind.FIGURE, "x"), caption("Alg. 5", 0)], "Algorithm 5 is skipped."),
        ([(BlockKind.FIGURE, "x"), caption("Scheme 2", 0)], "Scheme 2 is skipped."),
        ([(BlockKind.TABLE, "a b")], "A table is skipped."),
        ([(BlockKind.FIGURE, "")], "A figure is skipped."),
        ([(BlockKind.FORMULA, "x = y")], "A formula is skipped."),
        ([Block(BlockKind.FORMULA, "x = y (16a)", label="16a")], "Formula 16a is skipped."),
        (
            [Block(BlockKind.FORMULA, "x (3)", label="3"), caption("Eq. 3", 0)],
            "Equation 3 is skipped.",
        ),
    ],
)
def test_each_placeholder_reads_one_notice(blocks: list, notice: str) -> None:
    document = make_document(blocks)
    index = next(i for i, b in enumerate(document.blocks) if b.is_placeholder)
    spoken = read(document)
    assert spoken[index] == notice
    for i, block in enumerate(document.blocks):  # the caption reads as printed
        if block.kind is BlockKind.CAPTION:
            assert spoken[i] == spoken_text_of(block.text)


def spoken_text_of(text: str) -> str:
    return " ".join(text.split())


def test_several_captions_are_all_named_in_document_order() -> None:
    document = make_document(
        [
            caption("Algorithm 1", 1),
            (BlockKind.FIGURE, "1: loop"),
            caption("Algorithm 2", 1),
            caption("Figure 1", 1),
        ]
    )
    assert read(document)[1] == "Algorithm 1, Algorithm 2 and Figure 1 are skipped."


def test_a_caption_without_a_label_names_nothing() -> None:
    document = make_document(
        [(BlockKind.TABLE, "a"), Block(BlockKind.CAPTION, "Results.", describes=0)]
    )
    assert read(document) == ["A table is skipped.", "Results."]


def test_the_notice_is_one_replace_over_the_whole_block_with_a_reason() -> None:
    document = make_document(
        [(BlockKind.TABLE, "a b"), caption("Table 1", 0), (BlockKind.FORMULA, "")]
    )
    (table,) = TableFigureNoticeStep().find(document, EN)
    assert (table.span, table.kind, table.replacement) == (Span(0, 0, 3), EditKind.REPLACE,
                                                           "Table 1 is skipped.")  # fmt: skip
    assert table.reason == "Table 1 is not read; a short notice is read instead (D-55)"
    (formula,) = FormulaNoticeStep().find(document, EN)
    assert formula.span == Span(2, 0, 0)  # an empty placeholder: the notice is inserted
    assert formula.reason == "this formula is not read; a short notice is read instead (D-55)"


def test_switching_a_category_off_reads_the_placeholder_as_printed() -> None:
    document = make_document(
        [(BlockKind.TABLE, "a b"), Block(BlockKind.FORMULA, "x (1)", label="1")]
    )
    assert read(document, switched_off={Category.TABLES_AND_FIGURES}) == [
        "a b",
        "Formula 1 is skipped.",
    ]
    assert read(document, switched_off={Category.FORMULAS}) == ["A table is skipped.", "x (1)"]


def test_the_wording_lives_in_one_table_and_british_english_uses_it() -> None:
    english = wording_for("en")
    assert wording_for("en-GB") is english
    assert english.skipped(["A", "B"], BlockKind.TABLE) == "A and B are skipped."
    assert english.skipped([], BlockKind.FORMULA) == "A formula is skipped."
    assert english.label("Fig. 2") == "Figure 2"
    assert english.label("Figure 2") == "Figure 2"
    assert english.footnote.format("3") == "Footnote 3."


def test_notices_are_english_only() -> None:
    german = make_document([(BlockKind.TABLE, "a b")], "de")
    run = run_steps(german, StepContext("de"), strict=True)
    assert {"formula-notices", "table-figure-notices"} <= set(run.not_run)


# ---- the reference list ----------------------------------------------------------------------


def references(title: str, *, level: int = 1, nested: bool = False) -> Document:
    blocks = [
        (BlockKind.HEADING, "5 Results"),
        (BlockKind.PARAGRAPH, "It works."),
        (BlockKind.HEADING, title),
        (BlockKind.PARAGRAPH, "Doe, J. (2020). A study."),
        Block(BlockKind.FOOTNOTE, "9 A note printed on this page.", label="9"),
        (BlockKind.FURNITURE, "12"),
        (BlockKind.PARAGRAPH, ""),
        (BlockKind.HEADING, "A Appendix"),
        (BlockKind.PARAGRAPH, "More."),
    ]
    inner = Section(title, level, 2, 7)
    sections = (
        [Section("5 Results", 1, 0, 7, (Section(title, 2, 2, 7),)), Section("A Appendix", 1, 7, 9)]
        if nested
        else [Section("5 Results", 1, 0, 2), inner, Section("A Appendix", 1, 7, 9)]
    )
    return make_document(blocks, sections=sections)


@pytest.mark.parametrize(
    "title",
    ["References", "REFERENCES", "references", "7 References", "8. Bibliography",
     "8.1 Bibliography", "A References", "IV Bibliography", " References ", "Works Cited",
     "Literature cited", "9 Reference List"],
)  # fmt: skip
def test_a_reference_section_is_not_read_but_notes_and_what_follows_are(title: str) -> None:
    document = references(title)
    assert read(document) == [
        "5 Results",
        "It works.",
        "",
        "",
        "Footnote 9. A note printed on this page.",
        "",
        "",
        "A Appendix",
        "More.",
    ]
    edits = ReferenceListStep().find(document, EN)
    assert [(e.span.block, e.kind, e.reason) for e in edits] == [
        (2, EditKind.REMOVE, "the reference list is not read"),
        (3, EditKind.REMOVE, "the reference list is not read"),
    ]


def test_a_reference_section_is_found_at_any_level() -> None:
    assert [
        e.span.block for e in ReferenceListStep().find(references("References", nested=True), EN)
    ] == [2, 3]


@pytest.mark.parametrize(
    "title", ["Further references", "References and notes", "The References", "Notes", "Literature"]
)
def test_other_titles_are_not_a_reference_list(title: str) -> None:
    assert ReferenceListStep().find(references(title), EN) == []


def test_the_switch_keeps_the_reference_list() -> None:
    document = references("References")
    assert read(document, switched_off={Category.REFERENCES})[2:4] == [
        "References",
        "Doe, J. (2020). A study.",
    ]
    assert REFERENCE_TITLES == (
        "References",
        "Bibliography",
        "Reference list",
        "Works cited",
        "Literature cited",
    )


# ---- properties ------------------------------------------------------------------------------


@given(rule_documents())
def test_the_steps_keep_the_contract_on_any_document(document: Document) -> None:
    for step in (FormulaNoticeStep(), TableFigureNoticeStep(), ReferenceListStep()):
        check_text_step(step, [document], allow_ask=False)


@given(rule_documents())
def test_every_placeholder_reads_exactly_a_notice(document: Document) -> None:
    spoken = read(document)
    # the reference list is removed first and wins over a placeholder inside it (Q15)
    in_references = {edit.span.block for edit in ReferenceListStep().find(document, EN)}
    for index, block in enumerate(document.blocks):
        if block.is_placeholder and index not in in_references:
            assert spoken[index].endswith("skipped."), (block, spoken[index])
