"""Markers with a note (#474, D-723, D-728): the file, its guard, its writes under faults,
the undo store, finding a marker again in a changed document, and the API."""

from __future__ import annotations

import errno
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from web_helpers import FakeClock, markers_of

from sci2audio.app import files
from sci2audio.core import Document, Span
from sci2audio.testing.documents import make_document
from sci2audio.web import markers as module
from sci2audio.web.markers import (
    MARKERS,
    MAX_MARKERS,
    NOTE_LIMIT,
    UNDO_KEPT,
    UNDO_SECONDS,
    Anchor,
    MarkedAgain,
    Marker,
    MarkerBook,
    MarkerLimit,
    MarkerMissing,
    MarkersBroken,
    NoteRefused,
    UndoExpired,
    anchor_of,
    count_markers,
    markers_text,
    note_problem,
    place,
    read_markers,
)

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


def by_anchor(anchor: Anchor) -> Any:
    """`existing` for MarkerBook.set: the marker on exactly this anchor."""
    return lambda markers: next((m for m in markers if m.anchor == anchor), None)


def no_clash(marker: Marker, markers: list[Marker]) -> bool:
    return any(other.anchor == marker.anchor for other in markers)


@pytest.fixture
def work(tmp_path: Path) -> Path:
    folder = tmp_path / DOC
    folder.mkdir()
    return folder


# ---- the file --------------------------------------------------------------------------


def test_a_marker_and_its_note_are_kept_with_every_field(work: Path) -> None:
    book = MarkerBook()
    marker, new = book.set(work, DOC, first(), by_anchor(first()))
    assert new
    noted = book.note(work, DOC, marker.id, "Check the second cohort.\nLine two: ✓")
    data = markers_of(work)
    assert data["format"] == "sci2audio-web-markers"
    assert data["version"] == 1
    assert data["document"] == DOC
    [entry] = data["markers"]
    assert entry == {
        "id": marker.id,
        "created": marker.created,
        "changed": noted.changed,
        "anchor": {"block": 1, "start": 0, "end": len(FIRST), "text": FIRST},
        "note": "Check the second cohort.\nLine two: ✓",
    }
    assert read_markers(work, DOC) == [noted]
    assert len(marker.id) == 16


def test_a_second_marker_on_the_same_sentence_is_the_first_one(work: Path) -> None:
    book = MarkerBook()
    one, _ = book.set(work, DOC, first(), by_anchor(first()))
    before = (work / MARKERS).read_bytes()
    again, new = book.set(work, DOC, first(), by_anchor(first()))
    assert (again, new) == (one, False)
    assert (work / MARKERS).read_bytes() == before  # nothing written


def test_no_file_is_no_markers_and_is_not_made_by_reading(work: Path) -> None:
    assert read_markers(work, DOC) == []
    assert count_markers(work, DOC) == 0
    assert not (work / MARKERS).exists()


def test_the_limits_of_a_note_and_of_the_file() -> None:
    assert note_problem("x" * NOTE_LIMIT) is None
    assert note_problem("x" * (NOTE_LIMIT + 1))
    assert note_problem("a\x00b")
    many = [Marker(f"{n:016x}", "t", "t", first()) for n in range(MAX_MARKERS + 1)]
    with pytest.raises(MarkerLimit):
        markers_text(DOC, many)
    big = [Marker(f"{n:016x}", "t", "t", Anchor(1, 0, 1, "x" * 2000), "") for n in range(1500)]
    with pytest.raises(MarkerLimit) as large:
        markers_text(DOC, big)
    assert large.value.kind == "markers-too-large"


def test_a_marker_past_the_limit_is_refused_and_the_file_kept(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "MAX_MARKERS", 2)
    book = MarkerBook()
    book.set(work, DOC, first(), by_anchor(first()))
    book.set(work, DOC, second(), by_anchor(second()))
    before = (work / MARKERS).read_bytes()
    with pytest.raises(MarkerLimit):
        book.set(work, DOC, Anchor(0, 0, 9, "1 Results"), lambda markers: None)
    assert (work / MARKERS).read_bytes() == before


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
    # a file that reads well but is past the limit: refused for its size alone
    "too large": json.dumps(_valid()).encode() + b" " * module.FILE_LIMIT,
}


@pytest.mark.parametrize("case", sorted(BROKEN))
def test_a_file_this_version_cant_read_is_never_written(work: Path, case: str) -> None:
    """Without the guard the next write would replace the person's notes with one marker."""
    path = work / MARKERS
    path.write_bytes(BROKEN[case])
    before = path.read_bytes()
    with pytest.raises(MarkersBroken):
        read_markers(work, DOC)
    assert count_markers(work, DOC) is None
    book = MarkerBook()
    for change in (
        lambda: book.set(work, DOC, second(), by_anchor(second())),
        lambda: book.note(work, DOC, "a" * 16, "new"),
        lambda: book.remove(work, DOC, "a" * 16),
    ):
        with pytest.raises(MarkersBroken):
            change()
    assert path.read_bytes() == before
    assert sorted(p.name for p in work.iterdir()) == [MARKERS]  # no partial file either


@pytest.mark.skipif(sys.platform == "win32", reason="links need rights on Windows")
def test_a_link_in_the_markers_place_is_never_followed_or_written(
    work: Path, tmp_path: Path
) -> None:
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text(markers_text(DOC, []), encoding="utf-8")
    (work / MARKERS).symlink_to(elsewhere)
    before = elsewhere.read_bytes()
    with pytest.raises(MarkersBroken):
        MarkerBook().set(work, DOC, first(), by_anchor(first()))
    assert (work / MARKERS).is_symlink()
    assert elsewhere.read_bytes() == before


# ---- writing under faults (tests.md: file writing) -------------------------------------------


@pytest.fixture
def kept(work: Path) -> bytes:
    """A file with one marker and its note, as it was before the failing write."""
    book = MarkerBook()
    marker, _ = book.set(work, DOC, first(), by_anchor(first()))
    book.note(work, DOC, marker.id, "keep me")
    return (work / MARKERS).read_bytes()


def test_a_write_that_fails_half_way_leaves_the_old_file(
    work: Path, kept: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = files._write_partial

    def half(partial: Path, content: str | bytes) -> None:
        real(partial, content[: len(content) // 2])
        raise OSError(errno.EIO, "the disk went away")

    monkeypatch.setattr(files, "_write_partial", half)
    with pytest.raises(OSError, match="disk went away"):
        MarkerBook().set(work, DOC, second(), by_anchor(second()))
    assert (work / MARKERS).read_bytes() == kept
    assert sorted(p.name for p in work.iterdir()) == [MARKERS]


def test_a_full_disk_leaves_the_old_file(
    work: Path, kept: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full(texts: Any, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(module, "write_texts", full)
    with pytest.raises(OSError, match="No space") as error:
        MarkerBook().set(work, DOC, second(), by_anchor(second()))
    assert error.value.errno == errno.ENOSPC
    assert (work / MARKERS).read_bytes() == kept


def test_a_file_removed_between_read_and_write_keeps_what_was_read(
    work: Path, kept: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = module.read_markers

    def read_then_remove(folder: Path, document_id: str) -> list[Marker]:
        found = real(folder, document_id)
        (folder / MARKERS).unlink()
        return found

    monkeypatch.setattr(module, "read_markers", read_then_remove)
    MarkerBook().set(work, DOC, second(), by_anchor(second()))
    monkeypatch.undo()
    notes = [m.note for m in read_markers(work, DOC)]
    assert notes == ["keep me", ""]


@pytest.mark.skipif(sys.platform == "win32", reason="no read-only folders on Windows")
@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root writes anyway")
def test_a_read_only_folder_leaves_the_old_file(work: Path, kept: bytes) -> None:
    work.chmod(0o500)
    try:
        with pytest.raises(OSError, match="ermission"):
            MarkerBook().set(work, DOC, second(), by_anchor(second()))
    finally:
        work.chmod(0o700)
    assert (work / MARKERS).read_bytes() == kept


# ---- Undo: the removed marker is kept in memory only (D-723 ruling 1) -----------------------


def test_undo_puts_the_marker_back_unchanged_and_the_file_holds_no_removed_marker(
    work: Path,
) -> None:
    clock = FakeClock()
    book = MarkerBook(clock)
    marker, _ = book.set(work, DOC, first(), by_anchor(first()))
    noted = book.note(work, DOC, marker.id, "mine")
    gone = book.remove(work, DOC, marker.id)
    assert gone == noted
    assert markers_of(work)["markers"] == []
    assert marker.id not in (work / MARKERS).read_text(encoding="utf-8")
    clock.advance(UNDO_SECONDS - 1)
    assert book.restore(work, DOC, marker.id, no_clash) == noted
    assert read_markers(work, DOC) == [noted]
    with pytest.raises(UndoExpired):  # once only
        book.restore(work, DOC, marker.id, no_clash)


def test_undo_ends_after_ten_minutes_a_restart_or_twenty_later_removals(work: Path) -> None:
    clock = FakeClock()
    book = MarkerBook(clock)
    one, _ = book.set(work, DOC, first(), by_anchor(first()))
    book.remove(work, DOC, one.id)
    clock.advance(UNDO_SECONDS + 0.001)
    with pytest.raises(UndoExpired):
        book.restore(work, DOC, one.id, no_clash)
    two, _ = book.set(work, DOC, first(), by_anchor(first()))
    book.remove(work, DOC, two.id)
    with pytest.raises(UndoExpired):
        MarkerBook(clock).restore(work, DOC, two.id, no_clash)  # a new server run
    removed = []
    for n in range(UNDO_KEPT + 1):
        anchor = Anchor(1, n, n + 1, TEXT[n])
        marker, _ = book.set(work, DOC, anchor, by_anchor(anchor))
        removed.append(book.remove(work, DOC, marker.id))
    with pytest.raises(UndoExpired):
        book.restore(work, DOC, removed[0].id, no_clash)
    assert book.restore(work, DOC, removed[1].id, no_clash) == removed[1]


def test_undo_after_the_sentence_was_marked_again_is_refused(work: Path) -> None:
    book = MarkerBook(FakeClock())
    one, _ = book.set(work, DOC, first(), by_anchor(first()))
    book.remove(work, DOC, one.id)
    again, _ = book.set(work, DOC, first(), by_anchor(first()))
    before = (work / MARKERS).read_bytes()
    with pytest.raises(MarkedAgain):
        book.restore(work, DOC, one.id, no_clash)
    assert (work / MARKERS).read_bytes() == before
    assert read_markers(work, DOC) == [again]


def test_undo_writes_only_through_the_one_locked_change(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-728 ruling 2: a restore is a read-modify-write like a set, with no second path."""
    book = MarkerBook(FakeClock())
    marker, _ = book.set(work, DOC, first(), by_anchor(first()))
    book.remove(work, DOC, marker.id)
    calls: list[str] = []
    real = MarkerBook.change

    def counted(self: MarkerBook, *args: Any, **kwargs: Any) -> Any:
        calls.append("change")
        return real(self, *args, **kwargs)

    writes: list[Path] = []
    real_write = module.write_texts

    def watched(texts: Any, *, overwrite: bool) -> None:
        assert calls, "a write outside MarkerBook.change"
        writes.extend(texts)
        real_write(texts, overwrite=overwrite)

    monkeypatch.setattr(MarkerBook, "change", counted)
    monkeypatch.setattr(module, "write_texts", watched)
    book.restore(work, DOC, marker.id, no_clash)
    assert calls == ["change"]
    assert writes == [work / MARKERS]


def test_a_failed_undo_can_be_tried_again(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = MarkerBook(FakeClock())
    marker, _ = book.set(work, DOC, first(), by_anchor(first()))
    book.remove(work, DOC, marker.id)

    def full(texts: Any, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    with monkeypatch.context() as patched:
        patched.setattr(module, "write_texts", full)
        with pytest.raises(OSError, match="No space"):
            book.restore(work, DOC, marker.id, no_clash)
    assert book.restore(work, DOC, marker.id, no_clash) == marker


def test_a_note_the_file_could_not_hold_is_refused_before_any_write(work: Path) -> None:
    """Found by the state machine: a NUL in a note would write a file no version reads."""
    book = MarkerBook()
    marker, _ = book.set(work, DOC, first(), by_anchor(first()))
    before = (work / MARKERS).read_bytes()
    for note in ("a\x00b", "x" * (NOTE_LIMIT + 1)):
        with pytest.raises(NoteRefused):
            book.note(work, DOC, marker.id, note)
    assert (work / MARKERS).read_bytes() == before
    bad = Marker("b" * 16, "t", "t", Anchor(1, 0, 1, ""))  # an empty anchor text
    with pytest.raises(module.MarkerError) as refused:
        markers_text(DOC, [bad])
    assert refused.value.kind == "markers-not-saved"


def test_a_missing_marker_is_named(work: Path) -> None:
    book = MarkerBook()
    book.set(work, DOC, first(), by_anchor(first()))
    with pytest.raises(MarkerMissing):
        book.note(work, DOC, "f" * 16, "x")
    with pytest.raises(MarkerMissing):
        book.remove(work, DOC, "f" * 16)


# ---- any sequence of changes keeps a valid file equal to a plain model --------------------------


class MarkerMachine(RuleBasedStateMachine):
    """Set, note, remove, undo and a new server run, in any order (plan 7a item 4)."""

    def __init__(self) -> None:
        super().__init__()
        import tempfile

        self.folder = Path(tempfile.mkdtemp()) / DOC
        self.folder.mkdir()
        self.clock = FakeClock()
        self.book = MarkerBook(self.clock)
        self.model: list[Marker] = []
        self.removed: dict[str, tuple[Marker, float]] = {}

    def teardown(self) -> None:
        import shutil

        shutil.rmtree(self.folder.parent, ignore_errors=True)

    @rule(at=st.integers(0, len(TEXT) - 1))
    def set_marker(self, at: int) -> None:
        anchor = Anchor(1, at, at + 1, TEXT[at])
        marker, new = self.book.set(self.folder, DOC, anchor, by_anchor(anchor))
        existing = [m for m in self.model if m.anchor == anchor]
        if existing:
            assert (marker, new) == (existing[0], False)
        else:
            assert new
            self.model.append(marker)

    @precondition(lambda self: self.model)
    @rule(pick=st.integers(0, 10_000), note=st.text(max_size=40))
    def write_note(self, pick: int, note: str) -> None:
        target = self.model[pick % len(self.model)]
        if note_problem(note):
            with pytest.raises(NoteRefused):  # nothing written
                self.book.note(self.folder, DOC, target.id, note)
            return
        noted = self.book.note(self.folder, DOC, target.id, note)
        assert noted.note == note
        self.model[self.model.index(target)] = noted

    @precondition(lambda self: self.model)
    @rule(pick=st.integers(0, 10_000))
    def remove(self, pick: int) -> None:
        target = self.model[pick % len(self.model)]
        assert self.book.remove(self.folder, DOC, target.id) == target
        self.model.remove(target)
        self.removed.pop(target.id, None)
        self.removed[target.id] = (target, self.clock())
        while len(self.removed) > UNDO_KEPT:
            del self.removed[next(iter(self.removed))]

    @precondition(lambda self: self.removed)
    @rule(pick=st.integers(0, 10_000))
    def undo(self, pick: int) -> None:
        marker_id = list(self.removed)[pick % len(self.removed)]
        marker, at = self.removed[marker_id]
        expected: type[Exception] | None = None
        if self.clock() - at > UNDO_SECONDS:
            expected = UndoExpired
        elif any(m.anchor == marker.anchor for m in self.model):
            expected = MarkedAgain
        if expected is None:
            assert self.book.restore(self.folder, DOC, marker_id, no_clash) == marker
            self.model.append(marker)
            del self.removed[marker_id]
        else:
            with pytest.raises(expected):
                self.book.restore(self.folder, DOC, marker_id, no_clash)
            if expected is UndoExpired:
                del self.removed[marker_id]

    @rule(seconds=st.sampled_from([1.0, 120.0, UNDO_SECONDS]))
    def wait(self, seconds: float) -> None:
        self.clock.advance(seconds)

    @rule()
    def restart(self) -> None:
        self.book = MarkerBook(self.clock)
        self.removed.clear()

    @invariant()
    def the_file_is_the_model(self) -> None:
        found = read_markers(self.folder, DOC)
        assert found == self.model
        assert len({m.id for m in found}) == len(found)


TestMarkerMachine = MarkerMachine.TestCase
TestMarkerMachine.settings = settings(stateful_step_count=30, deadline=None)


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


def test_a_sentence_gone_is_listed_as_not_found_with_its_note_and_never_dropped(
    work: Path,
) -> None:
    """D-728 ruling 1: fails if a marker not found is left out of the list or the file."""
    book = MarkerBook()
    lost = Anchor(1, 0, 20, "A sentence no longer")
    marker, _ = book.set(work, DOC, lost, by_anchor(lost))
    book.note(work, DOC, marker.id, "still mine")
    document = paper()
    placed = place(read_markers(work, DOC), document, spans_of(document))
    assert [(p.marker.id, p.marker.note, p.chunk, p.state) for p in placed] == [
        (marker.id, "still mine", None, "not-found")
    ]
    # a later change of the file keeps it, as found or not
    book.set(work, DOC, first(), by_anchor(first()))
    ids = [m["id"] for m in markers_of(work)["markers"]]
    assert ids == [marker.id, read_markers(work, DOC)[1].id]
    again = place(read_markers(work, DOC), document, spans_of(document))
    assert [p.state for p in again] == ["found", "not-found"]  # found first, lost last


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
