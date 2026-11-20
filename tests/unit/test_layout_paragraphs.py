"""Layout on made-up pages: paragraphs and lines split by extraction (Issue #21 step 2, #27).

Pages are 600 x 800 points with body text in 10 point on a 14 point line pitch, one column
between x 70 and x 526 or two columns with a 16 point gutter, as in `test_layout`.
"""

from hypothesis import given
from hypothesis import strategies as st
from test_layout import GUTTER, LEFT, MIDDLE, RIGHT, content, line

from sci2audio.core import Block, BlockKind, Box, Document, Drawing, Part, TextLine, TextRun
from sci2audio.layout import build_document
from sci2audio.layout.geometry import Bars, union
from sci2audio.layout.order import Element
from sci2audio.layout.paragraphs import Held, Row, _denominator, _over, rows_of
from sci2audio.layout.paragraphs import paragraphs as make_paragraphs
from sci2audio.layout.settings import LayoutSettings

PITCH = 14.0
LEFT_END, RIGHT_START = MIDDLE - GUTTER / 2, MIDDLE + GUTTER / 2


def lines(name: str, x0: float, x1: float, top: float, count: int, **shape: float) -> list:
    """A paragraph: `count` full lines from `top`; `indent` moves the first line in, `last`
    is the share of the width the last line fills (1 = full)."""
    found = []
    for k in range(count):
        start = x0 + (shape.get("indent", 0.0) if k == 0 else 0.0)
        end = x1 if k < count - 1 else x0 + shape.get("last", 0.5) * (x1 - x0)
        found.append(line(f"{name}{k}", start, top + PITCH * k, end))
    return found


def worded(found: list[TextLine]) -> list[TextLine]:
    """The lines with more words, so that their size is the body size."""
    return [line(f"{li.text} of running text", li.box.x0, li.box.y0, li.box.x1) for li in found]


def bold(text: str, x0: float, y0: float, x1: float) -> TextLine:
    line_ = line(text, x0, y0, x1)
    return TextLine(line_.id, (TextRun(text, "Times-Bold", 10.0, bold=True),), line_.box)


def paragraphs(doc: Document) -> list[str]:
    """The text blocks: paragraphs, and the headings, footnotes, captions and list items
    step 3 of #21 tells apart from them."""
    text = {
        BlockKind.PARAGRAPH,
        BlockKind.HEADING,
        BlockKind.FOOTNOTE,
        BlockKind.CAPTION,
        BlockKind.LIST_ITEM,
    }
    return [b.text for b in doc.blocks if b.kind in text]


def joined(*groups: list[TextLine]) -> str:
    return "\n".join(li.text for group in groups for li in group)


# One column


def test_the_lines_of_a_paragraph_are_one_block() -> None:
    text = lines("a", LEFT, RIGHT, 100, 6)
    doc = build_document(content(text))
    assert paragraphs(doc) == [joined(text)]
    block = doc.blocks[0]
    assert [part.item for part in block.parts] == [li.id for li in text]
    assert [block.text[p.start :].split("\n")[0] for p in block.parts] == [li.text for li in text]


def test_a_short_last_line_ends_a_paragraph() -> None:
    first = lines("a", LEFT, RIGHT, 100, 4, last=0.6)
    second = lines("b", LEFT, RIGHT, 100 + 4 * PITCH, 4)
    assert paragraphs(build_document(content(first + second))) == [joined(first), joined(second)]


def test_an_indented_first_line_starts_a_paragraph_after_a_full_line() -> None:
    first = lines("a", LEFT, RIGHT, 100, 4, last=1.0)
    second = lines("b", LEFT, RIGHT, 100 + 4 * PITCH, 4, indent=15)
    assert paragraphs(build_document(content(first + second))) == [joined(first), joined(second)]


def test_more_white_than_the_line_spacing_starts_a_paragraph() -> None:
    first = lines("a", LEFT, RIGHT, 100, 4, last=1.0)
    second = lines("b", LEFT, RIGHT, 100 + 4 * PITCH + 10, 4)
    assert paragraphs(build_document(content(first + second))) == [joined(first), joined(second)]


def test_a_change_of_size_or_weight_starts_a_paragraph() -> None:
    heading = bold("2.1 Methods and Data", LEFT, 100, 250)
    body = lines("a", LEFT, RIGHT, 100 + PITCH, 4)
    big = line("3 Results", LEFT, 100 + 6 * PITCH, 200, size=12)
    more = lines("b", LEFT, RIGHT, 100 + 8 * PITCH, 4)
    doc = build_document(content([heading, *body, big, *more]))
    assert paragraphs(doc) == [heading.text, joined(body), big.text, joined(more)]


def test_entries_with_hanging_indents_stay_apart() -> None:
    entries, top = [], 100.0
    for name, count in (("a", 3), ("b", 2), ("c", 3)):
        entry = [line(f"{name}0", LEFT, top, RIGHT)]
        entry += [line(f"{name}{k}", LEFT + 15, top + PITCH * k, RIGHT) for k in range(1, count)]
        entries.append(entry)
        top += PITCH * count
    doc = build_document(content([li for entry in entries for li in entry]))
    assert paragraphs(doc) == [joined(entry) for entry in entries]


def test_two_line_paragraphs_with_indented_first_lines_stay_apart() -> None:
    """The second paragraph's indent is measured against the line before it, not against
    the first paragraph's own indented first line (nowak p4 footnotes 7 and 8)."""
    intro = lines("p", LEFT, RIGHT, 100, 3)
    first = lines("a", LEFT, RIGHT, 100 + 3 * PITCH, 2, indent=15, last=1.0)
    second = lines("b", LEFT, RIGHT, 100 + 5 * PITCH, 2, indent=15)
    doc = build_document(content([*intro, *first, *second]))
    assert paragraphs(doc) == [joined(intro), joined(first), joined(second)]


@given(st.sampled_from([(1, 2, 1), (1, 2, 1, 3, 1), (2, 1, 2, 1)]))
def test_hanging_entries_of_one_and_two_lines_stay_apart(counts: tuple[int, ...]) -> None:
    """Entries end in a short line; a two-line entry between one-line entries has its
    second line further in, which is not the indented first line of a paragraph."""
    entries, top = [], 100.0
    for n, count in enumerate(counts):
        entry = [line(f"e{n}-0", LEFT, top, RIGHT if count > 1 else 300)]
        entry += [
            line(f"e{n}-{k}", LEFT + 15, top + PITCH * k, RIGHT if k < count - 1 else 320)
            for k in range(1, count)
        ]
        entries.append(entry)
        top += PITCH * count
    doc = build_document(content([li for entry in entries for li in entry]))
    assert paragraphs(doc) == [joined(entry) for entry in entries]


def test_a_paragraph_does_not_end_inside_a_hyphenated_word() -> None:
    """A full line ending in a word split by a hyphen goes on, also between entries of a
    list with hanging indents (the second line here starts further in)."""
    first = line("[18] G. Montam-", LEFT, 100, RIGHT)
    second = line("baux, The European Physical Journal B", LEFT + 15, 100 + PITCH, 320)
    after = line("[19] A. Name, Journal", LEFT, 100 + 2 * PITCH, 300)
    doc = build_document(content([first, second, after]))
    assert paragraphs(doc) == [joined([first, second]), after.text]


def test_a_bold_run_in_head_does_not_make_its_line_bold() -> None:
    """A paragraph that opens with a bold head on its first line ("Definition 1.") is one
    paragraph, whether the head is a piece of its own or a run of the line."""
    head = bold("Domain-specific Continual Pre-training", LEFT, 100, 420)
    rest = line("In the", 432, 100, RIGHT)
    body = lines("a", LEFT, RIGHT, 100 + PITCH, 4)
    runs = (
        TextRun("Definition 1.", "Times-Bold", 10.0, bold=True),
        TextRun(" A", "Times-Italic", 10.0, italic=True),
        TextRun(" probabilistic context-free gram-", "Times-BoldItalic", 10.0, bold=True),
    )
    top = 100 + 6 * PITCH
    defined = TextLine("def", runs, Box(LEFT, top, RIGHT, top + 10))
    more = lines("b", LEFT, RIGHT, top + PITCH, 3)
    doc = build_document(content([head, rest, *body, defined, *more]))
    first = f"{head.text} {rest.text}\n{joined(body)}"
    assert paragraphs(doc) == [first, joined([defined, *more])]


def test_a_footnote_mark_or_subscripts_do_not_cut_a_paragraph() -> None:
    """A line's size is the size most of its letters have: a small piece on its baseline
    (a footnote mark, a subscript) does not make it a line in smaller letters."""
    text = lines("a", LEFT, RIGHT, 100, 6)
    y1, y2 = 100 + PITCH, 100 + 3 * PITCH
    marked = [
        line("rules of the grammar.", LEFT, y1, RIGHT - 6),
        line("1", RIGHT - 5, y1 - 3, RIGHT, size=7),
    ]
    subscripts = [
        line("where x", LEFT, y2, 120),
        line("ij", 121, y2 + 3, 128, size=7),
        line("is the weight of the edge from y", 131, y2, RIGHT - 9),
        line("kl", RIGHT - 8, y2 + 3, RIGHT, size=7),
    ]
    rows = [[li] for li in text]
    rows[1], rows[3] = marked, subscripts
    doc = build_document(content([li for row in rows for li in row]))
    # the mark and the subscripts are set close to their letters: no space before them (#36)
    printed = [li.text for li in text]
    printed[1] = "rules of the grammar.1"
    printed[3] = "where xij is the weight of the edge from ykl"
    assert paragraphs(doc) == ["\n".join(printed)]


def test_a_narrower_block_is_not_cut_at_every_line() -> None:
    """An abstract set narrower than its column: its lines end before the column's edge."""
    abstract = lines("a", LEFT + 20, RIGHT - 20, 100, 5)
    body = lines("b", LEFT, RIGHT, 100 + 6 * PITCH, 5)
    doc = build_document(content(abstract + body))
    assert paragraphs(doc) == [joined(abstract), joined(body)]


# Lines set flush right or centred; a line that ends inside a sentence (#454, D-719)

SMALL, SMALL_PITCH = 8.5, 11.0  # a motto's type


def set_right(texts: list[str], widths: list[float], top: float, edge: float = RIGHT) -> list:
    """Lines in small type that end at one edge and start where their widths say."""
    return [
        line(text, edge - width, top + SMALL_PITCH * k, edge, size=SMALL)
        for k, (text, width) in enumerate(zip(texts, widths, strict=True))
    ]


# the left edges of #454's motto, as widths from its right edge: the third line starts further
# in than the two lines before it and the one after it, as a paragraph's first line would
MOTTO_WIDTHS = [172.1, 154.8, 79.0, 129.5, 128.1]


def test_a_flush_right_motto_is_one_paragraph_and_its_source_another() -> None:
    """#454: the motto's ragged left edge is no first-line indent and no outdent; the source
    under it stands apart by white, and the body text by its size."""
    above = lines("a", LEFT, RIGHT, 100, 3)
    motto = set_right(
        [
            "\u201cA people must be taught so well that it",
            "knows its human aim and the danger,",
            "in which it stands.",
            "Between the aim and the danger lies the",
            "way to be found. To see is everything.\u201d",
        ],
        MOTTO_WIDTHS,
        100 + 3 * PITCH + 10,
    )
    source = set_right(["(Albers 1971, p. 12)"], [80.0], motto[-1].box.y0 + SMALL_PITCH + 6)
    below = lines("b", LEFT, RIGHT, source[0].box.y0 + 20, 3)
    doc = build_document(content([*above, *motto, *source, *below]))
    assert paragraphs(doc) == [joined(above), joined(motto), source[0].text, joined(below)]


def test_flush_right_lines_that_start_upper_case_are_one_paragraph_too() -> None:
    """The shape alone keeps them together: every line here starts with a capital (German
    nouns), so the rule for a line ending inside a sentence does not apply."""
    motto = set_right(
        ["Eine Gesellschaft muss ihr menschliches", "Ziel kennen und die Gefahr,", "Die sie",
         "Umgibt, und den Weg dazwischen", "Finden. Bewusstsein ist alles."],
        MOTTO_WIDTHS,
        100,
    )  # fmt: skip
    body = lines("a", LEFT, RIGHT, 100 + 5 * SMALL_PITCH + 10, 3)
    assert paragraphs(build_document(content([*motto, *body]))) == [joined(motto), joined(body)]


def test_centred_lines_are_one_paragraph() -> None:
    """Centred lines start and end at three or more places but share their middle: neither
    a short line nor an indent ends their paragraph."""
    middle = (LEFT + RIGHT) / 2
    widths = [300.0, 220.0, 260.0, 140.0]
    texts = ["Department of Acoustics and Listening,", "Example University, Town",
             "Example Country 12345", "(Dated: 1 May 2026)"]  # fmt: skip
    centred = [
        line(text, middle - width / 2, 100 + PITCH * k, middle + width / 2)
        for k, (text, width) in enumerate(zip(texts, widths, strict=True))
    ]
    body = lines("a", LEFT, RIGHT, 100 + 4 * PITCH + 10, 3)
    doc = build_document(content([*centred, *body]))
    assert paragraphs(doc) == [joined(centred), joined(body)]


def test_a_line_ending_inside_a_sentence_goes_on_with_a_lower_case_line() -> None:
    """Short lines set flush left, as a poem's: a line that ends inside a sentence (a comma,
    a letter, a slash) goes on with the line under it when that starts in lower case."""
    poem = [
        line("The road is made by walking,", LEFT, 100, LEFT + 150),
        line("and the walker learns the land", LEFT, 100 + PITCH, LEFT + 170),
        line("she crosses at https://example.org/", LEFT, 100 + 2 * PITCH, LEFT + 190),
        line("roads-and-rivers on foot.", LEFT, 100 + 3 * PITCH, LEFT + 130),
    ]
    assert paragraphs(build_document(content(poem))) == [joined(poem)]


def italic(text: str, x0: float, y0: float, x1: float) -> TextLine:
    """A line in italic, but for an upright mark ("1") in front of it, as an affiliation."""
    line_ = line(text, x0, y0, x1)
    mark, rest = text[:1], text[1:]
    runs = (TextRun(mark, "Times", 10.0), TextRun(rest, "Times-Italic", 10.0, italic=True))
    return TextLine(line_.id, runs, line_.box)


def test_an_upright_line_under_centred_italic_lines_starts_a_paragraph() -> None:
    """#476 (Liu p1): a centred affiliation in italic is one paragraph, the
    upright date under it another; in centred lines a short line ends nothing, so the change
    of style does."""
    middle = (LEFT + RIGHT) / 2
    centred = [
        italic("1Department of Acoustics and Listening, Example University,",
               middle - 190, 100, middle + 190),
        italic("1Example Town 12345, Example Country", middle - 110, 100 + PITCH, middle + 110),
        line("(Dated: 1 May 2026)", middle - 50, 100 + 2 * PITCH, middle + 50),
    ]  # fmt: skip
    body = lines("a", LEFT, RIGHT, 100 + 3 * PITCH + 10, 3)
    doc = build_document(content([*centred, *body]))
    assert paragraphs(doc) == [joined(centred[:2]), centred[2].text, joined(body)]


def test_an_indented_paragraph_starting_lower_case_stays_apart() -> None:
    """#476: a real first-line indent ends the paragraph even after a line
    without a full stop, when the new paragraph starts in lower case ("pandas")."""
    first = [
        line("Running text that fills its column from edge to edge and goes", LEFT, 100, RIGHT),
        line("on to the details on our website", LEFT, 100 + PITCH, LEFT + 200),
    ]
    second = [
        line("pandas reads the table and fills its column from edge to", LEFT + 15,
             100 + 2 * PITCH, RIGHT),
        line("edge, and the paragraph goes on and ends here.", LEFT, 100 + 3 * PITCH, RIGHT),
        line("And so does the next line.", LEFT, 100 + 4 * PITCH, LEFT + 150),
    ]  # fmt: skip
    doc = build_document(content([*first, *second]))
    assert paragraphs(doc) == [joined(first), joined(second)]


def test_an_outdented_entry_starting_lower_case_stays_apart() -> None:
    """#476: author-year entries with hanging indents; an entry ending in a
    link without a full stop, then one by "van Dijk": the outdent ends the entry."""
    entries = [
        [line("Albers, A. (2021). A study of the listening of papers. Journal of",
              LEFT, 100, RIGHT),
         line("Sound, 12, 45-67. https://example.org/listening", LEFT + 15, 100 + PITCH,
              LEFT + 300)],
        [line("van Dijk, T. (2022). Reading aloud in the laboratory and in the", LEFT,
              100 + 2 * PITCH, RIGHT),
         line("field. Proceedings of Things, 1-9.", LEFT + 15, 100 + 3 * PITCH, LEFT + 250)],
    ]  # fmt: skip
    doc = build_document(content([li for entry in entries for li in entry]))
    assert paragraphs(doc) == [joined(entry) for entry in entries]


def test_items_lettered_with_a_full_stop_stay_apart() -> None:
    """#476: "i." and "a." items (which `lists` does not split) start in lower
    case after a row without a full stop; each stays its own block."""
    for marks in (("i.", "ii.", "iii."), ("a.", "b.", "c.")):
        words = ("we read the paper aloud", "we listen to it", "we compare the two readings")
        items = [
            line(f"{mark} {said}", LEFT, 100 + PITCH * k, LEFT + 150 + 30 * (k % 2) - 10 * k)
            for k, (mark, said) in enumerate(zip(marks, words, strict=True))
        ]
        body = lines("x", LEFT, RIGHT, 100 + 3 * PITCH + 10, 3)
        doc = build_document(content([*items, *body]))
        assert paragraphs(doc) == [*(item.text for item in items), joined(body)]


def rows_at(spans: list[tuple[float, float]], top: float = 200.0) -> list[TextLine]:
    """Four rows of a block at these left and right edges, the third starting a sentence."""
    texts = ["The first line of the block.", "The second line ends here.",
             "A third line starts anew", "and goes on to its end."]  # fmt: skip
    pairs = enumerate(zip(texts, spans, strict=True))
    return [line(t, x0, top + PITCH * k, x1) for k, (t, (x0, x1)) in pairs]


def test_rows_ending_at_two_edges_are_no_flush_right_block() -> None:
    """#476: rows that start at three places but end at two edges are no
    flush-right lines, so the indented third row starts a paragraph."""
    above = lines("a", LEFT, RIGHT, 100, 3)
    block = rows_at([(LEFT, 450), (LEFT + 8, 450), (LEFT + 20, 400), (LEFT, 400)])
    doc = build_document(content(above + block))
    assert paragraphs(doc) == [joined(above), joined(block[:2]), joined(block[2:])]


def test_rows_with_two_middles_are_no_centred_block() -> None:
    """#476: rows whose middles stand at two places are not centred, so
    the indented third row starts a paragraph."""
    above = lines("a", LEFT, RIGHT, 100, 3)
    block = rows_at([(LEFT, 450), (LEFT + 10, 440), (LEFT + 30, 380), (LEFT, 410)])
    assert joined(block[2:]) in paragraphs(build_document(content(above + block)))


def test_one_italic_word_leaves_a_centred_row_upright() -> None:
    """#476: a row is italic when most of its letters are, so a journal's
    name in italic does not end a centred block of upright rows."""
    middle = (LEFT + RIGHT) / 2

    def centred(runs: list[tuple[str, bool]], width: float, k: int) -> TextLine:
        box = line("x", middle - width / 2, 100 + PITCH * k, middle + width / 2)
        styled = tuple(TextRun(text, "Times", 10.0, italic=slanted) for text, slanted in runs)
        return TextLine(box.id, styled, box.box)

    rows = [
        centred([("Department of Listening and Reading,", False)], 300, 0),
        centred([("for the ", False), ("Journal", True), (" of Sound, Town", False)], 220, 1),
        centred([("Example Country 12345", False)], 260, 2),
    ]
    body = lines("z", LEFT, RIGHT, 100 + 3 * PITCH + 10, 3)
    assert paragraphs(build_document(content(rows + body))) == [joined(rows), joined(body)]


@given(st.sampled_from(["e.g. the ones on the shelf.", "i.e. the ones on the shelf."]))
def test_a_short_line_goes_on_with_e_g_and_i_e(start: str) -> None:
    """#476: "e.g." and "i.e." are no lettered list marks, so a short
    line ending inside a sentence goes on with them."""
    rows = [
        line(
            "Running text that fills its column from one edge to the other edge", LEFT, 100, RIGHT
        ),
        line("we read the papers aloud", LEFT, 100 + PITCH, LEFT + 150),
        line(start, LEFT, 100 + 2 * PITCH, LEFT + 300),
    ]
    assert paragraphs(build_document(content(rows))) == [joined(rows)]


@given(st.sampled_from(["The danger.", "The danger", "the danger"]))
def test_a_short_line_still_ends_a_paragraph_before_a_new_sentence(first: str) -> None:
    """The short line ends a sentence, or the next line starts upper case or with a digit:
    the short line ends the paragraph, as before."""
    after = "Then came the aim." if first != "The danger." else "then came the aim."
    if first == "the danger":
        after = "2 more steps followed."
    rows = [
        line("Running text that fills its column from edge to edge", LEFT, 100, RIGHT),
        line(first, LEFT, 100 + PITCH, LEFT + 60),
        line(after, LEFT, 100 + 2 * PITCH, RIGHT),
        line("and ends here.", LEFT, 100 + 3 * PITCH, LEFT + 80),
    ]
    found = paragraphs(build_document(content(rows)))
    assert found == [joined(rows[:2]), joined(rows[2:])]


def test_a_narrower_block_s_indented_first_line_still_starts_a_paragraph() -> None:
    """An abstract set narrower than its column, justified: its rows share both edges and
    start at two places only (the first-line indent), so they are no flush-right lines."""
    first = lines("a", LEFT + 40, RIGHT - 40, 100, 3, last=1.0)
    second = lines("b", LEFT + 40, RIGHT - 40, 100 + 3 * PITCH, 3, indent=15)
    body = lines("c", LEFT, RIGHT, 100 + 6 * PITCH + 10, 3)
    doc = build_document(content([*first, *second, *body]))
    assert paragraphs(doc) == [joined(first), joined(second), joined(body)]


def test_reference_entries_ending_without_a_full_stop_stay_apart() -> None:
    """A hanging-indent list: an entry ending in a DOI without a full stop is followed by an
    entry that starts upper case, so it is not joined; and justified entries whose labels
    start at two places ("[9]", "[10]") are no flush-right lines, as they fill their column."""
    entries = [
        [line("[9] A. Albers. A study of the listening of papers. Journal of Sound,",
              LEFT + 5, 100, RIGHT),
         line("12(3):45-67, 2021. doi:10.1234/example.5678", LEFT + 15, 100 + PITCH, RIGHT)],
        [line("[10] B. Brandt and C. Keller. Reading aloud in the laboratory and the",
              LEFT, 100 + 2 * PITCH, RIGHT),
         line("field. Proceedings of Things, pages 1-9, 2022.", LEFT + 15, 100 + 3 * PITCH, RIGHT)],
        [line("[11] D. Dorn. A third entry that fills its column from one edge to the",
              LEFT, 100 + 4 * PITCH, RIGHT),
         line("other edge. Press, 2023.", LEFT + 15, 100 + 5 * PITCH, RIGHT)],
    ]  # fmt: skip
    doc = build_document(content([li for entry in entries for li in entry]))
    assert paragraphs(doc) == [joined(entry) for entry in entries]


# Across columns and pages


def two_column_text(left_count: int = 12, right_top: float = 100) -> tuple[list, list]:
    left = lines("l", LEFT, LEFT_END, 100, left_count, last=1.0)
    right = lines("r", RIGHT_START, RIGHT, right_top, 12)
    return left, right


def test_a_paragraph_runs_on_into_the_next_column() -> None:
    left, right = two_column_text()
    assert paragraphs(build_document(content(left + right))) == [joined(left, right)]


def test_an_indented_line_at_the_top_of_a_column_starts_a_paragraph() -> None:
    left, right = two_column_text()
    right[0] = line(right[0].text, RIGHT_START + 15, 100, RIGHT)
    assert paragraphs(build_document(content(left + right))) == [joined(left), joined(right)]


def test_a_heading_at_the_top_of_the_next_column_is_not_skipped() -> None:
    left, right = two_column_text(right_top=100 + PITCH)
    heading = bold("2 Related Work", RIGHT_START, 100, RIGHT_START + 90)
    doc = build_document(content([*left, heading, *right]))
    assert paragraphs(doc) == [joined(left), heading.text, joined(right)]


def test_a_paragraph_runs_on_across_a_page_and_the_page_number_waits() -> None:
    first = [*lines("a", LEFT, RIGHT, 100, 10, last=1.0), line("1", 295, 770, 305)]
    second = [*lines("b", LEFT, RIGHT, 100, 4), line("2", 295, 770, 305)]
    doc = build_document(content(first, second))
    assert [b.text for b in doc.blocks] == [joined(first[:-1], second[:-1]), "1", "2"]
    assert [b.kind for b in doc.blocks[1:]] == [BlockKind.FURNITURE] * 2


def test_a_footnote_does_not_cut_a_paragraph_and_follows_it() -> None:
    left, right = two_column_text(left_count=10)
    rule = Drawing("rule", Box(LEFT, 700, LEFT + 60, 700.5))
    note = line("1 A note in small letters.", LEFT, 705, LEFT + 120, size=8)
    doc = build_document(content([*left, note, *right], drawings=(rule,)))
    assert [b.text for b in doc.blocks] == [joined(left, right), note.text]
    assert [p.item for p in doc.blocks[-1].parts] == ["rule", note.id]  # #51


def test_a_table_at_the_top_of_the_next_page_does_not_cut_a_paragraph() -> None:
    """The table has no rules: its rows of cells, set smaller than the running text, are
    one TABLE block (PR D1)."""
    first = worded(lines("a", LEFT, RIGHT, 100, 10, last=1.0))
    cells = [
        line(f"c{r}{c}", LEFT + 120 * c, 80 + 12 * r, LEFT + 60 + 120 * c, size=9)
        for r in range(4)
        for c in range(3)
    ]
    caption = line("Table 1: Numbers.", 200, 140, 300, size=9)
    rest = worded(lines("b", LEFT, RIGHT, 180, 4))
    doc = build_document(content(first, [*cells, caption, *rest]))
    assert paragraphs(doc) == [joined(first, rest), caption.text]
    rows = (" ".join(cell.text for cell in cells[3 * r : 3 * r + 3]) for r in range(4))
    assert [b.text for b in doc.blocks if b.kind is BlockKind.TABLE] == ["\n".join(rows)]


# Lines split by extraction (#27)


def test_a_line_split_at_a_wide_word_gap_is_one_line_again() -> None:
    text = lines("a", LEFT, RIGHT, 100, 5)
    split = [
        line("words before a wide", LEFT, 100 + PITCH, 300),
        line("gap", 316, 100 + PITCH, RIGHT),
    ]
    text[1:2] = split
    doc = build_document(content(text))
    expected = joined(text).replace("wide\ngap", "wide gap")
    assert paragraphs(doc) == [expected]
    assert [p.item for p in doc.blocks[0].parts] == [li.id for li in text]


def test_a_numbered_heading_split_from_its_title_is_one_line() -> None:
    number, title = line("2.1", LEFT, 100, LEFT + 15), line("Probing Models", LEFT + 27, 100, 200)
    body = lines("a", LEFT, RIGHT, 100 + PITCH, 4)
    doc = build_document(content([number, title, *body]))
    assert paragraphs(doc)[0].startswith("2.1 Probing Models")


def test_the_gap_after_a_subscript_is_measured_from_the_line_s_end() -> None:
    """A subscript stored as a piece of its own may stand below the end of the piece before
    it; the white after them starts where the line's letters end, not where the subscript
    does (liu p2 "Next one feeds n(-1)E | into the")."""
    text = lines("a", LEFT, RIGHT, 100, 5)
    y = 100 + 2 * PITCH
    split = [
        line("ing integral. Next one feeds n", LEFT, y, 300),
        line("E", 284, y + 3, 290, size=7),
        line("into the", 306, y, RIGHT),
    ]
    # the row below has a word gap of 1 em (extraction cuts a line there, #27) halfway
    # between the subscript and "into the", but not halfway between the line's end and it
    below = [
        line("band off-diagonal", LEFT, y + PITCH, 292),
        line("terms", 302, y + PITCH, RIGHT),
    ]
    rows = [[li] for li in text]
    rows[2:4] = [split, below]
    doc = build_document(content([li for row in rows for li in row]))
    printed = [li.text for li in text]  # the subscript stands under "n", set close (#36)
    printed[2:4] = ["ing integral. Next one feeds nE into the", "band off-diagonal terms"]
    assert paragraphs(doc) == ["\n".join(printed)]


def test_two_columns_with_a_narrow_gutter_are_not_joined() -> None:
    """The gutter is barely wider than a wide word gap; the columns still stay apart."""
    gutter = 10.0
    left = lines("l", LEFT, MIDDLE - gutter / 2, 100, 12, last=1.0)
    right = lines("r", MIDDLE + gutter / 2, RIGHT, 100, 12)
    stored = [li for pair in zip(left, right, strict=True) for li in pair]
    doc = build_document(content(stored))
    assert paragraphs(doc) == [joined(left, right)]


def test_table_cells_stay_apart() -> None:
    above = lines("a", LEFT, RIGHT, 100, 3)
    cells = [
        [line(f"r{r}c{c}", LEFT + 150 * c, 160 + PITCH * r, LEFT + 60 + 150 * c) for c in range(3)]
        for r in range(4)
    ]
    doc = build_document(content([*above, *(cell for row in cells for cell in row)]))
    found = [text for block in paragraphs(doc) for text in block.split("\n")]
    assert found == [li.text for li in above] + [cell.text for row in cells for cell in row]


# Properties


@st.composite
def paragraph_pages(draw: st.DrawFn) -> tuple:
    """A page of 1 to 3 columns of paragraphs that end in a short line, any of them set
    apart by white or begun with an indent, stored in any order."""
    count = draw(st.integers(1, 3))
    width = (RIGHT - LEFT - GUTTER * (count - 1)) / count
    stored, expected = [], []
    for col in range(count):
        x0, top = LEFT + col * (width + GUTTER), 80.0
        for _ in range(draw(st.integers(2, 4))):
            indent = draw(st.sampled_from([0.0, 12.0]))
            text = lines(
                f"c{col}t{int(top)}-",
                x0,
                x0 + width,
                top,
                draw(st.integers(3, 6)),
                indent=indent,
                last=draw(st.floats(0.1, 0.7)),
            )
            stored += text
            expected.append(joined(text))
            top += PITCH * len(text) + draw(st.sampled_from([0.0, 8.0]))
    return content(draw(st.permutations(stored))), expected


@given(paragraph_pages())
def test_any_clean_page_keeps_each_paragraph_in_one_block(page: tuple) -> None:
    found, expected = page
    assert paragraphs(build_document(found)) == expected


@st.composite
def run_on_pages(draw: st.DrawFn) -> tuple:
    """A page of 2 or 3 columns whose paragraphs may end in a full line: inside a column
    the next paragraph then starts with an indent or after white; at a column's foot it
    runs on into the next column. The first column may end in a footnote under a short
    rule, which follows the paragraph open there. Stored in any order."""
    count = draw(st.integers(2, 3))
    width = (RIGHT - LEFT - GUTTER * (count - 1)) / count
    stored: list[TextLine] = []
    found: list[list[TextLine]] = []  # the paragraphs in reading order
    note, after = None, -1  # the footnote, and the paragraph it follows
    drawings: tuple = ()
    running = False  # the last paragraph runs on into this column
    for col in range(count):
        x0, top = LEFT + col * (width + GUTTER), 80.0
        chunks = draw(st.integers(2, 3))
        for k in range(chunks):
            last_chunk = k == chunks - 1
            run_on = last_chunk and col < count - 1 and draw(st.booleans())
            full = run_on if last_chunk else draw(st.booleans())
            goes_on = running and k == 0
            ended_full = k > 0 and found[-1][-1].box.x1 >= x0 + width - 1
            if goes_on:
                indent, gap = 0.0, 0.0
            else:
                ways = ["indent", "white", "both"] if ended_full else ["none", "indent", "white"]
                way = draw(st.sampled_from(ways))
                indent = 12.0 if way in ("indent", "both") else 0.0
                gap = 8.0 if k and way in ("white", "both") else 0.0
            top += gap
            text = lines(
                f"c{col}p{k}-",
                x0,
                x0 + width,
                top,
                draw(st.integers(3, 5)),
                indent=indent,
                last=1.0 if full else draw(st.floats(0.1, 0.7)),
            )
            stored += text
            if goes_on:
                found[-1] += text
            else:
                found.append(text)
            top += PITCH * len(text)
            running = run_on
        if col == 0 and draw(st.booleans()):
            drawings = (Drawing("rule", Box(x0, 700, x0 + 60, 700.5)),)
            note = line("1 A note in small letters.", x0, 705, x0 + 0.6 * width, size=8)
            stored.append(note)
            after = len(found) - 1
    expected = [joined(paragraph) for paragraph in found]
    if note:
        expected.insert(after + 1, note.text)
    return content(draw(st.permutations(stored)), drawings=drawings), expected


@given(run_on_pages())
def test_paragraphs_run_on_across_columns_and_past_a_footnote(page: tuple) -> None:
    found, expected = page
    assert paragraphs(build_document(found)) == expected


# A float at a page's top, then a caption (#61)


def _row(text: str, x0: float, y0: float, x1: float, column: tuple[float, float], page: int):
    found = line(text, x0, y0, x1)
    box = found.box or Box(x0, y0, x1, y0 + 10)
    return Row((found,), box, column[0], column[1], page, 10.0, False)


def _caption(text: str, label: str, x0: float, y0: float, column: tuple[float, float]):
    runs = (TextRun(label, "Times-Bold", 10.0, bold=True), TextRun(text, "Times", 10.0))
    found = TextLine(f"cap{y0}", runs, Box(x0, y0, x0 + 120, y0 + 10))
    return Row((found,), found.box, column[0], column[1], 2, 10.0, False)


LEFT_COLUMN, RIGHT_COLUMN = (LEFT, LEFT_END), (RIGHT_START, RIGHT)


def _float_then_caption(*after: Row, kind: BlockKind = BlockKind.FORMULA) -> list[Block]:
    """A paragraph running on at the foot of page 1's right column; on page 2 a float at
    the top, a caption under it in the left column, then `after`."""
    words = [f"Running text, line {k}" for k in range(3)]
    units: list = [
        _row(w, RIGHT_START, 100 + PITCH * k, RIGHT, RIGHT_COLUMN, 1) for k, w in enumerate(words)
    ]
    units.append(Held(Block(kind, "the float", (Part("float"),)), 2))
    units.append(_caption(" Fast prefix", "Algorithm 3", LEFT, 120, LEFT_COLUMN))
    return make_paragraphs([*units, *after], LayoutSettings())


def test_a_caption_after_a_float_is_never_read_into_the_paragraph() -> None:
    """The caption after a held float starts afresh: here after a figure, as after a formula
    (nowak p5's "Algorithm 3" under Eq. (16a) to (16f))."""
    on = _row("goes on and ends here.", RIGHT_START, 120, RIGHT, RIGHT_COLUMN, 2)
    for kind in (BlockKind.FORMULA, BlockKind.FIGURE):
        blocks = _float_then_caption(on, kind=kind)
        texts = [b.text for b in blocks]
        assert texts[0].endswith("Running text, line 2\ngoes on and ends here.")
        assert texts[1:] == ["the float", "Algorithm 3 Fast prefix"]


def test_the_lines_of_a_caption_s_float_do_not_end_the_paragraph_set_aside() -> None:
    """The algorithm's lines under its caption, even one that fills its column, belong to
    the float: the paragraph set aside still goes on after them, in the other column."""
    code = [
        _row(
            "for k in 0 to N: compute the prefix probability", LEFT, 134, LEFT_END, LEFT_COLUMN, 2
        ),
        _row("return π", LEFT + 30, 148, LEFT + 90, LEFT_COLUMN, 2),
    ]
    on = _row("goes on and ends here.", RIGHT_START, 120, RIGHT, RIGHT_COLUMN, 2)
    texts = [b.text for b in _float_then_caption(*code, on)]
    assert texts == [
        "Running text, line 0\nRunning text, line 1\nRunning text, line 2\ngoes on and ends here.",
        "the float",
        "Algorithm 3 Fast prefix",
        "for k in 0 to N: compute the prefix probability\nreturn π",
    ]


# Spaces between the pieces of one printed line (#36, D-274 to D-280)

ROW_Y = 100 + 2 * PITCH  # the third line of `_one_row`'s paragraph


def at(text: str, x0: float, x1: float, raised: float = 0.0, size: float = 10.0) -> TextLine:
    """A piece of the third line, `raised` points above its baseline (below if negative)."""
    return line(text, x0, ROW_Y - raised, x1, size=size)


def _one_row(
    *pieces: TextLine, settings: LayoutSettings | None = None, drawings: tuple = ()
) -> Block:
    """The paragraph block of 5 full lines whose third line is made of these pieces (and
    these drawings on the page)."""
    text = lines("a", LEFT, RIGHT, 100, 5)
    page = content([*text[:2], *pieces, *text[3:]], drawings=drawings)
    doc = build_document(page, settings)
    (block,) = [b for b in doc.blocks if b.kind is BlockKind.PARAGRAPH]
    return block


def _third(block: Block) -> str:
    return block.text.split("\n")[2]


def test_a_mark_set_close_after_a_word_gets_no_space() -> None:
    """Arsiwalla p3 "qualia1.": the mark stands 0.5 pt after the word, the full stop 0.5 pt
    after the mark."""
    pieces = (
        at("character of qualia", LEFT, 300),
        at("1", 300.5, 304, raised=3, size=7),
        at(". Possibly, the explanatory gap", 304.5, RIGHT),
    )
    assert _third(_one_row(*pieces)) == "character of qualia1. Possibly, the explanatory gap"


def test_a_mark_after_a_printed_word_space_keeps_it() -> None:
    """Hardt p3 "sets. 1": 5 pt of white, wider than a word space, stand before the mark."""
    pieces = (
        at("the size of the resulting sets.", LEFT, RIGHT - 9),
        at("1", RIGHT - 4, RIGHT, raised=3, size=7),
    )
    assert _third(_one_row(*pieces)) == "the size of the resulting sets. 1"


def test_a_subscript_right_after_its_letter_gets_no_space() -> None:
    pieces = (
        at("where x", LEFT, 120),
        at("ij", 120.5, 127, raised=-3, size=7),
        at("is the weight of the edge", 130, RIGHT),
    )
    assert _third(_one_row(*pieces)) == "where xij is the weight of the edge"


def test_a_subscript_stacked_under_a_superscript_follows_it() -> None:
    """Liu p2 "J^1st_0": the subscript starts back under the superscript's letters."""
    pieces = (
        at("the scattering integral J1st", LEFT, 300),
        at("0", 290, 294, raised=-3, size=7),
        at("[n] gives the field", 300.5, RIGHT),
    )
    assert _third(_one_row(*pieces)) == "the scattering integral J1st0[n] gives the field"


def test_digits_of_a_stacked_fraction_keep_their_space() -> None:
    """#128, Liu p4 "vF = 3/2 at": the denominator starts back under the
    numerator; joined, the two digits would read as one number ("32", thirty-two)."""
    pieces = (
        at("the Fermi velocity vF = 3", LEFT, 300),
        at("2", 296, 300, raised=-4, size=7),
        at("at the edge of the band", 303, RIGHT),
    )
    assert _third(_one_row(*pieces)) == "the Fermi velocity vF = 3 2 at the edge of the band"


def test_the_parts_of_an_inline_fraction_keep_a_space() -> None:
    """#202, Liu p2 "µB = eℏ over 2me": the denominator, stored as a piece of its own,
    starts back under the numerator's letters at the end of the piece before; the fraction
    bar between them keeps a space ("eh 2me"), and every piece keeps its text at its
    offset."""
    pieces = (
        at("Bohr-magneton is B = eh", LEFT, 300),
        at("2me", 292, 304, raised=-5, size=7),
        at(". The Berry connection is defined", 306, RIGHT),
    )
    bar = Drawing("bar", Box(291.5, ROW_Y + 6.0, 300.5, ROW_Y + 6.4))
    block = _one_row(*pieces, drawings=(bar,))
    assert _third(block) == "Bohr-magneton is B = eh 2me . The Berry connection is defined"
    starts = {part.item: part.start for part in block.parts}
    for piece in pieces:
        assert block.text[starts[piece.id] : starts[piece.id] + len(piece.text)] == piece.text
    # without the bar the two pieces stand as a superscript over a subscript: joined
    assert (
        _third(_one_row(*pieces)) == "Bohr-magneton is B = eh2me . The Berry connection is defined"
    )


# Liu p2's line "is within the energy gap s_int OH = -(e gs gv / 12 pi)(me / m*). Physically,"
# (#322), its pieces and bars where liu prints them, in a column 245 pt wide: extraction gives
# the denominator 12 pi last, and m* (with the rest of the line) before me.
FRACTION_X, FRACTION_Y = LEFT - 54, ROW_Y - 454.72
COLUMN_END = 299 + FRACTION_X


def _piece(name: str, *runs: tuple[str, float, float, float, float, float]) -> TextLine:
    """A piece of liu's line: its runs (text, size, x0, y0, x1, y1 on liu's page)."""
    found = tuple(
        TextRun(
            text,
            "Times",
            size,
            box=Box(x0 + FRACTION_X, y0 + FRACTION_Y, x1 + FRACTION_X, y1 + FRACTION_Y),
        )
        for text, size, x0, y0, x1, y1 in runs
    )
    return TextLine(name, found, union([run.box for run in found if run.box]))


def _bar(name: str, x0: float, x1: float) -> Drawing:
    return Drawing(
        name, Box(x0 + FRACTION_X, 458.74 + FRACTION_Y, x1 + FRACTION_X, 459.54 + FRACTION_Y)
    )


def _fraction_page(first: float = 212.52, bars: bool = True) -> list[str]:
    """The paragraphs of a two-column page whose left column's third line is liu's, its
    first denominator starting at `first` (liu: 212.52, its bar from 208.66 to 229.24)."""
    pieces = [
        _piece(
            "lead",
            ("is within the energy gap", 10, 54.0, 454.72, 162.2, 463.67),
            (" s", 10, 166.32, 454.72, 172.01, 463.56),
            ("int", 7, 172.37, 453.18, 181.92, 459.37),
        ),
        _piece(
            "num1",
            ("OH", 7, 172.02, 459.47, 184.01, 465.73),
            (" =", 10, 188.44, 454.72, 196.18, 463.56),
            (" -", 10, 200.11, 454.16, 207.85, 463.56),
            ("eg", 7, 209.06, 452.35, 216.72, 458.6),
            ("s", 5, 216.72, 454.73, 220.06, 459.15),
            ("g", 7, 220.56, 452.35, 224.44, 458.6),
            ("v", 5, 224.45, 454.73, 227.99, 459.15),
        ),
        _piece(
            "num2",
            ("m", 7, 231.38, 452.71, 238.45, 458.9),
            ("e", 5, 238.45, 455.08, 241.82, 459.51),
        ),
        _piece(
            "den2",
            ("m", 7, 231.24, 460.23, 238.3, 466.42),
            ("*", 5, 238.31, 459.34, 241.97, 464.04),
            (" . Physically,", 10, 243.67, 454.72, 299.01, 463.66),
        ),
        _piece(
            "den1",
            ("12", 7, first, 460.23, first + 7.94, 466.42),
            ("pi", 7, first + 7.95, 460.23, first + 12.61, 466.42),
        ),
    ]
    left = [line(f"left {k}", LEFT, 100 + 14 * k, COLUMN_END) for k in (0, 1, 3, 4)]
    right = [line(f"right {k}", COLUMN_END + 16, 100 + 14 * k, RIGHT) for k in range(5)]
    drawn = (_bar("bar1", 208.66, 229.24), _bar("bar2", 230.84, 242.87)) if bars else ()
    doc = build_document(content([*left[:2], *pieces, *left[2:], *right], drawings=drawn))
    return [b.text for b in doc.blocks if b.kind is BlockKind.PARAGRAPH]


def test_a_line_ending_in_two_inline_fractions_reads_each_over_its_bar() -> None:
    """#322, liu p2: the denominator read last joins its numerator's line instead of
    starting a paragraph of its own, and "me", the second numerator, is read before its
    denominator "m*", which starts 0.14 pt further left."""
    (column,) = _fraction_page()
    assert (
        column.split("\n")[2] == "is within the energy gap sintOH = -egsgv 12pi me m* . Physically,"
    )


def test_a_piece_starting_beside_a_bar_is_no_denominator() -> None:
    """Only a piece whose first letters stand within `fraction_inside` (0.1 em) of the bar's
    ends is its denominator (Nowak p10: a word under a brace drawn as two short rules
    starts beside them). 12pi starting 0.5 pt before the bar is; 2 pt before, it is not."""
    (column,) = _fraction_page(first=208.16)
    assert "-egsgv 12pi me m*" in column
    assert "12pi" in _fraction_page(first=206.66)[1:]
    # nor one whose first letters run past the bar's end by more: "12" ends 0.7 pt, then
    # 1.7 pt, past it ("pi" then runs into "me", so no space is put between them)
    (column,) = _fraction_page(first=222.0)
    assert column.split("\n")[2].startswith("is within the energy gap sintOH = -egsgv 12pi")
    assert "12pi" in _fraction_page(first=223.0)[1:]


def test_a_table_rule_under_a_line_is_no_fraction_bar() -> None:
    """A table's rule stands under its header line, not inside it: the first row under the
    rule, within `fraction_reach` of it and inside its width, is a line of its own."""
    header = [line("Model", LEFT, 100, 120, size=9), line("Accuracy", 200, 100, 240, size=9)]
    rule = Drawing("rule", Box(LEFT, 111, 250, 111.5))
    rows = [line("Base", LEFT, 114, 100, size=9), line("0.91", 200, 114, 220, size=9)]
    doc = build_document(content([*header, *rows], drawings=(rule,)))
    found = [text for b in doc.blocks for text in b.text.split("\n")]
    assert "Base 0.91" in found or ("Base" in found and "0.91" in found)
    assert not any("Model" in text and "Base" in text for text in found)


# rows_of on its own (#322, #647): pieces whose runs have no boxes, so a piece's
# letters are its whole box; body size 10, so `fraction_inside` is exactly 1 pt and
# `fraction_reach` 6 pt. Every coordinate below is exact in binary.
SIZE = 10.0
# a numerator, raised, and the bar under it: the bar's middle (105.25) lies inside the
# numerator's own height (99 to 107), below its letters' middle (103)
NUMERATOR = Box(121, 99, 130, 107)
UNDER = Box(120, 105, 131, 105.5)


def _text(text: str, box: Box) -> Element:
    return Element(box, TextLine(f"t-{text}", (TextRun(text, "Times", SIZE),), box))


def _printed(
    *pieces: Element, bars: tuple[Box, ...] = (UNDER,), other_column: tuple[Element, ...] = ()
) -> list[list[str]]:
    """The printed lines `rows_of` makes of the pieces, in this reading order, on a page
    with these bars; the pieces in `other_column` stand in a second column."""
    edges = {id(e): (300.0, 560.0) if e in other_column else (40.0, 290.0) for e in pieces}
    found = rows_of(list(pieces), edges, LayoutSettings(), SIZE, Bars.of(bars, 2.5))
    return [[e.line.text if e.line else "<mark>" for e in group] for group in found]


def test_a_line_of_one_fraction_reads_its_numerator_first() -> None:
    """A printed line of exactly two pieces, a numerator and its denominator starting
    1 pt further left, reads the numerator first (liu p2 "me over m*")."""
    up, down = _text("me", NUMERATOR), _text("m*", Box(120, 106, 128, 112))
    assert _printed(up, down) == [["me", "m*"]]
    # without the bar the denominator is a line of its own
    assert _printed(up, down, bars=()) == [["me"], ["m*"]]


def test_a_denominator_at_the_start_of_its_line_follows_its_numerator() -> None:
    """The leftmost piece of a printed line is a denominator whose numerator starts further
    right and is not the line's last piece: the numerator is read first, the rest keeps its
    order."""
    up, rest = _text("me", NUMERATOR), _text("is the mass", Box(140, 100, 170, 110))
    down = _text("m*", Box(120, 106, 128, 112))
    assert _printed(up, rest, down) == [["me", "m*", "is the mass"]]


def test_a_piece_in_another_column_under_a_bar_is_no_denominator() -> None:
    """The reading order puts the piece under the bar in the next column: it is not joined
    to the line read before it, whatever the bar."""
    up, down = _text("me", NUMERATOR), _text("m*", Box(120, 106, 128, 112))
    assert _printed(up, down, other_column=(down,)) == [["me"], ["m*"]]


def test_a_bar_whose_middle_is_on_the_line_s_bottom_edge_is_not_inside_it() -> None:
    """Inside the line means strictly between its top and bottom: a rule whose middle lies
    exactly on the bottom edge (107) is under the line, as a table's rule is, so the piece
    under it is a line of its own; 0.25 pt higher it is a fraction bar.

    A rule whose middle is on the line's top edge can have no numerator from the line above
    it: every piece's letters lie inside the line (`_letter_boxes` is the piece's runs, the
    line the union of the pieces), so their middles are below that edge and `fraction_bar`
    refuses it whatever `_denominator` says."""
    up, down = _text("me", NUMERATOR), _text("m*", Box(120, 108, 128, 114))
    assert _printed(up, down, bars=(Box(120, 106.75, 131, 107.25),)) == [["me"], ["m*"]]
    assert _printed(up, down, bars=(Box(120, 106.5, 131, 107),)) == [["me", "m*"]]


def test_fraction_inside_counts_at_its_exact_value_at_both_ends() -> None:
    """The denominator's first letters may start exactly `fraction_inside` (1 pt here)
    before the bar's left end and end exactly that far past its right end; a quarter point
    further they may not."""
    up = _text("me", NUMERATOR)
    for box, joined in [
        (Box(119, 106, 127, 112), True),
        (Box(118.75, 106, 127, 112), False),
        (Box(125, 106, 132, 112), True),
        (Box(125, 106, 132.25, 112), False),
    ]:
        down = _text("m*", box)
        assert _printed(up, down) == ([["me", "m*"]] if joined else [["me"], ["m*"]]), box


def test_a_denominator_cut_in_two_pieces_reads_its_numerator_once() -> None:
    """Every piece is read once: "x = a over 12", the denominator extracted as "1" and "2",
    both starting left of the numerator "a", reads "a" before "1" and never again before
    "2". (A nested fraction cannot read a piece twice: a numerator is only looked for
    among the pieces right of a denominator, so it can be found again only by a second
    denominator left of it under a bar it stands over, which is this shape.)"""
    lead = _text("x =", Box(100, 100, 118, 112))
    up = _text("a", Box(140, 99, 150, 105))
    one, two = _text("1", Box(120, 107.5, 128, 113.5)), _text("2", Box(129, 107.5, 136, 113.5))
    assert _printed(lead, up, one, two, bars=(Box(120, 106, 150, 106.5),)) == [
        ["x =", "a", "1", "2"]
    ]


def test_marks_are_neither_numerators_nor_denominators() -> None:
    """`rows_of` asks `_denominator` only about a text piece read after a printed line that
    ends in text, and every printed line of more than one element holds only text pieces
    (a mark either waits as a line of its own or starts one), so `_over` only sees text.
    Asked directly, a mark is no part of a fraction and nothing fails."""
    mark = Element(Box(121, 99, 130, 107), graphics=(Drawing("icon", Box(121, 99, 130, 107)),))
    up, down = _text("me", NUMERATOR), _text("m*", Box(120, 106, 128, 112))
    settings, bars = LayoutSettings(), Bars.of((UNDER,), 2.5)
    edges = {id(e): (40.0, 290.0) for e in (mark, up, down)}
    assert _over(UNDER, up, down, settings, SIZE)
    assert not _over(UNDER, mark, down, settings, SIZE)
    assert not _over(UNDER, up, mark, settings, SIZE)
    assert _denominator([up], down, edges, settings, SIZE, bars)
    assert not _denominator([mark], down, edges, settings, SIZE, bars)
    assert not _denominator([up], mark, edges, settings, SIZE, bars)


def test_two_words_split_at_a_wide_gap_keep_their_space() -> None:
    """Extraction cuts a line at a gap of 1 em (#27): that is always a word space."""
    pieces = (at("a widely spaced", LEFT, 250), at("justified line", 262, RIGHT))
    assert _third(_one_row(*pieces)) == "a widely spaced justified line"


def test_a_piece_far_back_under_earlier_words_keeps_a_space() -> None:
    """A piece starting more than `stack_reach` em back is out of its place: a space keeps
    it from running into the word before it (Liu p2 "Physically, me")."""
    pieces = (at("m*. Physically, the mass", LEFT, RIGHT), at("me", 200, 208, -6, size=7))
    assert _third(_one_row(*pieces)) == "m*. Physically, the mass me"


def test_each_piece_keeps_its_item_and_offset() -> None:
    pieces = (
        at("character of qualia", LEFT, 300),
        at("1", 300.5, 304, raised=3, size=7),
        at(". Possibly", 304.5, RIGHT),
    )
    block = _one_row(*pieces)
    starts = {part.item: part.start for part in block.parts}
    for piece in pieces:
        assert block.text[starts[piece.id] : starts[piece.id] + len(piece.text)] == piece.text
    assert [p.item for p in block.parts][2:5] == [piece.id for piece in pieces]


def test_the_thresholds_are_settings() -> None:
    """A wider `word_space` takes the 0.5 em before Hardt's mark for no space; a shorter
    `stack_reach` puts a space before a subscript stacked 1 em back."""
    hardt = (
        at("the size of the resulting sets.", LEFT, RIGHT - 9),
        at("1", RIGHT - 4, RIGHT, raised=3, size=7),
    )
    wide = LayoutSettings(word_space=0.6)
    assert _third(_one_row(*hardt, settings=wide)) == "the size of the resulting sets.1"
    liu = (
        at("the integral J1st", LEFT, 300),
        at("0", 290, 294, raised=-3, size=7),
        at("[n] gives the field", 300.5, RIGHT),
    )
    short = LayoutSettings(stack_reach=0.5)
    assert _third(_one_row(*liu, settings=short)) == "the integral J1st 0[n] gives the field"


# A tall piece and a row's letters (#126)


def ran(name: str, *runs: tuple[str, float, float, float, float, float]) -> TextLine:
    """A piece whose runs have boxes: (text, size, x0, y0, x1, y1) each."""
    made = tuple(TextRun(t, "Times", s, box=Box(x0, y0, x1, y1)) for t, s, x0, y0, x1, y1 in runs)
    return TextLine(name, made, union([run.box for run in made if run.box]))


def test_braces_reaching_below_the_line_do_not_take_in_the_next_line() -> None:
    """Chi p6: the braces of "{SOUPS}" (CMSY10, 9.9 pt) have boxes reaching 7 pt below the
    baseline, so the piece's box overlaps the printed line under it, "321-340."; that line
    is a row of its own, read after it."""
    text = lines("a", LEFT, RIGHT, 100, 2, last=1.0)
    y = 100 + 2 * PITCH
    braced = ran(
        "braced",
        ("able Privacy and Security (", 10.0, LEFT, y, 300, y + 10),
        ("{", 9.9, 300, y + 1.5, 305, y + 20),
        ("SOUPS", 10.0, 305, y, 340, y + 10),
        ("}", 9.9, 340, y + 1.5, 345, y + 20),
        (" 2016), pages", 10.0, 345, y, RIGHT, y + 10),
    )
    last = line("321-340.", LEFT, y + PITCH, LEFT + 40)
    doc = build_document(content([*text, braced, last]))
    assert paragraphs(doc) == [joined(text, [braced, last])]


def test_a_tall_piece_between_two_lines_does_not_chain_them() -> None:
    """A piece read between two printed lines and overlapping both (an accent drawn as a
    glyph of its own, #125) joins the row above; the line below is measured against that
    row as a whole, not against the tall piece, and stays a row of its own."""
    y = 100 + 2 * PITCH
    upper = line("Suchin Gururangan, Ana Marasovic, Swabha", LEFT, y, RIGHT)
    tall = line("\u00b4", 200, y + 4.9, 203, height=14.2)
    lower = line("Swayamdipta, Kyle Lo, Iz Beltagy.", LEFT, y + PITCH, 300)
    ordered = [Element(piece.box, piece) for piece in (upper, tall, lower)]
    edges = {id(e): (LEFT, RIGHT) for e in ordered}
    rows = rows_of(ordered, edges, LayoutSettings(), 10.0)
    assert [[e.line.text for e in row if e.line] for row in rows] == [
        [upper.text, tall.text],
        [lower.text],
    ]


def test_scripts_outnumbering_their_base_letters_stay_in_the_row() -> None:
    """Liu p2 "J1st0[n(-1)E]": the piece "0[n(-1)" holds more letters in scripts than on
    the baseline; it is measured by its base letters, so it stays in its row."""
    text = lines("a", LEFT, RIGHT, 100, 5)
    y = 100 + 2 * PITCH
    pieces = [
        ran(
            "j",
            ("ing integral J", 10.0, LEFT, y, 300, y + 10),
            ("1st", 7.0, 300, y - 1.5, 310, y + 5),
        ),
        ran(
            "script",
            ("0", 7.0, 300, y + 4.5, 304, y + 11),
            ("[", 10.0, 311, y - 0.5, 314, y + 9.5),
            ("n", 10.0, 314, y, 320, y + 9),
            ("(-1)", 7.0, 320, y - 3.5, 335, y + 3.5),
        ),
        line("E", 320, y + 5, 324, size=7),
        line("]. Next one feeds the field", 335.5, y, RIGHT),
    ]
    doc = build_document(content([*text[:2], *pieces, *text[3:]]))
    (block,) = paragraphs(doc)
    assert block.split("\n")[2] == "ing integral J1st0[n(-1)E]. Next one feeds the field"
