"""Generated audio jobs for the output tests: tones in 16-bit mono WAV files, no voice."""

from __future__ import annotations

import errno
import math
import os
import re
import struct
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from sci2audio.core import AudioChunk, Span
from sci2audio.output import BookInfo, Chapter, Pause, Spoken
from sci2audio.output.ffmpeg import find_ffmpeg
from sci2audio.output.write import _inspect_all, _trim_joins

RATE = 24000


def write_wav(path: Path, frames: int, rate: int = RATE, freq: float = 440.0) -> None:
    """A sine tone of `frames` samples."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join(
        struct.pack("<h", int(6000 * math.sin(2 * math.pi * freq * i / rate)))
        for i in range(frames)
    )
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(data)


@dataclass(frozen=True)
class Job:
    folder: Path
    chapters: list[Chapter]
    spoken: list[Spoken]
    book: BookInfo


def make_job(
    folder: Path,
    frames: tuple[tuple[int, ...], ...] = ((4800, 2400), (3600,), (2400, 1200, 6000)),
    pauses: tuple[Pause, ...] = (Pause.PARAGRAPH, Pause.SENTENCE, Pause.HEADING, Pause.NONE),
    titles: tuple[str, ...] = ("Introduction", "Methods; data = 1 # 2", "Results"),
    cover: Path | None = None,
) -> Job:
    """A book with one chapter per entry of `frames`, each chunk a tone of that many samples."""
    chapters, spoken = [], []
    for c, lengths in enumerate(frames):
        chapters.append(Chapter(titles[c], len(spoken)))
        for n in lengths:
            index = len(spoken)
            name = f"chunks/{index:04d}.wav"
            write_wav(folder / name, n, freq=300 + 40 * index)
            chunk = AudioChunk(Span(index, 0, 5), name, n / RATE)
            spoken.append(Spoken(chunk, pauses[index % len(pauses)]))
    book = BookInfo("A Study of Tones", ("Ada Lovelace", "Alan Turing"), "en-GB", cover)
    return Job(folder, chapters, spoken, book)


def quiet_edged_job(folder: Path) -> Job:
    """Every chunk a tone between a quiet lead and tail, as a voice leaves them, and every
    pause a clause pause, inside a chapter and at a chapter's start: the joins trim."""
    chapters, spoken = [], []
    for c, count in enumerate((3, 2)):
        chapters.append(Chapter(f"Part {c + 1}", len(spoken)))
        for _ in range(count):
            index = len(spoken)
            samples = np.concatenate(
                [
                    np.zeros(6000),
                    6000 * np.sin(np.arange(4800) * 0.06 * (index + 2)),
                    np.zeros(7000),
                ]
            ).astype("<i2")
            name = f"chunks/{index:04d}.wav"
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(folder / name), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(RATE)
                audio.writeframes(samples.tobytes())
            chunk = AudioChunk(Span(index, 0, 5), name, len(samples) / RATE)
            spoken.append(Spoken(chunk, Pause.CLAUSE, f"Piece {index},", index > 0))
    return Job(folder, chapters, spoken, BookInfo("Joined Pieces", ("Ada Lovelace",)))


def assert_joins_trim(job: Job) -> None:
    """Fail unless the job's clause joins leave out some of the voice's edge silence: a
    test that holds two ways of joining chunks to byte equality proves nothing about the
    join on chunks with no quiet edges (#480; #754 M1, #762 B1)."""
    audio = _trim_joins(_inspect_all(job.folder, job.spoken), job.chapters, job.spoken)
    assert any(chunk.kept < chunk.frames for chunk in audio), "no join trims anything"


def ffmpeg_exe() -> str:
    return str(find_ffmpeg())


def decoded_samples(path: Path) -> int:
    """How many samples a file decodes to (mono), counted from the raw PCM as it streams."""
    command = [ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-"]
    total = 0
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        assert process.stdout is not None
        while piece := process.stdout.read(1 << 20):
            total += len(piece)
    assert process.returncode == 0
    return total // 2


def write_silence_wav(path: Path, frames: int, rate: int = RATE) -> None:
    """A chunk of silence, quick to make even for hours of audio."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(bytes(2 * frames))


def ffmetadata(path: Path) -> str:
    """The file's tags and chapters as ffmpeg's metadata text (no ffprobe needed)."""
    result = subprocess.run(
        [ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "ffmetadata", "-"],
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def streams(path: Path) -> list[str]:
    """The "Stream #..." lines `ffmpeg -i` prints (it exits 1 for want of an output)."""
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    return re.findall(r"Stream #\S+.*", result.stderr)


def chapters_of(meta: str) -> list[tuple[int, int, str]]:
    """(start, end, title) of each CHAPTER in ffmetadata text, in samples at RATE."""
    found = []
    for section in meta.split("[CHAPTER]")[1:]:
        fields = dict(line.split("=", 1) for line in section.strip().splitlines() if "=" in line)
        num, den = fields["TIMEBASE"].split("/")
        scale = RATE * int(num) / int(den)
        start, end = round(int(fields["START"]) * scale), round(int(fields["END"]) * scale)
        found.append((start, end, unescape(fields["title"])))
    return found


def tags_of(meta: str) -> dict[str, str]:
    """The global tags of ffmetadata text (before the first section)."""
    head = meta.split("[", 1)[0]
    pairs = (line.split("=", 1) for line in head.splitlines()[1:] if "=" in line)
    return {key: unescape(value) for key, value in pairs}


def unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


NEWER = "\U0001fae8"  # SHAKING FACE, Unicode 15.0 (2022): newer than an older Mac's table


def refuse_newer_names(monkeypatch: pytest.MonkeyPatch, newer: str = NEWER) -> list[str]:
    """Make `os.open` act as an APFS whose Unicode table is older than Python's (#493): a
    name holding `newer` fails with EILSEQ in a folder that exists (in a missing one the
    real error comes first, as on a Mac). Returns the names it was asked to open (the
    probes), so a test can see that ordinary names are never tried."""
    asked: list[str] = []
    real = os.open

    def fake(path, flags, mode=0o777, *args, **kwargs):  # type: ignore[no-untyped-def]
        name = os.path.basename(os.fspath(path))
        asked.append(name)
        if newer in name and os.path.isdir(os.path.dirname(os.fspath(path)) or "."):
            raise OSError(errno.EILSEQ, os.strerror(errno.EILSEQ), os.fspath(path))
        return real(path, flags, mode, *args, **kwargs)

    monkeypatch.setattr(os, "open", fake)
    return asked
