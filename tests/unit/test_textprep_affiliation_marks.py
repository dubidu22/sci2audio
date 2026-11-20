"""Affiliation marks in a paper's title block are not read (#93, D-692).

The title block is the first page's PARAGRAPH blocks up to the first heading. A mark is a
run of digits, commas and note symbols, set small (a `sup` tag, or more than 8% under the
block's main size) and raised (a `sup` tag, or 0.1 em above a run in the main size on its
line), that is no footnote mark, after a name or before an affiliation.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
    apply_edits,
)
from sci2audio.testing import check_text_step, make_document
from sci2audio.testing.regression import render
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    AffiliationMarkStep,
    Category,
    StepContext,
    run_steps,
    spoken_text,
)
from sci2audio.textprep.footnotes import _after_name

EN = StepContext("en")
STEP = "affiliation-marks"
STAR = "\u2217"  # the asterisk operator, as papers print a note mark
AUTHORS = [Block(BlockKind.PARAGRAPH, "Ann Lee1"), [(7, 8, "sup")]]  # an author line (#448)

# a run of a PDF line: text, top, bottom and size; the main size is 10 pt
PdfRun = tuple[str, float, float, float]
NAME = (100.0, 110.0, 10.0)  # top, bottom, size of a name
RAISED = (97.0, 104.0, 7.0)  # a mark set small, ending 6 pt above the name's bottom


def pdf(*lines: tuple[PdfRun, ...], page: int = 1) -> Document:
    """A PDF-like paragraph of these lines on `page` (earlier pages empty)."""
    made = []
    for number, runs in enumerate(lines):
        x, line = 0.0, []
        for text, top, bottom, size in runs:
            line.append(TextRun(text, size=size, box=Box(x, top, x + 5 * len(text), bottom)))
            x += 5 * len(text)
        made.append(TextLine(f"l{number}", tuple(line)))
    parts, start = [], 0
    for line in made:
        parts.append(Part(line.id, start))
        start += len(line.text) + 1
    pages = tuple(Page(n, tuple(made) if n == page else ()) for n in range(1, page + 1))
    text = "\n".join(line.text for line in made)
    block = Block(BlockKind.PARAGRAPH, text, tuple(parts))
    content = Content(Source("title.pdf", SourceFormat.PDF), pages)
    return Document(content=content, language="en", blocks=(block,))


def name(text: str) -> PdfRun:
    return (text, *NAME)


def mark(text: str, top: float = 97.0, bottom: float = 104.0, size: float = 7.0) -> PdfRun:
    return (text, top, bottom, size)


def sup(*runs: str | tuple[str], kind: BlockKind = BlockKind.PARAGRAPH) -> list:
    """A block of runs: strings are plain, ("1",) is a run tagged `sup`."""
    text, ranges = "", []
    for run in runs:
        if isinstance(run, tuple):
            ranges.append((len(text), len(text) + len(run[0]), "sup"))
            run = run[0]
        text += run
    return [Block(kind, text), ranges]


def tagged(*blocks: list, language: str = "en", pages: dict[int, int] | None = None) -> Document:
    """A document of blocks made by `sup` (or a plain (kind, text) pair)."""
    made, tags = [], {}
    for number, block in enumerate(blocks):
        if isinstance(block, list):
            made.append(block[0])
            tags[number] = block[1]
        else:
            made.append(block)
    return make_document(made, language, tags=tags, pages=pages)


def removed(document: Document, context: StepContext = EN) -> list[str]:
    """The text of each removal the step proposes."""
    found = AffiliationMarkStep().find(document, context)
    return [document.blocks[e.span.block].text[e.span.start : e.span.end] for e in found]


def read(document: Document, switched_off: tuple[Category, ...] = ()) -> list[str]:
    run = run_steps(document, StepContext(document.language), switched_off=switched_off,
                    strict=True)  # fmt: skip
    return [
        spoken_text(p for p in run.script() if p.span.block == index)
        for index in range(len(document.blocks))
    ]


# ---- set small and raised (PDF) ----------------------------------------------------------


def test_a_mark_set_small_and_raised_after_a_name_is_removed() -> None:
    document = pdf((name("Jane Roe"), mark("1,2"), name(" Wasi Ahmed"), mark("3")))
    edits = AffiliationMarkStep().find(document, EN)
    assert [(e.span, e.kind, e.reason, e.step) for e in edits] == [
        (Span(0, 8, 11), EditKind.REMOVE, 'affiliation mark "1,2" is not read', STEP),
        (Span(0, 22, 23), EditKind.REMOVE, 'affiliation mark "3" is not read', STEP),
    ]
    assert read(document) == ["Jane Roe Wasi Ahmed"]


@pytest.mark.parametrize(
    ("run", "is_mark"),
    [
        (mark("1"), True),
        (mark("1", size=9.1), True),  # 9 % smaller: set small
        (mark("1", size=9.3), False),  # 7 % smaller: the text's size
        (mark("1", size=10.0), False),  # raised but not small: a superior figure is read
        (mark("1", top=103.0, bottom=110.0), False),  # small, on the line: no rise
        (mark("1", top=102.0, bottom=109.0), True),  # 1 pt = 0.1 em above: raised
        (mark("1", top=102.5, bottom=109.5), False),  # 0.05 em: not raised
        (mark("1", top=104.0, bottom=112.0), False),  # small and lowered: a subscript
    ],
)
def test_set_small_and_raised_are_both_needed(run: PdfRun, is_mark: bool) -> None:
    document = pdf((name("Jane Roe"), run, name(" Wasi Ahmed")))
    assert removed(document) == (["1"] if is_mark else [])


def test_the_rise_is_measured_against_a_run_in_the_main_size_on_the_same_line() -> None:
    # the mark opens the second line; the run it rises over is later on that line
    document = pdf((name("Simon Bigg"),), (mark("1"), name(", Matt Jenner"), mark("2")))
    assert read(document) == ["Simon Bigg, Matt Jenner"]
    # with only small runs on its line, a mark is not raised over anything
    alone = pdf((name("Simon Bigg"),), (mark("1"),))
    assert removed(alone) == []
    # a small run set lower (a subscript) does not make a small run on the line look raised
    lowered = pdf(
        (name("Jane Roe"), mark("1", 103.0, 110.0), name(" and"), mark("2", 106.0, 113.0))
    )
    assert removed(lowered) == []


def test_runs_side_by_side_make_one_mark() -> None:
    document = pdf((name("Jane Roe"), mark("1"), mark(","), mark("2"), name(" and")))
    assert removed(document) == ["1,2"]


@pytest.mark.parametrize("text", ["1a", "(1)", "i", "1.2", "a"])
def test_only_digits_commas_and_note_symbols_make_a_mark(text: str) -> None:
    document = tagged(sup("Jane Roe", (text,), " and Ann Lee"))
    assert removed(document) == []


@pytest.mark.parametrize(
    "text", ["1", "12", "1,2", STAR, "*", "†", "‡", "§", "¶", f"1,{STAR}", " 2 "]
)
def test_digits_commas_and_note_symbols_make_a_mark(text: str) -> None:
    document = tagged(sup("Jane Roe", (text,), " and Ann Lee"))
    # " 2 " has white space on both sides once stripped: the space before goes too (#445)
    assert removed(document) == [" 2" if text == " 2 " else text]


# ---- the two shapes ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("runs", "spoken"),
    [
        (["Jianfeng Chi", ("1,2",), " Wasi"], "Jianfeng Chi Wasi"),  # after a name, a space
        (["Yuan Tan", ("3",)], "Yuan Tan"),  # after a name, the block's end
        (["Simon Bigg ", ("1",), ", Matt"], "Simon Bigg, Matt"),  # after a name, a comma
        (["Ann Lee", ("2",), "; Bo Kim"], "Ann Lee; Bo Kim"),  # a semicolon
        (["Wasi Ahmed", ("3",), "†"], "Wasi Ahmed†"),  # a note mark follows (read as printed)
        (["Zoë Ångström", ("1",), " and"], "Zoë Ångström and"),  # letters of any script
        ([("1",), "Example AI, ", ("2",), "University"], "Example AI, University"),
        ([("1",), " Example AI"], "Example AI"),  # one space before the affiliation
        (["Lab, ", ("2",), " Example"], "Lab, Example"),
        (["Lab,", ("2",), "Example"], "Lab,Example"),  # after a comma
        (["Lab; ", ("2",), "Example"], "Lab; Example"),  # after a semicolon
        ([("1",), "AI Lab"], "AI Lab"),  # a word of two letters
        ([("2",), "\u00d6sterreichische Akademie"], "\u00d6sterreichische Akademie"),  # any capital
        (["Lab, ", ("3",), "\u00c9cole Normale"], "Lab, \u00c9cole Normale"),
        (["Lab, ", ("4",), " \u00dcberseemuseum"], "Lab, \u00dcberseemuseum"),
    ],
)
def test_marks_after_a_name_or_before_an_affiliation_are_removed(runs: list, spoken: str) -> None:
    """After an author line: a mark before an affiliation counts only after one (#448)."""
    assert read(tagged(AUTHORS, sup(*runs))) == ["Ann Lee", spoken]


@pytest.mark.parametrize(
    "runs",
    [
        [("1",), "Example AI, ", ("2",), "University"],
        [("1",), " Example AI"],
        ["Lab, ", ("2",), " Example"],
        [("1",), "AI Lab"],
        [("13",), "CO and C", ("18",), "O observations"],  # a title's mass numbers (#448)
        ["Mapping ", ("12",), "CO, ", ("13",), "CO and ", ("15",), "NH3"],
    ],
)
def test_before_the_author_line_a_mark_before_an_affiliation_is_read(runs: list) -> None:
    assert removed(tagged(sup(*runs), AUTHORS)) == ["1"]


def test_a_mark_after_a_name_earlier_in_the_same_block_starts_the_affiliations() -> None:
    document = tagged(sup(("13",), "CO maps by Ann Lee", ("1",), ", ", ("1",), "AI Lab"))
    assert read(document) == ["13CO maps by Ann Lee, AI Lab"]


def test_a_footnote_mark_after_a_name_starts_the_affiliations_too() -> None:
    """A corresponding author's note mark is the footnotes step's, yet shows the author line."""
    document = tagged(sup("Ann Lee", (STAR,)), sup(("1",), "AI Lab"), sup(f"{STAR} Corresponding"))
    found = AffiliationMarkStep().marks(document, {0: [(7, 8)]})
    assert [document.blocks[e.span.block].text[e.span.start : e.span.end] for e in found] == ["1"]
    assert AffiliationMarkStep().marks(document, {}) != []  # the star after a name is a mark
    assert AffiliationMarkStep().marks(tagged(sup(("1",), "AI Lab")), {}) == []
    # a footnote mark after no name (a title's note) shows no author line
    title = tagged(sup("Cold gas in clouds", (STAR,)), sup(("1",), "AI Lab"))
    assert AffiliationMarkStep().marks(title, {0: [(18, 19)]}) == []


def test_a_footnote_mark_after_a_name_starts_the_affiliations_of_its_own_block() -> None:
    document = tagged(sup("Ann Lee", (STAR,), ", ", ("1",), "AI Lab"))
    found = AffiliationMarkStep().marks(document, {0: [(7, 8)]})
    assert [document.blocks[0].text[e.span.start : e.span.end] for e in found] == ["1"]
    # a footnote mark after the affiliation's mark comes too late for it
    document = tagged(sup(("1",), "AI Lab, Ann Lee", (STAR,)))
    assert AffiliationMarkStep().marks(document, {0: [(16, 17)]}) == []


@pytest.mark.parametrize(
    "runs",
    [
        ["The cost is x", ("2",), " here"],  # one letter: a variable
        ["It runs in N", ("3",), " steps"],
        ["the size", ("3",), " + 1"],  # not capitalised
        ["The effect was small.", ("1",)],  # after a sentence
        [("5",), " is first"],  # no capital after
        [("5",), "  Two spaces"],  # more than one space before the capital
        ["MeV", ("2",), "x"],  # a letter right after
        ["Roe-", ("1",), " Lee"],  # after a hyphen
        ["Quantitative ", ("1",), "H NMR"],  # mass numbers: not after a comma
        ["NMR of ", ("13",), "C-labelled sugars"],
        ["Spin ", ("3",), "He films"],
        [("18",), "F-FDG PET"],  # at the start, but a one-letter word follows
        [("1",), "H-NMR-Spektroskopie"],
        ["Labs, ", ("238",), "U miners"],
        [("87",), "Rb condensates"],  # a two-letter element symbol
        ["Labs, ", ("3",), "He films"],
        ["Atoms of\n", ("6",), "Li"],
    ],
)
def test_maths_and_sentence_marks_are_read(runs: list) -> None:
    """Even after the author line."""
    assert removed(tagged(AUTHORS, sup(*runs))) == ["1"]


def test_a_mark_at_a_line_start_comes_before_an_affiliation() -> None:
    """A PDF paragraph joins its lines with a space, so the line's own start counts."""
    first = TextLine(
        "l0",
        (
            TextRun("Ann Lee", size=10.0, box=Box(0, 100, 35, 110)),  # the author line (#448)
            TextRun("1", size=7.0, box=Box(35, 97, 40, 104)),
            TextRun(", Somewhere, Los Angeles", size=10.0, box=Box(40, 100, 160, 110)),
        ),
    )
    second = TextLine(
        "l1",
        (
            TextRun("2", size=7.0, box=Box(0, 117, 5, 124)),
            TextRun("Example Institute", size=10.0, box=Box(5, 120, 90, 130)),
        ),
    )
    text = f"{first.text} {second.text}"
    block = Block(BlockKind.PARAGRAPH, text, (Part("l0"), Part("l1", len(first.text) + 1)))
    content = Content(Source("title.pdf", SourceFormat.PDF), (Page(1, (first, second)),))
    document = Document(content=content, language="en", blocks=(block,))
    assert removed(document) == ["1", "2"]
    # the same mark inside one line, after a word that is no name's end, is read
    one = TextLine("l0", (*first.runs, TextRun(" "), *second.runs))
    block = Block(BlockKind.PARAGRAPH, one.text, (Part("l0"),))
    content = Content(Source("title.pdf", SourceFormat.PDF), (Page(1, (one,)),))
    assert removed(Document(content=content, language="en", blocks=(block,))) == ["1"]


@pytest.mark.parametrize(
    ("text", "start", "end", "after"),
    [
        ("Jane Roe,1 Ann", 9, 10, True),  # REVTeX: the comma set before the mark (#585)
        ("Mapping 12CO,13CO and", 13, 15, False),  # a mass number glued after a comma
        ("Mapping 12CO, 13CO", 14, 16, False),
    ],
)
def test_a_comma_glued_before_the_mark_belongs_to_the_name(
    text: str, start: int, end: int, after: bool
) -> None:
    assert _after_name(text, start, end) is after


# ---- footnote marks ---------------------------------------------------------------------


def test_a_footnote_mark_beside_affiliation_marks_stays_with_the_footnotes_step() -> None:
    document = tagged(
        sup("Xavier D. Arden", ("1,2,",), (STAR,)),
        sup(("1",), "Example University"),
        Block(BlockKind.FOOTNOTE, f"{STAR}Corresponding author.", label=STAR),
    )
    run = run_steps(document, EN, strict=True)
    marks = sorted((e.span.start, e.span.end, e.step) for e in run.accepted if e.span.block == 0)
    assert marks == [(15, 19, "affiliation-marks"), (19, 20, "footnotes")]
    assert render(run) == [
        "Xavier D. Arden",
        "Footnote. Corresponding author.",
        "Example University",
    ]


def test_a_mark_that_marks_a_note_is_left_to_the_footnotes_step() -> None:
    document = tagged(
        sup("Jane Roe", ("1",)), Block(BlockKind.FOOTNOTE, "1 Work done at home.", label="1")
    )
    assert removed(document) == []
    assert render(run_steps(document, EN, strict=True)) == [
        "Jane Roe",
        "Footnote 1. Work done at home.",
    ]


def test_with_footnotes_switched_off_the_marks_are_read() -> None:
    document = tagged(sup("Jane Roe", ("1,2",), " and Ann Lee", ("2",)))
    assert read(document, switched_off=(Category.FOOTNOTES,)) == ["Jane Roe1,2 and Ann Lee2"]


# ---- the title block ---------------------------------------------------------------------


def test_the_title_block_ends_at_the_first_heading() -> None:
    document = tagged(
        sup("Jane Roe", ("1",)),
        (BlockKind.HEADING, "Abstract"),
        sup("As Smith", ("2",), " showed."),
    )
    assert removed(document) == ["1"]


def test_the_title_block_is_the_first_page_only() -> None:
    document = tagged(sup("Jane Roe", ("1",)), sup("Ann Lee", ("2",)), pages={1: 2})
    assert removed(document) == ["1"]


def test_the_first_page_is_the_page_of_the_first_block_with_parts() -> None:
    # an empty block has no parts; the title block starts on page 2 with the first text
    document = tagged(
        (BlockKind.PARAGRAPH, ""), sup("Jane Roe", ("1",)), sup("Ann Lee", ("2",)),
        pages={1: 2, 2: 2},
    )  # fmt: skip
    assert removed(document) == ["1", "2"]
    assert removed(pdf((name("Jane Roe"), mark("1")), page=3)) == ["1"]


@pytest.mark.parametrize("kind", [BlockKind.LIST_ITEM, BlockKind.CAPTION, BlockKind.FOOTNOTE])
def test_only_paragraphs_of_the_title_block_count(kind: BlockKind) -> None:
    document = tagged(sup("Jane Roe", ("1",), kind=kind), sup("Ann Lee", ("2",)))
    assert removed(document) == ["2"]


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_the_step_reads_every_language(language: str) -> None:
    document = tagged(sup("Anna Muster", ("1",)), language=language)
    assert removed(document, StepContext(language)) == ["1"]


def test_the_step_runs_right_after_the_footnotes_step() -> None:
    ids = [step.id for step in BUILT_IN_STEPS]
    assert ids[ids.index("footnotes") + 1] == "affiliation-marks"


def test_the_step_keeps_the_text_step_contract() -> None:
    check_text_step(AffiliationMarkStep(), allow_ask=False)


# ---- properties --------------------------------------------------------------------------

_NAMES = st.lists(
    st.tuples(
        st.sampled_from(["Jane Roe", "Wasi Uddin Ahmed", "Zoë Lee", "Kai-Wei Chang", "Bo Ng"]),
        st.sampled_from(["1", "2,3", STAR, f"1,{STAR}", "†", "12"]),
        st.sampled_from([" ", ", ", " and ", "\n"]),
    ),
    min_size=1,
    max_size=6,
)


@given(_NAMES)
def test_names_lose_their_marks_and_keep_their_text(names: list[tuple[str, str, str]]) -> None:
    runs: list = []
    for author, number, joint in names:
        runs += [author, (number,), joint]
    document = tagged(sup(*runs))
    spoken = spoken_text(apply_edits(document, AffiliationMarkStep().find(document, EN)))
    shown = "".join(author + joint for author, _, joint in names)
    assert spoken.split() == shown.split()


@given(_NAMES, st.sampled_from([BlockKind.HEADING, "page"]))
def test_marks_outside_the_title_block_are_never_touched(
    names: list[tuple[str, str, str]], limit: BlockKind | str
) -> None:
    runs: list = []
    for author, number, joint in names:
        runs += [author, (number,), joint]
    if limit == "page":
        document = tagged((BlockKind.PARAGRAPH, "Title"), sup(*runs), pages={1: 2})
    else:
        document = tagged((BlockKind.HEADING, "Abstract"), sup(*runs))
    assert AffiliationMarkStep().find(document, EN) == []


def test_later_steps_read_the_text_without_hidden_runs_and_affiliation_marks() -> None:
    from sci2audio.textprep.footnotes import unread_marks

    document = make_document(
        [(BlockKind.PARAGRAPH, "Jane Roe1 and x"), (BlockKind.PARAGRAPH, "at 37 °C13 here")],
        tags={0: [(8, 9, "sup")], 1: [(8, 10, ("span", "epub:pagebreak"))]},
    )
    assert unread_marks(document, EN) == {0: [(8, 9)], 1: [(8, 10)]}
    off = StepContext("en", switched_off=frozenset({Category.PAGE_FURNITURE}))
    assert unread_marks(document, off) == {0: [(8, 9)]}
    off = StepContext("en", switched_off=frozenset({Category.FOOTNOTES}))
    assert unread_marks(document, off) == {1: [(8, 10)]}
