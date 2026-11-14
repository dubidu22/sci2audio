"""Footnotes (TP-05, #64, Q2, D-142 to D-144): marks left out, notes introduced, and the
"Footnote texts" switch that leaves every note out."""

from dataclasses import replace

import pytest
from hypothesis import given
from textprep_documents import Line, body, note, rule_documents, sized_document

from sci2audio.core import (
    Block,
    BlockKind,
    Box,
    Content,
    Document,
    EditKind,
    Page,
    Part,
    Source,
    SourceFormat,
    Span,
    TextLine,
    TextRun,
)
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import (
    Category,
    FootnoteStep,
    FootnoteTextStep,
    Status,
    StepContext,
    run_steps,
    spoken_text,
)

EN = StepContext("en")
STAR = "\u2217"  # the asterisk operator, as papers print a note mark


def read(document: Document, **switches: object) -> list[str]:
    """Each block's spoken text after all built-in steps (empty for a block not read)."""
    run = run_steps(document, StepContext(document.language), strict=True, **switches)
    return [
        spoken_text(p for p in run.script() if p.span.block == index)
        for index in range(len(document.blocks))
    ]


def marked(text: str, mark: str, label: str | None = None) -> Document:
    """A paragraph whose `mark` (its last occurrence) is a superscript, and the note."""
    at = text.rindex(mark)
    label = mark if label is None else label
    return make_document(
        [(BlockKind.PARAGRAPH, text), Block(BlockKind.FOOTNOTE, f"{label} A note.", label=label)],
        tags={0: [(at, at + len(mark), "sup")]},
    )


# ---- introductions ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "label", "spoken"),
    [
        ("1 Measured twice.", "1", "Footnote 1. Measured twice."),
        ("12Measured twice.", "12", "Footnote 12. Measured twice."),  # no space after the mark
        ("a\nMeasured twice.", "a", "Footnote a. Measured twice."),
        (f"{STAR}Work done at home.", STAR, "Footnote. Work done at home."),  # a symbol is not read
        ("†‡ Two symbols.", "†‡", "Footnote. Two symbols."),
        ("  3 Leading space.", "3", "Footnote 3. Leading space."),
        ("A note without a mark.", "", "Footnote. A note without a mark."),
        ("Printed 4 later.", "4", "Footnote. Printed 4 later."),  # label not at the start
        ("Footnote 2 is already said.", "2", "Footnote 2 is already said."),
        ("Footnotes are discussed here.", "", "Footnote. Footnotes are discussed here."),
        ("1. Measured twice.", "1", "Footnote 1. Measured twice."),  # the "." goes with the mark
        ("1) Measured twice.", "1", "Footnote 1. Measured twice."),
        ("b.\nMeasured twice.", "b", "Footnote b. Measured twice."),
        ("2.", "2", "Footnote 2."),
        (f"{STAR}) Work done at home.", STAR, "Footnote. Work done at home."),
    ],
)
def test_each_note_is_introduced_once(text: str, label: str, spoken: str) -> None:
    document = make_document([Block(BlockKind.FOOTNOTE, text, label=label)])
    assert read(document) == [spoken]


def test_an_empty_or_blank_note_gets_no_introduction() -> None:
    document = make_document([(BlockKind.FOOTNOTE, ""), (BlockKind.FOOTNOTE, " \n ")])
    assert FootnoteStep().find(document, EN) == []


def test_the_introduction_replaces_the_mark_itself() -> None:
    document = make_document([Block(BlockKind.FOOTNOTE, "1 A note.", label="1")])
    (edit,) = FootnoteStep().find(document, EN)
    assert (edit.span, edit.kind, edit.replacement) == (Span(0, 0, 1), EditKind.REPLACE,
                                                        "Footnote 1.")  # fmt: skip
    assert edit.reason == "footnote 1 is introduced by its mark"


def test_a_point_or_parenthesis_after_the_mark_is_replaced_with_it() -> None:
    document = make_document([Block(BlockKind.FOOTNOTE, "1) A note.", label="1")])
    (edit,) = FootnoteStep().find(document, EN)
    assert (edit.span, edit.replacement) == (Span(0, 0, 2), "Footnote 1.")


# ---- marks in the running text -------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "mark", "spoken"),
    [
        ("The effect was small.1", "1", "The effect was small."),
        ("The effect was small1 in both.", "1", "The effect was small in both."),
        (f"Jane Doe{STAR}", STAR, "Jane Doe"),
        (f"Ahmad3{STAR} and others.", STAR, "Ahmad3 and others."),  # after an affiliation number
        ("as in the pack (2021).12 Then", "12", "as in the pack (2021). Then"),
        ("the string: 7", "7", "the string:"),  # set apart by a space (before #36)
        ("the “quoted”2 word", "2", "the “quoted” word"),
    ],
)
def test_a_superscript_mark_after_a_word_is_left_out(text: str, mark: str, spoken: str) -> None:
    assert read(marked(text, mark))[0] == spoken


@pytest.mark.parametrize(
    ("text", "mark"),
    [
        ("in time N3 on dense grammars", "3"),  # a one-letter variable: maths
        ("in time O(|N |3) overall", "3"),  # after a maths sign
        ("the sum x2", "2"),
        ("the cube of size3 + 1", "3"),  # an operator follows
        ("5 is first", "5"),  # nothing before it
    ],
)
def test_a_superscript_that_looks_like_maths_is_kept(text: str, mark: str) -> None:
    assert read(marked(text, mark))[0] == spoken_text_of(text)


def spoken_text_of(text: str) -> str:
    return " ".join(text.split())


def test_a_mark_needs_a_note_with_that_label() -> None:
    assert read(marked("The effect was small.1", "1", label="2"))[0] == "The effect was small.1"


def test_a_mark_needs_a_superscript_or_a_smaller_size() -> None:
    plain = make_document(
        [(BlockKind.PARAGRAPH, "Results1 hold."), Block(BlockKind.FOOTNOTE, "1 N.", label="1")]
    )
    assert read(plain)[0] == "Results1 hold."
    sized = sized_document(
        [body(1, ("Results", 10.0), ("1", 7.0), (" hold.", 10.0)), note(1, "1", " N.")]
    )
    assert read(sized)[0] == "Results hold."
    same_size = sized_document(
        [body(1, ("Results", 10.0), ("1", 10.0), (" hold.", 10.0)), note(1, "1", " N.")]
    )
    assert read(same_size)[0] == "Results1 hold."


def test_a_mark_is_matched_on_the_notes_page_only_and_once() -> None:
    document = sized_document(
        [
            body(1, ("Results", 10.0), ("1", 7.0), (" hold.", 10.0)),  # page 1: no note 1
            body(2, ("Noise", 10.0), ("1", 7.0), (" and sound", 10.0), ("1", 7.0)),
            note(2, "1", " The note."),
        ]
    )
    assert read(document)[:2] == ["Results1 hold.", "Noise and sound1"]


def test_marks_in_headings_captions_and_list_items_are_left_out_but_not_in_notes() -> None:
    lines = [
        Line(BlockKind.HEADING, 1, (("Introduction", 12.0), ("1", 8.0))),
        Line(BlockKind.LIST_ITEM, 1, (("(a) first item", 10.0), ("2", 7.0))),
        Line(BlockKind.FOOTNOTE, 1, (("3", 6.0), (" See note", 8.0), ("1", 5.0))),
        note(1, "1", " One."),
        note(1, "2", " Two."),
    ]
    assert read(sized_document(lines))[:3] == [
        "Introduction",
        "(a) first item",
        "Footnote. 3 See note1",  # a note without a label: introduced, its text untouched
    ]


def test_the_mark_edit_removes_only_the_mark() -> None:
    document = marked("The effect.1 It held.", "1")
    edits = [e for e in FootnoteStep().find(document, EN) if e.kind is EditKind.REMOVE]
    assert [(e.span, e.reason) for e in edits] == [
        (
            Span(0, 11, 12),
            "footnote mark 1 is not read; the note is read at the foot of the column (Q2)",
        )
    ]


# ---- the two switches -----------------------------------------------------------------------


def test_switching_footnotes_off_reads_marks_and_notes_as_printed() -> None:
    document = marked("The effect was small.1", "1")
    assert read(document, switched_off={Category.FOOTNOTES, Category.FOOTNOTE_TEXTS}) == [
        "The effect was small.1",
        "1 A note.",
    ]


def test_turning_footnote_texts_on_leaves_every_note_out_and_the_marks_too() -> None:
    document = marked("The effect was small.1", "1")
    run = run_steps(document, EN, switched_off=(), strict=True)
    assert [spoken_text(p for p in run.script() if p.span.block == i) for i in (0, 1)] == [
        "The effect was small.",
        "",
    ]
    (intro,) = [o for o in run.outcomes if o.edit.step == "footnotes" and o.edit.span.block == 1]
    assert intro.status is Status.SET_ASIDE
    assert intro.won_by is not None
    assert intro.won_by.step == "footnote-texts"


def test_footnote_texts_removes_each_note_with_text_as_a_whole_block() -> None:
    document = make_document(
        [
            Block(BlockKind.FOOTNOTE, "1 One.", label="1"),
            (BlockKind.FOOTNOTE, ""),
            (BlockKind.FOOTNOTE, "Two."),
            (BlockKind.PARAGRAPH, "Body."),
        ]
    )
    edits = FootnoteTextStep().find(document, EN)
    assert [(e.span, e.kind, e.reason) for e in edits] == [
        (Span(0, 0, 6), EditKind.REMOVE, "footnote 1 is left out (all footnotes are left out)"),
        (Span(2, 0, 4), EditKind.REMOVE, "a footnote is left out (all footnotes are left out)"),
    ]


def test_notes_are_introduced_in_english_and_german_and_left_out_in_any_language() -> None:
    assert FootnoteStep().languages == ("en", "de")
    french = make_document([Block(BlockKind.FOOTNOTE, "1 Une note.", label="1")], "fr")
    run = run_steps(french, StepContext("fr"), switched_off=(), strict=True)
    assert "footnotes" in run.not_run
    assert [edit.step for edit in run.accepted] == ["footnote-texts"]


# ---- German (#212) -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "label", "spoken"),
    [
        ("1 Gemessen.", "1", "Fußnote 1. Gemessen."),
        ("1. Gemessen.", "1", "Fußnote 1. Gemessen."),
        (f"{STAR}Am Institut.", STAR, "Fußnote. Am Institut."),
        ("Eine Notiz ohne Zeichen.", "", "Fußnote. Eine Notiz ohne Zeichen."),
        ("Fußnote 2 steht schon da.", "2", "Fußnote 2 steht schon da."),  # introduced already
        ("Fußnoten folgen hier.", "", "Fußnote. Fußnoten folgen hier."),
    ],
)
def test_a_german_note_is_introduced_in_german(text: str, label: str, spoken: str) -> None:
    document = make_document([Block(BlockKind.FOOTNOTE, text, label=label)], "de-AT")
    assert read(document) == [spoken]


def test_a_german_mark_after_a_closing_quote_is_left_out() -> None:
    document = marked("der „Alexa Top 1 Million“9 und", "9")
    document = replace(document, language="de")
    assert read(document)[:2] == ["der „Alexa Top 1 Million“ und", "Fußnote 9. A note."]


def test_an_english_note_still_reads_footnote_after_the_german_row() -> None:
    document = make_document([Block(BlockKind.FOOTNOTE, "Fußnote 1 Text.", label="")])
    assert read(document) == ["Footnote. Fußnote 1 Text."]  # English checks its own word


# ---- superior figures and the printed asterisk (#212, D-519) ---------------------------------


def boxed(*runs: tuple[str, float, float], note_label: str = "4", language: str = "de") -> Document:
    """A PDF-like paragraph of one line whose runs are (text, top, bottom) in 10 pt, and a note
    labelled `note_label` on the same page."""
    x, made = 0.0, []
    for text, top, bottom in runs:
        made.append(TextRun(text, size=10.0, box=Box(x, top, x + 5 * len(text), bottom)))
        x += 5 * len(text)
    line = TextLine("l0", tuple(made))
    note_line = TextLine("l1", (TextRun(f"{note_label} Eine Notiz.", size=8.0),))
    content = Content(Source("boxed.pdf", SourceFormat.PDF), (Page(1, (line, note_line)),))
    blocks = (
        Block(BlockKind.PARAGRAPH, line.text, (Part("l0"),)),
        Block(BlockKind.FOOTNOTE, note_line.text, (Part("l1"),), label=note_label),
    )
    return Document(content=content, language=language, blocks=blocks)


@pytest.mark.parametrize("language", ["de", "en"])
def test_a_mark_raised_in_the_texts_own_size_is_left_out(language: str) -> None:
    document = boxed(("gezeigt hat.", 100, 110), ("4", 97, 107), (" Weiter", 100, 110),
                     language=language)  # fmt: skip
    assert read(document)[0] == "gezeigt hat. Weiter"


@pytest.mark.parametrize(
    "runs",
    [
        (("gezeigt hat.", 100, 110), ("4", 99.5, 109.5), (" Weiter", 100, 110)),  # 0.05 em
        (("gezeigt hat.", 100, 110), ("4", 100, 110), (" Weiter", 100, 110)),  # on the line
        (("gezeigt hat.", 100, 110), ("4", 85, 95)),  # a line above, not a raised figure
        (("in time N", 100, 110), ("4", 97, 107)),  # one-letter variable: maths
    ],
)
def test_a_figure_not_raised_on_its_line_or_after_maths_is_kept(
    runs: tuple[tuple[str, float, float], ...],
) -> None:
    document = boxed(*runs)
    assert read(document)[0] == "".join(text for text, _, _ in runs)


def test_a_printed_asterisk_marks_the_note_with_the_asterisk_operator() -> None:
    document = boxed(("Zulässigkeit", 100, 110), ("*", 97, 107), note_label=STAR)
    assert read(document) == ["Zulässigkeit", "Fußnote. Eine Notiz."]


# ---- properties ------------------------------------------------------------------------------


@given(rule_documents())
def test_both_steps_keep_the_contract_on_any_document(document: Document) -> None:
    for step in (FootnoteStep(), FootnoteTextStep()):
        check_text_step(step, [document], allow_ask=False)


@given(rule_documents())
def test_the_steps_keep_the_contract_in_german_and_remove_the_same_marks(
    document: Document,
) -> None:
    german = replace(document, language="de")
    for step in (FootnoteStep(), FootnoteTextStep()):
        check_text_step(step, [german], allow_ask=False)
    marks = [e for e in FootnoteStep().find(document, EN) if e.kind is EditKind.REMOVE]
    assert [
        e for e in FootnoteStep().find(german, StepContext("de")) if e.kind is EditKind.REMOVE
    ] == marks
    spoken = read(german)
    for index, block in enumerate(german.blocks):
        if block.kind is BlockKind.FOOTNOTE and block.text.strip():
            assert spoken[index].startswith("Fußnote")


@given(rule_documents())
def test_every_note_reads_from_footnote_and_no_superscript_label_after_a_word_stays(
    document: Document,
) -> None:
    spoken = read(document)
    assert spoken[0] == "results"  # the mark every generated document has is left out
    for index, block in enumerate(document.blocks):
        if block.kind is BlockKind.FOOTNOTE and block.text.strip():
            assert spoken[index].startswith("Footnote")
    # every edit the mark rule made removes exactly one note label
    labels = {b.label for b in document.blocks if b.kind is BlockKind.FOOTNOTE and b.label}
    for edit in FootnoteStep().find(document, EN):
        if edit.kind is EditKind.REMOVE:
            assert document.text_of(edit.span) in labels
