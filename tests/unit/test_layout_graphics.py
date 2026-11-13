"""Layout on made-up pages: tables, figures and algorithms as placeholders (Issue #21 step 3,
PR D1, D-88 to D-91; #38, #51).

One column between x 70 and x 526 as in `test_layout`, body text in 10 point. A paragraph of
running text at the top of the page sets the line pitch; the floats stand below it.
"""

import itertools

from hypothesis import given
from hypothesis import strategies as st
from test_layout import LEFT, MIDDLE, RIGHT, line, short, two_columns

from sci2audio.core import (
    Block,
    BlockKind,
    Box,
    Content,
    Document,
    Drawing,
    FurnitureRole,
    Metadata,
    Page,
    Picture,
    Source,
    SourceFormat,
    TextLine,
    TextRun,
)
from sci2audio.layout import build_document

_ids = itertools.count()


def running(top: float = 100, count: int = 10, x0: float = LEFT, x1: float = RIGHT) -> list:
    """A paragraph of running text, its lines 14 points apart."""
    return [line(f"Running text, line {k}.", x0, top + 14 * k, x1) for k in range(count)]


def rule(x0: float, y: float, x1: float) -> Drawing:
    return Drawing(f"d{next(_ids)}", Box(x0, y, x1, y + 0.5))


def bold(text: str, x0: float, y0: float, x1: float) -> TextLine:
    found = line(text, x0, y0, x1)
    return TextLine(found.id, (TextRun(text, "Times-Bold", 10.0, bold=True),), found.box)


def algorithm_caption(label: str, name: str, x0: float, y0: float) -> TextLine:
    """ "Algorithm 1 CKY": the label in bold, the name not (D-87)."""
    found = line(f"{label} {name}", x0, y0, x0 + 120)
    runs = (TextRun(label, "Times-Bold", 10.0, bold=True), TextRun(f" {name}", "Times", 10.0))
    return TextLine(found.id, runs, found.box)


def build(*pages: list) -> Document:
    """Pages of lines, pictures and drawings."""
    return build_document(
        Content(
            Source("test.pdf", SourceFormat.PDF),
            tuple(
                Page(
                    n,
                    tuple(i for i in items if isinstance(i, TextLine)),
                    tuple(i for i in items if isinstance(i, Picture)),
                    tuple(i for i in items if isinstance(i, Drawing)),
                    width=600,
                    height=800,
                )
                for n, items in enumerate(pages, start=1)
            ),
            Metadata(),
        )
    )


def of(doc: Document, kind: BlockKind) -> list[Block]:
    return [block for block in doc.blocks if block.kind is kind]


def named(doc: Document, label: str) -> Block:
    """The block the caption with this label names."""
    caption = next(b for b in of(doc, BlockKind.CAPTION) if b.label == label)
    assert caption.describes is not None
    return doc.blocks[caption.describes]


def table(top: float, rows: list[list[str]], size: float = 10.0) -> list[TextLine]:
    """Cells 120 points apart, rows 14 points apart."""
    return [
        line(cell, LEFT + 120 * c, top + 14 * r, LEFT + 60 + 120 * c, size=size)
        for r, row in enumerate(rows)
        for c, cell in enumerate(row)
    ]


ROWS = [["Model", "F1", "EM"], ["A", "1.0", "2.0"], ["B", "3.0", "4.0"]]
READ = "Model F1 EM\nA 1.0 2.0\nB 3.0 4.0"


# Tables


def test_a_table_between_rules_is_read_row_by_row() -> None:
    """Its cells row by row, joined by a space; its rules among its parts (#38)."""
    rules = [rule(LEFT, 297, RIGHT), rule(LEFT, 312, RIGHT), rule(LEFT, 340, RIGHT)]
    caption = line("Table 1: Scores of the models.", LEFT, 350, 300)
    doc = build([*running(), *table(300, ROWS), caption, *rules])
    found = named(doc, "Table 1")
    assert (found.kind, found.text) == (BlockKind.TABLE, READ)
    assert {r.id for r in rules} <= {part.item for part in found.parts}
    assert [b.kind for b in doc.blocks] == [BlockKind.PARAGRAPH, BlockKind.TABLE, BlockKind.CAPTION]


def test_a_caption_above_its_table_names_the_table_below() -> None:
    caption = line("Table 2. Scores of the models.", LEFT, 290, 300)
    rules = [rule(LEFT, 305, RIGHT), rule(LEFT, 348, RIGHT)]
    after = running(top=380, count=3)
    doc = build([*running(), caption, *table(308, ROWS), *rules, *after])
    assert named(doc, "Table 2").text == READ
    assert [b.text for b in of(doc, BlockKind.PARAGRAPH)][-1] == "\n".join(a.text for a in after)


def test_a_table_without_rules_is_its_rows_of_small_cells() -> None:
    """Cells set smaller than the running text: a cell brings the others on its row."""
    caption = line("Table 3: Scores.", 250, 350, 330)
    doc = build([*running(), *table(300, ROWS, size=8), caption])
    assert named(doc, "Table 3").text == READ


def test_white_between_two_rules_of_a_table_is_inside_it() -> None:
    """chi's Table 4: examples in rows that rules divide, with white inside each row."""
    rules = [rule(LEFT, y, RIGHT) for y in (297, 345, 393)]
    cells = []
    for top in (300, 348):
        cells += [
            line(f"Text {top}.", LEFT, top, RIGHT),
            line(f"Classes {top}.", LEFT, top + 28, 300),
        ]
    caption = line("Table 4: Examples.", LEFT, 400, 300)
    doc = build([*running(), *cells, caption, *rules, *running(top=440, count=3)])
    found = named(doc, "Table 4")
    assert found.text == "\n".join(c.text for c in cells)
    assert {r.id for r in rules} <= {part.item for part in found.parts}


def test_text_after_the_white_below_a_table_is_not_part_of_it() -> None:
    rules = [rule(LEFT, 297, RIGHT), rule(LEFT, 340, RIGHT)]
    caption = line("Table 1: Scores.", LEFT, 350, 300)
    after = running(top=380, count=3)
    doc = build([*running(), *table(300, ROWS), caption, *rules, *after])
    assert named(doc, "Table 1").text == READ
    assert of(doc, BlockKind.PARAGRAPH)[-1].text == "\n".join(a.text for a in after)


# Figures


def test_a_chart_holds_its_axis_text() -> None:
    """The text beside and below the graphics, up to the caption, is the figure's."""
    curve = Drawing("curve", Box(120, 300, 400, 380))
    axis = Drawing("axis", Box(115, 300, 115.5, 385))
    ticks = [line("0", 100, 375, 108), line("10", 96, 300, 108), line("time", 240, 392, 270)]
    caption = line("Figure 1: The signal over time.", LEFT, 412, 300)
    doc = build([*running(), *ticks, caption, curve, axis])
    found = named(doc, "Figure 1")
    assert found.kind is BlockKind.FIGURE
    assert {part.item for part in found.parts} == {"curve", "axis", *(t.id for t in ticks)}
    assert found.text == "10\n0\ntime"


def test_a_short_caption_takes_the_text_its_figure_grows_to() -> None:
    """A caption narrower than its chart: the axis shows how wide the chart is, and the
    tick labels beside the caption are the chart's, though they are read before the axis."""
    frame, axis = (
        Drawing("frame", Box(LEFT, 200, RIGHT, 200.5)),
        Drawing("axis", Box(LEFT, 400, RIGHT, 400.5)),
    )
    ticks = [line(str(k), LEFT + 50 * k, 404, LEFT + 50 * k + 10) for k in range(10)]
    caption = line("Figure 1: Results.", 270, 420, 330)
    doc = build([*running(60, 5), frame, axis, *ticks, caption, *running(440, 3)])
    found = named(doc, "Figure 1")
    assert {t.id for t in ticks} <= {part.item for part in found.parts}
    assert found.text == "0 1 2 3 4 5 6 7 8 9"
    assert all(t.text not in p.text.split() for p in of(doc, BlockKind.PARAGRAPH) for t in ticks)


def test_a_caption_takes_every_marker_of_a_wide_cloud() -> None:
    """A cloud of small markers wider than its caption is one figure, whatever order the
    markers are met in."""
    cloud = [
        Drawing(f"m{c}-{r}", Box(LEFT + 3 * c, 200 + 3 * r, LEFT + 3 * c + 2.5, 202.5 + 3 * r))
        for c in range(100)
        for r in range(20)
    ]
    caption = line("Figure 1: Cloud.", 300, 270, 360)
    doc = build([*running(60, 5), *cloud, caption, *running(300, 3)])
    found = named(doc, "Figure 1")
    assert {m.id for m in cloud} <= {part.item for part in found.parts}


def test_running_text_that_names_a_figure_names_nothing() -> None:
    """ "Figure 1 gives …" is no caption (D-85): the picture above it is a figure no caption
    names, and the text stays a paragraph."""
    picture = Picture("pic", Box(150, 300, 450, 400))
    text = line("Figure 1 gives the accuracy of each model.", LEFT, 410, 400)
    doc = build([*running(), text, picture])
    assert of(doc, BlockKind.CAPTION) == []
    assert [b.text for b in of(doc, BlockKind.FIGURE)] == [""]
    assert of(doc, BlockKind.PARAGRAPH)[-1].text == text.text


def test_figures_side_by_side_are_named_by_their_own_captions() -> None:
    """Each caption reads up its own column (hardt's charts, two to a row)."""
    left = Picture("left", Box(LEFT, 80, 280, 180))
    right = Picture("right", Box(310, 80, 520, 180))
    captions = [line("Figure 1: Left.", LEFT, 190, 200), line("Figure 2: Right.", 310, 190, 440)]
    text = [[*column[:-1], short(column[-1])] for column in two_columns("text", 230, 15)]
    doc = build([*captions, *text[0], *text[1], left, right])
    assert [p.item for p in named(doc, "Figure 1").parts] == ["left"]
    assert [p.item for p in named(doc, "Figure 2").parts] == ["right"]


def test_a_caption_between_two_figures_names_the_nearer_one() -> None:
    upper, lower = (
        Picture("upper", Box(LEFT, 300, 280, 400)),
        Picture("lower", Box(LEFT, 425, 280, 525)),
    )
    captions = [line("Figure 1: Upper.", LEFT, 405, 200), line("Figure 2: Lower.", LEFT, 530, 200)]
    doc = build([*running(), *captions, upper, lower])
    assert [p.item for p in named(doc, "Figure 1").parts] == ["upper"]
    assert [p.item for p in named(doc, "Figure 2").parts] == ["lower"]


# Algorithms


def listing(x0: float, top: float, label: str, name: str, code: list[str]) -> list:
    """An algorithm in a box: a rule, the caption, a rule, numbered lines (the number a line
    of its own, as pdfium gives it), a rule."""
    items: list = [rule(x0, top, x0 + 210), algorithm_caption(label, name, x0, top + 3)]
    items.append(rule(x0, top + 15, x0 + 210))
    for k, text in enumerate(code):
        y = top + 18 + 13 * k
        items += [line(f"{k + 1}:", x0 + 2, y, x0 + 10, size=8), line(text, x0 + 14, y, x0 + 150)]
    items.append(rule(x0, top + 20 + 13 * len(code), x0 + 210))
    return items


CODE = ["def CKY(w):", "β ← 0 ▷ Initialize", "return β"]


def test_an_algorithm_is_read_line_by_line_with_its_numbers() -> None:
    """Each numbered line with its number first; its box's rules are its parts (#38)."""
    items = listing(LEFT, 300, "Algorithm 1", "CKY", CODE)
    doc = build([*running(), *items, *running(top=400, count=3)])
    found = named(doc, "Algorithm 1")
    assert (found.kind, found.text) == (
        BlockKind.FIGURE,
        "1: def CKY(w):\n2: β ← 0 ▷ Initialize\n3: return β",
    )
    rules = [i.id for i in items if isinstance(i, Drawing)]
    assert set(rules) <= {part.item for part in found.parts}
    kinds = [b.kind for b in doc.blocks]
    assert kinds == [BlockKind.PARAGRAPH, BlockKind.CAPTION, BlockKind.FIGURE, BlockKind.PARAGRAPH]


def test_two_algorithms_in_one_figure_are_one_block_all_three_captions_name() -> None:
    """nowak's Figure 1 (D-89): the left listing, then the right one."""
    left = listing(LEFT, 80, "Algorithm 1", "CKY", CODE)
    right = listing(MIDDLE + 8, 80, "Algorithm 2", "JL", ["def JL(w):", "return π"])
    caption = line("Figure 1: Pseudocode for CKY (left) and JL (right).", 140, 145, 460)
    columns = two_columns("text", 180, 15)
    doc = build([*left, *right, caption, *columns[0], *columns[1]])
    found = named(doc, "Figure 1")
    assert named(doc, "Algorithm 1") is found
    assert named(doc, "Algorithm 2") is found
    assert found.text == (
        "1: def CKY(w):\n2: β ← 0 ▷ Initialize\n3: return β\n1: def JL(w):\n2: return π"
    )
    assert len(of(doc, BlockKind.FIGURE)) == 1


# Graphics no caption names


def test_a_logo_on_every_page_is_a_running_head() -> None:
    """D-91: the JOSS logo."""
    pages = [[Picture(f"logo{n}", Box(18, 12, 174, 72)), *running()] for n in range(3)]
    doc = build(*pages)
    logos = [b for b in doc.blocks if b.parts[0].item.startswith("logo")]
    assert [(b.kind, b.role, b.text) for b in logos] == [
        (BlockKind.FURNITURE, FurnitureRole.RUNNING_HEAD, "")
    ] * 3


def test_a_mark_before_a_running_head_joins_it_and_is_no_figure() -> None:
    """A mark read before anything else, with a running-head logo after it, joins the
    logo's block: it moves past no block and is announced as no figure."""
    mark = Picture("mark", Box(20, 20, 24, 24))
    logos = [Picture(f"logo{n}", Box(500, 30, 540, 70)) for n in range(4)]
    doc = build(
        *([mark, logos[0], *running()] if n == 0 else [logos[n], *running()] for n in range(4))
    )
    assert of(doc, BlockKind.FIGURE) == []
    head = doc.blocks[0]
    assert head.kind is BlockKind.FURNITURE
    assert [part.item for part in head.parts] == ["mark", "logo0"]


def test_a_rule_between_paragraphs_joins_the_paragraph_before_it() -> None:
    """D-90: its text stays as it was; the rule is its last part."""
    first, second = running(), running(top=270, count=4)
    line_ = rule(LEFT, 250, RIGHT)
    doc = build([*first, *second, line_])
    assert [b.text for b in doc.blocks] == [
        "\n".join(li.text for li in first),
        "\n".join(li.text for li in second),
    ]
    assert doc.blocks[0].parts[-1].item == line_.id


def test_a_footnote_rule_is_part_of_the_footnote() -> None:
    """#51: the rule over the notes is no figure, but the first part of the note below it."""
    notes_rule = Drawing("rule", Box(LEFT, 700, LEFT + 60, 700.5))
    note = line("1 A note in small letters.", LEFT, 705, LEFT + 120, size=8)
    doc = build([*running(top=400, count=20), note, notes_rule])
    footnote = of(doc, BlockKind.FOOTNOTE)[0]
    assert [p.item for p in footnote.parts] == ["rule", note.id]
    assert footnote.text == note.text
    assert of(doc, BlockKind.FIGURE) == []


def test_an_icon_joins_the_block_before_it() -> None:
    """An ORCID icon by an author's name is no figure. Set below the last line, outside its
    box, it stands in no line and joins the block read before it (D-90; inside a line, #58)."""
    icon = Picture("icon", Box(200, 238, 208, 246))
    doc = build([*running(), icon])
    assert of(doc, BlockKind.FIGURE) == []
    assert doc.blocks[0].parts[-1].item == "icon"


def parts_of(doc: Document, item: str) -> list[tuple[str, int]]:
    """The parts, (item, start), of the block that holds the item."""
    block = next(b for b in doc.blocks if any(p.item == item for p in b.parts))
    return [(p.item, p.start) for p in block.parts]


def test_an_icon_drawn_in_a_line_stands_just_after_that_line() -> None:
    """#58 (D-329, D-331, D-332), as biggs's ORCID icons: the icon is drawn in two pieces
    inside the box of the paragraph's second line; it is read just after that line, where
    its text ends, not after the paragraph's last line."""
    lines = running(count=4)
    box = lines[1].box
    assert box is not None
    ring = Drawing("ring", Box(300, box.y0 + 1, 308, box.y0 + 9))
    dot = Picture("dot", Box(302, box.y0 + 3, 306, box.y0 + 7))
    doc = build([*lines, ring, dot])
    text = "\n".join(li.text for li in lines)
    assert [b.text for b in doc.blocks] == [text]
    end = text.index(lines[1].text) + len(lines[1].text)
    assert parts_of(doc, "ring")[1:4] == [
        (lines[1].id, end - len(lines[1].text)),
        ("dot", end),
        ("ring", end),
    ] or parts_of(doc, "ring")[1:4] == [
        (lines[1].id, end - len(lines[1].text)),
        ("ring", end),
        ("dot", end),
    ]


def test_a_mark_only_partly_inside_a_line_joins_the_block_before_it() -> None:
    """D-329, D-330: wholly inside, without slack; a fraction bar 0.4 pt below a line's box
    touches it but stands in no line, so D-90 holds: the end of the block read before it."""
    lines = running(count=4)
    box = lines[1].box
    assert box is not None
    bar = Drawing("bar", Box(300, box.y1 - 0.4, 310, box.y1 + 0.4))
    doc = build([*lines, bar])
    assert parts_of(doc, "bar")[-1] == ("bar", len(doc.blocks[0].text))


def test_a_group_only_partly_inside_a_line_keeps_the_old_rule() -> None:
    """D-331: the group drawn close together counts as one; here its second piece reaches
    out of the line's box, so the whole group joins the block read before it."""
    lines = running(count=4)
    box = lines[1].box
    assert box is not None
    inside = Drawing("inside", Box(300, box.y0 + 1, 304, box.y0 + 5))
    out = Drawing("out", Box(305, box.y0 + 3, 309, box.y1 + 3))  # 1 pt away: one group
    doc = build([*lines, inside, out])
    end = len(doc.blocks[0].text)
    assert parts_of(doc, "inside")[-2:] in (
        [("inside", end), ("out", end)],
        [("out", end), ("inside", end)],
    )


def test_a_mark_in_two_lines_stands_in_the_smaller() -> None:
    """D-329: a tall line box (a stacked formula's row) holds a short line set inside it;
    the mark inside both stands in the smaller box."""
    lines = running(count=3)
    tall = line("Sum over k of x k", LEFT, 160, 300, height=30)
    small = line("k = 1", 120, 172, 160, size=7)
    after = running(top=200, count=2)
    bar = Drawing("bar", Box(125, 178, 155, 178.5))
    doc = build([*lines, tall, small, *after, bar])
    parts = parts_of(doc, "bar")
    at = [item for item, _ in parts].index("bar")
    assert parts[at - 1][0] == small.id


# Properties


@st.composite
def tables(draw: st.DrawFn) -> tuple[list, str, str]:
    """A page of running text and a table between rules with its caption above or below,
    and the table's text expected."""
    count, width = draw(st.integers(1, 6)), draw(st.integers(1, 4))
    words = st.sampled_from(["a", "B2", "0.5", "x y", "Model", "\N{EN DASH}"])
    rows = [[draw(words) for _ in range(width)] for _ in range(count)]
    above = draw(st.booleans())
    label = f"Table {draw(st.integers(1, 20))}"
    caption_y = 300 if above else 300 + 14 * count + 12
    top = 318 if above else 300
    lines_ = table(top, rows)
    caption = line(f"{label}: {draw(words)}.", LEFT, caption_y, 300)
    rules = [rule(LEFT, top - 3, RIGHT), rule(LEFT, top + 14 * count, RIGHT)]
    after = running(top=caption_y + 60 if not above else top + 14 * count + 40, count=3)
    read = "\n".join(" ".join(row) for row in rows)
    return [*running(), *lines_, caption, *rules, *after], label, read


@given(tables())
def test_any_table_between_rules_is_one_table_its_caption_names(
    found: tuple[list, str, str],
) -> None:
    items, label, read = found
    doc = build(items)
    assert [b.text for b in of(doc, BlockKind.TABLE)] == [read]
    assert named(doc, label).text == read


@st.composite
def marked_pages(draw: st.DrawFn) -> tuple[list, dict[str, str]]:
    """Two paragraphs and a note below a rule, with thin marks drawn wholly inside some
    lines' boxes (a fraction bar, an underbrace), and the line each mark stands in."""
    first = running(count=draw(st.integers(1, 5)))
    second = running(top=300, count=draw(st.integers(1, 5)))
    notes = [line(f"{k + 1} A note.", LEFT, 705 + 10 * k, LEFT + 150, size=8) for k in range(2)]
    texts = [*first, *second, *notes]
    marks, hosts = [], {}
    for k, host in enumerate(draw(st.lists(st.sampled_from(texts), max_size=4, unique=True))):
        box = host.box
        assert box is not None
        x0 = draw(st.floats(box.x0, box.x1 - 4))
        x1 = draw(st.floats(x0 + 1, min(x0 + 30, box.x1)))
        y0 = draw(st.floats(box.y0, box.y1 - 0.5))
        mark = Drawing(f"m{k}", Box(x0, y0, x1, y0 + 0.5))
        marks.append(mark)
        hosts[mark.id] = host.id
    return [*texts, Drawing("rule", Box(LEFT, 700, LEFT + 60, 700.5)), *marks], hosts


@given(marked_pages())
def test_a_mark_drawn_inside_a_line_stands_just_after_it(
    found: tuple[list, dict[str, str]],
) -> None:
    """#58 (D-329 to D-333): each mark is read in the block of the line it stands in, after
    that line and any other mark standing there, with no text between."""
    items, hosts = found
    doc = build(items)
    texts = {li.id: li.text for li in items if isinstance(li, TextLine)}
    for mark, host in hosts.items():
        parts = parts_of(doc, mark)
        at = [item for item, _ in parts].index(mark)
        before = [item for item, _ in parts[:at] if item not in hosts]
        assert before[-1] == host
        start = dict(parts)[host]
        assert parts[at][1] == start + len(texts[host])
