"""Layout on made-up pages: a typewriter word inside a prose paragraph is inline code (#879).

A PDF has no markup, so layout tags a run set in a typewriter font `code` where it stands
in read text set in a proportional font: the text steps then read it as printed (#854),
as they do Markdown's backticks. One column as in `test_layout_code`.
"""

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_layout import RIGHT, content
from test_layout_code import MONO, PITCH, build, code, listing, prose, running, text_line

from sci2audio.core import BlockKind, Content, Document, TextRun
from sci2audio.layout import build_document
from sci2audio.textprep import BUILT_IN_STEPS, StepContext, run_steps, spoken_text

CODE = "code"


def tagged(doc: Document) -> list[str]:
    """The text of every run tagged `code`, in the order the pages store them."""
    return [
        run.text
        for page in doc.content.pages
        for line in page.lines
        for run in line.runs
        if CODE in run.tags
    ]


def runs(*pieces: tuple[str, str]) -> tuple[TextRun, ...]:
    return tuple(TextRun(text, font, 10.0) for text, font in pieces)


def test_a_courier_run_mid_sentence_is_tagged_code_and_the_prose_is_not() -> None:
    line = runs(("Write the rule", "Times"), (" x => x + 1", "Courier"), (" as shown.", "Times"))
    doc = build(text_line(line, 300, end=RIGHT))
    assert tagged(doc) == [" x => x + 1"]
    (block,) = [b for b in doc.blocks if "x =>" in b.text]
    assert block.kind is BlockKind.PARAGRAPH
    assert block.text == "Write the rule x => x + 1 as shown."


def read(doc: Document) -> str:
    run = run_steps(doc, StepContext("en"), BUILT_IN_STEPS, strict=True)
    assert not run.problems
    return spoken_text(run.script())


@pytest.mark.parametrize(
    ("printed", "said"), [(" x => x + 1", "x => x + 1"), (" a <=> b", "a <=> b")]
)
def test_the_text_steps_read_a_courier_run_as_printed_and_the_prose_around_it(
    printed: str, said: str
) -> None:
    """End to end (#879 with #854): the arrow in the Courier run stays as printed, the same
    arrow in the Times prose after it is read as words."""
    line = runs(
        ("Write the rule", "Times"), (printed, "Courier"), (" and A => B as shown.", "Times")
    )
    spoken = read(build(text_line(line, 300, end=RIGHT)))
    assert f"Write the rule {said} and A implies B as shown." in spoken


def test_in_a_typed_document_the_courier_run_is_read_by_the_steps() -> None:
    typed = [
        text_line((TextRun(f"Typed text, line {k}.", "Courier", 10.0),), 100 + PITCH * k, end=RIGHT)
        for k in range(10)
    ]
    mixed = text_line(runs(("Signed", "Times"), (" x => y", "Courier"), (" today.", "Times")), 300)
    spoken = read(build_document(content([*typed, mixed])))
    assert "Signed x implies y today." in spoken


def test_the_tag_is_added_to_the_run_s_own_tags() -> None:
    line = (
        TextRun("Call ", "Times", 10.0),
        TextRun("f(x)", MONO, 10.0, tags=("link:#f",)),
        TextRun(" here.", "Times", 10.0),
    )
    doc = build(text_line(line, 300))
    (run,) = [
        run
        for page in doc.content.pages
        for ln in page.lines
        for run in ln.runs
        if CODE in run.tags
    ]
    assert run.tags == ("link:#f", CODE)


def test_monospace_words_in_a_caption_and_a_list_item_are_tagged() -> None:
    cap = text_line(
        runs(("Figure 1: An example", "Times"), (" seaborn", MONO), (" plot.", "Times")), 300
    )
    item = text_line(
        runs(("• Use", "Times"), (" pandas", MONO), (" frames.", "Times")), 300 + 3 * PITCH
    )
    doc = build(cap, item)
    assert tagged(doc) == [" seaborn", " pandas"]


def test_nothing_is_tagged_in_a_typed_document() -> None:
    """#794's judgement: where most letters are typewriter type, a typewriter word is no
    code, so a proportional line among the typed ones changes nothing."""
    typed = [
        text_line((TextRun(f"Typed text, line {k}.", "Courier", 10.0),), 100 + PITCH * k, end=RIGHT)
        for k in range(10)
    ]
    mixed = text_line(runs(("Signed", "Times"), (" x => y", "Courier"), (" today.", "Times")), 300)
    doc = build_document(content([*typed, mixed]))
    assert tagged(doc) == []


def test_a_listing_is_a_code_block_and_its_runs_are_not_tagged() -> None:
    doc = build(*listing(("x = 1", 0), ("print(x)", 0), top=300))
    assert BlockKind.CODE in {block.kind for block in doc.blocks}
    assert tagged(doc) == []


def test_a_block_wholly_in_a_typewriter_font_is_not_tagged() -> None:
    """A paragraph that is only a monospace link stays a paragraph (`find_code`) and holds
    no proportional prose, so nothing in it is inline code."""
    doc = build(text_line(code("https://github.com/mwaskom/seaborn"), 300))
    assert tagged(doc) == []


def test_running_text_and_furniture_are_not_tagged() -> None:
    doc = build(text_line(prose("Only prose here."), 300))
    assert tagged(doc) == []


@pytest.mark.parametrize(
    "pieces",
    [
        # LaTeX's \url in typewriter type, inside a sentence
        [("Code is at", "Times"), (" https://github.com/JFChi/PLUE", MONO), (".", "Times")],
        [("Mail", "Times"), (" dha.msc@cbs.dk", MONO), (" for data.", "Times")],
        # nowak: the braces are proportional, the names and the host typewriter
        [
            ("{", "Times"),
            ("franz.nowak, ryan.cotterell", MONO),
            ("}", "Times"),
            ("@inf.ethz.ch", MONO),
        ],
        [("See", "Times"), (" doi:10.1000/182", MONO), (" for it.", "Times")],
    ],
)
def test_a_link_in_a_typewriter_font_is_not_tagged(pieces: list[tuple[str, str]]) -> None:
    """The links step reads or leaves out a link with its reason (TP-06); code would hide
    it from that step."""
    doc = build(text_line(runs(*pieces), 300, end=RIGHT))
    assert tagged(doc) == []


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ((" https://github.", MONO), ("com/citp/privacy-policy-historical", MONO)),
        ((" https:", MONO), ("//doi.org/10.1007/s10773-024-05576-0", MONO)),
        ((" https://doi.org/10.48550/", MONO), ("arXiv.2308.16068", MONO)),
    ],
)
def test_a_typewriter_link_broken_over_two_lines_is_not_tagged(
    first: tuple[str, str], second: tuple[str, str]
) -> None:
    """arsiwalla's and chi's DOIs and URLs: the line breaks inside the link, and neither
    half is a link on its own."""
    one = text_line(runs(("Available online:", "Times"), first), 300, end=RIGHT)
    two = text_line(runs(second, (" (accessed 2024).", "Times")), 300 + PITCH)
    doc = build(one, two)
    assert tagged(doc) == []


def test_names_set_in_a_typewriter_font_are_tagged_one_by_one() -> None:
    """chi: label names between proportional commas are code, the commas are not."""
    line = runs(
        ("It contains", "Times"),
        (" COLLECT", MONO),
        (",", "Times"),
        (" NOT_COLLECT", MONO),
        (" and", "Times"),
        (" NOT_SHARE", MONO),
        (".", "Times"),
    )
    doc = build(text_line(line, 300, end=RIGHT))
    assert tagged(doc) == [" COLLECT", " NOT_COLLECT", " NOT_SHARE"]


def test_a_name_broken_over_two_lines_is_tagged_on_both() -> None:
    """seaborn: "matplot" at one line's end, "lib" at the next one's start."""
    one = text_line(runs(("the analogous", "Times"), (" matplot", MONO)), 300, end=RIGHT)
    two = text_line(runs(("lib", MONO), (" function would", "Times")), 300 + PITCH)
    doc = build(one, two)
    assert tagged(doc) == [" matplot", "lib"]


def untagged(found: Content) -> Content:
    """The content with every `code` tag taken off again."""
    return replace(
        found,
        pages=tuple(
            replace(
                page,
                lines=tuple(
                    replace(
                        ln,
                        runs=tuple(
                            replace(run, tags=tuple(t for t in run.tags if t != CODE))
                            for run in ln.runs
                        ),
                    )
                    for ln in page.lines
                ),
            )
            for page in found.pages
        ),
    )


def test_tagging_changes_nothing_but_the_tags() -> None:
    line = runs(("Write the rule", "Times"), (" x => x + 1", "Courier"), (" as shown.", "Times"))
    given_content = content([*running(), text_line(line, 300, end=RIGHT)])
    doc = build_document(given_content)
    assert tagged(doc) == [" x => x + 1"]
    assert untagged(doc.content) == given_content


_WORDS = st.text(alphabet="abc xyz=>+1.@/:", min_size=1, max_size=12)


@given(st.lists(st.tuples(_WORDS, st.booleans()), min_size=1, max_size=6))
def test_only_typewriter_runs_are_tagged_and_building_twice_tags_the_same(
    pieces: list[tuple[str, bool]],
) -> None:
    line = tuple(TextRun(text, MONO if mono else "Times", 10.0) for text, mono in pieces)
    first = build(text_line(line, 300, end=RIGHT))
    for page in first.content.pages:
        for ln in page.lines:
            for run in ln.runs:
                if CODE in run.tags:
                    assert run.font == MONO
                    assert run.text.strip()
    again = build_document(first.content)
    assert again.content == first.content
    assert again.blocks == first.blocks
