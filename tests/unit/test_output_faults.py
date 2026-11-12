"""Fault injection for the output stage (#10, tests.md "any file writing"): ffmpeg failing
mid-stream, a full disk, the output folder or a chunk file removed during the run, a run
killed outright, an interrupt, ffmpeg missing. Never a half-written file afterwards."""

from __future__ import annotations

import errno
import json
import shutil
import sys
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

import pytest
from output_helpers import Job, make_job, write_wav
from syrupy.assertion import SnapshotAssertion

from sci2audio.output import (
    ChunkAudioError,
    Ffmpeg,
    FfmpegError,
    FfmpegNotFoundError,
    OutputSettings,
    find_ffmpeg,
    write_audiobook,
)
from sci2audio.output import ffmpeg as ffmpeg_module
from sci2audio.output import write as write_module

REAL = Ffmpeg(find_ffmpeg())


class Hooked(Ffmpeg):
    """The real ffmpeg, with a hook called before run number `at` (counted from 0)."""

    def __init__(self, at: int, hook) -> None:  # type: ignore[no-untyped-def]
        super().__init__(REAL.exe)
        object.__setattr__(self, "at", at)
        object.__setattr__(self, "hook", hook)
        object.__setattr__(self, "calls", [0])

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        call = self.calls[0]
        self.calls[0] += 1
        if call == self.at:
            return self.hook(args, feed)
        return REAL.run(args, feed)


def no_half_files(out: Path) -> None:
    """Nothing partial and no read-along file, which is written only when all audio is done."""
    if out.exists():
        left = [p.name for p in out.iterdir()]
        assert not [n for n in left if n.endswith(".partial")], left
        assert not [n for n in left if n.endswith(".readalong.json")], left


@pytest.fixture
def job(tmp_path: Path) -> Job:
    return make_job(tmp_path / "job", frames=((2400, 1200), (2400,), (1200,)))


def test_ffmpeg_failing_mid_stream_leaves_no_partial_file(job: Job, tmp_path: Path) -> None:
    out = tmp_path / "out"

    def fail(args: Sequence[str], feed: Iterable[bytes]) -> str:
        partial = Path(args[-1])
        with partial.open("wb") as f:  # ffmpeg had written half a file
            f.write(next(iter(feed)))
        raise FfmpegError(1, "Conversion failed!")

    with pytest.raises(FfmpegError, match="Conversion failed"):
        write_audiobook(job.folder, out, job.chapters, job.spoken, job.book, ffmpeg=Hooked(1, fail))
    no_half_files(out)
    assert [p.name for p in out.iterdir()] == ["A Study of Tones - 01 Introduction.mp3"]


@pytest.mark.parametrize("at", [0, 3])  # the first MP3, the M4B
def test_disk_full_while_encoding_leaves_no_partial_file(job: Job, tmp_path: Path, at: int) -> None:
    out = tmp_path / "out"

    def full(args: Sequence[str], feed: Iterable[bytes]) -> str:
        Path(args[-1]).write_bytes(b"\0" * 100)
        raise OSError(errno.ENOSPC, "No space left on device")

    with pytest.raises(OSError, match="No space left"):
        write_audiobook(
            job.folder, out, job.chapters, job.spoken, job.book, ffmpeg=Hooked(at, full)
        )
    no_half_files(out)
    assert not (out / "A Study of Tones.m4b").exists()


def test_disk_full_while_writing_the_readalong_file(
    job: Job, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    original = Path.write_text

    def half_then_full(self: Path, text: str, *args, **kwargs) -> int:  # type: ignore[no-untyped-def]
        if self.name.endswith(".readalong.json.partial"):
            original(self, text[: len(text) // 2], *args, **kwargs)
            raise OSError(errno.ENOSPC, "No space left on device")
        return original(self, text, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", half_then_full)
    with pytest.raises(OSError, match="No space left"):
        write_audiobook(job.folder, out, job.chapters, job.spoken, job.book)
    no_half_files(out)
    assert (out / "A Study of Tones.m4b").exists()  # complete files stay; the json is missing


def test_output_folder_removed_during_the_run(job: Job, tmp_path: Path) -> None:
    out = tmp_path / "out"

    def remove_folder(args: Sequence[str], feed: Iterable[bytes]) -> str:
        shutil.rmtree(out)
        return REAL.run(args, feed)

    with pytest.raises((FfmpegError, OSError)):
        write_audiobook(
            job.folder, out, job.chapters, job.spoken, job.book, ffmpeg=Hooked(1, remove_folder)
        )
    assert not out.exists()  # not silently created again


def test_chunk_file_removed_during_the_run_stops_ffmpeg_and_cleans_up(
    job: Job, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    victim = job.folder / job.spoken[-1].chunk.file

    def remove_chunk(args: Sequence[str], feed: Iterable[bytes]) -> str:
        victim.unlink()
        return REAL.run(args, feed)

    with pytest.raises(ChunkAudioError, match="removed during the run"):
        write_audiobook(
            job.folder, out, job.chapters, job.spoken, job.book, ffmpeg=Hooked(3, remove_chunk)
        )
    no_half_files(out)
    assert not (out / "A Study of Tones.m4b").exists()


def test_chunk_file_changed_during_the_run(job: Job, tmp_path: Path) -> None:
    out = tmp_path / "out"
    victim = job.folder / job.spoken[0].chunk.file

    def shorten(args: Sequence[str], feed: Iterable[bytes]) -> str:
        write_wav(victim, 100)
        return REAL.run(args, feed)

    with pytest.raises(ChunkAudioError, match="changed during the run"):
        write_audiobook(
            job.folder, out, job.chapters, job.spoken, job.book, ffmpeg=Hooked(0, shorten)
        )
    no_half_files(out)


def test_interrupt_while_encoding_leaves_no_partial_file(job: Job, tmp_path: Path) -> None:
    out = tmp_path / "out"

    def interrupted(feed: Iterable[bytes]) -> Iterator[bytes]:
        for n, piece in enumerate(feed):
            if n == 1:
                raise KeyboardInterrupt
            yield piece

    def interrupt(args: Sequence[str], feed: Iterable[bytes]) -> str:
        return REAL.run(args, interrupted(feed))

    with pytest.raises(KeyboardInterrupt):
        write_audiobook(
            job.folder, out, job.chapters, job.spoken, job.book, ffmpeg=Hooked(0, interrupt)
        )
    no_half_files(out)
    assert list(out.iterdir()) == []


def test_partial_files_of_a_killed_run_are_cleared(job: Job, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    stale = out / ".A Study of Tones.m4b.partial"
    stale.write_bytes(b"half")
    write_audiobook(job.folder, out, job.chapters, job.spoken, job.book)
    assert not stale.exists()
    no_partial = [p.name for p in out.iterdir() if p.name.endswith(".partial")]
    assert no_partial == []


def test_existing_files_are_not_replaced_without_overwrite(job: Job, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    mine = out / "A Study of Tones.m4b"
    mine.write_bytes(b"the user's own file")
    with pytest.raises(FileExistsError, match=r"A Study of Tones\.m4b"):
        write_audiobook(job.folder, out, job.chapters, job.spoken, job.book)
    assert mine.read_bytes() == b"the user's own file"
    assert [p.name for p in out.iterdir()] == [mine.name]  # nothing else was written
    write_audiobook(job.folder, out, job.chapters, job.spoken, job.book, overwrite=True)
    assert mine.read_bytes() != b"the user's own file"


def test_a_failed_rerun_leaves_no_old_readalong_file(job: Job, tmp_path: Path) -> None:
    """With overwrite, the old read-along file goes first, so it never vouches for audio that
    a failed rerun left half old, half new."""
    out = tmp_path / "out"
    first = write_audiobook(job.folder, out, job.chapters, job.spoken, job.book)

    def fail(args: Sequence[str], feed: Iterable[bytes]) -> str:
        raise FfmpegError(1, "Conversion failed!")

    with pytest.raises(FfmpegError):
        write_audiobook(
            job.folder,
            out,
            job.chapters,
            job.spoken,
            job.book,
            ffmpeg=Hooked(1, fail),
            overwrite=True,
        )
    assert not first.readalong.exists()
    no_half_files(out)


def test_bad_chunks_are_refused_before_anything_is_written(job: Job, tmp_path: Path) -> None:
    out = tmp_path / "out"
    (job.folder / job.spoken[1].chunk.file).unlink()
    with pytest.raises(ChunkAudioError, match="missing"):
        write_audiobook(job.folder, out, job.chapters, job.spoken, job.book)
    assert not out.exists()
    write_wav(job.folder / job.spoken[1].chunk.file, 100, rate=16000)
    with pytest.raises(ChunkAudioError, match="one sample rate"):
        write_audiobook(job.folder, out, job.chapters, job.spoken, job.book)
    (job.folder / job.spoken[1].chunk.file).write_bytes(b"RIFF....not a wav")
    with pytest.raises(ChunkAudioError, match="not a PCM WAV"):
        write_audiobook(job.folder, out, job.chapters, job.spoken, job.book)
    assert not out.exists()


def test_stereo_or_8_bit_chunks_are_refused(job: Job, tmp_path: Path) -> None:
    import wave

    path = job.folder / job.spoken[0].chunk.file
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\0" * 400)
    with pytest.raises(ChunkAudioError, match="2 channel"):
        write_audiobook(job.folder, tmp_path / "out", job.chapters, job.spoken, job.book)


def test_cover_must_be_jpeg_or_png(job: Job, tmp_path: Path) -> None:
    from dataclasses import replace

    bad = tmp_path / "cover.gif"
    bad.write_bytes(b"GIF89a....")
    with pytest.raises(ValueError, match="JPEG or PNG"):
        write_audiobook(
            job.folder, tmp_path / "out", job.chapters, job.spoken, replace(job.book, cover=bad)
        )
    with pytest.raises(ValueError, match="cannot read the cover"):
        write_audiobook(
            job.folder,
            tmp_path / "out",
            job.chapters,
            job.spoken,
            replace(job.book, cover=tmp_path / "none.jpg"),
        )
    assert not (tmp_path / "out").exists()


# --- finding ffmpeg ------------------------------------------------------------------------


def test_path_ffmpeg_is_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    import imageio_ffmpeg

    def no_bundled() -> str:
        raise RuntimeError("No ffmpeg exe could be found.")

    monkeypatch.setattr(imageio_ffmpeg, "get_ffmpeg_exe", no_bundled)
    monkeypatch.setattr(ffmpeg_module.shutil, "which", lambda name: f"/opt/bin/{name}")
    assert find_ffmpeg() == Path("/opt/bin/ffmpeg")


def test_path_ffmpeg_is_the_fallback_when_imageio_ffmpeg_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)  # import raises ImportError
    monkeypatch.setattr(ffmpeg_module.shutil, "which", lambda name: f"/opt/bin/{name}")
    assert find_ffmpeg() == Path("/opt/bin/ffmpeg")


def test_missing_ffmpeg_gives_a_clear_message(
    job: Job, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    monkeypatch.setattr(ffmpeg_module.shutil, "which", lambda name: None)
    with pytest.raises(FfmpegNotFoundError, match="reinstall sci2audio") as error:
        write_audiobook(job.folder, tmp_path / "out", job.chapters, job.spoken, job.book)
    assert "PATH" in str(error.value)
    assert "IMAGEIO_FFMPEG_EXE" in str(error.value)


def test_ffmpeg_error_message_holds_the_last_lines() -> None:
    error = FfmpegError(1, "\n".join(f"line {n}" for n in range(30)))
    assert "line 29" in str(error)
    assert "line 17" not in str(error)
    assert error.returncode == 1


def test_ffmpeg_stopping_early_with_success_is_still_an_error(tmp_path: Path) -> None:
    """ffmpeg reading only part of the input (here: `-t` stops it) must not pass silently."""
    target = tmp_path / "x.mp3"
    pieces = (bytes(48000) for _ in range(200))  # 100 s at 24 kHz, far beyond the pipe buffer
    with pytest.raises(FfmpegError, match="stopped reading its input early"):
        REAL.run(
            [
                *ffmpeg_module.LOCAL_ONLY,
                "-f",
                "s16le",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-i",
                "pipe:0",
                "-t",
                "0.1",
                "-f",
                "mp3",
                "-y",
                str(target),
            ],
            pieces,
        )


# --- golden file -------------------------------------------------------------------------


class Touching(Ffmpeg):
    """Writes an empty file instead of encoding: the read-along file does not depend on it."""

    def run(self, args: Sequence[str], feed: Iterable[bytes] = ()) -> str:
        for _ in feed:
            pass
        Path(args[-1]).write_bytes(b"")
        return ""


def test_readalong_file_golden(job: Job, tmp_path: Path, snapshot: SnapshotAssertion) -> None:
    written = write_audiobook(
        job.folder,
        tmp_path / "out",
        job.chapters,
        job.spoken,
        job.book,
        OutputSettings(),
        ffmpeg=Touching(Path("unused")),
    )
    text = written.readalong.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert json.loads(text) == snapshot  # parsed, so the golden file's diffs stay readable
    assert write_module.AI_LABEL.startswith("AI-generated")
