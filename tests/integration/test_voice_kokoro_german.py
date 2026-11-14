"""Kokoro German (Thorsten-Voice) with the real model, offline (#211, D-467). Nightly only.

Needs the voice files fetched by `prepare_models.py` (the German pack is part of the
download); SCI2AUDIO_TEST_MODELS and SCI2AUDIO_TEST_WHISPER as for the English voice.
Every test runs with the network blocked. The sentences are our own, written for #211,
in the spoken form the German text rules hand over (numbers as words).
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from test_voice_kokoro import at_16_khz, edit_distance, models_dir, wav_params

from sci2audio.testing import check_voice_engine, no_network
from sci2audio.voices import (
    GERMAN_DEFAULT_VOICE,
    GERMAN_VOICES,
    EngineConfig,
    KokoroEngine,
    create_kokoro_engine,
    speak_to_wav,
)

WER_LIMIT = 0.10
SENTENCES = (
    "In dieser Arbeit untersuchen wir, wie sich die Wärmeleitfähigkeit dünner Schichten "
    "mit der Temperatur ändert.",
    "Die Messungen wurden an zweiundvierzig Proben durchgeführt, die zwischen "
    "neunzehnhundertachtundneunzig und zweitausendzwanzig hergestellt wurden.",
    "Überraschenderweise zeigt sich ein deutlicher Rückgang der Leitfähigkeit oberhalb von "
    "dreihundert Kelvin.",
    "Wir führen diesen Effekt auf die Streuung von Phononen an Korngrenzen zurück, wie "
    "bereits frühere Studien vermutet haben.",
    "Für die Auswertung verwenden wir ein neuronales Netz, das mit Methoden des maschinellen "
    "Lernens trainiert wurde.",
    "Die Software ist frei verfügbar, und alle Daten werden nach Abschluss des "
    "Begutachtungsverfahrens veröffentlicht.",
    "Abbildung drei zeigt die Abhängigkeit des Wirkungsgrades von der Schichtdicke für beide "
    "Materialsysteme.",
    "Bemerkenswert ist, dass die Brückenstruktur auch bei hoher Luftfeuchtigkeit mechanisch "
    "stabil bleibt.",
    "Im Gegensatz zu herkömmlichen Verfahren benötigt unser Ansatz weder Vakuum noch eine "
    "aufwendige Nachbehandlung.",
    "Zusammenfassend lässt sich sagen, dass die Ergebnisse die ursprüngliche Hypothese nur "
    "teilweise bestätigen.",
    "Weitere Untersuchungen sollten klären, ob sich das Verhalten auf andere Halbleiter "
    "übertragen lässt.",
    "Wir danken der Deutschen Forschungsgemeinschaft für die großzügige Förderung dieses Projekts.",
)
# whisper writes some spoken numbers back as digits
HEARD_AS_DIGITS = {
    "42": "zweiundvierzig",
    "1998": "neunzehnhundertachtundneunzig",
    "2020": "zweitausendzwanzig",
    "300": "dreihundert",
    "3": "drei",
}


@pytest.fixture(scope="module")
def engine() -> Iterator[KokoroEngine]:
    with no_network():
        made = create_kokoro_engine(models_dir(), EngineConfig(language="de-DE"))
    yield made
    made.dispose()


def words(text: str) -> list[str]:
    found = re.findall(r"[a-zäöüß0-9]+", text.lower())
    return [HEARD_AS_DIGITS.get(w, w) for w in found]


def test_german_words_and_whisper_digits() -> None:
    assert words("Die 42 Proben, Größe: 3.") == ["die", "zweiundvierzig", "proben", "größe", "drei"]


@pytest.mark.slow
def test_thorsten_speaks_a_sentence_into_a_wav_file(engine: KokoroEngine, tmp_path: Path) -> None:
    path = tmp_path / "thorsten.wav"
    with no_network():
        seconds = speak_to_wav(engine.createSession(), SENTENCES[0], GERMAN_DEFAULT_VOICE, path)
    params, pcm = wav_params(path)
    assert (params.nchannels, params.sampwidth, params.framerate) == (1, 2, 24000)
    assert 3.0 < seconds < 15.0
    assert np.abs(pcm).max() > 1000  # not silence


@pytest.mark.slow
def test_german_kokoro_passes_the_conformance_suite() -> None:
    check_voice_engine(
        lambda: create_kokoro_engine(models_dir(), EngineConfig(language="de-DE")),
        voices=lambda listed: tuple(v for v in listed if v in GERMAN_VOICES),
    )


def recogniser() -> object:
    whisper_dir = os.environ.get("SCI2AUDIO_TEST_WHISPER")
    if not whisper_dir:
        pytest.skip("SCI2AUDIO_TEST_WHISPER is not set (run tests/integration/prepare_models.py)")
    from faster_whisper import WhisperModel

    return WhisperModel(whisper_dir, device="cpu", compute_type="int8")


def heard(model: object, path: Path) -> str:
    segments, _ = model.transcribe(at_16_khz(path), language="de", beam_size=5)  # type: ignore[attr-defined]
    return " ".join(s.text for s in segments)


@pytest.mark.slow
def test_speech_recognition_round_trip(
    engine: KokoroEngine, tmp_path: Path, record_property: pytest.RecordProperty
) -> None:
    """The check that caught the silent weight skip: noise is heard as nothing or as
    whisper's stock phrases, never as these sentences."""
    model = recogniser()
    session = engine.createSession()
    errors = total = 0
    worst: list[tuple[float, str, str]] = []
    with no_network():
        for n, sentence in enumerate(SENTENCES):
            path = tmp_path / f"{n:02d}.wav"
            speak_to_wav(session, sentence, GERMAN_DEFAULT_VOICE, path)
            got = heard(model, path)
            expected = words(sentence)
            wrong = edit_distance(expected, words(got))
            errors += wrong
            total += len(expected)
            worst.append((wrong / len(expected), sentence, got))
    wer = errors / total
    report = [f"WER {wer:.3f} over {total} words"] + [
        f"  {w:.2f}  said: {s!r}\n        heard: {h!r}" for w, s, h in sorted(worst)[-3:]
    ]
    print("\n".join(report))
    record_property("wer", round(wer, 4))
    assert wer < WER_LIMIT, "\n".join(report)


@pytest.mark.slow
def test_a_text_longer_than_one_model_call_is_spoken_whole(
    engine: KokoroEngine, tmp_path: Path
) -> None:
    """Over 510 phonemes the German pipeline cuts at sentence ends; nothing is lost."""
    text = " ".join(SENTENCES[:6])
    assert len(text) > 600
    path = tmp_path / "long.wav"
    model = recogniser()
    with no_network():
        speak_to_wav(engine.createSession(), text, GERMAN_DEFAULT_VOICE, path)
        got = heard(model, path)
    expected = words(text)
    wer = edit_distance(expected, words(got)) / len(expected)
    assert wer < WER_LIMIT, f"WER {wer:.2f}: heard {got!r}"


BENCHMARK_TEXT = SENTENCES[0] + " " + SENTENCES[9]


@pytest.mark.benchmark
def test_german_kokoro_speed_on_cpu(
    engine: KokoroEngine, tmp_path: Path, benchmark: object
) -> None:
    session = engine.createSession()
    path = tmp_path / "bench.wav"

    def speak() -> float:
        with no_network():
            return speak_to_wav(session, BENCHMARK_TEXT, GERMAN_DEFAULT_VOICE, path)

    started = time.perf_counter()
    seconds = benchmark.pedantic(speak, rounds=3, warmup_rounds=1)  # type: ignore[attr-defined]
    elapsed = (time.perf_counter() - started) / 4
    benchmark.extra_info["characters_per_second"] = round(len(BENCHMARK_TEXT) / elapsed, 1)  # type: ignore[attr-defined]
    benchmark.extra_info["realtime_factor"] = round(seconds / elapsed, 2)  # type: ignore[attr-defined]
    assert seconds > 5
