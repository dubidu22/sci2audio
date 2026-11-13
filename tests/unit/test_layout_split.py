"""Keeping some of a block's parts (layout `split.kept`): each kept line's text as found,
graphics holding no text wherever they stand (review of PR #61). Cutting a block and reading
lines row by row, with pieces of a printed line joined by a space only where the page prints
one (#36)."""

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
