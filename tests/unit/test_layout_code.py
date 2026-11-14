"""Layout on made-up pages: code listings are CODE placeholder blocks (#280, D-542, D-543).

One column between x 70 and x 526 as in `test_layout`, body text in 10 point Times on a
14 point pitch. A code line is set wholly in a typewriter font.
"""

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_layout import LEFT, RIGHT, content

from sci2audio.core import BlockKind, Box, Document, TextLine, TextRun
from sci2audio.layout import build_document
from sci2audio.layout.code import monospace

PITCH = 14.0
HALF = (LEFT + RIGHT) / 2
MONO = "LMMono10-Regular"
_ids = itertools.count()


def text_line(runs: tuple[TextRun, ...], y: float, x0: float = LEFT, end: float = HALF):
    return TextLine(f"t{next(_ids)}", runs, Box(x0, y, end, y + 10))


def prose(text: str) -> tuple[TextRun, ...]:
    return (TextRun(text, "Times", 10.0),)


def code(text: str, size: float = 10.0) -> tuple[TextRun, ...]:
    return (TextRun(text, MONO, size),)


def running(top: float = 100) -> list[TextLine]:
    """A paragraph of running text, which sets the line pitch, ending at `top` + 10 rows."""
    return [
        text_line(prose(f"Running text, line {k}."), top + PITCH * k, end=RIGHT if k < 9 else HALF)
        for k in range(10)
    ]


def listing(*rows: tuple[str, float], top: float) -> list[TextLine]:
    """Code lines on the line pitch, each `(text, indent)`, short as code lines are."""
    return [
        text_line(code(text), top + PITCH * k, x0=LEFT + indent, end=LEFT + indent + 6 * len(text))
        for k, (text, indent) in enumerate(rows)
    ]


def build(*lines: TextLine) -> Document:
    return build_document(content([*running(), *lines]))


def kinds(doc: Document) -> list[tuple[str, str]]:
    return [(block.kind.value, block.text) for block in doc.blocks]


SEABORN = (
    ("import seaborn as sns", 0),
    ('sns.set_theme(context="paper")', 0),
    ("g = sns.relplot(", 0),
    ('data=fmri, kind="line",', 21),
    (")", 0),
    ('g.savefig("paper_demo.pdf")', 0),
)


def test_a_run_of_monospace_lines_is_one_code_block_holding_all_its_lines() -> None:
    lines = listing(*SEABORN, top=280)
    after = text_line(prose("Users interface with seaborn through functions."), 400)
    doc = build(*lines, after)
    assert kinds(doc)[1:] == [
        ("code", "\n".join(text for text, _ in SEABORN)),
        ("paragraph", "Users interface with seaborn through functions."),
    ]
    block = doc.blocks[1]
    assert [part.item for part in block.parts] == [line.id for line in lines]
    assert block.is_placeholder
    assert block.label == ""


def test_a_single_monospace_line_on_its_own_is_code() -> None:
    doc = build(*listing(("pip install seaborn", 0), top=300))
    assert kinds(doc)[1:] == [("code", "pip install seaborn")]


def test_two_listings_with_prose_between_them_are_two_code_blocks() -> None:
    doc = build(
        *listing(("x = 1", 0), ("y = 2", 0), top=280),
        text_line(prose("Then the second example follows."), 330),
        *listing(("print(x + y)", 0), top=360),
    )
    assert [kind for kind, _ in kinds(doc)[1:]] == ["code", "paragraph", "code"]


@pytest.mark.parametrize(
    "rows",
    [
        (("https://github.com/rycolab/", 0), ("prefix-parsing", 0)),  # nowak's author block
        (("name@example.org", 0),),
        (("doi:10.21105/joss.03021", 0),),
        (("https://doi.org/10.21105/joss.03021", 0),),
        (("www.example.org/data", 0),),
    ],
    ids=["url-over-two-lines", "e-mail", "doi", "doi-url", "www"],
)
def test_a_monospace_link_on_lines_of_its_own_is_read(rows: tuple) -> None:
    doc = build(*listing(*rows, top=300))
    assert BlockKind.CODE not in {block.kind for block in doc.blocks}


def test_a_paragraph_with_a_monospace_word_is_read() -> None:
    mixed = (TextRun("Call ", "Times", 10.0), TextRun("relplot()", MONO, 10.0))
    doc = build(text_line((*mixed, TextRun(" to draw.", "Times", 10.0)), 300))
    assert kinds(doc)[1:] == [("paragraph", "Call relplot() to draw.")]


def test_a_monospace_line_larger_than_the_body_text_is_not_code() -> None:
    doc = build(text_line(code("seaborn", size=14.0), 300))
    assert BlockKind.CODE not in {block.kind for block in doc.blocks}


def test_white_space_runs_in_another_font_do_not_stop_a_code_line() -> None:
    runs = (TextRun("x", MONO, 10.0), TextRun(" ", "Times", 10.0), TextRun("= 1", MONO, 10.0))
    doc = build(text_line(runs, 300))
    assert kinds(doc)[1:] == [("code", "x = 1")]


@pytest.mark.parametrize(
    "font",
    [
        "LMMono10-Regular",
        "LMMono9-Regular",
        "Inconsolatazi4-Regular",
        "NimbusMonL-Regu",
        "NimbusMonoPS-Regular",
        "SFTT1000",
        "CMTT10",
        "txtt",
        "Courier",
        "CourierNewPSMT",
        "Consolas",
        "Menlo-Regular",
        "Monaco",
        "DejaVuSansMono",
        "SourceCodePro-Regular",
        "FiraCode-Regular",
        "LucidaSansTypewriter",
    ],
)
def test_typewriter_fonts_are_monospace(font: str) -> None:
    assert monospace(font)


@pytest.mark.parametrize(
    "font",
    ["Times", "LMSans10-Regular", "SFTI1095", "CMR10", "MonotypeCorsiva", "NimbusRomNo9L", ""],
)
def test_other_fonts_are_not_monospace(font: str) -> None:
    assert not monospace(font)


@given(st.lists(st.text(st.characters(exclude_categories=("Cs", "Cc")), min_size=1), max_size=6))
def test_every_line_of_a_code_block_is_set_in_a_typewriter_font(rows: list[str]) -> None:
    """Property: whatever mono and prose lines stand after the running text, every item of
    a CODE block is a line whose visible runs are all monospace, and every item is in
    exactly one block."""
    lines = [
        text_line(code(text) if k % 3 else prose(text), 280 + PITCH * k, end=HALF)
        for k, text in enumerate(rows)
    ]
    found = content([*running(), *lines])
    doc = build_document(found)
    items = {item.id: item for _, item in found.items().values()}
    for block in doc.blocks:
        if block.kind is BlockKind.CODE:
            for part in block.parts:
                runs = [r for r in items[part.item].runs if r.text.strip()]
                assert runs
                assert all(monospace(r.font) for r in runs)
    held = [part.item for block in doc.blocks for part in block.parts]
    assert sorted(held) == sorted(items)
