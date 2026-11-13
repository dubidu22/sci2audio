"""The voice conformance suite catches engines that break the contract (#6, PE-07)."""

from __future__ import annotations

import contextlib
import math
import socket
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sci2audio.testing import NetworkUsedError, check_voice_engine, no_network
from sci2audio.voices import (
    API_VERSION,
    PCM_FLOAT32,
    Duration,
    EngineError,
    InvalidInputError,
    SynthesisRequest,
    SynthesizedAudio,
    VoiceInfo,
)

VOICES = (VoiceInfo("v1", "One", "en-US", "female"), VoiceInfo("v2", "Two", "en-GB", "male"))


class Session:
    """A correct toy session; subclasses break one rule each."""

    rate = 8000

    def __init__(self) -> None:
        self.disposed = False

    def samples(self, request: SynthesisRequest) -> np.ndarray:
        speed = request.parameters.values.get("speed", 1.0)
        if not isinstance(speed, int | float) or not math.isfinite(speed) or not 0.5 <= speed <= 2:
            raise InvalidInputError("bad speed")
        return np.full(int(len(request.text) * 10 / speed), 0.25, dtype="<f4")

    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        if self.disposed:
            raise EngineError("disposed")
        if not request.text.strip():
            raise InvalidInputError("empty")
        if request.voice.key not in {v.id for v in VOICES}:
            raise InvalidInputError("voice")
        samples = self.samples(request)
        return SynthesizedAudio(
            samples.tobytes(), PCM_FLOAT32, Duration(len(samples) / self.rate), self.rate
        )

    def dispose(self) -> None:
        self.disposed = True


class Engine:
    api_version = API_VERSION
    session_class: type[Session] = Session

    def __init__(self) -> None:
        self.disposed = False

    def createSession(self) -> Session:
        if self.disposed:
            raise EngineError("disposed")
        return self.session_class()

    def listVoices(self) -> tuple[VoiceInfo, ...]:
        if self.disposed:
            raise EngineError("disposed")
        return VOICES

    def dispose(self) -> None:
        self.disposed = True


def engine_with(session_class: type[Session], **attributes: Any) -> type[Engine]:
    return type("Broken", (Engine,), {"session_class": session_class, **attributes})


class NaNSession(Session):
    def samples(self, request: SynthesisRequest) -> np.ndarray:
        out = super().samples(request)
        out[0] = np.nan
        return out


class SpeedIgnored(Session):
    def samples(self, request: SynthesisRequest) -> np.ndarray:
        return np.full(len(request.text) * 10, 0.25, dtype="<f4")


class RawErrors(Session):
    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        if not request.text:
            raise ValueError("empty")
        return super().synthesize(request)


class Silent(Session):
    def samples(self, request: SynthesisRequest) -> np.ndarray:
        return np.zeros_like(super().samples(request))


class WrongDuration(Session):
    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        result = super().synthesize(request)
        return SynthesizedAudio(result.data, result.format, Duration(99.0), result.sample_rate)


class Online(Session):
    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        socket.create_connection(("example.org", 443))
        return super().synthesize(request)


class UsableAfterDispose(Session):
    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        self.disposed = False
        return super().synthesize(request)


def test_a_correct_engine_passes() -> None:
    check_voice_engine(Engine)


@pytest.mark.parametrize(
    ("engine", "message"),
    [
        (engine_with(Session, api_version="0.1"), "api_version"),
        (engine_with(NaNSession), "NaN"),
        (engine_with(SpeedIgnored), "speed 2.0"),
        (engine_with(RawErrors), "not an EngineError"),
        (engine_with(Silent), "silence"),
        (engine_with(WrongDuration), "duration"),
        (engine_with(Online), "network access attempted"),
        (engine_with(UsableAfterDispose), "after dispose"),
        (engine_with(Session, listVoices=lambda self: ()), "non-empty"),
        (engine_with(Session, listVoices=lambda self: (VOICES[0], VOICES[0])), "unique"),
    ],
)
def test_a_broken_engine_fails_with_a_clear_message(engine: type[Engine], message: str) -> None:
    with pytest.raises(AssertionError, match=message):
        check_voice_engine(engine)


def test_an_engine_that_goes_online_while_loading_fails() -> None:
    def make() -> Engine:
        socket.getaddrinfo("huggingface.co", 443)
        return Engine()

    with pytest.raises(AssertionError, match="network access attempted while creating the engine"):
        check_voice_engine(make)


class QuietlyOnline(Session):
    """Tries the network, swallows the refusal, and answers anyway."""

    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        with contextlib.suppress(Exception):
            socket.create_connection(("example.org", 443))
        return super().synthesize(request)


def test_an_engine_that_hides_its_network_attempt_still_fails() -> None:
    with pytest.raises(AssertionError, match="network access attempted while speaking"):
        check_voice_engine(engine_with(QuietlyOnline))


def test_no_network_restores_the_socket_module() -> None:
    before = (socket.socket.connect, socket.create_connection, socket.getaddrinfo)
    with pytest.raises(NetworkUsedError), no_network():
        socket.socket().connect(("127.0.0.1", 9))
    assert (socket.socket.connect, socket.create_connection, socket.getaddrinfo) == before


def test_suite_needs_no_pytest(tmp_path: Path) -> None:
    import subprocess
    import sys

    code = "import sys, sci2audio.testing.voices; print('pytest' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
