"""A fake voice for the audio job tests: the voice contract without torch or a model.

It speaks 10 samples of a quiet tone per character at 24 kHz, so a page is a second of
audio and ffmpeg encodes a whole test book in well under a second. It counts what it
speaks and can be told to fail on some texts, to stop for ever on a text (for the kill
test) or to fail when it is made.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import numpy as np

from sci2audio.app import JobSettings, VoiceSource, plan_audio, prepare_script
from sci2audio.app.job import read_document
from sci2audio.voices import (
    PCM_FLOAT32,
    Duration,
    EngineError,
    InvalidInputError,
    SynthesisRequest,
    SynthesizedAudio,
    VoiceInfo,
)

RATE = 24000
SAMPLES_PER_CHARACTER = 10
VOICES = (
    VoiceInfo(id="af_heart", name="Heart", language="en-US", gender="female"),
    VoiceInfo(id="bm_george", name="George", language="en-GB", gender="male"),
)


@dataclass
class FakeVoice:
    """Makes fake engines and records what they did."""

    fail_on: Callable[[str], bool] = lambda text: False
    hang_on: Callable[[str], bool] = lambda text: False  # stop for ever (kill test)
    marker: Path | None = None  # written just before hanging
    fail_to_make: EngineError | None = None
    version: str = "fake-1"
    samples_per_character: int = SAMPLES_PER_CHARACTER  # more: longer speech (player tests)
    on_speak: Callable[[str], None] = lambda text: None  # e.g. moves a fake clock on
    spoken: list[tuple[str, str, float]] = field(default_factory=list)  # text, voice, speed
    made: int = 0
    released: int = 0
    sessions_disposed: int = 0

    def source(self) -> VoiceSource:
        return VoiceSource(
            engine="fake",
            version=self.version,
            make=self.make,
            voices=tuple(v.id for v in VOICES),
            default_voice="af_heart",
            release=self.release,
        )

    def make(self) -> FakeEngine:
        if self.fail_to_make is not None:
            raise self.fail_to_make
        self.made += 1
        return FakeEngine(self)

    def release(self, engine: object) -> None:
        self.released += 1
        assert isinstance(engine, FakeEngine)
        engine.dispose()

    @property
    def texts(self) -> list[str]:
        return [text for text, _, _ in self.spoken]


class FakeSession:
    def __init__(self, voice: FakeVoice) -> None:
        self.voice = voice
        self.disposed = False

    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        if self.disposed:
            raise EngineError("Session disposed")
        text = request.text
        if not text.strip():
            raise InvalidInputError("nothing to say")
        if self.voice.hang_on(text):
            if self.voice.marker is not None:
                self.voice.marker.write_text(str(len(self.voice.spoken)))
            time.sleep(600)
        if self.voice.fail_on(text):
            raise InvalidInputError(f"cannot say {text[:20]!r}")
        speed = float(request.parameters.values.get("speed", 1.0))
        self.voice.on_speak(text)
        self.voice.spoken.append((text, request.voice.key, speed))
        n = int(len(text) * self.voice.samples_per_character / speed)
        samples = (0.3 * np.sin(np.arange(n, dtype=np.float32) / 5.0)).astype("<f4")
        return SynthesizedAudio(
            data=samples.tobytes(),
            format=PCM_FLOAT32,
            duration=Duration(seconds=n / RATE),
            sample_rate=RATE,
        )

    def dispose(self) -> None:
        if not self.disposed:
            self.voice.sessions_disposed += 1
        self.disposed = True


class FakeEngine:
    api_version = "1.0"

    def __init__(self, voice: FakeVoice) -> None:
        self.voice = voice
        self.disposed = False

    def createSession(self) -> FakeSession:
        if self.disposed:
            raise EngineError("Engine disposed")
        return FakeSession(self.voice)

    def listVoices(self) -> tuple[VoiceInfo, ...]:
        return VOICES

    def dispose(self) -> None:
        self.disposed = True


@cache
def chunk_count(source: Path) -> int:
    """How many different chunks a job with the default settings speaks for `source`.

    It follows from the text steps, so tests that count chunks do not change when a step
    reads a paper differently.
    """
    settings = JobSettings(output_folder=source.parent)
    result = prepare_script(read_document(source, settings, lambda phase: None), settings)
    plan = plan_audio(result, engine="fake", engine_version="1", voice="v", speed=1.0)
    return len({chunk.key for chunk in plan.chunks})
