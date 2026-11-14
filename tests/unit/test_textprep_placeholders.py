"""Formulas, tables, figures and code blocks are read as a short notice (FX-01, FX-02, #64,
Q3, D-145, #280, D-545), and the reference list is not read (TP-06, D-146)."""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from textprep_documents import rule_documents

from sci2audio.app.chapters import REFERENCE_NAMES as APP_REFERENCE_NAMES
from sci2audio.app.chapters import is_reference_title as app_is_reference_title
from sci2audio.core import Block, BlockKind, Document, EditKind, Section, Span
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import (
    GERMAN_REFERENCE_TITLES,
    REFERENCE_TITLES,
    Category,
    CodeNoticeStep,
    FormulaNoticeStep,
    ReferenceListStep,
    StepContext,
    TableFigureNoticeStep,
    is_reference_title,
    run_steps,
    spoken_text,
    wording_for,
)

EN = StepContext("en")
DE = StepContext("de")


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
        ([(BlockKind.CODE, "import os\nos.getcwd()")], "A code block is skipped."),
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
    for i, block in enumerate(document.blocks):  # the caption reads in its place,
        if block.kind is BlockKind.CAPTION:  # its label word in full (#68)
            printed = spoken_text_of(block.text)
            assert spoken[i] == wording_for("en").label(block.label) + printed[len(block.label) :]


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


def test_a_code_block_is_one_notice_in_its_language_and_nothing_inside_it_is_read() -> None:
    """#280, D-545: no other step edits code; switched off, the code reads as printed."""
    code = 'x = f(3)  # see https://example.org\nprint("e.g. 5 mg-\nper-kg")'
    document = make_document([(BlockKind.PARAGRAPH, "Run this:"), (BlockKind.CODE, code)])
    (edit,) = CodeNoticeStep().find(document, EN)
    assert (edit.span, edit.kind) == (Span(1, 0, len(code)), EditKind.REPLACE)
    assert edit.reason == "this code block is not read; a short notice is read instead (D-55)"
    assert read(document) == ["Run this:", "A code block is skipped."]
    assert read(replace(document, language="de"))[1] == "Ein Codeblock wird übersprungen."
    off = read(document, switched_off={Category.CODE})
    assert off[1] == " ".join(code.split())  # read as printed: no link, unit or hyphen edit
    check_text_step(CodeNoticeStep(), allow_ask=False)


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


@pytest.mark.parametrize(
    ("printed", "read_as"),
    [
        ("FIG. 3", "Figure 3"),  # APS and PRL print the label in capitals
        ("fig. 3", "Figure 3"),
        ("TABLE 2", "TABLE 2"),  # a full word is read as printed
        ("Fig.3", "Figure 3"),  # the short word against its number
        ("FIGS.3a", "Figures 3a"),
        ("Eq.(4)", "Equation (4)"),
        ("Tab.IV", "Table IV"),
        ("Fig.", "Figure"),
        ("S.3", "S.3"),  # not a label word: as printed
        ("Figure 2", "Figure 2"),
        ("Scheme 1", "Scheme 1"),
    ],
)
def test_a_short_label_word_is_read_in_full_in_any_case_and_spacing(
    printed: str, read_as: str
) -> None:
    assert wording_for("en").label(printed) == read_as


def test_a_capital_short_caption_label_reads_its_notice_in_full() -> None:
    document = make_document([(BlockKind.FIGURE, "x"), caption("FIG. 3", 0, ". Shown.")])
    assert read(document)[0] == "Figure 3 is skipped."
    document = make_document([(BlockKind.FIGURE, "x"), caption("Fig.3", 0, ". Shown.")])
    assert read(document)[0] == "Figure 3 is skipped."


def test_notices_are_read_in_german_for_a_german_job() -> None:
    document = make_document(
        [
            (BlockKind.TABLE, "a b"),
            caption("Tab. 2", 0, ": Werte."),
            Block(BlockKind.FORMULA, "x = 1 (4)", label="4"),
            (BlockKind.FORMULA, "y = 2"),
            (BlockKind.FIGURE, ""),
            (BlockKind.FIGURE, "0 1"),
            caption("Abbildung 1", 5, " und "),
            caption("Abb. 2", 5, ": Verlauf."),
        ],
        "de",
    )
    assert [read(document)[i] for i in (0, 2, 3, 4, 5)] == [
        "Tabelle 2 wird übersprungen.",
        "Formel 4 wird übersprungen.",
        "Eine Formel wird übersprungen.",
        "Eine Abbildung wird übersprungen.",
        "Abbildung 1 und Abbildung 2 werden übersprungen.",
    ]
    (edit,) = [e for e in FormulaNoticeStep().find(document, DE) if e.span.block == 2]
    # the reason stays English (D-291) and names the item as the notice does
    assert edit.reason == "Formel 4 is not read; a short notice is read instead (D-55)"


@pytest.mark.parametrize("language", ["de", "de-AT", "DE-ch"])
def test_every_german_tag_uses_the_german_wording(language: str) -> None:
    german = wording_for(language)
    assert german is wording_for("de")
    assert german.skipped(["Tabelle 1", "Abbildung 2", "Formel 3"], BlockKind.TABLE) == (
        "Tabelle 1, Abbildung 2 und Formel 3 werden übersprungen."
    )
    assert german.skipped([], BlockKind.TABLE) == "Eine Tabelle wird übersprungen."
    assert german.footnote.format("3") == "Fußnote 3."
    assert german.footnote_unnamed == "Fußnote."
    assert (german.reference, german.references, german.range_to) == ("Quelle", "Quellen", "bis")


@pytest.mark.parametrize(
    ("printed", "read_as"),
    [
        ("Abb. 3", "Abbildung 3"),
        ("ABB. 3", "Abbildung 3"),
        ("Abb.3", "Abbildung 3"),
        ("Tab. 2", "Tabelle 2"),
        ("Gl. (4)", "Gleichung (4)"),
        ("Alg. 1", "Algorithmus 1"),
        ("Abbildung 1", "Abbildung 1"),
        ("Fig. 3", "Fig. 3"),  # an English short label is named as printed (D-518)
    ],
)
def test_a_german_short_label_is_read_in_full(printed: str, read_as: str) -> None:
    assert wording_for("de").label(printed) == read_as


def test_the_english_wording_does_not_read_german_short_labels() -> None:
    assert wording_for("en").label("Abb. 3") == "Abb. 3"


def test_notices_are_not_run_for_a_language_without_wording() -> None:
    french = make_document([(BlockKind.TABLE, "a b")], "fr")
    run = run_steps(french, StepContext("fr"), strict=True)
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
     "Literature cited", "9 Reference List", "References:", "A.1 References"],
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


@pytest.mark.parametrize(
    "title",
    ["Literatur", "LITERATUR", "7 Literatur", "Literaturverzeichnis", "Literaturverzeichnis:",
     "Quellen", "8. Quellenverzeichnis", "Bibliographie", "Bibliografie", "A Literatur",
     "References", "Bibliography"],
)  # fmt: skip
@pytest.mark.parametrize("language", ["de", "de-AT", "de-CH"])
def test_a_german_reference_section_is_not_read(title: str, language: str) -> None:
    """#221, D-481: the German names, and the English ones a German paper may print."""
    edits = ReferenceListStep().find(references(title), StepContext(language))
    assert [e.span.block for e in edits] == [2, 3]


@pytest.mark.parametrize(
    "title", ["Literaturüberblick", "Weitere Literatur", "Quellenkritik", "Anmerkungen", "Notes"]
)
def test_other_german_titles_are_not_a_reference_list(title: str) -> None:
    assert ReferenceListStep().find(references(title), DE) == []


@pytest.mark.parametrize("title", ["Literatur", "Quellen", "Bibliographie"])
def test_german_names_count_only_in_german_jobs(title: str) -> None:
    """An English paper's section "Quellen" is no reference list of that job (D-481)."""
    assert ReferenceListStep().find(references(title), EN) == []
    assert not is_reference_title(title)
    assert is_reference_title(title, "de")


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


TITLES = [
    "References", "REFERENCES", "References:", "References.", "7 References", "7. References",
    "8.1 Bibliography", "A References", "A.1 References", "IV Bibliography", "IV. Bibliography",
    " References ", "Works Cited", "Works  cited", "Reference list", "Literature cited:",
    "100 References", "Further references", "References and notes", "The References",
    "Results", "Notes", "Literature", "", "7", "References 2", "a References",
    "VI.2 Bibliography", "Literatur", "7 Literaturverzeichnis", "Quellen:", "BIBLIOGRAFIE",
    "A.1 Bibliographie", "Literaturüberblick", "Weitere Quellen", "Quellenverzeichnis.",
    "Literaturliste", "8 Verwendete Literatur", "Zitierte Literatur:",
    "Quellen- und Literaturverzeichnis", "LITERATUR- UND QUELLENVERZEICHNIS", "Literatur und",
]  # fmt: skip


def test_the_names_are_the_apps_chapter_names() -> None:
    """One source: the app's English chapter names are the step's own tuple (D-132, D-146)."""
    assert APP_REFERENCE_NAMES["en"] is REFERENCE_TITLES
    assert APP_REFERENCE_NAMES["de"] is GERMAN_REFERENCE_TITLES
    assert set(APP_REFERENCE_NAMES) == {"en", "de"}


@pytest.mark.parametrize("title", TITLES)
def test_the_step_and_the_chapter_choice_agree_on_every_title(title: str) -> None:
    """The same titles, matched the same way (number, case, a closing "." or ":"); the
    chapter choice takes the names of every language, the step those of the job's."""
    assert app_is_reference_title(title) == any(
        is_reference_title(title, language) for language in APP_REFERENCE_NAMES
    )
    assert is_reference_title(title) == is_reference_title(title, "en")


# ---- properties ------------------------------------------------------------------------------


@given(rule_documents())
def test_the_steps_keep_the_contract_on_any_document(document: Document) -> None:
    for step in (FormulaNoticeStep(), TableFigureNoticeStep(), ReferenceListStep()):
        check_text_step(step, [document], allow_ask=False)


@given(rule_documents(), st.sampled_from(GERMAN_REFERENCE_TITLES))
def test_the_reference_step_keeps_the_contract_on_any_german_document(
    document: Document, name: str
) -> None:
    """The same documents in German, their reference sections headed with a German name."""
    sections = tuple(
        replace(section, title=name) if is_reference_title(section.title) else section
        for section in document.sections
    )
    german = replace(document, language="de", sections=sections)
    check_text_step(ReferenceListStep(), [german], allow_ask=False)
    expected = ReferenceListStep().find(document, EN)
    assert ReferenceListStep().find(german, DE) == expected


@given(rule_documents())
def test_the_notice_steps_keep_the_contract_on_any_german_document(document: Document) -> None:
    german = replace(document, language="de")
    for step in (FormulaNoticeStep(), TableFigureNoticeStep(), CodeNoticeStep()):
        check_text_step(step, [german], allow_ask=False)
    spoken = read(german)
    in_references = {edit.span.block for edit in ReferenceListStep().find(german, DE)}
    for index, block in enumerate(german.blocks):
        if block.is_placeholder and index not in in_references:
            assert spoken[index].endswith(("wird übersprungen.", "werden übersprungen."))


@given(rule_documents())
def test_every_placeholder_reads_exactly_a_notice(document: Document) -> None:
    spoken = read(document)
    # the reference list is removed first and wins over a placeholder inside it (Q15)
    in_references = {edit.span.block for edit in ReferenceListStep().find(document, EN)}
    for index, block in enumerate(document.blocks):
        if block.is_placeholder and index not in in_references:
            assert spoken[index].endswith("skipped."), (block, spoken[index])
