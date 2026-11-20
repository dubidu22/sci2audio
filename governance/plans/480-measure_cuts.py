"""Measure, with the real voices, what a cut inside a sentence sounds like (#480 plan).

For each long sentence: speak it whole and cut at its comma (as textprep cuts), then
report the voice's own edge silences per piece, the silence Kokoro itself leaves at the
comma when it speaks the sentence whole, and the phoneme tokens per character.
"""

import sys
from pathlib import Path

import numpy as np

from sci2audio.voices.kokoro_engine import create_kokoro_engine
from sci2audio.voices.types import EngineConfig

RATE = 24_000
models = Path(sys.argv[1])

SENTENCES = {
    "en": [
        (
            "The results of the second survey, which was carried out two years after the first "
            "one in the same schools and with the same questionnaire,",
            "show that the share of teachers who use the new material in every lesson has "
            "almost doubled since the start of the programme.",
        ),
        (
            "Although the model explains most of the variance in the training data,",
            "it fails on the held-out sample in a way that suggests the features we chose "
            "capture the period rather than the effect we set out to measure.",
        ),
    ],
    "de": [
        (
            "BNE ist zugleich Objekt der Kritik in dem Sinne,",
            "dass der pädagogische Umgang mit gesellschaftlichen Herausforderungen diese zu "
            "individualisieren droht und politische Fragen in Lernaufgaben übersetzt.",
        ),
        (
            "Die Ergebnisse der zweiten Befragung, die zwei Jahre nach der ersten an denselben "
            "Schulen durchgeführt wurde,",
            "zeigen, dass sich der Anteil der Lehrkräfte, die das neue Material in jeder Stunde "
            "nutzen, seit Beginn des Programms fast verdoppelt hat.",
        ),
    ],
}
VOICE = {"en": ("a", "af_heart"), "de": ("d", "dm_thorsten")}


def edges(audio: np.ndarray, db: float = -45.0) -> tuple[float, float]:
    """Seconds of near-silence at the start and at the end (20 ms frames, peak below db)."""
    frame = RATE // 50
    limit = 10 ** (db / 20) * float(np.max(np.abs(audio)) or 1.0)
    loud = [
        float(np.max(np.abs(audio[i : i + frame]))) > limit for i in range(0, len(audio), frame)
    ]
    first = loud.index(True) if True in loud else len(loud)
    last = loud[::-1].index(True) if True in loud else len(loud)
    return first / 50, last / 50


def gaps(audio: np.ndarray, db: float = -45.0, least: float = 0.08) -> list[tuple[float, float]]:
    """(time, length) of every inner silence of at least `least` seconds."""
    frame = RATE // 100
    limit = 10 ** (db / 20) * float(np.max(np.abs(audio)))
    quiet = [
        float(np.max(np.abs(audio[i : i + frame]))) <= limit for i in range(0, len(audio), frame)
    ]
    found, start = [], None
    for n, q in enumerate(quiet):
        if q and start is None:
            start = n
        elif not q and start is not None:
            if start > 0 and (n - start) / 100 >= least:
                found.append((start / 100, (n - start) / 100))
            start = None
    return found


def speak(pipeline, voice: str, text: str) -> tuple[np.ndarray, int]:
    parts, tokens = [], 0
    for result in pipeline(text, voice=voice, speed=1.0, split_pattern=None):
        if result.audio is None:
            continue
        audio = result.audio.numpy() if hasattr(result.audio, "numpy") else result.audio
        parts.append(np.asarray(audio, dtype="float32").reshape(-1))
        tokens += len(result.phonemes or "")
    return np.concatenate(parts), tokens


engine = create_kokoro_engine(models, EngineConfig())
for language, pairs in SENTENCES.items():
    code, voice_id = VOICE[language]
    pipeline = engine.pipeline_for(code)
    voice = str(engine.voice_file(voice_id))
    print(f"== {language} ({voice_id})")
    for first, second in pairs:
        whole_text = f"{first} {second}"
        whole, tokens = speak(pipeline, voice, whole_text)
        a, _ = speak(pipeline, voice, first)
        b, _ = speak(pipeline, voice, second)
        cut_at = len(a) / RATE - edges(a)[1]
        print(f"  {len(whole_text)} chars, {tokens} phoneme chars ({tokens / len(whole_text):.2f}/char)")
        print(f"  whole: {len(whole) / RATE:.2f} s, edges {edges(whole)}, inner gaps {gaps(whole)}")
        print(f"  piece 1: {len(a) / RATE:.2f} s, edges {edges(a)} (speech ends at {cut_at:.2f} s)")
        print(f"  piece 2: {len(b) / RATE:.2f} s, edges {edges(b)}")
        print(f"  joined today (Pause.NONE): silence at the cut = {edges(a)[1] + edges(b)[0]:.2f} s")
