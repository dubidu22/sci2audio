"""Footnote marks tied to their notes by link tags (#189, D-420 to D-428): EPUB and Markdown
noterefs, notes on other pages, introductions from the mark, back-links."""

import time

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import Block, BlockKind, Document, EditKind, Span
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import Category, FootnoteStep, StepContext, run_steps, spoken_text

EN = StepContext("en")
NOTEREF = ("sup", "a", "#fnref1", "role:doc-noteref")
EPUB_NOTEREF = ("a", "#noteref-1", "epub:noteref", "role:doc-noteref")
BACKLINK = ("a", "epub:backlink", "role:doc-backlink", "link:b0l0")
ARROW = "↩︎"  # "↩︎", as Standard Ebooks prints a back-link


def to(block: int, tags: tuple[str, ...] = NOTEREF) -> tuple[str, ...]:
    """A noteref's tags, linking to the first line of `block`."""
    return (*tags, f"link:b{block}l0")


def at(text: str, part: str, tags: tuple[str, ...], nth: int = 0) -> tuple[int, int, tuple]:
    """The tagged range of the `nth` occurrence of `part` in `text`."""
    start = -1
    for _ in range(nth + 1):
        start = text.index(part, start + 1)
    return (start, start + len(part), tags)


def read(document: Document, **switches: object) -> list[str]:
    run = run_steps(document, StepContext(document.language), strict=True, **switches)
    return [
        spoken_text(p for p in run.script() if p.span.block == index)
        for index in range(len(document.blocks))
    ]


def removed(document: Document) -> list[str]:
    """The text of each remove-edit of the footnote step, in order."""
    edits = sorted(
        (e for e in FootnoteStep().find(document, EN) if e.kind is EditKind.REMOVE),
        key=lambda e: (e.span.block, e.span.start),
    )
    return [document.text_of(e.span) for e in edits]


# ---- linked marks -------------------------------------------------------------------------


def test_a_mark_is_left_out_when_its_note_is_on_another_page() -> None:
    text = "It sloped at all.1 The end was lit."
    document = make_document(
        [(BlockKind.PARAGRAPH, text), (BlockKind.FOOTNOTE, "It may be a hill.")],
        tags={0: [at(text, "1", to(1, EPUB_NOTEREF))]},  # no superscript, as Standard Ebooks
        pages={1: 3},
    )
    assert read(document) == ["It sloped at all. The end was lit.", "Footnote 1. It may be a hill."]


def test_every_mark_of_a_note_is_left_out_and_the_first_introduces_it() -> None:
    first, second, third = "Do footnotes2 help?", "Kept up.2", "Both.b"
    document = make_document(
        [
            (BlockKind.LIST_ITEM, first),
            (BlockKind.PARAGRAPH, second),
            (BlockKind.HEADING, third),
            (BlockKind.FOOTNOTE, "A note."),
        ],
        tags={
            0: [at(first, "2", to(3))],
            1: [at(second, "2", to(3))],
            2: [at(third, "b", to(3))],
        },
    )
    assert read(document) == ["Do footnotes help?", "Kept up.", "Both.", "Footnote 2. A note."]


@pytest.mark.parametrize(
    ("mark", "spoken"),
    [
        ("1", "Footnote 1."),
        ("12a", "Footnote 12a."),
        ("[1]", "Footnote 1."),  # D-422
        ("(12)", "Footnote 12."),
        ("*", "Footnote."),  # a symbol is not read (D-144)
        ("[*]", "Footnote."),
        ("{1}", "Footnote."),  # not brackets or parentheses
        ("Note 3", "Footnote."),
    ],
)
def test_a_note_is_introduced_by_its_mark(mark: str, spoken: str) -> None:
    text = f"The effect.{mark} It held."
    document = make_document(
        [(BlockKind.PARAGRAPH, text), (BlockKind.FOOTNOTE, "Measured twice.")],
        tags={0: [at(text, mark, to(1))]},
    )
    assert read(document) == ["The effect. It held.", f"{spoken} Measured twice."]


@pytest.mark.parametrize(
    "tags",
    [
        ("sup", "a", "role:doc-noteref"),  # no link
        ("sup", "a", "role:doc-noteref", "href:https://example.org/#fn1"),  # did not resolve
        ("sup", "a", "role:doc-noteref", "link:b2l0"),  # links to a paragraph
        ("sup", "a", "role:doc-noteref", "link:p9-l9"),  # links to no item here
        ("sup", "a", "link:b1l0"),  # an ordinary link to the note: not a noteref
    ],
)
def test_a_noteref_that_does_not_reach_a_note_is_read_as_printed(tags: tuple[str, ...]) -> None:
    text = "See the table.1"
    document = make_document(
        [
            (BlockKind.PARAGRAPH, text),
            (BlockKind.FOOTNOTE, "A note."),
            (BlockKind.PARAGRAPH, "1 A paragraph."),
        ],
        tags={0: [at(text, "1", tags)]},
    )
    assert read(document) == ["See the table.1", "Footnote. A note.", "1 A paragraph."]


def test_the_printed_label_rule_never_takes_a_noteref() -> None:
    # a superscript after a word, with a labelled note on the page: D-143 would take it,
    # but it is a noteref that links elsewhere, so it is read as printed (D-423, D-428)
    text = "The effect.1"
    document = make_document(
        [(BlockKind.PARAGRAPH, text), Block(BlockKind.FOOTNOTE, "1 A note.", label="1")],
        tags={0: [at(text, "1", ("sup", "a", "role:doc-noteref", "link:p9-l9"))]},
    )
    assert read(document) == ["The effect.1", "Footnote 1. A note."]


def test_a_mark_in_a_note_is_left_out_but_not_one_linking_to_its_own_note() -> None:
    first, second = "See also note 2.2", "Back to this one.1"
    document = make_document(
        [
            (BlockKind.FOOTNOTE, first),
            (BlockKind.FOOTNOTE, second),
            (BlockKind.PARAGRAPH, "Body.1"),
        ],
        tags={
            0: [at(first, "2", to(1), nth=1)],
            1: [at(second, "1", to(1))],
            2: [at("Body.1", "1", to(0))],
        },
    )
    assert read(document) == [
        "Footnote 1. See also note 2.",
        "Footnote 2. Back to this one.1",
        "Body.",
    ]


def test_marks_in_furniture_and_placeholders_are_not_looked_at() -> None:
    document = make_document(
        [
            Block(BlockKind.FURNITURE, "Running head1"),
            (BlockKind.TABLE, "x 1"),
            (BlockKind.FOOTNOTE, "A note."),
        ],
        tags={0: [at("Running head1", "1", to(2))], 1: [at("x 1", "1", to(2))]},
    )
    assert removed(document) == []


def test_a_mark_set_over_two_runs_is_one_edit_and_only_its_letters_go() -> None:
    text = "Results 1a hold."
    document = make_document(
        [(BlockKind.PARAGRAPH, text), (BlockKind.FOOTNOTE, "A note.")],
        tags={0: [(7, 9, to(1)), (9, 10, ("b", *to(1)))]},  # " 1" then "a", one link
    )
    edits = [e for e in FootnoteStep().find(document, EN) if e.kind is EditKind.REMOVE]
    assert [(e.span, e.reason) for e in edits] == [
        (
            Span(0, 8, 10),
            "footnote mark 1a is not read; the note is read where the file places it (Q2, D-414)",
        )
    ]
    assert read(document)[1] == "Footnote 1a. A note."


def test_two_marks_side_by_side_with_different_links_are_two_edits() -> None:
    text = "Results12 hold."
    document = make_document(
        [(BlockKind.PARAGRAPH, text), (BlockKind.FOOTNOTE, "One."), (BlockKind.FOOTNOTE, "Two.")],
        tags={0: [(7, 8, to(1)), (8, 9, to(2))]},
    )
    assert removed(document) == ["1", "2"]
    assert read(document) == ["Results hold.", "Footnote 1. One.", "Footnote 2. Two."]


def test_a_blank_noteref_is_nothing() -> None:
    text = "Results hold."
    document = make_document(
        [(BlockKind.PARAGRAPH, text), (BlockKind.FOOTNOTE, "A note.")],
        tags={0: [(7, 8, to(1))]},  # the space
    )
    assert removed(document) == []
    assert read(document)[1] == "Footnote. A note."


def test_a_labelled_note_keeps_its_introduction_and_its_mark_goes_once() -> None:
    # layout labels a note whose text starts with its noteref's mark (D-406)
    text = "Noise1 and sound1 here."
    document = make_document(
        [(BlockKind.PARAGRAPH, text), Block(BlockKind.FOOTNOTE, "1. Measured.", label="1")],
        tags={0: [at(text, "1", to(1)), at(text, "1", ("sup",), nth=1)]},
    )
    # the noteref is the mark; the printed-label rule takes no second "1" on the page
    assert read(document) == ["Noise and sound1 here.", "Footnote 1. Measured."]


# ---- back-links -----------------------------------------------------------------------------


def test_a_back_link_is_left_out_with_the_space_before_it() -> None:
    text = f"It may be a hill. —Ed. {ARROW}"
    document = make_document(
        [(BlockKind.PARAGRAPH, "Body.1"), (BlockKind.FOOTNOTE, text)],
        tags={0: [at("Body.1", "1", to(1))], 1: [at(text, ARROW, BACKLINK)]},
    )
    edits = [
        e
        for e in FootnoteStep().find(document, EN)
        if e.kind is EditKind.REMOVE and e.span.block == 1
    ]
    assert [(document.text_of(e.span), e.reason) for e in edits] == [
        (f" {ARROW}", "the back-link of a footnote is not read")
    ]
    assert read(document)[1] == "Footnote 1. It may be a hill. —Ed."


def test_back_links_side_by_side_are_one_edit_and_apart_are_two() -> None:
    text = f"One. {ARROW}{ARROW} Two. {ARROW}"
    first = text.index(ARROW)
    document = make_document(
        [(BlockKind.FOOTNOTE, text)],
        tags={
            0: [
                (first, first + 2, BACKLINK),
                (first + 2, first + 4, BACKLINK),
                at(text, ARROW, BACKLINK, nth=2),
            ]
        },
    )
    assert removed(document) == [f" {ARROW}{ARROW}", f" {ARROW}"]
    assert read(document) == ["Footnote. One. Two."]


def test_a_back_link_ending_in_a_space_leaves_that_space_to_the_next_one() -> None:
    text = f"Note {ARROW}  {ARROW}"  # the first back-link run holds the space after it
    document = make_document(
        [(BlockKind.FOOTNOTE, text)], tags={0: [(5, 8, BACKLINK), (9, 11, BACKLINK)]}
    )
    assert removed(document) == [f" {ARROW}", f"  {ARROW}"]
    assert read(document) == ["Footnote. Note"]


def test_a_back_link_at_the_start_of_a_note_comes_before_its_introduction() -> None:
    text = f"{ARROW} The note."
    document = make_document(
        [(BlockKind.PARAGRAPH, "Body.1"), (BlockKind.FOOTNOTE, text)],
        tags={0: [at("Body.1", "1", to(1))], 1: [at(text, ARROW, BACKLINK)]},
    )
    assert read(document)[1] == "Footnote 1. The note."


def test_a_note_of_only_a_back_link_gets_no_introduction() -> None:
    document = make_document(
        [(BlockKind.PARAGRAPH, "Body.1"), (BlockKind.FOOTNOTE, f"  {ARROW} ")],
        tags={0: [at("Body.1", "1", to(1))], 1: [at(f"  {ARROW} ", ARROW, BACKLINK)]},
    )
    assert read(document) == ["Body.", ""]


def test_a_back_link_also_tagged_as_a_noteref_is_a_back_link() -> None:
    text = f"The note. {ARROW}"
    both = ("a", "epub:noteref", "epub:backlink", "link:b1l0")
    document = make_document(
        [(BlockKind.FOOTNOTE, text), (BlockKind.FOOTNOTE, "Another.")],
        tags={0: [at(text, ARROW, both)]},
    )
    assert removed(document) == [f" {ARROW}"]
    assert read(document) == ["Footnote. The note.", "Footnote. Another."]


def test_a_back_link_outside_a_note_is_read() -> None:
    text = f"Back {ARROW}"
    document = make_document([(BlockKind.PARAGRAPH, text)], tags={0: [at(text, ARROW, BACKLINK)]})
    assert removed(document) == []


# ---- the switches ---------------------------------------------------------------------------


def epub_like() -> Document:
    text, note = "Sloped.1 The end.", f"A hill. {ARROW}"
    return make_document(
        [(BlockKind.PARAGRAPH, text), (BlockKind.FOOTNOTE, note)],
        tags={0: [at(text, "1", to(1, EPUB_NOTEREF))], 1: [at(note, ARROW, BACKLINK)]},
        pages={1: 2},
    )


def test_switching_footnotes_off_reads_marks_back_links_and_notes_as_printed() -> None:
    assert read(epub_like(), switched_off={Category.FOOTNOTES, Category.FOOTNOTE_TEXTS}) == [
        "Sloped.1 The end.",
        f"A hill. {ARROW}",
    ]


def test_turning_footnote_texts_on_leaves_the_note_and_the_mark_out() -> None:
    assert read(epub_like(), switched_off=()) == ["Sloped. The end.", ""]


# ---- properties -----------------------------------------------------------------------------

_KINDS = [
    BlockKind.PARAGRAPH,
    BlockKind.LIST_ITEM,
    BlockKind.HEADING,
    BlockKind.FOOTNOTE,
    BlockKind.FOOTNOTE,
    BlockKind.FURNITURE,
    BlockKind.FORMULA,
]
_PIECES = st.sampled_from(["word", " ", "1", "12", "[3]", "*", "†", ARROW, "Footnote", ".", ""])


@st.composite
def linked_documents(draw: st.DrawFn) -> Document:
    """Documents of one-line blocks holding noterefs that link to random blocks (or to
    nothing), back-links, superscripts and printed labels, on pages that never go back."""
    count = draw(st.integers(1, 7))
    blocks, tags, pages, page = [], {}, {}, 1
    for number in range(count):
        kind = draw(st.sampled_from(_KINDS))
        text, ranges = "", []
        for _ in range(draw(st.integers(0, 6))):
            piece = draw(_PIECES)
            role = draw(st.sampled_from(["plain", "noteref", "backlink", "sup", "epub", "both"]))
            if piece and role != "plain":
                link = f"link:b{draw(st.integers(0, count))}l0"  # count: links to nothing
                tag = {
                    "noteref": ("sup", "role:doc-noteref", link),
                    "epub": ("epub:noteref", link),
                    "backlink": ("role:doc-backlink", link),
                    "both": ("epub:noteref", "epub:backlink", link),
                    "sup": ("sup",),
                }[role]
                ranges.append((len(text), len(text) + len(piece), tag))
            text += piece
        label = ""
        if kind is BlockKind.FOOTNOTE and draw(st.booleans()):
            label = text.split()[0] if text.split() else ""
        blocks.append(Block(kind, text, label=label))
        tags[number] = ranges
        page += draw(st.integers(0, 1))
        pages[number] = page
    return make_document(blocks, tags=tags, pages=pages)


@given(linked_documents())
def test_the_step_keeps_the_contract_on_linked_documents(document: Document) -> None:
    check_text_step(FootnoteStep(), [document], allow_ask=False)  # spans, overlaps, idempotent


@given(linked_documents())
def test_every_removed_letter_is_in_a_noteref_a_back_link_or_a_superscript(
    document: Document,
) -> None:
    items = document.content.items()
    for edit in FootnoteStep().find(document, EN):
        if edit.kind is not EditKind.REMOVE:
            continue
        block = document.blocks[edit.span.block]
        tagged: set[int] = set()  # positions in the block of runs the step may remove
        for part in block.parts:
            offset = part.start
            for run in items[part.item][1].runs:
                if {"role:doc-noteref", "epub:noteref", "role:doc-backlink", "sup"} & set(run.tags):
                    tagged.update(range(offset, offset + len(run.text)))
                offset += len(run.text)
        for position in range(edit.span.start, edit.span.end):
            assert position in tagged or block.text[position].isspace()
    run_steps(document, EN, strict=True)  # the whole pipeline accepts it


def test_many_marks_and_notes_take_linear_time() -> None:
    def sized(count: int) -> Document:
        text = "word1 " * count
        notes = [(BlockKind.FOOTNOTE, f"Note {n}.") for n in range(count)]
        ranges = [(6 * n + 4, 6 * n + 5, to(1 + n)) for n in range(count)]
        return make_document([(BlockKind.PARAGRAPH, text), *notes], tags={0: ranges})

    def seconds(document: Document) -> float:
        start = time.perf_counter()
        FootnoteStep().find(document, EN)
        return time.perf_counter() - start

    small, large = seconds(sized(2_000)), seconds(sized(20_000))
    assert large < 2.0
    assert large < 25 * max(small, 1e-3)  # ten times the work: not a hundred times the time
