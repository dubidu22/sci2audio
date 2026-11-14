"""Voice audio as the WAV files the output stage reads (#69 contract, VA-05).

Every chunk file is a WAV with 16-bit PCM, one channel and the voice's sample rate (24 kHz
for Kokoro). Output reads the header with the stdlib `wave` module and times the audio
from its frame count, so the duration returned here is computed the same way.
"""

from __future__ import annotations

import os
import wave
from pathlib import Path

import numpy as np

from sci2audio.voices.engine import EngineSession
from sci2audio.voices.errors import InvalidInputError
from sci2audio.voices.types import (
    PCM_FLOAT32,
    ParameterValues,
    SynthesisRequest,
    VoiceSelection,
)

PREVIEW_TEXT = (
    "This is how this voice reads your text. "
    "The results in the second table were measured over three years."
)
# The preview sentence per language's primary subtag; English for any other language.
PREVIEW_TEXTS: dict[str, str] = {
    "en": PREVIEW_TEXT,
    "de": (
        "So liest diese Stimme Ihren Text vor. "
        "Die Ergebnisse der zweiten Tabelle wurden über drei Jahre gemessen."
    ),
}


def preview_text(language: str) -> str:
    """The preview sentence for a BCP 47 tag ("de-DE" → German), English by default."""
    return PREVIEW_TEXTS.get(language.split("-")[0].lower(), PREVIEW_TEXT)


def to_pcm16(samples: np.ndarray) -> bytes:
    """Float samples (nominally -1 to 1) as little-endian 16-bit PCM.

    Values outside the range are clipped; NaN becomes silence and infinities the extremes,
    so a glitch in the model never stops a job.
    """
    floats = np.nan_to_num(np.asarray(samples, dtype=np.float64).reshape(-1), nan=0.0)
    clipped = np.clip(floats, -1.0, 1.0)
    return np.round(clipped * 32767.0).astype("<i2").tobytes()


def write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> float:
    """Write mono 16-bit PCM WAV atomically (`<name>.part`, then rename); return seconds."""
    if sample_rate <= 0:
        raise InvalidInputError(f"sample rate must be positive, got {sample_rate}")
    pcm = to_pcm16(samples)
    frames = len(pcm) // 2
    part = path.with_name(path.name + ".part")
    try:
        with wave.open(str(part), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(sample_rate)
            out.writeframes(pcm)
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)
    return frames / sample_rate


def speak_to_wav(
    session: EngineSession,
    text: str,
    voice_id: str,
    path: Path,
    *,
    speed: float = 1.0,
    letter_speed: float = 1.0,
) -> float:
    """Speak `text` with one voice into a WAV file at `path`; return its length in seconds.

    The app turns the path and the length into an `AudioChunk` (it knows the span).
    `letter_speed` slows letters the voice spells out (#295); at 1.0 it is not sent, so the
    request is the one from before.
    """
    parameters: dict[str, float] = {"speed": speed}
    if letter_speed != 1.0:
        parameters["letter_speed"] = letter_speed
    result = session.synthesize(
        SynthesisRequest(
            text=text,
            voice=VoiceSelection(source="builtin", key=voice_id),
            parameters=ParameterValues(parameters),
            format=PCM_FLOAT32,
        )
    )
    samples = np.frombuffer(result.data, dtype="<f4")
    return write_wav(path, samples, result.sample_rate)


def preview(
    session: EngineSession,
    voice_id: str,
    path: Path,
    *,
    speed: float = 1.0,
    language: str = "en",
    letter_speed: float = 1.0,
) -> float:
    """Speak a short fixed sample with one voice and speed, for choosing a voice (VA-05);
    `language` is the voice's language, which picks the sample's language."""
    return speak_to_wav(
        session,
        preview_text(language),
        voice_id,
        path,
        speed=speed,
        letter_speed=letter_speed,
    )
