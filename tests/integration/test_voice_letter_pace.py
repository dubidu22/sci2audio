"""Spelled abbreviations at the listener's pace with the real voices (#295, D-554).
Nightly only; needs SCI2AUDIO_TEST_MODELS like the other voice tests.

Measured on 14 Nov 2026 (issue #295): at speed 1.0 the English voice spells 5.8 to 7.0
letters a second, at letter_speed 0.7 4.2 to 4.8 and at 0.5 2.9 to 3.5; German 4.3 to 5.1,
3.1 to 3.7 and 2.3 to 2.7. The bounds below leave room for other machines.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from sci2audio.testing import no_network
from sci2audio.voices import (
    PCM_FLOAT32,
    KokoroEngine,
    ParameterValues,
    SynthesisRequest,
    SynthesizedAudio,
    VoiceSelection,
    create_kokoro_engine,
)

CARRIERS = {
    "af_heart": ("We use {} here.", ["NLP", "LSTM", "FKZ"]),
    "dm_thorsten": ("Wir nutzen {} hier.", ["NLP", "LSTM", "FKZ"]),
}


def models_dir() -> Path:
    folder = os.environ.get("SCI2AUDIO_TEST_MODELS")
    if not folder:
        pytest.skip("SCI2AUDIO_TEST_MODELS is not set (run tests/integration/prepare_models.py)")
    return Path(folder)


@pytest.fixture(scope="module")
def engine() -> Iterator[KokoroEngine]:
    with no_network():
        made = create_kokoro_engine(models_dir())
    yield made
    made.dispose()


def say(engine: KokoroEngine, text: str, voice: str, letters: float) -> SynthesizedAudio:
    with no_network():
        return engine.createSession().synthesize(
            SynthesisRequest(
                text=text,
                voice=VoiceSelection("builtin", voice),
                parameters=ParameterValues({"speed": 1.0, "letter_speed": letters}),
                format=PCM_FLOAT32,
            )
        )


def spoken_seconds(result: SynthesizedAudio) -> float:
    """From the first to the last sample above a quiet level: the leading and trailing
    silence does not count."""
    samples = np.frombuffer(result.data, dtype="<f4")
    loud = np.flatnonzero(np.abs(samples) > 0.01)
    return float(loud[-1] - loud[0]) / result.sample_rate


@pytest.mark.slow
@pytest.mark.parametrize("voice", list(CARRIERS))
def test_spelled_letters_slow_down_at_each_pace(engine: KokoroEngine, voice: str) -> None:
    carrier, words = CARRIERS[voice]
    empty = carrier.replace(" {}", "")
    for word in words:
        rates = []
        for letters in (1.0, 0.7, 0.5):
            extra = spoken_seconds(say(engine, carrier.format(word), voice, letters)) - (
                spoken_seconds(say(engine, empty, voice, letters))
            )
            rates.append(len(word) / extra)
        normal, slower, slowest = rates
        assert slower < 0.9 * normal, (word, rates)
        assert slowest < 0.85 * slower, (word, rates)
        assert slowest < 4.0, (word, rates)  # letters a second


@pytest.mark.slow
@pytest.mark.parametrize(
    ("voice", "text"),
    [
        ("af_heart", "We read the data of the space agency NASA."),
        ("dm_thorsten", "Wir lesen die Daten von BERT."),  # BERT is said as the word "Bert"
    ],
)
def test_a_sentence_without_spelled_letters_keeps_its_length(
    engine: KokoroEngine, voice: str, text: str
) -> None:
    lengths = {len(say(engine, text, voice, letters).data) for letters in (1.0, 0.7, 0.5)}
    assert len(lengths) == 1


@pytest.mark.slow
def test_english_word_timings_follow_the_slower_letters(engine: KokoroEngine) -> None:
    def lstm(letters: float) -> float:
        result = say(engine, "We train an LSTM on the data.", "af_heart", letters)
        token = next(t for s in result.segments for t in s.tokens if t.text == "LSTM")
        return token.end - token.start

    assert lstm(0.5) > 1.5 * lstm(1.0)
