"""Conformance suite for voice engines (#6, PE-07, D-52).

`check_voice_engine(make_engine)` runs every check against an engine factory; the
built-in Kokoro engine passes it in the nightly run, and a fake pipeline in every PR.
Network access is blocked while the factory runs and while every voice speaks (the same
`no_network` as the text-step suite), so an engine that goes online fails, even when it
catches the refusal itself (VA-04).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import numpy as np

from sci2audio.testing.text_steps import NetworkUsedError, no_network
from sci2audio.voices import (
    API_VERSION,
    PCM_FLOAT32,
    Engine,
    EngineError,
    EngineSession,
    InvalidInputError,
    ParameterValues,
    SynthesisRequest,
    SynthesizedAudio,
    VoiceInfo,
    VoiceSelection,
)

SAMPLE_TEXT = "The voice reads this sentence aloud."


def _fail(message: str) -> None:
    raise AssertionError(message)


@contextmanager
def _offline(what: str) -> Iterator[None]:
    """Run a block with the network blocked; any attempt fails the check."""
    with no_network() as attempts:
        try:
            yield
        except NetworkUsedError as error:
            raise AssertionError(f"network access attempted while {what}: {error}") from error
    if attempts:
        _fail(f"network access attempted while {what}: {', '.join(attempts)}")


def _request(text: str, voice: str, **parameters: Any) -> SynthesisRequest:
    return SynthesisRequest(
        text=text,
        voice=VoiceSelection(source="builtin", key=voice),
        parameters=ParameterValues(parameters),
        format=PCM_FLOAT32,
    )


def _expect_invalid(session: EngineSession, request: SynthesisRequest, what: str) -> None:
    try:
        session.synthesize(request)
    except InvalidInputError:
        return
    except EngineError as error:
        _fail(f"{what}: raised {type(error).__name__}, expected InvalidInputError")
    except Exception as error:
        _fail(f"{what}: raised {type(error).__name__}, which is not an EngineError")
    _fail(f"{what}: no error, expected InvalidInputError")


def _expect_engine_error(call: Callable[[], object], what: str) -> None:
    try:
        call()
    except EngineError:
        return
    except Exception as error:
        _fail(f"{what}: raised {type(error).__name__}, which is not an EngineError")
    _fail(f"{what}: no error, expected EngineError")


def check_audio(result: SynthesizedAudio, what: str) -> np.ndarray:
    """One result: raw float32 mono, positive rate, duration matching the samples."""
    if not isinstance(result, SynthesizedAudio):
        _fail(f"{what}: synthesize returned {type(result).__name__}, not SynthesizedAudio")
    if result.format != PCM_FLOAT32:
        _fail(f"{what}: format {result.format}, expected {PCM_FLOAT32}")
    if result.sample_rate <= 0:
        _fail(f"{what}: sample rate {result.sample_rate} is not positive")
    if len(result.data) % 4:
        _fail(f"{what}: {len(result.data)} bytes is not a whole number of float32 samples")
    samples = np.frombuffer(result.data, dtype="<f4")
    expected = len(samples) / result.sample_rate
    if not math.isclose(result.duration.seconds, expected, abs_tol=1e-6):
        _fail(f"{what}: duration {result.duration.seconds} s, but the samples last {expected} s")
    if not np.all(np.isfinite(samples)):
        _fail(f"{what}: audio contains NaN or infinite samples")
    return samples


def check_voice_engine(
    make_engine: Callable[[], Engine],
    *,
    voices: Callable[[tuple[VoiceInfo, ...]], tuple[VoiceInfo, ...]] | None = None,
) -> None:
    """Check an engine factory against the voice plugin contract.

    `voices` picks which of the listed voices speak the sample (default: all of them).
    """
    with _offline("creating the engine"):
        engine = make_engine()
    if getattr(engine, "api_version", None) != API_VERSION:
        _fail(
            f"engine api_version is {getattr(engine, 'api_version', None)!r}, "
            f"expected {API_VERSION!r}"
        )
    if not isinstance(engine, Engine):
        _fail("engine does not implement the Engine protocol")

    listed = engine.listVoices()
    if not listed or not all(isinstance(v, VoiceInfo) for v in listed):
        _fail("listVoices must return a non-empty tuple of VoiceInfo")
    ids = [v.id for v in listed]
    if len(set(ids)) != len(ids):
        _fail(f"voice ids are not unique: {ids}")
    for voice in listed:
        if not voice.id or not voice.name or not voice.language:
            _fail(f"voice {voice} lacks an id, a name or a language tag")

    session = engine.createSession()
    if not isinstance(session, EngineSession):
        _fail("createSession did not return an EngineSession")
    chosen = voices(listed) if voices else listed
    with _offline("speaking"):
        for voice in chosen:
            samples = check_audio(
                session.synthesize(_request(SAMPLE_TEXT, voice.id)), f"voice {voice.id}"
            )
            if samples.size == 0 or not np.any(samples):
                _fail(f"voice {voice.id} returned silence for {SAMPLE_TEXT!r}")

        first = chosen[0].id
        normal = check_audio(session.synthesize(_request(SAMPLE_TEXT, first)), "speed 1.0")
        fast = check_audio(session.synthesize(_request(SAMPLE_TEXT, first, speed=2.0)), "speed 2")
        if not fast.size < normal.size:
            _fail(f"speed 2.0 gave {fast.size} samples, not fewer than speed 1.0 ({normal.size})")

        _expect_invalid(session, _request("", first), "empty text")
        _expect_invalid(session, _request("   \n", first), "blank text")
        _expect_invalid(session, _request(SAMPLE_TEXT, "no-such-voice"), "unknown voice")
        for speed in (0.0, -1.0, 100.0, math.nan, math.inf, "fast"):
            _expect_invalid(session, _request(SAMPLE_TEXT, first, speed=speed), f"speed {speed!r}")

    session.dispose()
    session.dispose()
    _expect_engine_error(
        lambda: session.synthesize(_request(SAMPLE_TEXT, first)), "synthesize after dispose"
    )
    engine.dispose()
    engine.dispose()
    _expect_engine_error(engine.createSession, "createSession after dispose")
    _expect_engine_error(engine.listVoices, "listVoices after dispose")
