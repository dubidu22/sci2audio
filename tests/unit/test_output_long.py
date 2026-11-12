"""Long books: no drift over hours (slow, nightly) and the encoding speed (benchmark)."""

from __future__ import annotations

from pathlib import Path

import pytest
from output_helpers import (
    RATE,
    chapters_of,
    decoded_samples,
    ffmetadata,
    write_silence_wav,
)

from sci2audio.core import AudioChunk, Span
from sci2audio.output import (
    BookInfo,
    Chapter,
    OutputSettings,
    Pause,
    Spoken,
    read_readalong,
    write_audiobook,
)
from sci2audio.output.timeline import plan_timeline


def long_job(folder: Path, minutes: int, chunk_seconds: int = 10, per_chapter: int = 60):
    """`minutes` of audio in chunks of `chunk_seconds`, a chapter every `per_chapter` chunks."""
    count = minutes * 60 // chunk_seconds
    frames = chunk_seconds * RATE
    for name in ("odd.wav", "even.wav"):
        write_silence_wav(folder / name, frames + (name == "odd.wav"))  # unequal on purpose
    spoken = [
        Spoken(AudioChunk(Span(i, 0, 1), "odd.wav" if i % 2 else "even.wav", 10.0), Pause.SENTENCE)
        for i in range(count)
    ]
    chapters = [Chapter(f"Part {n + 1}", n) for n in range(0, count, per_chapter)]
    lengths = [frames + (i % 2) for i in range(count)]
    return chapters, spoken, lengths


@pytest.mark.slow
def test_two_hour_book_has_no_drift(tmp_path: Path) -> None:
    chapters, spoken, lengths = long_job(tmp_path / "job", minutes=120)
    written = write_audiobook(
        tmp_path / "job", tmp_path / "out", chapters, spoken, BookInfo("Long")
    )
    timeline = plan_timeline(chapters, spoken, lengths, RATE, OutputSettings())
    assert written.m4b is not None
    assert chapters_of(ffmetadata(written.m4b)) == [
        (c.start, c.end, c.title) for c in timeline.chapters
    ]
    assert decoded_samples(written.m4b) == timeline.total
    last = written.mp3s[-1]
    assert decoded_samples(last) == timeline.chapters[-1].end - timeline.chapters[-1].start
    data = read_readalong(written.readalong)
    assert data.chunks[-1].end == round(timeline.total / RATE, 3)


@pytest.mark.benchmark
def test_benchmark_ten_minutes(tmp_path: Path, benchmark) -> None:  # type: ignore[no-untyped-def]
    """Encode 10 minutes of audio to MP3s and an M4B (docs/baseline.md)."""
    chapters, spoken, _ = long_job(tmp_path / "job", minutes=10, per_chapter=20)

    def run() -> None:
        write_audiobook(
            tmp_path / "job", tmp_path / "out", chapters, spoken, BookInfo("Bench"), overwrite=True
        )

    benchmark.pedantic(run, rounds=3, iterations=1)
