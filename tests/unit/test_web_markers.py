"""The v1.3 markers file, read only since the captures replace it (#474, D-728, #887): the
file as v1.3 wrote it (the tests' own copy of v1.3's writer and reader), the library's
count of it, which only the carry-over in `app.captures` reads, and finding a sentence
again in a changed document, which the captures use (#397)."""

from __future__ import annotations

import errno
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from web_helpers import (
    FILE_LIMIT,
    MAX_MARKERS,
    NOTE_LIMIT,
    Marker,
    MarkerError,
    MarkerLimit,
    MarkersBroken,
    MarkersTooLarge,
    markers_of,
    markers_text,
    note_problem,
    read_markers,
)

from sci2audio.app import files
from sci2audio.app.captures import (
    CAPTURES,
    MARKERS,
    MarkersNotCarried,
    load_captures,
    peek_captures,
)
from sci2audio.core import Document, Span, apply_edits
from sci2audio.testing.documents import make_document
from sci2audio.textprep import cut_utterances
from sci2audio.web import markers as module
from sci2audio.web.captures import CarryOverUnsaved
from sci2audio.web.captures import load as captures_load
from sci2audio.web.markers import Anchor, State, anchor_of, count_captures, locate

DOC = "0123456789abcdef"
FIRST = "It fell by twelve points on early shifts."
SECOND = "Naps were not counted."
TEXT = f"{FIRST} {SECOND}"


def paper() -> Document:
    return make_document([("heading", "1 Results"), ("paragraph", TEXT)])


def first() -> Anchor:
    return Anchor(1, 0, len(FIRST), FIRST)


def second() -> Anchor:
    start = len(FIRST) + 1
    return Anchor(1, start, start + len(SECOND), SECOND)


@dataclass(frozen=True)
class Placed:
    """A marker where this audiobook reads it: the chunk it is shown on, or None."""

    marker: Marker
    chunk: int | None
    state: State


def place(markers: Sequence[Marker], document: Document, spans: Sequence[Span]) -> list[Placed]:
    """Each marker where this audiobook reads it, in reading order, as `locate` places
    captures."""
    return [
        Placed(marker, chunk, state)
        for marker, chunk, state in locate(markers, lambda m: m.anchor, document, spans)
    ]


def put(work: Path, markers: list[Marker]) -> bytes:
    """The markers file as v1.3 left it."""
    raw = markers_text(DOC, markers).encode("utf-8")
    (work / MARKERS).write_bytes(raw)
    return raw


@pytest.fixture
def work(tmp_path: Path) -> Path:
    folder = tmp_path / DOC
    folder.mkdir()
    return folder


# ---- the file --------------------------------------------------------------------------


def test_the_file_holds_every_field_as_v13_wrote_it(work: Path) -> None:
    marker = Marker("0123456789abcdef", "2026-11-01T09:00:00Z", "2026-11-01T09:05:00Z",
                    first(), "Check the second cohort.\nLine two: ✓")  # fmt: skip
    put(work, [marker])
    data = markers_of(work)
    assert data["format"] == "sci2audio-web-markers"
    assert data["version"] == 1
    assert data["document"] == DOC
    [entry] = data["markers"]
    assert entry == {
        "id": marker.id,
        "created": marker.created,
        "changed": marker.changed,
        "anchor": {"block": 1, "start": 0, "end": len(FIRST), "text": FIRST},
        "note": "Check the second cohort.\nLine two: ✓",
    }
    assert read_markers(work, DOC) == [marker]
    assert count_captures(work, DOC) == {"note": 1, "quote": 0, "mark": 0, "unread": None}


def test_no_file_is_no_markers_and_is_not_made_by_reading(work: Path) -> None:
    assert read_markers(work, DOC) == []
    assert count_captures(work, DOC) == {"note": 0, "quote": 0, "mark": 0, "unread": None}
    assert not (work / MARKERS).exists()


def test_the_limits_of_a_note_and_of_the_file() -> None:
    assert note_problem("x" * NOTE_LIMIT) is None
    assert note_problem("x" * (NOTE_LIMIT + 1))
    assert note_problem("a\x00b")
    many = [Marker(f"{n:016x}", "t", "t", first()) for n in range(MAX_MARKERS + 1)]
    with pytest.raises(MarkerLimit):
        markers_text(DOC, many)
    big = [Marker(f"{n:016x}", "t", "t", Anchor(1, 0, 1, "x" * 2000), "") for n in range(1500)]
    with pytest.raises(MarkersTooLarge):
        markers_text(DOC, big)


# ---- the guard: a file this version can't read is never written (D-728 ruling 1) -----------


def _valid() -> dict[str, Any]:
    return json.loads(markers_text(DOC, [Marker("a" * 16, "t", "t", first(), "mine")]))


BROKEN: dict[str, bytes] = {
    "not JSON": b"{not json",
    "not UTF-8": b"\xff\xfe{}",
    "deeply nested": b"[" * 100_000 + b"]" * 100_000,
    "a list": b"[]",
    "NaN": json.dumps({**_valid(), "version": float("nan")}).encode(),
    "another format": json.dumps({**_valid(), "format": "other"}).encode(),
    "another version": json.dumps({**_valid(), "version": 2}).encode(),
    "another document": json.dumps({**_valid(), "document": "f" * 16}).encode(),
    "an extra key": json.dumps({**_valid(), "more": 1}).encode(),
    "markers not a list": json.dumps({**_valid(), "markers": {}}).encode(),
    "a bad id": json.dumps(
        {**_valid(), "markers": [{**_valid()["markers"][0], "id": "XYZ"}]}
    ).encode(),
    "a bool block": json.dumps(
        {
            **_valid(),
            "markers": [
                {
                    **_valid()["markers"][0],
                    "anchor": {"block": True, "start": 0, "end": 1, "text": "x"},
                }
            ],
        }
    ).encode(),
    "an id twice": json.dumps({**_valid(), "markers": _valid()["markers"] * 2}).encode(),
    "a long note": json.dumps(
        {**_valid(), "markers": [{**_valid()["markers"][0], "note": "x" * (NOTE_LIMIT + 1)}]}
    ).encode(),
    # more markers than a document holds, each one valid, the file well under 2 MB
    "more than 2000 markers": json.dumps(
        {
            **_valid(),
            "markers": [
                {**_valid()["markers"][0], "id": f"{n:016x}"} for n in range(MAX_MARKERS + 1)
            ],
        }
    ).encode(),
    # a file that reads well but is past the limit: refused for its size alone
    "too large": json.dumps(_valid()).encode() + b" " * FILE_LIMIT,
}


@pytest.mark.parametrize("case", sorted(BROKEN))
def test_a_file_this_version_cant_read_is_refused_and_left_as_it_is(work: Path, case: str) -> None:
    """The library counts it as a file it can't read (#418), and reading changes nothing."""
    path = work / MARKERS
    path.write_bytes(BROKEN[case])
    before = path.read_bytes()
    with pytest.raises(MarkersBroken):
        read_markers(work, DOC)
    assert count_captures(work, DOC)["unread"] == "markers"
    assert path.read_bytes() == before
    assert sorted(p.name for p in work.iterdir()) == [MARKERS]


@pytest.mark.skipif(sys.platform == "win32", reason="links need rights on Windows")
def test_a_link_in_the_markers_place_is_never_followed(work: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text(markers_text(DOC, []), encoding="utf-8")
    (work / MARKERS).symlink_to(elsewhere)
    before = elsewhere.read_bytes()
    with pytest.raises(MarkersBroken):
        read_markers(work, DOC)
    assert count_captures(work, DOC)["unread"] == "markers"
    assert (work / MARKERS).is_symlink()
    assert elsewhere.read_bytes() == before


def _surrogate(field: str) -> bytes:
    """A file v1.3 reads, with a lone surrogate (no UTF-8 form) in one of its texts."""
    data = _valid()
    entry = data["markers"][0]
    if field == "sentence":
        entry["anchor"]["text"] = "\udfff" + entry["anchor"]["text"]
    else:
        entry[field] = "\ud800" + entry[field]
    return json.dumps(data).encode("utf-8")  # escaped as \ud800, as v1.3 accepts it


@pytest.mark.parametrize("field", ["note", "sentence", "created", "changed"])
def test_markers_the_carry_over_refuses_count_as_unread_as_a_load_finds_them(
    work: Path, field: str
) -> None:
    """#887: v1.3 reads them, but the capture model refuses a lone surrogate (#786), so a
    load can't carry them over; the library says the same, never counts them."""
    raw = _surrogate(field)
    (work / MARKERS).write_bytes(raw)
    assert len(read_markers(work, DOC)) == 1  # v1.3 reads it
    with pytest.raises(MarkersNotCarried):
        peek_captures(work, DOC)
    assert count_captures(work, DOC) == {"note": 0, "quote": 0, "mark": 0, "unread": "markers"}
    assert (work / MARKERS).read_bytes() == raw
    assert sorted(p.name for p in work.iterdir()) == [MARKERS]


@pytest.mark.parametrize(("unreadable", "named"), [(CAPTURES, "captures"), (MARKERS, "markers")])
def test_a_file_that_cant_be_read_at_all_is_named_in_the_count(
    work: Path, monkeypatch: pytest.MonkeyPatch, unreadable: str, named: str
) -> None:
    put(work, [Marker("a" * 16, "t", "t", first(), "mine")])
    if unreadable == CAPTURES:
        load_captures(work, DOC)  # carried over: captures.json beside markers.json
    real = Path.read_bytes

    def read_bytes(self: Path) -> bytes:
        if self.name == unreadable:
            raise PermissionError(errno.EACCES, "Permission denied")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    assert count_captures(work, DOC) == {"note": 0, "quote": 0, "mark": 0, "unread": named}


def test_only_the_carry_over_reads_the_markers_file(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#887: `app.captures` is the one reader of markers.json, so the library's counts, a
    load and its full-disk check can't judge one file in two ways."""
    put(work, [Marker("a" * 16, "t", "t", first(), "mine")])
    readers: list[str] = []
    real = Path.open

    def opening(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == MARKERS:
            frame = sys._getframe(1)
            while frame.f_globals["__name__"].startswith("pathlib"):
                frame = frame.f_back  # type: ignore[assignment]
            readers.append(frame.f_globals["__name__"])
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opening)
    assert count_captures(work, DOC)["note"] == 1

    def full(partial: Path, content: str | bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(CarryOverUnsaved):  # it asks again whether the write was the carry-over
        captures_load(work, DOC)
    assert readers
    assert set(readers) == {"sci2audio.app.captures"}


def test_a_file_v13_could_not_read_back_is_never_made() -> None:
    """A NUL or a note past the limit, or an empty anchor text, would make a file no
    version reads."""
    for note in ("a\x00b", "x" * (NOTE_LIMIT + 1)):
        with pytest.raises(MarkerError):
            markers_text(DOC, [Marker("b" * 16, "t", "t", first(), note)])
    bad = Marker("b" * 16, "t", "t", Anchor(1, 0, 1, ""))  # an empty anchor text
    with pytest.raises(MarkerError):
        markers_text(DOC, [bad])


# ---- finding a marker again (plan section 3, step 1 to 5) ----------------------------------------


def spans_of(document: Document) -> list[Span]:
    """One chunk per sentence of TEXT-like blocks: cut at ". " (enough for these tests)."""
    found = []
    for number, block in enumerate(document.blocks):
        start = 0
        text = block.text
        while start < len(text):
            end = text.find(". ", start)
            end = len(text) if end < 0 else end + 1
            found.append(Span(number, start, end))
            start = end + 1
    return found


def one(document: Document, anchor: Anchor, spans: list[Span] | None = None) -> Any:
    marker = Marker("a" * 16, "t", "t", anchor, "a note")
    [placed] = place([marker], document, spans if spans is not None else spans_of(document))
    return placed


def text_of(document: Document, spans: list[Span], placed: Any) -> str:
    span = spans[placed.chunk]
    return document.blocks[span.block].text[span.start : span.end]


def test_the_same_place_with_the_same_text_is_found() -> None:
    document = paper()
    spans = spans_of(document)
    placed = one(document, second(), spans)
    assert placed.state == "found"
    assert text_of(document, spans, placed) == SECOND


def test_a_block_put_before_it_moves_the_marker_with_its_text() -> None:
    document = make_document(
        [("heading", "1 Results"), ("paragraph", "A new paragraph."), ("paragraph", TEXT)]
    )
    spans = spans_of(document)
    placed = one(document, second(), spans)
    assert placed.state == "found"
    assert spans[placed.chunk].block == 2
    assert text_of(document, spans, placed) == SECOND


def test_a_changed_line_break_or_a_joined_hyphen_does_not_lose_the_sentence() -> None:
    printed = "It fell by twelve po-\nints on early\nshifts. Naps were not counted."
    stored = Anchor(1, 0, len(FIRST), "It fell by twelve points on early shifts.")
    document = make_document([("heading", "1 Results"), ("paragraph", printed)])
    spans = spans_of(document)
    placed = one(document, stored, spans)
    assert placed.state == "found"
    assert text_of(document, spans, placed).startswith("It fell by twelve po-\nints")


def test_a_sentence_now_cut_in_two_goes_to_the_piece_it_overlaps_most() -> None:
    document = paper()
    pieces = [Span(1, 0, 12), Span(1, 12, len(FIRST)), Span(1, len(FIRST) + 1, len(TEXT))]
    placed = one(document, first(), pieces)
    assert (placed.state, placed.chunk) == ("found", 1)  # 29 of its characters, not 12


# a sentence of about 350 characters (cut at 300, one utterance at 400) and one of about 650
# (three pieces at 300, two at 400), between two short ones
_MID = (
    "The teachers who took part in the second round of the study were asked to keep a diary "
    "of every lesson in which they used the new material, to note what worked well and what "
    "did not, and to send it back at the end of each month, so that the team could see how "
    "the use of the material changed over the school year and where help was needed."
)
_LONG = (
    "The second experiment, which we ran on a larger set of recordings from three different "
    "sites over a period of several months and with the help of two new assistants who had not "
    "taken part before, used the same procedure as the first one and the same group of "
    "listeners, but this time the recordings were played back on a cheap, small, "
    "battery-powered loudspeaker in a quiet room at the back of the old building, and the "
    "listeners, who had heard the same recordings on good headphones a week before, were asked "
    "to say which of the two versions they liked better and to write down in a few words what "
    "made the difference for them."
)


def test_a_marker_in_a_sentence_whose_cut_moves_or_goes_lands_on_that_sentence() -> None:
    """#494 (D-743 A2): an audiobook made again after the cut limit went from 300 to 400
    characters. A marker set on any piece of the old cut, or on the whole sentence (#480),
    is found on a chunk of the same sentence: the one-utterance sentence, or the new piece
    it overlaps most."""
    text = f"A short one first. {_MID} {_LONG} A short one last."
    document = make_document([("paragraph", text)])
    script = apply_edits(document, [])

    def chunks(limit: int) -> list[Span]:
        return [u.span for u in cut_utterances(document, script, max_chars=limit) if not u.pause]

    old, new = chunks(300), chunks(400)
    mid_at, long_at = text.index(_MID), text.index(_LONG)

    def sentence_of(span: Span) -> str:
        for sentence, at in ((_MID, mid_at), (_LONG, long_at)):
            if at <= span.start < at + len(sentence):
                return sentence
        return ""

    assert 300 < len(_MID) <= 400 < len(_LONG)
    assert len([s for s in old if mid_at <= s.start < long_at]) == 2  # cut at 300
    assert [(s.start, s.end) for s in new if mid_at <= s.start < long_at] == [
        (mid_at, mid_at + len(_MID))
    ]  # whole at 400
    long_old = [(s.start, s.end) for s in old if sentence_of(s) == _LONG]
    long_new = [(s.start, s.end) for s in new if sentence_of(s) == _LONG]
    assert (len(long_old), len(long_new)) == (3, 2)  # the cuts moved
    wholes = [Span(0, mid_at, mid_at + len(_MID)), Span(0, long_at, long_at + len(_LONG))]
    for span in [s for s in old if sentence_of(s) in (_MID, _LONG)] + wholes:
        placed = one(document, anchor_of(document, span), new)
        assert placed.state == "found"
        assert sentence_of(new[placed.chunk]) == sentence_of(span)


def test_two_sentences_now_joined_into_one_show_both_markers_there() -> None:
    document = paper()
    joined = [Span(0, 0, 9), Span(1, 0, len(TEXT))]
    markers = [
        Marker("a" * 16, "t", "t", first()),
        Marker("b" * 16, "t", "t", second()),
    ]
    placed = place(markers, document, joined)
    assert [(p.marker.id, p.chunk, p.state) for p in placed] == [
        ("a" * 16, 1, "found"),
        ("b" * 16, 1, "found"),
    ]


def test_the_same_sentence_twice_takes_the_one_nearest_its_block() -> None:
    document = make_document(
        [("paragraph", SECOND)] + [("paragraph", "Filler.")] * 5 + [("paragraph", SECOND)]
    )
    spans = spans_of(document)
    placed = one(document, Anchor(5, 0, len(SECOND), SECOND), spans)
    assert spans[placed.chunk].block == 6


def test_a_sentence_the_layout_now_spreads_over_two_blocks_is_found() -> None:
    document = make_document(
        [
            ("heading", "1 Results"),
            ("paragraph", "It fell by twelve"),
            ("paragraph", "points on early shifts."),
        ]
    )
    spans = spans_of(document)
    placed = one(document, first(), spans)
    assert placed.state == "found"
    assert spans[placed.chunk].block == 2  # the larger share


def test_the_same_sentence_three_times_in_one_block_takes_the_one_nearest_its_old_place() -> None:
    """Step 2: text put before all three, so step 1 fails; the marker was on
    the middle one and stays there."""
    old = f"{SECOND} {SECOND} {SECOND}"
    middle = len(SECOND) + 1
    anchor = Anchor(0, middle, middle + len(SECOND), SECOND)
    assert old[anchor.start : anchor.end] == SECOND
    added = "Added. "
    document = make_document([("paragraph", added + old)])
    start = len(added) + middle
    assert module._Finder(document).find(anchor) == (0, start, start + len(SECOND))


def split_far(gap: int) -> Document:
    """FIRST spread over two blocks, the first of them `gap` blocks after the anchor's."""
    fillers = [("paragraph", f"Filler {n}.") for n in range(gap)]
    return make_document(
        [
            ("heading", "1 Results"),
            *fillers,
            ("paragraph", "It fell by twelve"),
            ("paragraph", "points on early shifts."),
        ]
    )


def test_a_split_sentence_is_looked_for_twenty_blocks_either_side_and_no_further() -> None:
    """Step 3's window."""
    near = split_far(15)
    assert near.blocks[16].text == "It fell by twelve"
    assert module._Finder(near).find(first()) == (17, 0, len("points on early shifts."))
    assert one(near, first()).state == "found"
    far = split_far(25)
    assert far.blocks[26].text == "It fell by twelve"
    assert module._Finder(far).find(first()) is None
    assert one(far, first()).state == "not-found"


def test_a_split_sentence_goes_to_the_block_with_the_larger_share_the_earlier_on_a_tie() -> None:
    """Step 3: the larger share wins in either direction."""
    earlier = make_document(
        [
            ("heading", "1 Results"),
            ("paragraph", "It fell by twelve points on"),
            ("paragraph", "early shifts."),
        ]
    )
    assert module._Finder(earlier).find(first()) == (1, 0, len("It fell by twelve points on"))
    even = make_document([("paragraph", "abcd"), ("paragraph", "efgh")])
    assert module._Finder(even).find(Anchor(0, 0, 9, "abcd efgh")) == (0, 0, 4)


def test_a_place_two_chunks_overlap_alike_is_shown_on_the_first() -> None:
    """Step 5: 20 characters each, the first chunk wins."""
    document = paper()
    pieces = [Span(1, 0, 20), Span(1, 21, len(FIRST))]
    assert [min(p.end, len(FIRST)) - p.start for p in pieces] == [20, 20]
    assert one(document, first(), pieces).chunk == 0


@pytest.mark.parametrize(
    "printed",
    [
        "It fell by twelve   points on early\n  shifts.",  # runs of spaces and a line break
        "It  fell by twelve points on early shifts.",
    ],
)
def test_runs_of_white_space_read_as_one_space(printed: str) -> None:
    """The stored anchor has single spaces."""
    document = make_document([("heading", "1 Results"), ("paragraph", f"{printed} {SECOND}")])
    assert module._Finder(document).find(first()) == (1, 0, len(printed))
    assert one(document, first()).state == "found"


def test_soft_hyphens_are_read_through_both_ways() -> None:
    """A soft hyphen now in the block, or one stored in the anchor."""
    printed = "It fell by twel\u00adve points on early shifts."
    now = make_document([("heading", "1 Results"), ("paragraph", f"{printed} {SECOND}")])
    assert module._Finder(now).find(first()) == (1, 0, len(printed))
    stored = Anchor(1, 5, 5 + len(printed), printed)  # an old place, so step 1 fails
    assert module._Finder(paper()).find(stored) == (1, 0, len(FIRST))


def test_a_sentence_gone_is_listed_as_not_found_with_its_note_and_never_dropped(
    work: Path,
) -> None:
    """D-728 ruling 1: fails if a marker not found is left out of the list."""
    marker = Marker("a" * 16, "t", "t", Anchor(1, 0, 20, "A sentence no longer"), "still mine")
    found = Marker("b" * 16, "t", "t", first())
    put(work, [marker, found])
    document = paper()
    placed = place(read_markers(work, DOC), document, spans_of(document))
    assert [(p.marker.id, p.marker.note, p.chunk, p.state) for p in placed] == [
        (found.id, "", 1, "found"),  # found first (chunk 0 is the heading), lost last
        (marker.id, "still mine", None, "not-found"),
    ]


def test_text_the_audiobook_does_not_read_is_listed_as_not_read() -> None:
    document = paper()
    only_heading = [Span(0, 0, 9)]
    placed = one(document, second(), only_heading)
    assert (placed.chunk, placed.state) == (None, "not-read")


def test_the_order_is_reading_order_then_not_read_then_not_found() -> None:
    document = paper()
    spans = [Span(0, 0, 9), Span(1, 0, len(FIRST))]
    markers = [
        Marker("1" * 16, "t", "t", Anchor(1, 0, 5, "Gone.")),
        Marker("2" * 16, "t", "t", second()),  # not read: no chunk reads it
        Marker("3" * 16, "t", "t", first()),
        Marker("4" * 16, "t", "t", Anchor(0, 0, 9, "1 Results")),
    ]
    placed = place(markers, document, spans)
    assert [p.marker.id[0] for p in placed] == ["4", "3", "2", "1"]


def test_the_anchor_of_a_chunk_is_its_printed_text() -> None:
    document = paper()
    assert anchor_of(document, Span(1, 0, len(FIRST))) == first()


@st.composite
def changed_documents(draw: st.DrawFn) -> tuple[Document, Anchor, Document]:
    words = st.text(alphabet="abc .\n-", min_size=1, max_size=30)
    texts = draw(st.lists(words, min_size=1, max_size=6))
    old = make_document([("paragraph", t) for t in texts])
    block = draw(st.integers(0, len(texts) - 1))
    text = old.blocks[block].text
    start = draw(st.integers(0, max(0, len(text) - 1)))
    end = draw(st.integers(start + 1, max(start + 1, len(text))))
    anchor = Anchor(block, start, min(end, len(text)), text[start : min(end, len(text))])
    new = list(texts)
    for _ in range(draw(st.integers(0, 3))):
        if new and draw(st.booleans()):
            del new[draw(st.integers(0, len(new) - 1))]
        else:
            new.insert(draw(st.integers(0, len(new))), draw(words))
    if not new:
        new = ["x"]
    return old, anchor, make_document([("paragraph", t) for t in new])


@settings(deadline=None)
@given(changed_documents())
def test_finding_never_fails_and_a_found_place_reads_as_the_marker(
    case: tuple[Document, Anchor, Document],
) -> None:
    _old, anchor, new = case
    if not anchor.text:
        return
    spans = [Span(n, 0, len(b.text)) for n, b in enumerate(new.blocks)]
    found = module._Finder(new).find(anchor)
    placed = one(new, anchor, spans)
    needle = module._normal(anchor.text)[0]
    if found is None or not needle:
        assert placed.state == "not-found"
        return
    block, start, end = found
    assert 0 <= start < end <= len(new.blocks[block].text)
    assert module._normal(new.blocks[block].text[start:end])[0] in needle
    assert placed.state == "found"
