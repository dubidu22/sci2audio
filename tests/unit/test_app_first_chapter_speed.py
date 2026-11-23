"""How soon the first chapter is playable (#723, LW-01; docs/baseline.md): a ten-chapter
book and a voice that takes a fixed time per chunk, as a real voice does."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from audio_fakes import FakeVoice

from sci2audio.app import AudioProgress, JobSettings, run_audio_job

CHAPTERS = 10
PER_CHUNK = 0.1  # seconds the voice takes for each chunk


@pytest.mark.benchmark
def test_time_to_the_first_playable_chapter(tmp_path: Path, benchmark) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "book.md"
    source.write_text(
        "\n\n".join(
            f"# Chapter {n}\n\nThe chapter {n} starts here. It ends after this sentence."
            for n in range(1, CHAPTERS + 1)
        ),
        encoding="utf-8",
    )
    times: list[tuple[float, float]] = []

    def job() -> None:
        first: list[float] = []

        def progress(event: AudioProgress) -> None:
            if event.ready is not None and not first:
                first.append(time.perf_counter())

        voice = FakeVoice(on_speak=lambda text: time.sleep(PER_CHUNK))
        start = time.perf_counter()
        run_audio_job(
            source,
            JobSettings(output_folder=tmp_path / "out"),
            tmp_path / "work",
            voice=voice.source(),
            progress=progress,
            overwrite=True,
        )
        times.append((first[0] - start, time.perf_counter() - start))
        # the next round speaks again
        for chunk in (tmp_path / "work" / "chunks").glob("*/*.wav"):
            chunk.unlink()

    benchmark.pedantic(job, rounds=3, iterations=1)
    for first, whole in times:
        print(f"first chapter playable after {first:.2f} s of {whole:.2f} s ({first / whole:.0%})")
        # before #723 nothing was playable before the job's end (100 %)
        assert first / whole < 0.2
