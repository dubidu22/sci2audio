# Copied from Abogen (https://github.com/denizsafak/abogen), file abogen/tts_plugin/engine.py,
# revision 1807822f5871d1c92740cb470c5c6e8328b8f851, under the MIT licence below (D-52).
# Changes for sci2audio: `API_VERSION`, and the voice list and `api_version` on `Engine`
# (Abogen's `VoiceLister` capability, whose module is not copied).
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
"""Engine interfaces of the voice plugin contract (D-46, D-52).

This module defines the core Engine and EngineSession protocols.
These are the primary interfaces that plugin implementations must satisfy.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sci2audio.voices.types import SynthesisRequest, SynthesizedAudio, VoiceInfo

# Version of this contract. An engine states the version it implements in `api_version`;
# the conformance suite (`sci2audio.testing.voices`) checks it.
API_VERSION = "1.0"


@runtime_checkable
class EngineSession(Protocol):
    """Protocol for a session that owns mutable execution state.

    An EngineSession is created by Engine.createSession() and owns
    mutable execution state isolated from other concurrent work.
    It is NOT thread-safe.

    Lifecycle:
        1. Created by Engine.createSession()
        2. Used for synthesis via synthesize()
        3. Disposed via dispose()

    After dispose(), all methods except dispose() raise EngineError.
    """

    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        """Synthesize audio from text.

        Args:
            request: The synthesis request containing text, voice, parameters, and format.

        Returns:
            SynthesizedAudio with the synthesized audio data.

        Raises:
            EngineError: On synthesis failure. Session remains usable after error.
            EngineError: If called after dispose().
        """
        ...

    def dispose(self) -> None:
        """Release session resources.

        This method is idempotent and safe to call multiple times.
        It never raises exceptions (catches and logs internally).
        After dispose(), all methods except dispose() raise EngineError.
        """
        ...


@runtime_checkable
class Engine(Protocol):
    """Protocol for a TTS engine that creates sessions.

    An Engine is a factory for EngineSession instances. It is stateless
    and thread-safe for createSession().

    Lifecycle:
        1. Created via create_engine() (plugin contract)
        2. Sessions created via createSession()
        3. Disposed via dispose()

    Thread Safety:
        - createSession() is thread-safe and can be called from any thread.
        - dispose() must be called after all sessions are disposed.
        - Disposing engine while sessions are alive violates API contract.
    """

    api_version: str

    def createSession(self) -> EngineSession:
        """Create a new session for synthesis.

        Returns:
            A new EngineSession instance. Ownership transfers to caller.

        Raises:
            EngineError: On failure. No partially initialized session is returned.
        """
        ...

    def listVoices(self) -> tuple[VoiceInfo, ...]:
        """List the voices this engine can speak with.

        Raises:
            EngineError: If called after dispose().
        """
        ...

    def dispose(self) -> None:
        """Release engine resources.

        Caller must ensure all sessions created by this engine are disposed
        before calling dispose(). Disposing an engine while any session is
        still alive violates the API contract; behavior is undefined.

        This method is idempotent and safe to call multiple times.
        It never raises exceptions (catches and logs internally).
        After dispose(), all methods except dispose() raise EngineError.
        """
        ...
