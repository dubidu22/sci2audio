# ruff: noqa: RUF001  (the sentences are as papers print them)
"""A document's `captures.json` (#396, ADR-008 2.1 item 4): reading and writing it, a
golden file of its text, refusing a file this version can't read without touching it,
never touching another file, and writes under faults (tests.md: file writing)."""

from __future__ import annotations

import errno
import sys
from pathlib import Path

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.app import captures as module
from sci2audio.app import files
from sci2audio.app.captures import (
    CAPTURES,
    FILE_LIMIT,
    CapturesBroken,
    captures_text,
    read_captures,
    write_captures,
)
from sci2audio.core import Anchor, Capture, CaptureFile, CaptureType

DOC = "0123456789abcdef"
TIME = "2026-11-20T19:04:00Z"
SENTENCE = "Sleep loss lowered recall by 12 % (p < .01)."
MARK = Capture("00000000000000a1", CaptureType.MARK, TIME, TIME, Anchor(1, 0, 44, SENTENCE))
NOTE = Capture(
    "00000000000000b2",
    CaptureType.NOTE,
    TIME,
    TIME,
    Anchor(2, 0, 22, "Naps were not counted."),
    "Were naps left out on purpose?",
)
QUOTE = Capture("00000000000000c3", CaptureType.QUOTE, TIME, TIME, Anchor(1, 0, 44, SENTENCE))
THREE = CaptureFile(DOC, (MARK, NOTE, QUOTE))

# the person's other files in the working folder, which a captures write never touches
NEIGHBOURS = {
    "markers.json": b'{"format": "sci2audio-web-markers", "a person\'s": "markers"}\n',
    "position.json": b'{"chunk": 3}\n',
    "source.pdf": b"%PDF-1.7 not really",
}


@pytest.fixture
def work(tmp_path: Path) -> Path:
    folder = tmp_path / DOC
    folder.mkdir()
    for name, content in NEIGHBOURS.items():
        (folder / name).write_bytes(content)
    return folder


def _neighbours_untouched(work: Path) -> None:
    for name, content in NEIGHBOURS.items():
        assert (work / name).read_bytes() == content
    assert sorted(p.name for p in work.iterdir()) == sorted([*NEIGHBOURS, CAPTURES])


def test_no_file_reads_as_none_and_reading_creates_nothing(work: Path) -> None:
    assert read_captures(work, DOC) is None
    assert not (work / CAPTURES).exists()


def test_written_captures_read_back_the_same_and_nothing_else_changes(work: Path) -> None:
    write_captures(work, THREE)
    assert read_captures(work, DOC) == THREE
    _neighbours_untouched(work)


def test_the_file_text_golden_file(work: Path, snapshot: SnapshotAssertion) -> None:
    """The bytes on disk, key order and all; a carried-over file names its source."""
    write_captures(work, THREE)
    assert (work / CAPTURES).read_text(encoding="utf-8") == snapshot(name="three types")
    carried = CaptureFile(DOC, (MARK, NOTE), migrated_from="markers.json")
    write_captures(work, carried)
    assert (work / CAPTURES).read_text(encoding="utf-8") == snapshot(name="carried over")
    assert read_captures(work, DOC) == carried


def test_the_file_stays_when_it_holds_no_capture_any_more(work: Path) -> None:
    write_captures(work, THREE)
    write_captures(work, CaptureFile(DOC))
    assert read_captures(work, DOC) == CaptureFile(DOC)
    _neighbours_untouched(work)


def test_the_file_is_utf8_with_the_printed_text_as_it_is(work: Path) -> None:
    quote = Capture("00000000000000d4", CaptureType.QUOTE, TIME, TIME, Anchor(0, 0, 9, "α = 0.05 "))
    write_captures(work, CaptureFile(DOC, (quote,)))
    raw = (work / CAPTURES).read_bytes()
    assert "α = 0.05 ".encode() in raw
    assert raw.endswith(b"\n")


# ---- a file this version can't read --------------------------------------------------------

GOOD = captures_text(THREE).encode()
BROKEN = {
    "not json": b"{broken",
    "not utf-8": b'{"format": "sci2audio-captures", "x": "\xff"}',
    "a list": b"[]",
    "another format": GOOD.replace(b"sci2audio-captures", b"sci2audio-web-markers"),
    "a later version": GOOD.replace(b'"version": 1', b'"version": 2'),
    "another document": GOOD.replace(DOC.encode(), b"fedcba9876543210"),
    "a card": GOOD.replace(b'"type": "quote"', b'"type": "card"'),
    "a nan": GOOD.replace(b'"block": 2', b'"block": NaN'),
    "nested too deeply": b"[" * 100_000 + b"]" * 100_000,
    "empty": b"",
}


@pytest.mark.parametrize("case", sorted(BROKEN))
def test_a_file_this_version_cant_read_fails_clearly_and_is_never_written(
    work: Path, case: str
) -> None:
    path = work / CAPTURES
    path.write_bytes(BROKEN[case])
    with pytest.raises(CapturesBroken, match=r"captures\.json"):
        read_captures(work, DOC)
    with pytest.raises(CapturesBroken):
        write_captures(work, THREE)
    assert path.read_bytes() == BROKEN[case]
    _neighbours_untouched(work)  # and no partial file either


def test_a_file_over_the_limit_is_not_read(work: Path) -> None:
    path = work / CAPTURES
    with path.open("wb") as big:
        big.truncate(FILE_LIMIT + 1)
    with pytest.raises(CapturesBroken, match="larger than"):
        read_captures(work, DOC)
    with pytest.raises(CapturesBroken):
        write_captures(work, THREE)
    assert path.stat().st_size == FILE_LIMIT + 1


def test_captures_that_would_pass_the_limit_are_not_written(
    work: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_captures(work, CaptureFile(DOC, (MARK,)))
    before = (work / CAPTURES).read_bytes()
    monkeypatch.setattr(module, "FILE_LIMIT", len(before) + 10)
    with pytest.raises(ValueError, match="larger than"):
        write_captures(work, THREE)
    assert (work / CAPTURES).read_bytes() == before
    _neighbours_untouched(work)


def test_a_folder_in_the_files_place_is_refused(work: Path) -> None:
    (work / CAPTURES).mkdir()
    with pytest.raises(CapturesBroken, match="not a plain file"):
        read_captures(work, DOC)
    with pytest.raises(CapturesBroken):
        write_captures(work, THREE)
    assert (work / CAPTURES).is_dir()


@pytest.mark.skipif(sys.platform == "win32", reason="links need rights on Windows")
def test_a_link_in_the_files_place_is_never_followed_or_written(work: Path, tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text(captures_text(CaptureFile(DOC)), encoding="utf-8")
    before = elsewhere.read_bytes()
    (work / CAPTURES).symlink_to(elsewhere)
    with pytest.raises(CapturesBroken, match="not a plain file"):
        read_captures(work, DOC)
    with pytest.raises(CapturesBroken):
        write_captures(work, THREE)
    assert (work / CAPTURES).is_symlink()
    assert elsewhere.read_bytes() == before


def test_a_dangling_link_is_refused_too(work: Path, tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("links need rights on Windows")
    (work / CAPTURES).symlink_to(tmp_path / "gone.json")
    with pytest.raises(CapturesBroken):
        write_captures(work, THREE)
    assert not (tmp_path / "gone.json").exists()


# ---- writing under faults ------------------------------------------------------------------


@pytest.fixture
def kept(work: Path) -> bytes:
    write_captures(work, CaptureFile(DOC, (NOTE,)))
    return (work / CAPTURES).read_bytes()


def test_a_write_that_fails_half_way_leaves_the_old_file(
    work: Path, kept: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = files._write_partial

    def half(partial: Path, content: str | bytes) -> None:
        real(partial, content[: len(content) // 2])
        raise OSError(errno.EIO, "the disk went away")

    monkeypatch.setattr(files, "_write_partial", half)
    with pytest.raises(OSError, match="disk went away"):
        write_captures(work, THREE)
    assert (work / CAPTURES).read_bytes() == kept
    _neighbours_untouched(work)


def test_a_full_disk_leaves_the_old_file(
    work: Path, kept: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full(partial: Path, content: str | bytes) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "_write_partial", full)
    with pytest.raises(OSError, match="No space") as error:
        write_captures(work, THREE)
    assert error.value.errno == errno.ENOSPC
    assert (work / CAPTURES).read_bytes() == kept
    _neighbours_untouched(work)


def test_a_removed_working_folder_fails_clearly_and_is_not_made_again(tmp_path: Path) -> None:
    gone = tmp_path / DOC
    with pytest.raises(FileNotFoundError):
        write_captures(gone, THREE)
    assert not gone.exists()


@pytest.mark.parametrize(
    "field",
    ['"document": "', '"created": "', '"changed": "', '"text": "Sleep', '"text": "Were'],
)
def test_a_lone_surrogate_in_any_text_makes_the_file_unreadable(work: Path, field: str) -> None:
    """Valid UTF-8 JSON, but "\\ud800" has no UTF-8 form: such a file could be read and
    never written back, so it is refused and left as it is."""
    text = captures_text(THREE).replace(field, field + "\\ud800", 1)
    assert field + "\\ud800" in text
    path = work / CAPTURES
    path.write_text(text, encoding="utf-8")
    with pytest.raises(CapturesBroken, match="surrogate"):
        read_captures(work, DOC)
    with pytest.raises(CapturesBroken):
        write_captures(work, THREE)
    assert path.read_text(encoding="utf-8") == text
    _neighbours_untouched(work)
