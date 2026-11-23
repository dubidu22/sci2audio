"""Fault injection for the whole-audiobook build (#725, tests.md "resume, download or any
file writing"): killed midway, a full disk, a chunk removed during the build, no network.
Never a half-written file afterwards, and the next build works."""

from __future__ import annotations

import errno
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest
from audio_fakes import FakeVoice

from sci2audio.app import JobError, JobSettings, build_book, run_audio_job
from sci2audio.app import book as book_module
from sci2audio.app.playable import read_record
from sci2audio.output import Ffmpeg, find_ffmpeg
from sci2audio.testing import no_network

UNIT = Path(__file__).resolve().parent
TITLES = ("Alpha", "Beta", "Gamma")
BOOK = "\n\n".join(f"# {t}\n\nThe chapter {t} starts here. It ends with {t}." for t in TITLES)


def made(folder: Path) -> None:
    path = folder / "in" / "book.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BOOK, encoding="utf-8", newline="\n")
    settings = JobSettings(output_folder=folder / "out")
    run_audio_job(path, settings, folder / "work", voice=FakeVoice().source())


def books(folder: Path) -> list[str]:
    """Every whole-book file and partial file in the output folder."""
    return sorted(p.name for p in (folder / "out").iterdir() if ".m4b" in p.name)


KILLED_BUILD = textwrap.dedent(
    """
    import sys, time
    from pathlib import Path
    from sci2audio.app import build_book
    from sci2audio.output import Ffmpeg, find_ffmpeg

    folder = Path(sys.argv[1])

    class Hanging(Ffmpeg):
        def run(self, args, feed=()):
            for _ in feed:  # part of the book is given to ffmpeg, then it hangs
                break
            Path(args[-1]).write_bytes(b"half an m4b")
            (folder / "hanging").write_text("building")
            while True:
                time.sleep(1)

    build_book(folder / "work", folder / "out", ffmpeg=Hanging(find_ffmpeg()))
    """
)


def test_a_build_killed_midway_leaves_no_half_file_and_builds_again(tmp_path: Path) -> None:
    made(tmp_path)
    child = subprocess.Popen([sys.executable, "-c", KILLED_BUILD, str(tmp_path)])
    try:
        deadline = time.monotonic() + 120
        while not (tmp_path / "hanging").exists():
            assert child.poll() is None, "the build ended before it was killed"
            assert time.monotonic() < deadline  # clock-bound: the loop's way out only
            time.sleep(0.05)
        child.kill()  # SIGKILL / TerminateProcess: no clean-up runs
        child.wait(timeout=60)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
    assert "book.m4b" not in books(tmp_path)  # only ever a partial file, never the book
    built = build_book(tmp_path / "work", tmp_path / "out")
    assert not built.reused
    assert books(tmp_path) == ["book.m4b"]  # the partial left by the kill is gone
    record = read_record(tmp_path / "work")
    assert record is not None
    assert [b.file.name for b in record.built] == ["book.m4b"]


class FullDisk(Ffmpeg):
    """ffmpeg that writes part of the file, then finds the disk full."""

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        for _ in feed:
            break
        Path(args[-1]).write_bytes(b"half")
        raise OSError(errno.ENOSPC, "No space left on device", args[-1])


def test_a_full_disk_while_building_leaves_no_half_file(tmp_path: Path) -> None:
    made(tmp_path)
    with pytest.raises(JobError, match="No space left on device"):
        build_book(tmp_path / "work", tmp_path / "out", ffmpeg=FullDisk(find_ffmpeg()))
    assert books(tmp_path) == []
    record = read_record(tmp_path / "work")
    assert record is not None
    assert record.built == ()
    assert build_book(tmp_path / "work", tmp_path / "out").path.is_file()


def test_a_chunk_removed_during_the_build_fails_with_a_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    made(tmp_path)
    found = book_module._chapters

    def then_removed(work: Path, record):  # type: ignore[no-untyped-def]
        chapters, unavailable = found(work, record)
        (work / chapters[1][1][0].chunk.file).unlink()  # after the check, before the build
        return chapters, unavailable

    monkeypatch.setattr(book_module, "_chapters", then_removed)
    with pytest.raises(JobError, match="generate the chapter again"):
        build_book(tmp_path / "work", tmp_path / "out")
    assert books(tmp_path) == []


def test_a_build_runs_with_the_network_blocked(tmp_path: Path) -> None:
    made(tmp_path)
    with no_network() as attempts:
        built = build_book(tmp_path / "work", tmp_path / "out")
    assert attempts == []
    assert built.path.is_file()
