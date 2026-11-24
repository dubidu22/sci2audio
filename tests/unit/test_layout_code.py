"""Layout on made-up pages: code listings are CODE placeholder blocks (#280, D-542, D-543).

One column between x 70 and x 526 as in `test_layout`, body text in 10 point Times on a
14 point pitch. A code line is set wholly in a typewriter font.
"""

import itertools

import pytest
from hypothesis import given
from hypothesis import strategies as st
from test_layout import LEFT, RIGHT, content

from sci2audio.core import (
    Block,
    BlockKind,
    Box,
    Document,
    FurnitureRole,
    Part,
    TextLine,
    TextRun,
)
from sci2audio.layout import build_document
from sci2audio.layout.code import find_code, monospace

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
        (("alice@uni-x.de", 0), ("bob@uni-y.org", 0)),  # one address per author
        (("{alice,bob}@cs.uni-x.edu", 0),),  # ACL's brace form
        (("{alice, bob}@cs.uni-x.edu", 0),),
    ],
    ids=[
        "url-over-two-lines",
        "e-mail",
        "doi",
        "doi-url",
        "www",
        "two-e-mails",
        "braces",
        "braces-spaced",
    ],
)
def test_a_monospace_link_on_lines_of_its_own_is_read(rows: tuple) -> None:
    doc = build(*listing(*rows, top=300))
    assert BlockKind.CODE not in {block.kind for block in doc.blocks}


def test_two_monospace_e_mail_paragraphs_are_read() -> None:
    """Two addresses that layout reads as two paragraphs stay two paragraphs."""
    doc = build(
        text_line(code("alice@uni-x.de"), 300), text_line(code("bob@uni-y.org"), 300 + 2 * PITCH)
    )
    assert kinds(doc)[1:] == [("paragraph", "alice@uni-x.de"), ("paragraph", "bob@uni-y.org")]


def test_a_document_set_wholly_in_a_typewriter_font_has_no_code() -> None:
    """A typed memo or an RFC printed in Courier is read as today; code can only
    be told from text that is not itself typewriter type."""
    typed = [
        text_line((TextRun(f"Typed text, line {k}.", "Courier", 10.0),), 100 + PITCH * k, end=RIGHT)
        for k in range(10)
    ]
    listing_too = listing(("x = 1", 0), ("print(x)", 0), top=300)
    doc = build_document(content([*typed, *listing_too]))
    assert BlockKind.CODE not in {block.kind for block in doc.blocks}


@pytest.mark.parametrize("font", ["Times-Bold", "LMMono10-Bold", "CourierNewPS-BoldMT"])
@pytest.mark.parametrize("size", [10.0, 10.5])
def test_a_bold_monospace_heading_stays_a_heading(font: str, size: float) -> None:
    """Numbered bold headings at about body size are headings whatever their
    font, and the sections they open keep their blocks."""
    titles = ["1 Introduction", "2 The relplot() function", "3 Results"]
    lines = []
    for k, title in enumerate(titles):
        y = 280 + 5 * PITCH * k
        lines.append(text_line((TextRun(title, font, size, bold=True),), y))
        lines.append(text_line(prose(f"Text of section {k + 1}."), y + 2 * PITCH))
    doc = build(*lines)
    assert [b.text for b in doc.blocks if b.kind is BlockKind.HEADING] == titles
    assert BlockKind.CODE not in {block.kind for block in doc.blocks}
    assert [s.title for s in doc.sections] == titles


def test_bold_keyword_lines_inside_a_listing_are_part_of_it() -> None:
    """A listing that sets its "end" lines wholly in bold is one CODE block,
    not code plus a paragraph "end end" read aloud."""
    bold_end = (TextRun("end", "LMMono10-Bold", 10.0, bold=True),)
    rows = [code("for k = 1:3"), code("  if k > 1"), code("    disp(k)"), bold_end, bold_end]
    lines = [text_line(row, 280 + PITCH * k, end=LEFT + 80) for k, row in enumerate(rows)]
    doc = build(*lines, text_line(prose("Then the loop ends."), 400))
    assert kinds(doc)[1:] == [
        ("code", "for k = 1:3\n  if k > 1\n    disp(k)\nend\nend"),
        ("paragraph", "Then the loop ends."),
    ]


def test_a_run_of_only_bold_monospace_lines_is_read() -> None:
    """A wholly bold monospace line that is not a heading on its own is not code either."""
    bold = (TextRun("seaborn.objects", "LMMono10-Bold", 10.0, bold=True),)
    doc = build(text_line(bold, 300), text_line(prose("The new interface."), 300 + 2 * PITCH))
    assert BlockKind.CODE not in {block.kind for block in doc.blocks}
    assert "seaborn.objects" in [block.text for block in doc.blocks]


def test_sections_and_captions_point_at_the_right_blocks_after_a_listing() -> None:
    """Code is found after headings and captions: the section after a listing still starts at
    its heading, and a caption after it still names its figure."""
    bold = (TextRun("2 Results", "Times-Bold", 10.0, bold=True),)
    doc = build(
        text_line((TextRun("1 Method", "Times-Bold", 10.0, bold=True),), 250),
        *listing(*SEABORN, top=280),
        text_line(bold, 400),
        text_line(prose("Text of the results."), 400 + 2 * PITCH),
    )
    for section in doc.sections:
        assert doc.blocks[section.start].text == section.title
    (code_block,) = [k for k, b in enumerate(doc.blocks) if b.kind is BlockKind.CODE]
    assert doc.sections[0].start < code_block < doc.sections[0].end


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
        "LucidaConsole",
        "TeXGyreCursor-Regular",
        "CascadiaCode-Regular",
    ],
)
def test_typewriter_fonts_are_monospace(font: str) -> None:
    assert monospace(font)


@pytest.mark.parametrize(
    "font",
    [
        "Times",
        "LMSans10-Regular",
        "SFTI1095",
        "CMR10",
        "MonotypeCorsiva",
        "NimbusRomNo9L",
        "LucidaSansUnicode",  # a bare "code" matched these four
        "ArialUnicodeMS",
        "EncodeSans-Regular",
        "Barcode39",
        "AmericanTypewriter",  # proportional, despite its name
        "",
    ],
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


# A listing's caption names its CODE block (#281)


def caption(text: str, y: float, end: float = LEFT + 200) -> TextLine:
    return text_line(prose(text), y, end=end)


def described(doc: Document) -> list[tuple[str, str]]:
    """Each caption's label and the first line of the block it names ("" for none)."""
    return [
        (block.label, doc.blocks[block.describes].text.split("\n")[0] if block.describes else "")
        for block in doc.blocks
        if block.kind is BlockKind.CAPTION
    ]


@pytest.mark.parametrize("label", ["Listing 3", "LISTING 3", "Quelltext 3"])
def test_a_listing_caption_above_the_code_names_it(label: str) -> None:
    doc = build(
        caption(f"{label}: Drawing a line plot.", 280), *listing(*SEABORN, top=280 + 2 * PITCH)
    )
    assert kinds(doc)[1:] == [
        ("caption", f"{label}: Drawing a line plot."),
        ("code", "\n".join(text for text, _ in SEABORN)),
    ]
    assert doc.blocks[1].label == label
    assert doc.blocks[1].describes == 2


def test_a_listing_caption_below_the_code_names_it() -> None:
    doc = build(*listing(*SEABORN, top=280), caption("Listing 1: A line plot.", 280 + 7 * PITCH))
    assert [kind for kind, _ in kinds(doc)[1:]] == ["code", "caption"]
    assert doc.blocks[2].describes == 1


def test_captions_above_two_listings_name_the_listing_below_each() -> None:
    doc = build(
        caption("Listing 1: Setting up.", 280),
        *listing(("import seaborn as sns", 0), ("sns.set_theme()", 0), top=280 + 1.5 * PITCH),
        caption("Listing 2: Plotting.", 280 + 5 * PITCH),
        *listing(("g = sns.relplot(data=fmri)", 0), top=280 + 6.5 * PITCH),
    )
    assert described(doc) == [
        ("Listing 1", "import seaborn as sns"),
        ("Listing 2", "g = sns.relplot(data=fmri)"),
    ]


def test_captions_below_two_listings_name_the_listing_above_each() -> None:
    doc = build(
        *listing(("import seaborn as sns", 0), ("sns.set_theme()", 0), top=280),
        caption("Listing 1: Setting up.", 280 + 2.5 * PITCH),
        *listing(("g = sns.relplot(data=fmri)", 0), top=280 + 6 * PITCH),
        caption("Listing 2: Plotting.", 280 + 7.5 * PITCH),
    )
    assert described(doc) == [
        ("Listing 1", "import seaborn as sns"),
        ("Listing 2", "g = sns.relplot(data=fmri)"),
    ]


def test_a_listing_caption_names_the_code_on_its_own_page() -> None:
    """Code ends page 2; page 3 opens with a caption and the code it names."""
    pages = [
        [*running(), *listing(("x = 1", 0), top=700)],
        [
            caption("Listing 2: The second step.", 100),
            *listing(("y = x + 1", 0), top=100 + 2 * PITCH),
        ],
    ]
    doc = build_document(content(*pages))
    assert described(doc) == [("Listing 2", "y = x + 1")]


def test_a_full_width_listing_caption_keeps_out_of_the_code() -> None:
    """A caption line that fills its column, on the line pitch above the code, ends where
    the first typewriter line starts: without the cut the first code lines are read as
    part of the caption."""
    lines = listing(*SEABORN, top=280 + PITCH)
    doc = build(caption("Listing 3: Drawing a line plot.", 280, end=RIGHT), *lines)
    assert kinds(doc)[1:] == [
        ("caption", "Listing 3: Drawing a line plot."),
        ("code", "\n".join(text for text, _ in SEABORN)),
    ]
    assert doc.blocks[1].describes == 2
    assert [part.item for part in doc.blocks[2].parts] == [line.id for line in lines]


def test_code_right_under_a_full_paragraph_line_is_one_code_block() -> None:
    """#599: a paragraph whose last line fills its column, then code lines on the line
    pitch right under it: the code is one CODE block, none of it read as prose."""
    top = 280
    para = [
        text_line(prose("The plot is drawn by the following lines of code"), top, end=RIGHT),
    ]
    lines = listing(*SEABORN, top=top + PITCH)
    after = text_line(prose("Users interface with seaborn through functions."), 400)
    doc = build(*para, *lines, after)
    assert kinds(doc)[1:] == [
        ("paragraph", "The plot is drawn by the following lines of code"),
        ("code", "\n".join(text for text, _ in SEABORN)),
        ("paragraph", "Users interface with seaborn through functions."),
    ]
    assert [part.item for part in doc.blocks[2].parts] == [line.id for line in lines]


def test_a_monospace_line_inside_prose_stays_in_the_paragraph() -> None:
    """A wrapped line that is only a code name, with prose going on under it, is part of
    the paragraph: it is no listing (#599)."""
    rows = [
        prose("The training loop calls the loss function, which is named"),
        code("compute_loss_for_every_batch_and_every_epoch_of_the_run()"),
        prose("and returns a number for every batch of the data set."),
    ]
    lines = [
        text_line(row, 280 + PITCH * k, end=RIGHT if k < 2 else HALF) for k, row in enumerate(rows)
    ]
    doc = build(*lines)
    assert kinds(doc)[1:] == [("paragraph", "\n".join(row[0].text for row in rows))]


@pytest.mark.parametrize(
    "rows",
    [
        (("https://github.com/rycolab/", 0), ("prefix-parsing", 0)),
        (("alice@uni-x.de", 0), ("bob@uni-y.org", 0)),
    ],
    ids=["url-over-two-lines", "two-e-mails"],
)
def test_monospace_links_right_under_a_full_paragraph_line_are_read(rows: tuple) -> None:
    """Links set in a typewriter font under a full prose line are no listing (#599)."""
    words = "The code and data are available from the authors at"
    para = text_line(prose(words), 280, end=RIGHT)
    doc = build(para, *listing(*rows, top=280 + PITCH))
    assert kinds(doc)[1:] == [("paragraph", "\n".join([words, *(text for text, _ in rows)]))]


def test_typewriter_lines_under_a_proportional_line_in_a_typed_memo_stay_one_paragraph() -> None:
    """In a document set mostly in a typewriter font nothing is a listing: a line in another
    font with typed lines right under it on the pitch is one paragraph (#599)."""
    first = "To: all staff. Subject: the move to the new building next month."
    typed = [f"Typed text of the memo, line {k}, as it was typed." for k in range(8)]
    lines = [text_line(prose(first), 100, end=RIGHT)] + [
        text_line(
            (TextRun(text, "Courier", 10.0),), 100 + PITCH * (k + 1), end=RIGHT if k < 7 else HALF
        )
        for k, text in enumerate(typed)
    ]
    doc = build_document(content(lines))
    assert kinds(doc) == [("paragraph", "\n".join([first, *typed]))]


def test_a_wrapped_caption_line_that_is_only_a_code_name_stays_in_the_caption() -> None:
    """#603: a caption whose wrapped line holds only a code name, set in a typewriter font
    on the caption's line pitch, with the code after more white: the name is the caption's,
    the code starts at the listing's first line."""
    head = caption("Listing 3: The training loop that calls the loss function", 280, end=RIGHT)
    name = text_line(code("compute_loss()"), 280 + PITCH, end=LEFT + 84)
    lines = listing(("for x in xs:", 0), ("    f(x)", 0), top=280 + 3 * PITCH)
    doc = build(head, name, *lines)
    assert kinds(doc)[1:] == [
        ("caption", "Listing 3: The training loop that calls the loss function\ncompute_loss()"),
        ("code", "for x in xs:\n    f(x)"),
    ]
    assert doc.blocks[1].describes == 2


def test_a_caption_line_in_a_typewriter_font_larger_than_the_body_text_is_not_cut() -> None:
    """A caption's wrapped lines set in a typewriter font larger than the body text (the
    caption itself is set a little larger) are no code, so the caption keeps them: the cut
    judges them as `find_code` does (#603)."""
    words = "Listing 3: The package of this paper, named"
    head = text_line((TextRun(words, "Times", 11.0),), 280, end=RIGHT)
    big = [
        text_line(code(name, size=11.5), 280 + PITCH * k) for k, name in [(1, "big"), (2, "pkg")]
    ]
    doc = build(head, *big)
    assert kinds(doc)[1:] == [("caption", "Listing 3: The package of this paper, named\nbig\npkg")]


def test_a_listing_caption_beside_no_code_names_nothing() -> None:
    doc = build(
        caption("Listing 4: Left out of this version.", 280), text_line(prose("Text."), 310)
    )
    assert kinds(doc)[1:] == [
        ("caption", "Listing 4: Left out of this version."),
        ("paragraph", "Text."),
    ]
    assert doc.blocks[1].describes is None


def test_a_listing_caption_takes_no_lines_into_a_figure() -> None:
    """A figure's caption walks to the lines next to it; a listing's does not, so its code
    is a CODE block, not a FIGURE holding the code."""
    doc = build(
        caption("Listing 1: A loop.", 280), *listing(("for x in xs:", 0), ("    f(x)", 0), top=310)
    )
    assert BlockKind.FIGURE not in {block.kind for block in doc.blocks}
    assert [kind for kind, _ in kinds(doc)[1:]] == ["caption", "code"]


def test_a_figure_caption_beside_code_does_not_name_it() -> None:
    doc = build(caption("Figure 1: Not about the code.", 280), *listing(("x = 1", 0), top=310))
    assert all(
        doc.blocks[block.describes].kind is not BlockKind.CODE
        for block in doc.blocks
        if block.describes is not None
    )


# A listing broken by a page break (#283)


def page_number(number: int) -> TextLine:
    return text_line(prose(str(number)), 760, x0=290, end=300)


def head() -> TextLine:
    return text_line(prose("Journal of Open Things"), 40, end=300)


def four_pages(second: list[TextLine], third: list[TextLine]) -> Document:
    """Four pages under a running head and over a page number; pages 2 and 3 end and start
    with these lines."""
    pages = [[head(), *running(), page_number(1)]]
    pages.append([head(), *running(), *second, page_number(2)])
    pages.append([head(), *third, page_number(3)])
    pages.append([head(), *running(), page_number(4)])
    return build_document(content(*pages))


FIRST = (("import seaborn as sns", 0), ("sns.set_theme()", 0), ("g = sns.relplot(", 0))
SECOND = (('data=fmri, kind="line",', 21), (")", 0), ('g.savefig("demo.pdf")', 0))


def test_a_listing_over_a_page_break_is_one_code_block() -> None:
    second = listing(*FIRST, top=640)
    third = listing(*SECOND, top=100)
    after = text_line(prose("After the code, the text goes on."), 160)
    doc = four_pages(second, [*third, after, *running(200)])
    found = [
        (kind, text) for kind, text in kinds(doc) if kind != "paragraph" or "Running" not in text
    ]
    assert found[3:8] == [
        ("code", "\n".join(text for text, _ in FIRST + SECOND)),
        ("furniture", "2"),
        ("furniture", "Journal of Open Things"),
        ("paragraph", "After the code, the text goes on."),
        ("furniture", "3"),
    ]
    (block,) = [b for b in doc.blocks if b.kind is BlockKind.CODE]
    assert [part.item for part in block.parts] == [line.id for line in second + third]


def test_listings_on_two_pages_with_text_between_are_two_code_blocks() -> None:
    second = listing(*FIRST, top=640)
    before = text_line(prose("Then the plot is saved."), 100)
    doc = four_pages(second, [before, *listing(*SECOND, top=130), *running(200)])
    assert [kind for kind, _ in kinds(doc)].count("code") == 2


def test_furniture_between_two_code_paragraphs_on_one_page_does_not_join_them() -> None:
    """Furniture read between two code paragraphs of one page is no page break. Layout
    reads a page's furniture before or after its body, so the blocks are made by hand."""
    one, two = listing(("x = 1", 0), ("y = 2", 0), top=280)
    stamp = text_line(prose("arXiv:2101.00001v1"), 300, x0=20, end=30)
    found = content([*running(), one, stamp, two])
    blocks = [
        Block(BlockKind.PARAGRAPH, one.text, (Part(one.id),)),
        Block(BlockKind.FURNITURE, stamp.text, (Part(stamp.id),), role=FurnitureRole.SIDE_STAMP),
        Block(BlockKind.PARAGRAPH, two.text, (Part(two.id),)),
    ]
    out, _ = find_code(blocks, (), found, 10.0)
    assert [block.kind for block in out] == [BlockKind.CODE, BlockKind.FURNITURE, BlockKind.CODE]


def test_a_listing_after_a_page_break_that_starts_a_section_is_its_own_block() -> None:
    bold = (TextRun("2 Results", "Times-Bold", 10.0, bold=True),)
    third = [text_line(bold, 100), *listing(*SECOND, top=100 + 2 * PITCH), *running(200)]
    lines = [text_line((TextRun("1 Method", "Times-Bold", 10.0, bold=True),), 600)]
    lines += listing(*FIRST, top=640)
    pages = [[head(), *running(), page_number(1)]]
    pages.append([head(), *running(), *lines, page_number(2)])
    pages.append([head(), *third, page_number(3)])
    more = (TextRun("3 Discussion", "Times-Bold", 10.0, bold=True),)
    pages.append([head(), text_line(more, 100), *running(130), page_number(4)])
    doc = build_document(content(*pages))
    assert [s.title for s in doc.sections] == ["1 Method", "2 Results", "3 Discussion"]
    assert [b.kind for b in doc.blocks].count(BlockKind.CODE) == 2
    assert doc.blocks[doc.sections[1].start].text == "2 Results"


def test_a_link_over_a_page_break_stays_as_printed() -> None:
    """A monospace address broken over a page break is a link, not code: its two
    paragraphs and the furniture between them are read in the order printed."""
    doc = four_pages(
        listing(("https://github.com/rycolab/", 0), top=700),
        [
            *listing(("prefix-parsing", 0), top=100),
            *running(130),
        ],
    )
    found = [(kind, text) for kind, text in kinds(doc) if "Running" not in text]
    assert found[3:7] == [
        ("paragraph", "https://github.com/rycolab/"),
        ("furniture", "2"),
        ("furniture", "Journal of Open Things"),
        ("paragraph", "prefix-parsing"),
    ]


def test_a_code_block_is_named_by_one_listing_caption_at_most() -> None:
    """A caption above and one below a single listing: the nearer names it, the other
    names nothing."""
    doc = build(
        caption("Listing 1: Setting up.", 280),
        *listing(("import seaborn as sns", 0), top=280 + 1.5 * PITCH),
        caption("Listing 2: Not shown here.", 280 + 4 * PITCH),
    )
    assert described(doc) == [("Listing 1", "import seaborn as sns"), ("Listing 2", "")]


def test_a_listing_caption_set_in_a_typewriter_font_is_not_cut() -> None:
    """A caption over two lines set wholly in a typewriter font is one caption: only a
    caption whose own text is in another font ends where the code starts."""
    rows = [code("Listing 1: A caption set in the typewriter font that"), code("runs on.")]
    lines = [
        text_line(row, 280 + PITCH * k, end=RIGHT if k == 0 else HALF) for k, row in enumerate(rows)
    ]
    doc = build(*lines)
    assert [(b.kind.value, b.text) for b in doc.blocks if b.kind is BlockKind.CAPTION] == [
        ("caption", "Listing 1: A caption set in the typewriter font that\nruns on.")
    ]


def test_a_listing_caption_names_the_code_in_its_own_column() -> None:
    """#600: column 1 ends with listing A and its caption, column 2 opens with
    listing B and its caption. Code in the other column is farther, as on another page,
    though its top lies above the caption."""
    left, right, left2, right2 = 70.0, 290.0, 306.0, 526.0

    def at(runs: tuple[TextRun, ...], y: float, x0: float, x1: float) -> TextLine:
        return TextLine(f"t{next(_ids)}", runs, Box(x0, y, x1, y + 10))

    lines = [
        at(
            prose(f"Left column running text line {k} here."),
            100 + PITCH * k,
            left,
            right if k < 19 else 200,
        )
        for k in range(20)
    ]
    lines += [at(code("import a"), 420, left, left + 48), at(code("a.run()"), 434, left, left + 42)]
    lines.append(at(prose("Listing 1: First."), 460, left, left + 120))
    lines += [
        at(code("import b"), 100, left2, left2 + 48),
        at(code("b.run()"), 114, left2, left2 + 42),
    ]
    lines.append(at(prose("Listing 2: Second."), 140, left2, left2 + 120))
    lines += [
        at(
            prose(f"Right column running text line {k} here."),
            170 + PITCH * k,
            left2,
            right2 if k < 19 else 400,
        )
        for k in range(20)
    ]
    doc = build_document(content(lines))
    assert described(doc) == [("Listing 1", "import a"), ("Listing 2", "import b")]


_PIECES = st.lists(
    st.tuples(
        st.sampled_from(["code", "caption", "prose", "code", "caption"]),
        st.sampled_from([2.0, 1.0]),
    ),
    min_size=1,
    max_size=8,
)


@given(st.lists(_PIECES, min_size=2, max_size=4))
def test_listings_captions_and_furniture_over_pages_keep_every_item_once(pages: list) -> None:
    """#600, property: pages under a running head and over a page number, whose
    bodies are prose, code and "Listing N:" caption lines in any order (so a page may end
    and the next begin with code). Every item is in exactly one block, a CODE block holds
    only monospace lines, a CODE block is named by one caption at most, and every
    `describes` is in range and, for a listing caption, names a CODE block."""
    built = []
    for number, pieces in enumerate(pages, start=1):
        lines = [head(), *(running() if number == 1 else [])]
        y = 260.0 if number == 1 else 100.0
        for k, (kind, step) in enumerate(pieces):
            if kind == "code":
                lines.append(text_line(code(f"x{k} = f({k})"), y, end=LEFT + 60))
            elif kind == "caption":
                lines.append(caption(f"Listing {number}{k}: Example {k}.", y))
            else:
                lines.append(text_line(prose(f"Some text {number} {k}."), y))
            y += step * PITCH
        built.append([*lines, page_number(number)])
    found = content(*built)
    doc = build_document(found)
    items = {item.id: item for _, item in found.items().values()}
    held = [part.item for block in doc.blocks for part in block.parts]
    assert sorted(held) == sorted(items)
    named: list[int] = []
    for block in doc.blocks:
        if block.kind is BlockKind.CODE:
            for part in block.parts:
                runs = [r for r in items[part.item].runs if r.text.strip()]
                assert runs
                assert all(monospace(r.font) for r in runs)
        if block.describes is not None:
            assert 0 <= block.describes < len(doc.blocks)
            if block.label.startswith("Listing"):
                assert doc.blocks[block.describes].kind is BlockKind.CODE
                named.append(block.describes)
    assert len(named) == len(set(named))
