"""Keeping some of a block's parts (layout `split.kept`): each kept line's text as found,
graphics holding no text wherever they stand (review of PR #61)."""

from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Block, BlockKind, Part
from sci2audio.layout.split import kept, part_ends


def block(text: str, parts: list[tuple[str, int]]) -> Block:
    return Block(BlockKind.PARAGRAPH, text, tuple(Part(item, start) for item, start in parts))


def test_a_line_before_a_graphic_at_the_text_end_keeps_its_last_letter() -> None:
    """liu p2-l69 lost its final comma when a rule stood at the end of its block."""
    b = block("first line\nsecond line,", [("l1", 0), ("l2", 11), ("d1", 23)])
    assert kept(b, b.parts[1:], {"l1", "l2"}).text == "second line,"
    assert part_ends(b, {"l1", "l2"}) == {"l1": 10, "l2": 23}


def test_a_graphic_where_a_line_ends_does_not_end_it_early() -> None:
    b = block("one\ntwo\nthree", [("l1", 0), ("d1", 3), ("l2", 4), ("l3", 8)])
    out = kept(b, [b.parts[0], b.parts[1], b.parts[3]], {"l1", "l2", "l3"})
    assert out.text == "one\nthree"
    assert [(p.item, p.start) for p in out.parts] == [("l1", 0), ("d1", 3), ("l3", 4)]


@st.composite
def blocks(draw: st.DrawFn) -> tuple[Block, dict[str, str]]:
    """A block of lines joined by a break or a space, with graphics standing at a line's
    start or end, or at the text's end."""
    words = st.text(alphabet="abcxyz,.() ", min_size=0, max_size=8)
    texts = draw(st.lists(words, min_size=1, max_size=6))
    text, parts, lines = "", [], {}
    for k, line in enumerate(texts):
        if k:
            text += draw(st.sampled_from(["\n", " "]))
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
    out = kept(b, keep, set(lines))
    for before, after in zip(keep, out.parts, strict=True):
        assert before.item == after.item
        if before.item in lines:
            line = lines[before.item]
            assert out.text[after.start : after.start + len(line)] == line
