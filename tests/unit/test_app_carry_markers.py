# ruff: noqa: RUF001  (the sentences are as papers print them)
"""The v1.3 markers carried over into the capture model (#475, ADR-008 2.1 item 5).

A marker without a note becomes a mark, one with a note a note; id, times and anchor stay.
The carry-over runs only when a document has `markers.json` and no `captures.json`, writes
`captures.json` with `migrated_from: markers.json` and never changes `markers.json`. A v1
file that can't be read, or whose markers the capture model refuses, is left byte for byte
as it is and reported, nothing is written, and capturing stays off (`CapturesBroken`).
Faults while writing (tests.md: file writing): a full disk, a write failing half-way, a
process killed outright mid-write and run again, files removed during the run.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from syrupy.assertion import SnapshotAssertion

from sci2audio.app import captures as module
from sci2audio.app import files
from sci2audio.app.captures import (
    CAPTURES,
    MARKERS,
    CapturesBroken,
    MarkersNotCarried,
    captures_text,
    load_captures,
    read_captures,
    write_captures,
)
from sci2audio.core import Anchor, Capture, CaptureFile, CaptureType
from sci2audio.web import markers as v13
from sci2audio.web.markers import Marker, markers_text

DOC = "0123456789abcdef"
CREATED = "2026-09-02T08:15:00Z"
CHANGED = "2026-09-03T21:40:12Z"
SENTENCE = "Sleep loss lowered recall by 12 % (p < .01)."
PLAIN = Marker("00000000000000a1", CREATED, CREATED, v13.Anchor(1, 0, 44, SENTENCE))
NOTED = Marker(
    "00000000000000b2",
    CREATED,
    CHANGED,
    v13.Anchor(4, 10, 32, "Naps were not counted."),
    "Were naps left out on purpose? α ≤ 0.05",
)
LATER = Marker("00000000000000c3", CHANGED, CHANGED, v13.Anchor(0, 3, 9, "µ = 3 "))
V1 = markers_text(DOC, [PLAIN, NOTED, LATER])

# what the three markers become, in the file's order
CARRIED = CaptureFile(
    DOC,
    (
        Capture(PLAIN.id, CaptureType.MARK, CREATED, CREATED, Anchor(1, 0, 44, SENTENCE)),
        Capture(
            NOTED.id,
            CaptureType.NOTE,
            CREATED,
            CHANGED,
            Anchor(4, 10, 32, "Naps were not counted."),
            "Were naps left out on purpose? α ≤ 0.05",
        ),
        Capture(LATER.id, CaptureType.MARK, CHANGED, CHANGED, Anchor(0, 3, 9, "µ = 3 ")),
    ),
    migrated_from="markers.json",
)

# the person's other files in the working folder, which the carry-over never touches
NEIGHBOURS = {"position.json": b'{"chunk": 3}\n', "source.pdf": b"%PDF-1.7 not really"}


@pytest.fixture
def work(tmp_path: Path) -> Path:
    folder = tmp_path / DOC
    folder.mkdir()
    for name, content in NEIGHBOURS.items():
        (folder / name).write_bytes(content)
    return folder


def _put_markers(work: Path, content: str | bytes) -> bytes:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    (work / MARKERS).write_bytes(raw)
    return raw


def _untouched(work: Path, markers: bytes, *, captures: bool) -> None:
    """markers.json byte for byte as it was, the neighbours too, no partial file left, and
    captures.json there only if `captures`."""
    assert (work / MARKERS).read_bytes() == markers
    for name, content in NEIGHBOURS.items():
        assert (work / name).read_bytes() == content
    expected = [*NEIGHBOURS, MARKERS] + ([CAPTURES] if captures else [])
    assert sorted(p.name for p in work.iterdir()) == sorted(expected)


# ---- carrying over -------------------------------------------------------------------------


def test_every_marker_its_note_and_its_times_carry_over(work: Path) -> None:
    raw = _put_markers(work, V1)
    assert load_captures(work, DOC) == CARRIED
    assert read_captures(work, DOC) == CARRIED  # written, and it reads back the same
    _untouched(work, raw, captures=True)


def test_the_carried_file_golden_file(work: Path, snapshot: SnapshotAssertion) -> None:
    """The v1 file as v1.3 wrote it and the captures.json made from it, byte for byte."""
    _put_markers(work, V1)
    load_captures(work, DOC)
    assert (work / MARKERS).read_text(encoding="utf-8") == snapshot(name="v1 markers")
    assert (work / CAPTURES).read_text(encoding="utf-8") == snapshot(name="carried over")


def test_a_v1_file_with_no_marker_carries_over_as_an_empty_captures_file(work: Path) -> None:
    raw = _put_markers(work, markers_text(DOC, []))
    assert load_captures(work, DOC) == CaptureFile(DOC, migrated_from="markers.json")
    _untouched(work, raw, captures=True)


def test_a_v1_file_written_by_hand_carries_over_as_v13_reads_it(work: Path) -> None:
    """Compact JSON, keys in another order, escapes: what the v1.3 reader accepts."""
    data = {
        "markers": [
            {
                "note": "\\u00e9t\\u00e9",
                "anchor": {"text": "A\\/B", "end": 3, "start": 0, "block": 0},
                "changed": CHANGED,
                "created": CREATED,
                "id": "abcdef0123456789",
            }
        ],
        "document": DOC,
        "version": 1,
        "format": "sci2audio-web-markers",
    }
    text = json.dumps(data, separators=(",", ":")).replace("\\\\", "\\")
    raw = _put_markers(work, text)
    assert v13.read_markers(work, DOC)[0].note == "été"
    (capture,) = load_captures(work, DOC).captures  # type: ignore[union-attr]
    assert capture.type is CaptureType.NOTE
    assert capture.text == "été"
    assert capture.anchor == Anchor(0, 0, 3, "A/B")
    _untouched(work, raw, captures=True)


def test_no_file_at_all_reads_as_none_and_writes_nothing(work: Path) -> None:
    assert load_captures(work, DOC) is None
    assert sorted(p.name for p in work.iterdir()) == sorted(NEIGHBOURS)


def test_markers_are_not_read_while_captures_json_is_there(work: Path) -> None:
    write_captures(work, CaptureFile(DOC))
    kept = (work / CAPTURES).read_bytes()
    raw = _put_markers(work, V1)
    assert load_captures(work, DOC) == CaptureFile(DOC)
    assert (work / CAPTURES).read_bytes() == kept
    _untouched(work, raw, captures=True)
    broken = _put_markers(work, b"{broken")  # not even looked at
    assert load_captures(work, DOC) == CaptureFile(DOC)
    _untouched(work, broken, captures=True)


def test_a_carried_file_is_not_carried_again_and_later_changes_stay(work: Path) -> None:
    raw = _put_markers(work, V1)
    carried = load_captures(work, DOC)
    assert carried is not None
    fewer = CaptureFile(DOC, carried.captures[1:], migrated_from="markers.json")
    write_captures(work, fewer)
    assert load_captures(work, DOC) == fewer  # the removed mark does not come back
    _untouched(work, raw, captures=True)


def test_removing_captures_json_by_hand_brings_the_markers_back(work: Path) -> None:
    """The recovery path of ADR-008 2.1 item 5."""
    raw = _put_markers(work, V1)
    load_captures(work, DOC)
    write_captures(work, CaptureFile(DOC, migrated_from="markers.json"))
    (work / CAPTURES).unlink()
    assert load_captures(work, DOC) == CARRIED
    _untouched(work, raw, captures=True)


def test_a_broken_captures_json_is_reported_and_markers_are_not_carried(work: Path) -> None:
    raw = _put_markers(work, V1)
    (work / CAPTURES).write_bytes(b"{broken")
    with pytest.raises(CapturesBroken, match=r"captures\.json") as error:
        load_captures(work, DOC)
    assert not isinstance(error.value, MarkersNotCarried)
    assert (work / CAPTURES).read_bytes() == b"{broken"
    _untouched(work, raw, captures=True)


# ---- a v1 file that is not carried over ---------------------------------------------------

GOOD = V1.encode("utf-8")
BROKEN_V1 = {
    "not json": b"{broken",
    "not utf-8": b'{"format": "sci2audio-web-markers", "x": "\xff"}',
    "empty": b"",
    "a list": b"[]",
    "another format": GOOD.replace(b"sci2audio-web-markers", b"sci2audio-captures"),
    "a later version": GOOD.replace(b'"version": 1', b'"version": 2'),
    "another document": GOOD.replace(DOC.encode(), b"fedcba9876543210"),
    "a key too many": GOOD.replace(b'"note": ""', b'"note": "", "type": "mark"', 1),
    "a short id": GOOD.replace(b"00000000000000a1", b"a1"),
    "an id twice": GOOD.replace(b"00000000000000b2", b"00000000000000a1"),
    "a nan": GOOD.replace(b'"block": 4', b'"block": NaN'),
    "a negative offset": GOOD.replace(b'"start": 10', b'"start": -1'),
    "an empty sentence": GOOD.replace(b'"text": "\xc2\xb5 = 3 "', b'"text": ""'),
    "a nul in a note": GOOD.replace(b'"note": "Were', b'"note": "\\u0000Were'),
    "nested too deeply": b"[" * 100_000 + b"]" * 100_000,
    # one past each limit of the v1.3 reader, and numbers of another type
    "a note one character too long": GOOD.replace(
        b'"note": "Were naps left out on purpose? \xce\xb1 \xe2\x89\xa4 0.05"',
        b'"note": "' + b"n" * (v13.NOTE_LIMIT + 1) + b'"',
    ),
    "a created time one character too long": GOOD.replace(
        b'"created": "2026-09-02T08:15:00Z"', b'"created": "' + b"t" * 41 + b'"', 1
    ),
    "a changed time one character too long": GOOD.replace(
        b'"changed": "2026-09-03T21:40:12Z"', b'"changed": "' + b"t" * 41 + b'"', 1
    ),
    "a block true": GOOD.replace(b'"block": 4', b'"block": true'),
    "a block as text": GOOD.replace(b'"block": 4', b'"block": "1"'),
    "an end as a fraction": GOOD.replace(b'"end": 32', b'"end": 32.0'),
}
# texts the v1.3 reader accepts but the capture model refuses (#786: no UTF-8 form)
SURROGATE_V1 = {
    "a note": GOOD.replace(b'"note": "Were', b'"note": "\\ud800Were'),
    "a sentence": GOOD.replace(b'"text": "Naps', b'"text": "\\udfffNaps'),
    "a created time": GOOD.replace(b'"created": "2026-09-02', b'"created": "\\ud800-09-02', 1),
    "a changed time": GOOD.replace(b'"changed": "2026-09-03', b'"changed": "\\udc00-09-03', 1),
}


def _refused_and_untouched(work: Path, raw: bytes, match: str) -> None:
    for _ in range(2):  # and capturing stays off: the next load refuses it again
        with pytest.raises(MarkersNotCarried, match=match) as error:
            load_captures(work, DOC)
        assert isinstance(error.value, CapturesBroken)
        assert "markers.json" in str(error.value)
    _untouched(work, raw, captures=False)


@pytest.mark.parametrize("case", sorted(BROKEN_V1))
def test_a_v1_file_v13_cant_read_is_reported_and_left_as_it_is(work: Path, case: str) -> None:
    assert BROKEN_V1[case] != GOOD
    raw = _put_markers(work, BROKEN_V1[case])
    with pytest.raises(v13.MarkersBroken):  # v1.3 refuses it too
        v13.read_markers(work, DOC)
    _refused_and_untouched(work, raw, "can't be read")


@pytest.mark.parametrize("case", sorted(SURROGATE_V1))
def test_a_lone_surrogate_v13_accepts_is_refused_and_nothing_is_written(
    work: Path, case: str
) -> None:
    """The lead's criterion on #475: the whole CaptureFile is built first; on a
    CaptureFormatError nothing is written and markers.json stays as it is."""
    raw = _put_markers(work, SURROGATE_V1[case])
    assert len(v13.read_markers(work, DOC)) == 3  # v1.3 reads it
    _refused_and_untouched(work, raw, "surrogate")


def test_the_v1_limits_are_the_v13_readers() -> None:
    assert module.MARKERS_LIMIT == v13.FILE_LIMIT
    assert module.MAX_MARKERS == v13.MAX_MARKERS
    assert module.NOTE_LIMIT == v13.NOTE_LIMIT


def test_a_v1_file_at_every_limit_carries_over(work: Path) -> None:
    """Exactly 2000 markers, a 4000-character note and 40-character times: v1.3 reads
    them, so every one carries over."""
    time = "2026-09-02T08:15:00.000000000000000+0000"
    assert len(time) == 40
    note = "n" * v13.NOTE_LIMIT
    full = [
        Marker(f"{n:016x}", time, time, v13.Anchor(n, 0, 1, "x"), note if n == 0 else "")
        for n in range(v13.MAX_MARKERS)
    ]
    raw = _put_markers(work, markers_text(DOC, full))
    assert len(v13.read_markers(work, DOC)) == v13.MAX_MARKERS
    carried = load_captures(work, DOC)
    assert carried is not None
    assert len(carried.captures) == v13.MAX_MARKERS
    first = carried.captures[0]
    assert (first.type, first.text, first.created, first.changed) == (
        CaptureType.NOTE,
        note,
        time,
        time,
    )
    _untouched(work, raw, captures=True)


def test_too_many_markers_are_refused(work: Path) -> None:
    many = [
        Marker(f"{n:016x}", CREATED, CREATED, v13.Anchor(n, 0, 1, "x"))
        for n in range(v13.MAX_MARKERS + 1)
    ]
    data = json.loads(markers_text(DOC, many[:1]))
    data["markers"] = [{**data["markers"][0], "id": m.id} for m in many]
    raw = _put_markers(work, json.dumps(data))
    _refused_and_untouched(work, raw, "can't be read")


def test_a_v1_file_over_its_limit_is_not_read(work: Path) -> None:
    with (work / MARKERS).open("wb") as big:
        big.truncate(v13.FILE_LIMIT + 1)
    raw = (work / MARKERS).read_bytes()
    _refused_and_untouched(work, raw, "larger than")


def test_markers_that_would_pass_the_captures_limit_are_not_carried(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _put_markers(work, V1)
    monkeypatch.setattr(module, "FILE_LIMIT", len(captures_text(CARRIED)) - 1)
    _refused_and_untouched(work, raw, "larger than")


def test_a_folder_in_the_markers_place_is_refused(work: Path) -> None:
    (work / MARKERS).mkdir()
    with pytest.raises(MarkersNotCarried, match="not a plain file"):
        load_captures(work, DOC)
    assert (work / MARKERS).is_dir()
    assert not (work / CAPTURES).exists()


@pytest.mark.skipif(sys.platform == "win32", reason="links need rights on Windows")
def test_a_link_in_the_markers_place_is_never_followed(work: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text(V1, encoding="utf-8")
    (work / MARKERS).symlink_to(elsewhere)
    with pytest.raises(MarkersNotCarried, match="not a plain file"):
        load_captures(work, DOC)
    assert (work / MARKERS).is_symlink()
    assert elsewhere.read_text(encoding="utf-8") == V1
    assert not (work / CAPTURES).exists()


# ---- the same verdict as the v1.3 reader ---------------------------------------------------

_id = st.text("0123456789abcdef", min_size=16, max_size=16)
_any_char = st.one_of(st.characters(), st.sampled_from(["\ud800", "\udbff", "\udc00", "\x00"]))
_text = st.text(_any_char, max_size=12)
_marker = st.fixed_dictionaries(
    {
        "id": st.one_of(_id, st.text(max_size=3)),
        "created": _text,
        "changed": _text,
        "anchor": st.fixed_dictionaries(
            {
                "block": st.integers(-1, 5),
                "start": st.integers(-1, 5),
                "end": st.integers(-1, 9),
                "text": _text,
            }
        ),
        "note": st.one_of(st.just(""), _text),
    }
)


@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(_marker, max_size=4), st.booleans())
def test_any_v1_file_carries_over_one_to_one_or_nothing_is_written(
    entries: list[dict[str, Any]], escaped: bool
) -> None:
    """Whatever the v1.3 reader accepts either becomes captures one to one, or is refused
    with nothing written; whatever it refuses is refused here too, with nothing written."""
    data = {"format": "sci2audio-web-markers", "version": 1, "document": DOC, "markers": entries}
    text = json.dumps(data, ensure_ascii=True)
    if not escaped:  # raw UTF-8 where it has a UTF-8 form
        try:
            text = json.dumps(data, ensure_ascii=False)
            text.encode("utf-8")
        except UnicodeEncodeError:
            assume(False)
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        raw = text.encode("utf-8")
        (work / MARKERS).write_bytes(raw)
        try:
            markers = v13.read_markers(work, DOC)
        except v13.MarkersBroken:
            markers = None
        try:
            carried = load_captures(work, DOC)
        except MarkersNotCarried:
            carried = None
        assert (work / MARKERS).read_bytes() == raw
        if carried is None:
            assert not (work / CAPTURES).exists()
            if markers is not None:  # v1.3 reads it: refused only for a lone surrogate
                texts = [t for m in markers for t in (m.created, m.changed, m.note, m.anchor.text)]
                assert any("\ud800" <= c <= "\udfff" for t in texts for c in t)
            return
        assert markers is not None, "carried over a file v1.3 refuses"
        assert len(carried.captures) == len(markers)
        for capture, marker in zip(carried.captures, markers, strict=True):
            assert capture.id == marker.id
            assert capture.type is (CaptureType.NOTE if marker.note else CaptureType.MARK)
            assert capture.text == marker.note
            assert (capture.created, capture.changed) == (marker.created, marker.changed)
            a = marker.anchor
            assert capture.anchor == Anchor(a.block, a.start, a.end, a.text)
        assert read_captures(work, DOC) == carried


# ---- faults while carrying over -------------------------------------------------------------


def test_a_full_disk_writes_nothing_and_the_next_load_carries_over(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _put_markers(work, V1)
    real = files._write_partial

    def full(partial: Path, content: str | bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(OSError, match="No space") as error:
        load_captures(work, DOC)
    assert error.value.errno == errno.ENOSPC
    _untouched(work, raw, captures=False)
    monkeypatch.setattr(files, "_write_partial", real)  # space again
    assert load_captures(work, DOC) == CARRIED
    _untouched(work, raw, captures=True)


def test_a_write_that_fails_half_way_writes_nothing(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _put_markers(work, V1)
    real = files._write_partial

    def half(partial: Path, content: str | bytes) -> None:
        real(partial, content[: len(content) // 2])
        raise OSError(errno.EIO, "the disk went away")

    monkeypatch.setattr(files, "_write_partial", half)
    with pytest.raises(OSError, match="disk went away"):
        load_captures(work, DOC)
    _untouched(work, raw, captures=False)


_KILLED = """
import os, sys
from pathlib import Path
from sci2audio.app import files
from sci2audio.app.captures import load_captures

def before_rename(partial, target, overwrite):
    os._exit(9)  # killed outright: the partial file is complete, nothing renamed

def half_written(partial, content):
    with partial.open("w", encoding="utf-8", newline="\\n") as text:
        text.write(content[: len(content) // 2])
        text.flush()
        os.fsync(text.fileno())
    os._exit(9)  # killed outright while the partial file is half written

if sys.argv[3] == "commit":
    files._commit = before_rename
else:
    files._write_partial = half_written
load_captures(Path(sys.argv[1]), sys.argv[2])
"""


@pytest.mark.parametrize("point", ["write", "commit"])
def test_a_carry_over_killed_mid_write_is_done_again_on_the_next_load(
    work: Path, point: str
) -> None:
    raw = _put_markers(work, V1)
    child = subprocess.run(
        [sys.executable, "-c", _KILLED, str(work), DOC, point], capture_output=True, timeout=120
    )
    assert child.returncode == 9, child.stderr
    assert not (work / CAPTURES).exists()
    left = [p for p in work.iterdir() if p.name.endswith(".partial")]
    assert len(left) == 1  # swept by a later write once its process is gone an hour
    full = len(captures_text(CARRIED).encode("utf-8"))
    assert (left[0].stat().st_size == full) is (point == "commit")
    assert load_captures(work, DOC) == CARRIED
    assert (work / MARKERS).read_bytes() == raw
    assert read_captures(work, DOC) == CARRIED


def test_markers_json_removed_during_the_run_writes_nothing(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put_markers(work, V1)
    real = Path.read_bytes

    def gone(path: Path) -> bytes:
        if path.name == MARKERS:
            path.unlink()  # removed between the check and the read
        return real(path)

    monkeypatch.setattr(Path, "read_bytes", gone)
    with pytest.raises(FileNotFoundError):
        load_captures(work, DOC)
    monkeypatch.undo()
    assert not (work / CAPTURES).exists()
    assert load_captures(work, DOC) is None  # nothing left to carry over


def test_markers_json_removed_after_its_read_still_carries_what_was_read(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put_markers(work, V1)
    real = files._write_partial

    def remove_then_write(partial: Path, content: str | bytes) -> None:
        (work / MARKERS).unlink(missing_ok=True)
        real(partial, content)

    monkeypatch.setattr(files, "_write_partial", remove_then_write)
    assert load_captures(work, DOC) == CARRIED
    assert read_captures(work, DOC) == CARRIED


def test_the_working_folder_removed_during_the_run_fails_and_is_not_made_again(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put_markers(work, V1)
    real = files._write_partial

    def folder_gone(partial: Path, content: str | bytes) -> None:
        for path in work.iterdir():
            path.unlink()
        work.rmdir()
        real(partial, content)

    monkeypatch.setattr(files, "_write_partial", folder_gone)
    with pytest.raises(FileNotFoundError):
        load_captures(work, DOC)
    assert not work.exists()


def test_a_captures_json_written_during_the_run_is_kept_not_replaced(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two servers on one working folder: the other one's file wins and is returned."""
    raw = _put_markers(work, V1)
    theirs = CaptureFile(DOC, CARRIED.captures[:1], migrated_from="markers.json")
    real = files._write_partial

    def other_writer(partial: Path, content: str | bytes) -> None:
        real(partial, content)
        if not (work / CAPTURES).exists():
            (work / CAPTURES).write_text(captures_text(theirs), encoding="utf-8")

    monkeypatch.setattr(files, "_write_partial", other_writer)
    assert load_captures(work, DOC) == theirs
    assert read_captures(work, DOC) == theirs
    _untouched(work, raw, captures=True)


def test_markers_json_is_never_opened_for_writing(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _put_markers(work, V1)
    before = os.stat(work / MARKERS)
    digest = hashlib.sha256(raw).hexdigest()
    real_open = Path.open

    def guarded(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if path.name == MARKERS:
            assert set(mode) <= {"r", "b", "t"}, f"markers.json opened with {mode!r}"
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    load_captures(work, DOC)
    after = os.stat(work / MARKERS)
    assert hashlib.sha256((work / MARKERS).read_bytes()).hexdigest() == digest
    assert after.st_mtime_ns == before.st_mtime_ns
