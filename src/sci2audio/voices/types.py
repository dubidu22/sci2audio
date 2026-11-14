# Copied from Abogen (https://github.com/denizsafak/abogen), file abogen/tts_plugin/types.py,
# revision 1807822f5871d1c92740cb470c5c6e8328b8f851, under the MIT licence below (D-52).
# Changes for sci2audio: Abogen's `Language` enum is a BCP 47 tag string; `SynthesizedAudio`
# carries its sample rate; `PCM_FLOAT32` names the one format voices return; `VoiceInfo`
# replaces Abogen's `VoiceManifest` (its manifest module is not copied).
#
# MIT License
#
# Copyright (c) 2025 Deniz Şafak
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
"""Value objects of the voice plugin contract (D-46, D-52).

Immutable and free of engine code, so callers and engines share them without importing
torch or a model.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AudioFormat:
    """Immutable value object representing an audio format.

    Attributes:
        mime: MIME type of the audio (e.g., "audio/wav", "audio/mpeg").
        extension: File extension (e.g., "wav", "mp3").
    """

    mime: str
    extension: str


# Raw little-endian float32 mono samples: what every voice returns from `synthesize`.
# `sci2audio.voices.wav` turns them into the 16-bit WAV files the output stage reads.
PCM_FLOAT32 = AudioFormat(mime="audio/x-raw-float32", extension="f32")


@dataclass(frozen=True)
class Duration:
    """Immutable value object representing a time duration.

    Attributes:
        seconds: Duration in seconds.
    """

    seconds: float


@dataclass(frozen=True)
class VoiceSelection:
    """Immutable value object for voice selection. Opaque to engine.

    Attributes:
        source: Voice source identifier (e.g., "builtin", "clone").
        key: Voice key within the source.
        payload: Optional payload for clone/blend sources.
    """

    source: str
    key: str
    payload: Any = None


@dataclass(frozen=True)
class ParameterValues:
    """Immutable value object for synthesis parameters. Behaves like Mapping[str, Any].

    Attributes:
        values: Mapping of parameter names to their values.

    Parameters every engine takes (all optional):
        speed: the pace, 1.0 = the voice's own; an engine refuses values it cannot speak.
        letter_speed: the pace of letters the voice spells out ("NLP", "LSTM") as a factor
            of `speed`, from LETTER_SPEED_MIN (0.25) to 1.0 (default: as the voice says
            them). An engine that cannot slow letters ignores it, but still refuses values
            outside that range (#295, D-554).
    """

    values: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SynthesisRequest:
    """Immutable value object for a synthesis request.

    Attributes:
        text: Text to synthesize.
        voice: Voice selection.
        parameters: Synthesis parameters.
        format: Desired audio output format.
    """

    text: str
    voice: VoiceSelection
    parameters: ParameterValues
    format: AudioFormat


@dataclass(frozen=True)
class TokenTiming:
    """Per-token timing within a synthesized segment.

    Attributes:
        text: Token text.
        whitespace: Whitespace following the token ("" if none).
        start: Start time in seconds (relative to segment start).
        end: End time in seconds (relative to segment start).
    """

    text: str
    whitespace: str = ""
    start: float = 0.0
    end: float = 0.0


@dataclass(frozen=True)
class AudioSegment:
    """One contiguous synthesized segment (sentence-level chunk).

    Engines that split the input text (via ``split_pattern``) expose each
    chunk as its own AudioSegment so hosts can report per-sentence progress
    and build subtitles from per-token timings.

    Attributes:
        graphemes: The text this segment was synthesized from.
        audio: Raw float32 PCM audio bytes for this segment.
        sample_rate: Sample rate of ``audio``.
        tokens: Per-token timing details, when the engine provides them.
    """

    graphemes: str
    audio: bytes
    sample_rate: int
    tokens: tuple[TokenTiming, ...] = ()


@dataclass(frozen=True)
class SynthesizedAudio:
    """Immutable value object for synthesized audio result.

    Attributes:
        data: Raw audio bytes.
        format: Audio format of the result.
        duration: Duration of the audio.
        sample_rate: Samples per second of ``data``.
        segments: Per-segment details when the engine split the text into
            sentence-level chunks (empty for engines that only produce a
            single merged result).
    """

    data: bytes
    format: AudioFormat
    duration: Duration
    sample_rate: int
    segments: tuple[AudioSegment, ...] = ()


@dataclass(frozen=True)
class EngineConfig:
    """Immutable configuration of an Engine instance.

    Contains parameters that define how a particular Engine instance is
    created and that remain constant throughout the lifetime of that Engine.

    Plugin implementations may ignore fields that are not applicable to them.

    Attributes:
        device: Device to use ("auto", "cpu", "mps", "cuda", "cuda:0").
        language: BCP 47 language tag (e.g. "en-US"). The engine converts it to its
            internal format; callers never see engine-specific codes.
    """

    device: str = "auto"
    language: str = "en-US"


@dataclass(frozen=True)
class VoiceInfo:
    """One voice an engine offers, for voice lists and the consent screen.

    Attributes:
        id: Voice key passed in `VoiceSelection.key` (e.g. "af_heart").
        name: Display name.
        language: BCP 47 language tag of the accent (e.g. "en-GB").
        gender: "female" or "male", as the voice's maker labels it.
    """

    id: str
    name: str
    language: str
    gender: str
