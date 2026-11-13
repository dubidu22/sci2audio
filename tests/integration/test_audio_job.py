"""The audio job end to end with the real Kokoro voice, offline (#71, VA-04, WI-02). Nightly.

Needs the voice files fetched by `prepare_models.py` (SCI2AUDIO_TEST_MODELS). Every test
runs with the network blocked: after the voice setup, nothing goes online.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pytest

from sci2audio.app import JobSettings, kokoro_voice, run_audio_job
from sci2audio.app import voice as voice_module
from sci2audio.output import find_ffmpeg, read_readalong
from sci2audio.testing import no_network

CORPUS = Path(__file__).parents[1] / "corpus"
PYMEDPHYS = CORPUS / "papers" / "joss2022-biggs-pymedphys.pdf"


def models_dir() -> Path:
    folder = os.environ.get("SCI2AUDIO_TEST_MODELS")
    if not folder:
        pytest.skip("SCI2AUDIO_TEST_MODELS is not set (run tests/integration/prepare_models.py)")
    return Path(folder)


def chapter_marks(m4b: Path) -> list[str]:
    """The chapter titles ffmpeg reads back from the M4B."""
    import subprocess

    done = subprocess.run(  # noqa: S603 (our own argument list)
        [str(find_ffmpeg()), "-hide_banner", "-i", str(m4b), "-f", "ffmetadata", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    lines = done.stdout.splitlines()
    return [
        line.removeprefix("title=")
        for i, line in enumerate(lines)
        if line.startswith("title=") and any(x == "[CHAPTER]" for x in lines[max(0, i - 4) : i])
    ]


@pytest.mark.slow
def test_a_paper_becomes_an_audiobook_with_the_real_voice_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    voice = kokoro_voice(models_dir())
    settings = JobSettings(output_folder=tmp_path / "out")
    with no_network():
        job = run_audio_job(PYMEDPHYS, settings, tmp_path / "work", voice=voice)
    assert job.skipped == ()
    assert job.written.m4b is not None
    assert len(job.written.mp3s) == 4
    chosen = [c.chapter.title for c in job.result.chapters if c.selected]
    readalong = read_readalong(job.written.readalong)
    assert [c.title for c in readalong.chapters] == chosen
    marks = chapter_marks(job.written.m4b)
    assert [re.sub(r"\\(.)", r"\1", mark) for mark in marks] == [" ".join(t.split()) for t in chosen]
    # about 13 characters per second of speech at speed 1: a sanity range, not a measure
    characters = sum(len(u.text) for u in job.result.utterances if not u.pause)
    assert characters / 30 < readalong.duration < characters / 5
    record = json.loads(job.record.read_text(encoding="utf-8"))
    assert record["engine_version"].startswith("kokoro-82m@")
    assert record["chunks"]["spoken"] + record["chunks"]["reused"] == record["chunks"]["total"]

    # resume: a rerun takes every chunk from the cache and never loads the model
    made: list[int] = []
    real = voice_module.create_kokoro_engine

    def counting(models: Path):  # type: ignore[no-untyped-def]
        made.append(1)
        return real(models)

    monkeypatch.setattr(voice_module, "create_kokoro_engine", counting)
    with no_network():
        again = run_audio_job(
            PYMEDPHYS, settings, tmp_path / "work", voice=kokoro_voice(models_dir()), overwrite=True
        )
    assert (again.spoken, made) == (0, [])
    assert again.written.readalong.read_text() == job.written.readalong.read_text()


@pytest.mark.benchmark
def test_benchmark_the_audio_job_on_a_short_paper(tmp_path: Path, benchmark: object) -> None:
    """Characters per second of the whole job with the real voice, and the job's own
    overhead (everything but speaking: reading, steps, planning, encoding), measured as a
    rerun from the cache."""
    voice = kokoro_voice(models_dir())
    settings = JobSettings(output_folder=tmp_path / "out")
    started = time.perf_counter()
    with no_network():
        job = run_audio_job(PYMEDPHYS, settings, tmp_path / "work", voice=voice)
    whole = time.perf_counter() - started

    def rerun() -> float:
        with no_network():
            return run_audio_job(
                PYMEDPHYS, settings, tmp_path / "work", voice=voice, overwrite=True
            ).duration

    benchmark.pedantic(rerun, rounds=3, warmup_rounds=0)  # type: ignore[attr-defined]
    characters = sum(len(u.text) for u in job.result.utterances if not u.pause)
    info = benchmark.extra_info  # type: ignore[attr-defined]
    info["characters"] = characters
    info["whole_job_seconds"] = round(whole, 1)
    info["characters_per_second_whole_job"] = round(characters / whole, 1)
    info["characters_per_second_speech"] = job.characters_per_second
    info["audio_seconds"] = job.duration
