"""A long sentence cut for the voice sounds like one sentence, with the real voices (#480,
D-730). Nightly.

Needs the voice files and the whisper model fetched by `prepare_models.py`
(SCI2AUDIO_TEST_MODELS, SCI2AUDIO_TEST_WHISPER). Every audio job runs with the network
blocked. The sentences are our own, written for #480.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest
from test_voice_kokoro import edit_distance, models_dir
from test_voice_kokoro import words as english_words
from test_voice_kokoro_german import recogniser
from test_voice_kokoro_german import words as german_words

from sci2audio.app import JobSettings, kokoro_voice, run_audio_job
from sci2audio.output import OutputSettings, find_ffmpeg, read_readalong
from sci2audio.testing import no_network

RATE = 24_000
STEP = RATE // 100  # 10 ms
WER_LIMIT = 0.10
# What is heard at a cut: the clause pause, 30 ms of each piece's quiet, a 10 ms step each
SLACK = 0.1

SENTENCES = {
    "en": (
        "The results of the second survey, which was carried out two years after the first "
        "one in the same schools and with the same questionnaire, show that the share of "
        "teachers who use the new material in every lesson has almost doubled since the start "
        "of the programme."
    ),
    "de": (
        "Die Ergebnisse der zweiten Befragung, die zwei Jahre nach der ersten an den gleichen "
        "Schulen mit dem gleichen Fragebogen durchgeführt wurde, zeigen, dass sich der Anteil der "
        "Lehrkräfte, die das neue Material in jeder Stunde nutzen, fast verdoppelt hat."
    ),
}


def decoded(path: Path) -> np.ndarray:
    """The audio file as 16-bit mono samples at 24 kHz."""
    command = [str(find_ffmpeg()), "-v", "error", "-i", str(path)]
    command += ["-f", "s16le", "-ac", "1", "-ar", str(RATE), "-"]
    done = subprocess.run(command, capture_output=True, check=True)
    return np.frombuffer(done.stdout, dtype="<i2").astype(np.int32)


def quiet_run(samples: np.ndarray, at: int, peak: int) -> float:
    """Seconds of the quiet stretch around sample `at` (10 ms steps 45 dB under `peak`)."""
    level = peak * 10 ** (-45 / 20)

    def quiet(step: int) -> bool:
        piece = samples[step * STEP : (step + 1) * STEP]
        return len(piece) > 0 and int(np.abs(piece).max()) < level

    middle = at // STEP
    first = last = middle
    while first > 0 and quiet(first - 1):
        first -= 1
    while quiet(last + 1):
        last += 1
    return (last - first + 1) * STEP / RATE if quiet(middle) else 0.0


@pytest.mark.slow
@pytest.mark.parametrize("language", ["en", "de"])
def test_a_cut_sounds_like_a_comma_and_every_word_is_heard(language: str, tmp_path: Path) -> None:
    sentence = SENTENCES[language]
    source = tmp_path / "sentence.txt"
    source.write_text(sentence + "\n", encoding="utf-8")
    settings = JobSettings(language=language, output_folder=tmp_path / "out")
    with no_network():
        job = run_audio_job(
            source,
            settings,
            tmp_path / "work",
            voice=kokoro_voice(models_dir()),
            max_chars=len(sentence) // 2 + 20,
        )
    data = read_readalong(job.written.readalong)
    joins = [n for n, chunk in enumerate(data.chunks) if chunk.joins]
    assert joins, "the sentence was not cut"
    assert job.written.m4b is not None
    samples = decoded(job.written.m4b)
    first, last = data.chunks[joins[0] - 1], data.chunks[joins[-1]]
    stretch = samples[round(first.start * RATE) : round(last.end * RATE)]
    peak = int(np.abs(stretch).max())
    clause = OutputSettings().clause_pause
    for n in joins:
        before, after = data.chunks[n - 1], data.chunks[n]
        middle = round((before.end + after.start) / 2 * RATE)
        gap = quiet_run(samples, middle, peak)
        print(f"{language}: gap at cut {n}: {gap:.3f} s")
        assert clause <= gap + 0.02, gap  # the clause pause is there
        assert gap <= clause + SLACK, gap  # and not the voice's own silence on top

    # the joined stretch is heard as the whole sentence
    model = recogniser()
    at_16_khz = np.interp(
        np.arange(int(len(stretch) / RATE * 16000)) / 16000,
        np.arange(len(stretch)) / RATE,
        stretch.astype(np.float32) / 32768.0,
    ).astype(np.float32)
    segments, _ = model.transcribe(at_16_khz, language=language, beam_size=5)  # type: ignore[attr-defined]
    heard = " ".join(s.text for s in segments)
    words = english_words if language == "en" else german_words
    expected = words(sentence)
    wer = edit_distance(expected, words(heard)) / len(expected)
    assert wer < WER_LIMIT, f"WER {wer:.2f}: heard {heard!r}"
