"""The server's capture store (#397, ADR-008 2.1): one read, one change and one atomic write
of `captures.json` under a lock per folder, the in-memory Undo, the refusals that leave the
file as it is, and the v1.3 markers that wait for their carry-over (#475)."""

from __future__ import annotations

import errno
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from web_helpers import FakeClock

from sci2audio.app import captures as app_captures
from sci2audio.app.captures import CAPTURES, read_captures
from sci2audio.core import Anchor, Capture, CaptureFile, CaptureType
from sci2audio.core.captures import MAX_CAPTURES, TEXT_LIMIT
from sci2audio.web import captures as module
from sci2audio.web.captures import (
    UNDO_KEPT,
    UNDO_SECONDS,
    CaptureBook,
    CapturedAgain,
    CaptureLimit,
    CaptureMissing,
    CapturesUnreadable,
    MarkersWaiting,
    TextRefused,
    UndoExpired,
    load,
)
from sci2audio.web.markers import MARKERS

DOC = "0123456789abcdef"
MARK, NOTE, QUOTE = CaptureType.MARK, CaptureType.NOTE, CaptureType.QUOTE
FIRST = Anchor(1, 0, 10, "It fell by")
SECOND = Anchor(1, 11, 20, "twelve pts")


def on(anchor: Anchor, kind: CaptureType) -> Any:
    """`existing` for CaptureBook.add: the capture of `kind` on exactly this anchor."""
    return lambda captures: next(
        (c for c in captures if c.anchor == anchor and c.type is kind), None
    )


def same_type_there(capture: Capture, captures: list[Capture]) -> bool:
    return any(c.anchor == capture.anchor and c.type is capture.type for c in captures)


@pytest.fixture
def work(tmp_path: Path) -> Path:
    folder = tmp_path / DOC
    folder.mkdir()
    return folder


def file_of(work: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((work / CAPTURES).read_text(encoding="utf-8"))
    return data


# ---- adding ----------------------------------------------------------------------------------


def test_each_type_is_kept_with_every_field_and_one_of_each_type_per_sentence(work: Path) -> None:
    book = CaptureBook()
    assert load(work, DOC) is None
    assert not (work / CAPTURES).exists()  # reading makes nothing
    mark, new = book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    quote, _ = book.add(work, DOC, QUOTE, FIRST, "", on(FIRST, QUOTE))
    note, _ = book.add(work, DOC, NOTE, FIRST, "Ask Sam.", on(FIRST, NOTE))
    assert new
    assert [(c.type, c.anchor, c.text) for c in (mark, quote, note)] == [
        (MARK, FIRST, ""),
        (QUOTE, FIRST, ""),
        (NOTE, FIRST, "Ask Sam."),
    ]
    again, new = book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    assert (again, new) == (mark, False)
    before = (work / CAPTURES).read_bytes()
    with pytest.raises(module.NoteThere) as refused:  # its text is never dropped
        book.add(work, DOC, NOTE, FIRST, "Other.", on(FIRST, NOTE))
    assert refused.value.kind == "note-exists"
    assert (work / CAPTURES).read_bytes() == before
    saved = read_captures(work, DOC)
    assert saved is not None
    assert saved.captures == (mark, quote, note)
    entry = file_of(work)["captures"][0]
    assert set(entry) == {"id", "type", "created", "changed", "anchor", "text"}
    assert entry["created"].endswith("Z")


def test_text_only_on_a_note_and_never_empty_or_too_long(work: Path) -> None:
    book = CaptureBook()
    for kind, text in (
        (MARK, "x"),
        (QUOTE, "x"),
        (NOTE, ""),
        (NOTE, "  \n"),
        (NOTE, "a\x00b"),
        (NOTE, "x" * (TEXT_LIMIT + 1)),
    ):
        with pytest.raises(TextRefused):
            book.add(work, DOC, kind, FIRST, text, on(FIRST, kind))
    assert not (work / CAPTURES).exists()


def test_a_notes_text_changes_and_a_mark_takes_none(work: Path) -> None:
    book = CaptureBook()
    note, _ = book.add(work, DOC, NOTE, FIRST, "one", on(FIRST, NOTE))
    mark, _ = book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    changed = book.write_note(work, DOC, note.id, "two")
    assert (changed.id, changed.text, changed.created) == (note.id, "two", note.created)
    before = (work / CAPTURES).read_bytes()
    assert book.write_note(work, DOC, note.id, "two") == changed  # nothing to write
    with pytest.raises(TextRefused):
        book.write_note(work, DOC, mark.id, "text")
    with pytest.raises(TextRefused):
        book.write_note(work, DOC, note.id, "")
    with pytest.raises(CaptureMissing):
        book.write_note(work, DOC, "f" * 16, "text")
    assert (work / CAPTURES).read_bytes() == before


def test_the_limit_of_captures_is_refused_and_the_file_kept(work: Path) -> None:
    many = tuple(
        Capture(f"{n:016x}", MARK, "t", "t", Anchor(1, n, n + 1, "x")) for n in range(MAX_CAPTURES)
    )
    app_captures.write_captures(work, CaptureFile(DOC, many))
    before = (work / CAPTURES).read_bytes()
    with pytest.raises(CaptureLimit):
        CaptureBook().add(work, DOC, MARK, SECOND, "", on(SECOND, MARK))
    assert (work / CAPTURES).read_bytes() == before


# ---- what is never written -----------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [b"{not json", b'{"format": "other"}', "ä".encode("latin-1")],
    ids=["bad-json", "other-format", "not-utf8"],
)
def test_a_file_this_version_cant_read_is_never_written(work: Path, content: bytes) -> None:
    (work / CAPTURES).write_bytes(content)
    with pytest.raises(CapturesUnreadable) as refused:
        CaptureBook().add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    assert refused.value.kind == "captures-unreadable"
    assert (work / CAPTURES).read_bytes() == content
    assert sorted(p.name for p in work.iterdir()) == [CAPTURES]


def test_markers_waiting_for_their_carry_over_are_never_hidden(work: Path) -> None:
    """ADR-008 2.1 item 5: writing captures.json beside markers.json would hide them."""
    (work / MARKERS).write_bytes(b"{}")
    with pytest.raises(MarkersWaiting) as refused:
        CaptureBook().add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    assert refused.value.kind == "markers-not-carried"
    assert sorted(p.name for p in work.iterdir()) == [MARKERS]
    # once captures.json is there, markers.json is not read and stays as it is
    app_captures.write_captures(work, CaptureFile(DOC, (), "markers.json"))
    capture, _ = CaptureBook().add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    assert file_of(work)["migrated_from"] == "markers.json"  # kept on every write
    assert (work / MARKERS).read_bytes() == b"{}"
    assert [c.id for c in load(work, DOC).captures] == [capture.id]  # type: ignore[union-attr]


def test_a_full_disk_leaves_the_old_file(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = CaptureBook()
    book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    before = (work / CAPTURES).read_bytes()

    def full(texts: Any, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(app_captures, "write_texts", full)
    with pytest.raises(OSError, match="No space"):
        book.add(work, DOC, QUOTE, FIRST, "", on(FIRST, QUOTE))
    assert (work / CAPTURES).read_bytes() == before


def test_a_file_too_large_is_refused_and_kept(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = CaptureBook()
    book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    before = (work / CAPTURES).read_bytes()
    monkeypatch.setattr(app_captures, "FILE_LIMIT", len(before) + 10)
    with pytest.raises(module.CapturesTooLarge) as refused:
        book.add(work, DOC, NOTE, FIRST, "x" * 200, on(FIRST, NOTE))
    assert refused.value.kind == "captures-too-large"
    assert (work / CAPTURES).read_bytes() == before


def test_two_adds_at_once_both_land(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The lock per folder: the second read waits for the first write."""
    book = CaptureBook()
    real = module.load
    inside = threading.Event()
    go = threading.Event()

    def slow(folder: Path, document_id: str) -> CaptureFile | None:
        found = real(folder, document_id)
        if not inside.is_set():
            inside.set()
            go.wait(5)
        return found

    monkeypatch.setattr(module, "load", slow)
    first = threading.Thread(target=book.add, args=(work, DOC, MARK, FIRST, "", on(FIRST, MARK)))
    first.start()
    inside.wait(5)
    second = threading.Thread(
        target=book.add, args=(work, DOC, QUOTE, SECOND, "", on(SECOND, QUOTE))
    )
    second.start()
    go.set()
    first.join(5)
    second.join(5)
    assert [c["type"] for c in file_of(work)["captures"]] == ["mark", "quote"]


# ---- Undo ------------------------------------------------------------------------------------


def test_undo_puts_a_capture_back_unchanged_and_the_file_holds_no_removed_one(work: Path) -> None:
    clock = FakeClock()
    book = CaptureBook(clock)
    note, _ = book.add(work, DOC, NOTE, FIRST, "mine", on(FIRST, NOTE))
    gone = book.remove(work, DOC, note.id)
    assert gone == note
    assert file_of(work)["captures"] == []  # the file stays, empty
    assert "mine" not in (work / CAPTURES).read_text(encoding="utf-8")
    clock.advance(UNDO_SECONDS)
    assert book.restore(work, DOC, note.id, same_type_there) == note
    with pytest.raises(UndoExpired):  # once only
        book.restore(work, DOC, note.id, same_type_there)


def test_undo_ends_after_ten_minutes_a_restart_or_twenty_later_removals(work: Path) -> None:
    clock = FakeClock()
    book = CaptureBook(clock)
    one, _ = book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    book.remove(work, DOC, one.id)
    clock.advance(UNDO_SECONDS + 0.001)
    with pytest.raises(UndoExpired):
        book.restore(work, DOC, one.id, same_type_there)
    two, _ = book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    book.remove(work, DOC, two.id)
    with pytest.raises(UndoExpired):
        CaptureBook(clock).restore(work, DOC, two.id, same_type_there)  # a new server run
    removed = []
    for n in range(UNDO_KEPT + 1):
        anchor = Anchor(2, n, n + 1, "x")
        capture, _ = book.add(work, DOC, QUOTE, anchor, "", on(anchor, QUOTE))
        removed.append(book.remove(work, DOC, capture.id))
    with pytest.raises(UndoExpired):
        book.restore(work, DOC, removed[0].id, same_type_there)
    assert book.restore(work, DOC, removed[1].id, same_type_there) == removed[1]


def test_undo_after_the_sentence_got_that_type_again_is_refused(work: Path) -> None:
    book = CaptureBook(FakeClock())
    one, _ = book.add(work, DOC, QUOTE, FIRST, "", on(FIRST, QUOTE))
    book.remove(work, DOC, one.id)
    again, _ = book.add(work, DOC, QUOTE, FIRST, "", on(FIRST, QUOTE))
    book.add(work, DOC, MARK, SECOND, "", on(SECOND, MARK))
    before = (work / CAPTURES).read_bytes()
    with pytest.raises(CapturedAgain) as refused:
        book.restore(work, DOC, one.id, same_type_there)
    assert refused.value.kind == "captured-again"
    assert (work / CAPTURES).read_bytes() == before
    assert again in load(work, DOC).captures  # type: ignore[union-attr]


def test_a_removal_between_a_restores_write_and_its_end_keeps_its_own_undo(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another window removes the capture again right after this restore wrote it; the
    restore must not drop that removal's Undo."""
    book = CaptureBook(FakeClock())
    mark, _ = book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    book.remove(work, DOC, mark.id)
    real = CaptureBook.change
    calls: list[str] = []

    def then_removed(self: CaptureBook, *args: Any, **kwargs: Any) -> Any:
        result = real(self, *args, **kwargs)
        if not calls:  # the restore's own write, then the other window's removal
            calls.append("removed")
            book.remove(work, DOC, mark.id)
        return result

    monkeypatch.setattr(CaptureBook, "change", then_removed)
    assert book.restore(work, DOC, mark.id, same_type_there) == mark
    monkeypatch.undo()
    assert load(work, DOC).captures == ()  # type: ignore[union-attr]
    assert book.restore(work, DOC, mark.id, same_type_there) == mark  # its Undo is kept


def test_a_failed_undo_can_be_tried_again(work: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    book = CaptureBook(FakeClock())
    mark, _ = book.add(work, DOC, MARK, FIRST, "", on(FIRST, MARK))
    book.remove(work, DOC, mark.id)

    def full(texts: Any, *, overwrite: bool) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    with monkeypatch.context() as patched:
        patched.setattr(app_captures, "write_texts", full)
        with pytest.raises(OSError, match="No space"):
            book.restore(work, DOC, mark.id, same_type_there)
    assert book.restore(work, DOC, mark.id, same_type_there) == mark


def test_every_write_goes_through_the_one_locked_change(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    book = CaptureBook(FakeClock())
    calls: list[str] = []
    real = CaptureBook.change

    def counted(self: CaptureBook, *args: Any, **kwargs: Any) -> Any:
        calls.append("change")
        return real(self, *args, **kwargs)

    real_write = module.write_captures

    def watched(folder: Path, captures: CaptureFile) -> None:
        assert calls, "a write outside CaptureBook.change"
        real_write(folder, captures)

    monkeypatch.setattr(CaptureBook, "change", counted)
    monkeypatch.setattr(module, "write_captures", watched)
    note, _ = book.add(work, DOC, NOTE, FIRST, "a", on(FIRST, NOTE))
    book.write_note(work, DOC, note.id, "b")
    book.remove(work, DOC, note.id)
    book.restore(work, DOC, note.id, same_type_there)
    assert calls == ["change"] * 4
