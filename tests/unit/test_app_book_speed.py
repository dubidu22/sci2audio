"""How long building the whole audiobook on request takes (#725, LW-03; docs/baseline.md):
a ten-chapter book of about two minutes of audio, built from the chunk cache."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from audio_fakes import FakeVoice

from sci2audio.app import JobSettings, build_book, run_audio_job
from sci2audio.output import BookKind, read_readalong

CHAPTERS = 10
SENTENCE = "This sentence is one of many that make the chapter long enough to time."


@pytest.mark.benchmark
@pytest.mark.parametrize("kind", [BookKind.M4B, BookKind.MP3])
def test_time_to_build_the_whole_book(tmp_path: Path, benchmark, kind: BookKind) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "book.md"
    source.write_text(
        "\n\n".join(
            f"# Chapter {n}\n\n" + " ".join([SENTENCE] * 20) for n in range(1, CHAPTERS + 1)
        ),
        encoding="utf-8",
    )
    # 50 samples a character at 24 kHz: about 12 s of audio a chapter
    job = run_audio_job(
        source,
        JobSettings(output_folder=tmp_path / "out"),
        tmp_path / "work",
        voice=FakeVoice(samples_per_character=50).source(),
    )
    audio = read_readalong(job.written.readalong).duration
    times: list[float] = []

    def build() -> None:
        for old in (tmp_path / "out").glob(f"book.{kind.value}"):
            old.unlink()  # a build of a file still current reuses it
        start = time.perf_counter()
        built = build_book(tmp_path / "work", tmp_path / "out", kind)
        times.append(time.perf_counter() - start)
        assert not built.reused

    benchmark.pedantic(build, rounds=3, iterations=1)
    for seconds in times:
        speed = audio / seconds
        print(f"{kind.value}: {audio:.0f} s of audio built in {seconds:.2f} s ({speed:.0f}x)")
        # the encoding budget (docs/baseline.md): at least 50 times faster than real time;
        # 10 here, so a slow CI machine does not fail it
        assert speed > 10
