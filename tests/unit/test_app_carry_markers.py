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
    peek_captures,
    peek_carry_over,
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


def _v1_of_size(size: int) -> bytes:
    """A valid v1 file of exactly `size` bytes: spaces after the JSON, which v1.3 reads."""
    raw = V1.encode("utf-8")
    assert len(raw) <= size
    return raw + b" " * (size - len(raw))


def test_a_v1_file_of_exactly_the_size_limit_carries_over(work: Path) -> None:
    raw = _put_markers(work, _v1_of_size(v13.FILE_LIMIT))
    assert (work / MARKERS).stat().st_size == module.MARKERS_LIMIT == 2_000_000
    assert len(v13.read_markers(work, DOC)) == len(CARRIED.captures)  # v1.3 accepts it
    assert load_captures(work, DOC) == CARRIED
    _untouched(work, raw, captures=True)


def test_a_valid_v1_file_one_byte_over_the_size_limit_is_refused(work: Path) -> None:
    raw = _put_markers(work, _v1_of_size(v13.FILE_LIMIT + 1))
    with pytest.raises(v13.MarkersBroken):  # v1.3 refuses it too
        v13.read_markers(work, DOC)
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


# ---- looking at what a load would carry over, writing nothing (#1023) ----------------------


def _folder(work: Path) -> dict[str, bytes]:
    """Every entry of the working folder with its bytes (a folder as the marker byte string
    b"<not a file>"): what a call that must write, rename and delete nothing leaves
    exactly as it was."""
    return {
        p.name: (p.read_bytes() if p.is_file() else b"<not a file>") for p in sorted(work.iterdir())
    }


def _copy(work: Path, to: Path) -> Path:
    to.mkdir()
    for p in work.iterdir():
        (to / p.name).write_bytes(p.read_bytes())
    return to


def test_peeking_at_v1_markers_shows_what_the_carry_over_makes_and_writes_nothing(
    work: Path,
) -> None:
    _put_markers(work, V1)
    before = _folder(work)
    assert peek_captures(work, DOC) == CARRIED
    assert peek_captures(work, DOC).count() == {  # type: ignore[union-attr]
        CaptureType.NOTE: 1,
        CaptureType.QUOTE: 0,
        CaptureType.MARK: 2,
    }
    assert _folder(work) == before
    assert not (work / CAPTURES).exists()


def test_peeking_with_no_file_at_all_is_none_and_writes_nothing(work: Path) -> None:
    before = _folder(work)
    assert peek_captures(work, DOC) is None
    assert _folder(work) == before


def test_peeking_reads_captures_json_and_not_the_markers_beside_it(work: Path) -> None:
    _put_markers(work, b"{broken")
    write_captures(work, CARRIED)
    (work / MARKERS).write_bytes(b"{broken")
    before = _folder(work)
    assert peek_captures(work, DOC) == CARRIED
    assert _folder(work) == before


def test_peeking_at_a_broken_captures_json_reports_it_and_leaves_it(work: Path) -> None:
    _put_markers(work, V1)
    (work / CAPTURES).write_bytes(b"{broken")
    before = _folder(work)
    with pytest.raises(CapturesBroken, match=r"captures\.json") as error:
        peek_captures(work, DOC)
    assert not isinstance(error.value, MarkersNotCarried)
    assert _folder(work) == before


@pytest.mark.parametrize("case", sorted(BROKEN_V1) + sorted(SURROGATE_V1))
def test_peeking_at_a_markers_file_the_carry_over_refuses_gives_its_error_and_writes_nothing(
    work: Path, tmp_path: Path, case: str
) -> None:
    raw = _put_markers(work, {**BROKEN_V1, **SURROGATE_V1}[case])
    twin = _copy(work, tmp_path / "twin")
    before = _folder(work)
    with pytest.raises(MarkersNotCarried) as peeked:
        peek_captures(work, DOC)
    with pytest.raises(MarkersNotCarried) as loaded:
        load_captures(twin, DOC)
    assert str(peeked.value).replace(str(work), "") == str(loaded.value).replace(str(twin), "")
    assert _folder(work) == before
    _untouched(work, raw, captures=False)


def test_peeking_at_v1_markers_that_would_pass_the_captures_limit_is_refused_as_a_load_is(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _put_markers(work, V1)
    monkeypatch.setattr(module, "FILE_LIMIT", len(captures_text(CARRIED)) - 1)
    with pytest.raises(MarkersNotCarried, match="larger than"):
        peek_captures(work, DOC)
    _untouched(work, raw, captures=False)


def test_peeking_at_a_folder_or_a_link_in_the_markers_place_is_refused_and_not_followed(
    work: Path, tmp_path: Path
) -> None:
    (work / MARKERS).mkdir()
    with pytest.raises(MarkersNotCarried, match="not a plain file"):
        peek_captures(work, DOC)
    (work / MARKERS).rmdir()
    if sys.platform != "win32":
        elsewhere = tmp_path / "elsewhere.json"
        elsewhere.write_text(V1, encoding="utf-8")
        (work / MARKERS).symlink_to(elsewhere)
        with pytest.raises(MarkersNotCarried, match="not a plain file"):
            peek_captures(work, DOC)
        assert (work / MARKERS).is_symlink()
    assert not (work / CAPTURES).exists()


def test_peeking_never_calls_the_writer_and_never_opens_a_file_for_writing(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _put_markers(work, V1)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a peek wrote")

    monkeypatch.setattr(module, "write_texts", refuse)
    monkeypatch.setattr(files, "write_texts", refuse)
    monkeypatch.setattr(Path, "write_bytes", refuse)
    monkeypatch.setattr(Path, "write_text", refuse)
    monkeypatch.setattr(Path, "unlink", refuse)
    monkeypatch.setattr(Path, "rename", refuse)
    monkeypatch.setattr(Path, "replace", refuse)
    monkeypatch.setattr(os, "replace", refuse)
    monkeypatch.setattr(os, "rename", refuse)
    monkeypatch.setattr(os, "remove", refuse)
    assert peek_captures(work, DOC) == CARRIED


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(_marker, max_size=4), st.booleans())
def test_a_peek_and_a_load_agree_on_any_v1_file(
    entries: list[dict[str, Any]], escaped: bool
) -> None:
    data = {"format": "sci2audio-web-markers", "version": 1, "document": DOC, "markers": entries}
    text = json.dumps(data, ensure_ascii=True)
    if not escaped:
        try:
            text = json.dumps(data, ensure_ascii=False)
            text.encode("utf-8")
        except UnicodeEncodeError:
            assume(False)
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder) / "a"
        twin = Path(folder) / "b"
        work.mkdir()
        (work / MARKERS).write_bytes(text.encode("utf-8"))
        _copy(work, twin)
        before = _folder(work)
        try:
            peeked: CaptureFile | None = peek_captures(work, DOC)
        except MarkersNotCarried:
            peeked = None
        assert _folder(work) == before
        try:
            loaded: CaptureFile | None = load_captures(twin, DOC)
        except MarkersNotCarried:
            loaded = None
        assert peeked == loaded


# ---- asking whether a carry-over is what is left to do, writing nothing (#1023) ------------


def test_the_carry_over_peek_shows_what_a_load_would_write_and_writes_nothing(
    work: Path,
) -> None:
    _put_markers(work, V1)
    before = _folder(work)
    assert peek_carry_over(work, DOC) == CARRIED
    assert _folder(work) == before


def test_the_carry_over_peek_is_none_with_no_markers_or_beside_a_captures_json(
    work: Path,
) -> None:
    assert peek_carry_over(work, DOC) is None
    _put_markers(work, b"{broken")  # not read while captures.json is there
    write_captures(work, CaptureFile(DOC, migrated_from=MARKERS))
    before = _folder(work)
    assert peek_carry_over(work, DOC) is None
    assert _folder(work) == before


def test_the_carry_over_peek_refuses_what_a_load_refuses(work: Path) -> None:
    _put_markers(work, b"{broken")
    with pytest.raises(MarkersNotCarried):
        peek_carry_over(work, DOC)
    (work / MARKERS).unlink()
    (work / CAPTURES).write_bytes(b"{broken")
    with pytest.raises(CapturesBroken):
        peek_carry_over(work, DOC)


def test_after_a_full_disk_the_peek_tells_the_carry_over_from_another_failure(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the web layer asks after an OSError of a load (#910): the carry-over's own
    write failed, so the peek still sees the carry-over; with the markers gone the peek
    is None, and nothing is written either way."""
    raw = _put_markers(work, V1)

    def full(partial: Path, content: str | bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(OSError, match="No space"):
        load_captures(work, DOC)
    assert peek_carry_over(work, DOC) == CARRIED
    _untouched(work, raw, captures=False)
    (work / MARKERS).unlink()
    assert peek_carry_over(work, DOC) is None


@pytest.mark.parametrize("unreadable", [MARKERS, CAPTURES])
@pytest.mark.parametrize("peek", [peek_captures, peek_carry_over])
def test_a_peek_whose_read_fails_raises_the_oserror_and_leaves_the_folder(
    work: Path, monkeypatch: pytest.MonkeyPatch, unreadable: str, peek: Any
) -> None:
    """A file that can't be read (no permission, a failing disk) reaches the caller as the
    same OSError a load raises, never as a refusal, a count of zero or a written file."""
    _put_markers(work, V1)
    (work / CAPTURES).write_bytes(captures_text(CARRIED).encode("utf-8"))
    if unreadable == MARKERS:
        (work / CAPTURES).unlink()
    before = _folder(work)
    real = Path.read_bytes

    def read_bytes(self: Path) -> bytes:
        if self.name == unreadable:
            raise PermissionError(errno.EACCES, "Permission denied")
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    with pytest.raises(PermissionError):
        peek(work, DOC)
    monkeypatch.undo()
    assert _folder(work) == before


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


# ---- no write hides markers that wait for their carry-over (#875) --------------------------
# Once captures.json exists, markers.json is not read (ADR-008 2.1 item 5): a writer that
# skips `load_captures` and creates captures.json beside them would hide them for good.

FRESH = CaptureFile(DOC, CARRIED.captures[:1])  # not the carry-over: no migrated_from


def _markers_in_place(work: Path, tmp_path: Path, kind: str) -> None:
    if kind == "v1":
        _put_markers(work, V1)
    elif kind == "broken":
        _put_markers(work, b"{broken")
    elif kind == "folder":
        (work / MARKERS).mkdir()
    elif kind == "dangling":
        if sys.platform == "win32":
            pytest.skip("links need rights on Windows")
        (work / MARKERS).symlink_to(tmp_path / "gone.json")
    else:
        if sys.platform == "win32":
            pytest.skip("links need rights on Windows")
        (tmp_path / "elsewhere.json").write_text(V1, encoding="utf-8")
        (work / MARKERS).symlink_to(tmp_path / "elsewhere.json")


def _snapshot(work: Path) -> dict[str, bytes | str]:
    """Every entry of the working folder: a file's bytes, a link's target path and, if
    there is one, its bytes, or 'folder'."""
    seen: dict[str, bytes | str] = {}
    for path in work.iterdir():
        if path.is_symlink():
            seen[path.name] = str(os.readlink(path))
            if path.exists() and path.is_file():
                seen[f"{path.name} -> target"] = path.read_bytes()
        elif path.is_dir():
            seen[path.name] = "folder"
        else:
            seen[path.name] = path.read_bytes()
    return seen


@pytest.mark.parametrize("kind", ["v1", "broken", "folder", "link", "dangling"])
@pytest.mark.parametrize("captures", [FRESH, CaptureFile(DOC)], ids=["one", "empty"])
def test_a_new_captures_json_beside_uncarried_markers_is_refused(
    work: Path, tmp_path: Path, kind: str, captures: CaptureFile
) -> None:
    _markers_in_place(work, tmp_path, kind)
    before = _snapshot(work)
    with pytest.raises(MarkersNotCarried, match=r"markers\.json") as refused:
        write_captures(work, captures)
    assert isinstance(refused.value, CapturesBroken)  # capturing stays off, as for a broken file
    assert _snapshot(work) == before  # markers.json as it was, no captures.json, no partial


def test_the_carry_over_itself_still_writes(work: Path) -> None:
    raw = _put_markers(work, V1)
    write_captures(work, CARRIED)
    assert read_captures(work, DOC) == CARRIED
    _untouched(work, raw, captures=True)


def test_a_write_after_the_carry_over_goes_through(work: Path) -> None:
    """The server's flow (#397, PR #886): `load_captures`, a change, `write_captures`."""
    raw = _put_markers(work, V1)
    assert load_captures(work, DOC) == CARRIED
    write_captures(work, FRESH)  # once captures.json is there, migrated_from may go
    assert load_captures(work, DOC) == FRESH
    _untouched(work, raw, captures=True)


def test_markers_put_beside_an_existing_captures_json_do_not_stop_a_write(work: Path) -> None:
    write_captures(work, CaptureFile(DOC))
    raw = _put_markers(work, b"{broken")  # not read while captures.json is there
    write_captures(work, FRESH)
    assert read_captures(work, DOC) == FRESH
    _untouched(work, raw, captures=True)


def test_captures_json_removed_by_hand_after_a_load_refuses_the_next_write(work: Path) -> None:
    """The recovery path stays open: the markers come back, they are not hidden again."""
    raw = _put_markers(work, V1)
    load_captures(work, DOC)
    (work / CAPTURES).unlink()
    with pytest.raises(MarkersNotCarried):
        write_captures(work, FRESH)
    _untouched(work, raw, captures=False)
    assert load_captures(work, DOC) == CARRIED


def test_a_full_disk_during_a_carry_over_write_leaves_both_files(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _put_markers(work, V1)

    def full(partial: Path, content: str | bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(OSError, match="No space"):
        write_captures(work, CARRIED)
    _untouched(work, raw, captures=False)


def test_a_refused_write_never_opens_a_file_for_writing(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _put_markers(work, V1)

    def no_write(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("a refused write reached write_texts")

    monkeypatch.setattr(module, "write_texts", no_write)
    with pytest.raises(MarkersNotCarried):
        write_captures(work, FRESH)
    _untouched(work, raw, captures=False)
