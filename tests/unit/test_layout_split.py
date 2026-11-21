"""Keeping some of a block's parts (layout `split.kept`): each kept line's text as found,
graphics holding no text wherever they stand (#61). Cutting a block and reading
lines row by row, with pieces of a printed line joined by a space only where the page prints
one (#36) or a fraction bar stands between them (#202)."""

from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Block, BlockKind, Box, Part, TextLine, TextRun
from sci2audio.layout.geometry import separators
from sci2audio.layout.settings import LayoutSettings
from sci2audio.layout.split import kept, part_ends, read_rows, split_at


def block(text: str, parts: list[tuple[str, int]]) -> Block:
    return Block(BlockKind.PARAGRAPH, text, tuple(Part(item, start) for item, start in parts))


def test_a_line_before_a_graphic_at_the_text_end_keeps_its_last_letter() -> None:
    """liu p2-l69 lost its final comma when a rule stood at the end of its block."""
    b = block("first line\nsecond line,", [("l1", 0), ("l2", 11), ("d1", 23)])
    assert kept(b, b.parts[1:], {"l1": 10, "l2": 12}).text == "second line,"
    assert part_ends(b, {"l1": 10, "l2": 12}) == {"l1": 10, "l2": 23}


def test_a_graphic_where_a_line_ends_does_not_end_it_early() -> None:
    b = block("one\ntwo\nthree", [("l1", 0), ("d1", 3), ("l2", 4), ("l3", 8)])
    out = kept(b, [b.parts[0], b.parts[1], b.parts[3]], {"l1": 3, "l2": 3, "l3": 5})
    assert out.text == "one\nthree"
    assert [(p.item, p.start) for p in out.parts] == [("l1", 0), ("d1", 3), ("l3", 4)]


@st.composite
def blocks(draw: st.DrawFn) -> tuple[Block, dict[str, str]]:
    """A block of lines joined by a break, a space or nothing (pieces of a printed line set
    close together, #36), with graphics standing at a line's start or end, or at the text's
    end."""
    words = st.text(alphabet="abcxyz,.() ", min_size=0, max_size=8)
    texts = draw(st.lists(words, min_size=1, max_size=6))
    text, parts, lines = "", [], {}
    for k, line in enumerate(texts):
        if k:
            text += draw(st.sampled_from(["\n", " ", ""]))
        if draw(st.booleans()):
            parts.append((f"d{k}", len(text)))
        parts.append((f"l{k}", len(text)))
        lines[f"l{k}"] = line
        text += line
        if draw(st.booleans()):
            parts.append((f"e{k}", len(text)))
    return block(text, parts), lines


@given(blocks(), st.data())
def test_kept_lines_keep_their_text(
    case: tuple[Block, dict[str, str]], data: st.DataObject
) -> None:
    b, lines = case
    keep = [p for p in b.parts if data.draw(st.booleans())]
    out = kept(b, keep, {item: len(line) for item, line in lines.items()})
    for before, after in zip(keep, out.parts, strict=True):
        assert before.item == after.item
        if before.item in lines:
            line = lines[before.item]
            assert out.text[after.start : after.start + len(line)] == line


def test_pieces_joined_without_a_space_lose_no_letter() -> None:
    """#36: "qualia" + "1" + "." set close: no separator stands before the mark or the
    full stop, so cutting, ending or keeping parts must not drop a letter."""
    b = block("of qualia1. Then\nnext", [("l1", 0), ("l2", 9), ("l3", 10), ("l4", 17)])
    lengths = {"l1": 9, "l2": 1, "l3": 6, "l4": 4}
    assert part_ends(b, lengths) == {"l1": 9, "l2": 10, "l3": 16, "l4": 21}
    assert [x.text for x in split_at(b, [10, 17])] == ["of qualia1", ". Then", "next"]
    assert kept(b, [b.parts[0], b.parts[2]], lengths).text == "of qualia. Then"
    assert kept(b, [b.parts[1], b.parts[3]], lengths).text == "1\nnext"


def test_a_graphic_at_a_cut_without_a_separator_stays_with_the_line_it_stands_in() -> None:
    """#58 (D-335): "ab" and "cd" set close, a graphic standing in "ab" (where its text ends,
    which is where "cd" starts): cut before "cd", the graphic stays with "ab"."""
    b = block("abcd ef\ngh", [("l1", 0), ("g", 2), ("l2", 2), ("l3", 5), ("l4", 8)])
    first, second = split_at(b, [2])
    assert (first.text, [(p.item, p.start) for p in first.parts]) == ("ab", [("l1", 0), ("g", 2)])
    assert (second.text, [(p.item, p.start) for p in second.parts]) == (
        "cd ef\ngh",
        [("l2", 0), ("l3", 3), ("l4", 6)],
    )


def test_a_graphic_before_a_line_at_the_block_start_stays_first() -> None:
    """A footnote rule stands before the note's first line, at 0 (#51): no cut moves it."""
    b = block("one\ntwo", [("r", 0), ("l1", 0), ("l2", 4)])
    first, second = split_at(b, [4])
    assert [(p.item, p.start) for p in first.parts] == [("r", 0), ("l1", 0)]
    assert [(p.item, p.start) for p in second.parts] == [("l2", 0)]


def piece(text: str, x0: float, x1: float, y0: float = 100.0, size: float = 10.0) -> TextLine:
    return TextLine(text, (TextRun(text, "Times", size),), Box(x0, y0, x1, y0 + size))


def test_read_rows_joins_pieces_only_where_the_page_prints_a_space() -> None:
    """A formula or table read row by row (#36): "a" with a subscript "i" set close, then
    "= b" after a space."""
    row = [piece("a", 100, 105), piece("i", 105.3, 108, 103, 7), piece("= b", 111, 125)]
    text, parts = read_rows(row, [], LayoutSettings())
    assert text == "ai = b"
    assert [(p.item, p.start) for p in parts] == [("a", 0), ("i", 1), ("= b", 3)]


def test_separators() -> None:
    size, space, reach = 10.0, 0.15, 2.0
    close = [piece("x", 0, 10), piece("y", 11, 20)]  # 1 pt: less than 0.15 em
    wide = [piece("x", 0, 10), piece("y", 11.5, 20)]  # 1.5 pt: 0.15 em
    stacked = [piece("x", 0, 10), piece("y", 0, 5), piece("z", 10.5, 20)]  # z after x's end
    far = [piece("x", 0, 50), piece("y", 29, 35)]  # 2.1 em back
    assert separators(close, size, space, reach) == ["", ""]
    assert separators(wide, size, space, reach) == ["", " "]
    assert separators(stacked, size, space, reach) == ["", "", ""]
    assert separators(far, size, space, reach) == ["", " "]
    fraction = [piece("x = 1", 0, 10), piece("22", 5, 13, 105), piece("t", 13.5, 16)]
    assert separators(fraction, size, space, reach) == ["", " ", ""]  # 1/22 is no "122"
    script = [piece("J1st", 0, 10), piece("0n", 5, 9, 105)]  # a letter or digit after
    assert separators(script, size, space, reach) == ["", ""]  # a letter: no number to misread
    assert separators(close, 0.0, space, reach) == ["", " "]  # no sizes: a space, as before
    unplaced = [TextLine("u", (TextRun("u"),)), TextLine("v", (TextRun("v"),))]
    assert separators(unplaced, size, space, reach) == ["", " "]  # EPUB, text: as before
    assert separators([], size, space, reach) == []


def _liu_fraction() -> tuple[TextLine, TextLine, Box]:
    """Liu p2 "µB = eℏ over 2me . The": the numerator ends one piece, the denominator starts
    the next one 1.2 em back under it, a 0.8 pt fraction bar between them (boxes as
    extraction gives them)."""
    numerator = TextLine(
        "p2-l107",
        (
            TextRun("Bohr-magneton µB =", "CMR10", 10.0, box=Box(388.3, 339.7, 518.0, 348.6)),
            TextRun(" e", "CMMI7", 7.0, box=Box(525.3, 337.8, 529.1, 344.0)),
            TextRun("ℏ", "CMR7", 7.0, box=Box(529.1, 337.8, 533.5, 342.7)),
        ),
        Box(388.3, 337.8, 533.5, 349.4),
    )
    denominator = TextLine(
        "p2-l108",
        (
            TextRun("2me", "CMR7", 7.0, box=Box(521.9, 345.2, 536.3, 352.0)),
            TextRun(" . The", "CMR10", 10.0, box=Box(538.0, 339.7, 562.1, 348.5)),
        ),
        Box(521.9, 339.7, 562.1, 352.0),
    )
    return numerator, denominator, Box(521.5, 343.7, 537.2, 344.5)


def test_a_piece_under_a_fraction_bar_keeps_a_space() -> None:
    """#202 (D-575): the denominator of an inline fraction starts back under its numerator
    in the piece before; with the bar drawn between them it keeps a space ("eℏ 2me"), so
    the voice never reads the two as one word ("eℏ2me")."""
    size, space, reach = 10.0, 0.15, 2.0
    numerator, denominator, bar = _liu_fraction()
    row = [numerator, denominator]
    assert separators(row, size, space, reach) == ["", ""]  # no bar known: as before
    assert separators(row, size, space, reach, [bar]) == ["", " "]
    thick = Box(521.5, 342.0, 537.2, 345.0)  # 3 pt: a frame or a figure's line, no bar
    aside = Box(400.0, 343.7, 420.0, 344.5)  # under other letters, not the numerator's
    low = Box(521.5, 360.0, 537.2, 360.8)  # well below both pieces
    for other in (thick, aside, low):
        assert separators(row, size, space, reach, [other]) == ["", ""]
    # a script stacked under a superscript with no bar stays joined (D-277)
    script = [piece("J1st", 0, 10), piece("0n", 5, 9, 105)]
    assert separators(script, size, space, reach, [Box(30, 104, 40, 104.4)]) == ["", ""]


def test_a_numerator_with_a_raised_superscript_keeps_its_space() -> None:
    """#323, liu p2 "∂E^m_q over ∂q": the reach to the bar is measured from
    the numerator letter nearest it (the subscript q, 0.02 em above), not from its
    superscript m, here lifted 2 pt more than liu prints it (0.72 em above the bar)."""
    numerator = TextLine(
        "p2-l122",
        (
            TextRun(" =", "CMR10", 10.0, box=Box(377.6, 413.3, 385.3, 422.2)),
            TextRun(" ∂E", "CMMI7", 7.0, box=Box(396.1, 409.2, 406.6, 415.5)),
            TextRun("m", "CMMI5", 5.0, box=Box(407.0, 405.7, 413.1, 410.1)),
            TextRun("q", "CMMI5", 5.0, box=Box(406.6, 412.7, 410.2, 417.1)),
        ),
        Box(377.6, 405.7, 413.1, 422.2),
    )
    denominator = TextLine(
        "p2-l123",
        (
            TextRun("∂q", "CMMI7", 7.0, box=Box(400.5, 418.7, 408.9, 425.0)),
            TextRun(" δ", "CMMI10", 10.0, box=Box(414.8, 413.1, 419.3, 422.2)),
        ),
        Box(400.5, 413.1, 419.3, 425.0),
    )
    bar = Box(395.7, 417.3, 414.0, 418.1)
    assert separators([numerator, denominator], 10.0, 0.15, 2.0, [bar]) == ["", " "]


def test_an_underlined_piece_keeps_a_subscript_after_it_joined() -> None:
    """#323: an underline under a word does not stand between the word and
    a subscript tucked back under its last letter (the subscript's middle is above it)."""
    word = TextLine(
        "w", (TextRun("word", "Times", 10.0, box=Box(0, 100, 30, 110)),), Box(0, 100, 30, 110)
    )
    script = TextLine(
        "q",
        (TextRun("q", "Times", 7.0, box=Box(29.5, 104.5, 33, 111.5)),),
        Box(29.5, 104.5, 33, 111.5),
    )
    underline = Box(0, 109.5, 30, 109.9)
    assert separators([word, script], 10.0, 0.15, 2.0, [underline]) == ["", ""]


@given(
    st.lists(
        st.tuples(st.floats(0, 500), st.floats(0, 60), st.floats(-5, 5)), min_size=1, max_size=8
    ),
    st.lists(
        st.tuples(st.floats(0, 500), st.floats(90, 120), st.floats(0, 60), st.floats(0, 3)),
        max_size=4,
    ),
    st.floats(0.0, 20.0),
)
def test_fraction_bars_only_add_spaces(boxes: list, bars: list, size: float) -> None:
    """A bar keeps a space where there was none; it never takes one away."""
    row = [piece(f"p{k}", x, x + w, 100 + dy) for k, (x, w, dy) in enumerate(boxes)]
    drawn = [Box(x, y, x + w, y + h) for x, y, w, h in bars]
    without = separators(row, size, 0.15, 2.0)
    found = separators(row, size, 0.15, 2.0, drawn)
    assert len(found) == len(without)
    assert all(b == " " for a, b in zip(without, found, strict=True) if a == " ")


@given(
    st.lists(
        st.tuples(st.floats(0, 500), st.floats(0, 60), st.floats(-5, 5)), min_size=1, max_size=8
    ),
    st.floats(0.0, 20.0),
)
def test_separators_are_a_space_or_nothing(boxes: list, size: float) -> None:
    row = [piece(f"p{k}", x, x + w, 100 + dy) for k, (x, w, dy) in enumerate(boxes)]
    found = separators(row, size, 0.15, 2.0)
    assert len(found) == len(row)
    assert found[0] == ""
    assert set(found[1:]) <= {"", " "}
