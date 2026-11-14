"""Spelled abbreviations at the listener's pace with the real voices (#295, D-554).
Nightly only; needs SCI2AUDIO_TEST_MODELS like the other voice tests.

Measured on 14 Nov 2026 (issue #295): at speed 1.0 the English voice spells 5.8 to 7.0
letters a second, at letter_speed 0.7 4.2 to 4.8 and at 0.5 2.9 to 3.5; German 4.3 to 5.1,
3.1 to 3.7 and 2.3 to 2.7. The bounds below leave room for other machines.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from test_voice_kokoro import at_16_khz, edit_distance

from sci2audio.testing import no_network
from sci2audio.voices import (
    PCM_FLOAT32,
    KokoroEngine,
    ParameterValues,
    SynthesisRequest,
    SynthesizedAudio,
    VoiceSelection,
    create_kokoro_engine,
    speak_to_wav,
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


# --- speech recognition at each pace (plan section 4) -------------------------------------

# Sentences dense with spelled abbreviations, about one in four words. Measured on 14 Nov
# 2026 with whisper small, two runs each (WER at normal, slower, slowest): English 0.04,
# 0.10, 0.12; German 0.00, 0.00, 0.04. Whisper's own slips decide most of it: "LSTM" heard
# as "LSDM" and "RMSE" as "RMSC" at every pace, "BERT" as "BART" at slower and slowest
# ("BERT" is a name to whisper), "use CNNs" as "you CNNs" at slowest. The limit is higher
# than the prose round trip's 0.10 because every abbreviation is a chance to slip; it fails
# when a pace makes the voice hard to follow, not on one misheard name.
ABBREVIATION_SENTENCES = {
    ("af_heart", "en"): (
        "We fine-tune BERT and an LSTM for NLP tasks on one GPU.",
        "The US and the UK use CNNs and GPUs.",
        "We report the AUC and the RMSE on the test set.",
        "The HTML page loads a PDF over HTTP.",
        "An SVM and an HMM were trained on the same data.",
    ),
    ("dm_thorsten", "de"): (
        "Wir nutzen NLP und ein LSTM auf der GPU.",
        "Das Projekt wurde von der DFG und dem BMBF gefördert.",
        "Die Seite lädt ein PDF über HTTP.",
        "Wir messen den pH-Wert mit einem EKG und einer MRT.",
        "Die Daten liegen im CSV-Format in der EU vor.",
    ),
}
LETTERS_WER_LIMIT = 0.20
PACES = {"normal": 1.0, "slower": 0.7, "slowest": 0.5}
# letters whisper writes with dots or dashes between them ("U.S.", "G-P-U's")
_SPELLED = re.compile(r"\b(?:[^\W\d_][.\-])+[^\W\d_]?\b\.?")


def heard_words(text: str) -> list[str]:
    """Words to compare, with spelled letters joined ("U.S." and "US" both "us") and a
    plural or possessive "'s" after letters the same as "s" ("GPU's" and "GPUs")."""
    text = text.replace("\u2019", "'")
    text = _SPELLED.sub(lambda found: re.sub(r"[.\-]", "", found.group()), text)
    text = re.sub(r"(?<=[^\W\d_])'s\b", "s", text)
    return re.findall(r"[^\W_]+(?:'[^\W\d_]+)?", text.lower())


def test_heard_words_join_spelled_letters() -> None:
    assert heard_words("The U.S. and the U.K. use G-P-U's.") == heard_words(
        "The US and the UK use GPUs."
    )
    assert heard_words("Wir messen den pH-Wert über HTTP.") == [
        "wir", "messen", "den", "ph", "wert", "über", "http",
    ]  # fmt: skip
    assert heard_words("It\u2019s fine-tuned.") == ["its", "fine", "tuned"]  # both sides alike


@pytest.mark.slow
@pytest.mark.parametrize(("voice", "language"), list(ABBREVIATION_SENTENCES))
def test_speech_recognition_round_trip_at_each_pace(
    engine: KokoroEngine,
    tmp_path: Path,
    record_property: pytest.RecordProperty,
    voice: str,
    language: str,
) -> None:
    whisper_dir = os.environ.get("SCI2AUDIO_TEST_WHISPER")
    if not whisper_dir:
        pytest.skip("SCI2AUDIO_TEST_WHISPER is not set (run tests/integration/prepare_models.py)")
    from faster_whisper import WhisperModel

    sentences = ABBREVIATION_SENTENCES[(voice, language)]
    session = engine.createSession()
    report = []
    rates = {}
    with no_network():
        recogniser = WhisperModel(whisper_dir, device="cpu", compute_type="int8")
        for pace, letters in PACES.items():
            errors = total = 0
            for n, sentence in enumerate(sentences):
                path = tmp_path / f"{pace}-{n}.wav"
                speak_to_wav(session, sentence, voice, path, letter_speed=letters)
                segments, _ = recogniser.transcribe(at_16_khz(path), language=language, beam_size=5)
                heard = " ".join(s.text for s in segments).strip()
                expected = heard_words(sentence)
                wrong = edit_distance(expected, heard_words(heard))
                errors += wrong
                total += len(expected)
                if wrong:
                    report.append(f"  {pace}: said {sentence!r}, heard {heard!r}")
            rates[pace] = errors / total
            record_property(f"wer_{pace}", round(rates[pace], 4))
    summary = ", ".join(f"{pace} {wer:.3f}" for pace, wer in rates.items())
    print(f"WER {summary}\n" + "\n".join(report))
    assert max(rates.values()) < LETTERS_WER_LIMIT, f"WER {summary}\n" + "\n".join(report)
