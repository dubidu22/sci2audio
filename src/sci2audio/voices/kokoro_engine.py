# Adapted from Abogen (https://github.com/denizsafak/abogen), files plugins/kokoro/__init__.py
# and plugins/kokoro/engine.py, revision 1807822f5871d1c92740cb470c5c6e8328b8f851, under the
# MIT licence below (D-52). Changes for sci2audio: English voices only (D-50); the model,
# voices and spaCy model are loaded from local files and never downloaded (VA-04); one
# pipeline per accent sharing one model; speed and input checks; raw float32 output with
# its sample rate; no plugin manifest, host context or plugin loader (not copied).
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
"""Kokoro English through the voice contract (VA-01, D-48, D-52).

`create_kokoro_engine(models_dir)` builds the engine from the files that
`download_voice_files` put into `models_dir`. It never goes online: when a file is missing
it raises `ModelNotFoundError` before misaki could try to download its spaCy model.
torch and kokoro are imported only inside `create_kokoro_engine`, so importing this module
stays fast.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from sci2audio.voices.download import (
    KOKORO_REPO,
    KOKORO_WEIGHTS,
    SPACY_MODEL,
    kokoro_dir,
    missing_files,
)
from sci2audio.voices.engine import API_VERSION
from sci2audio.voices.errors import EngineError, InvalidInputError, ModelNotFoundError
from sci2audio.voices.runtime import prepare_environment
from sci2audio.voices.types import (
    PCM_FLOAT32,
    AudioSegment,
    Duration,
    EngineConfig,
    SynthesisRequest,
    SynthesizedAudio,
    TokenTiming,
    VoiceInfo,
)

logger = logging.getLogger(__name__)

# Sample rate for Kokoro audio
SAMPLE_RATE = 24000
DEFAULT_VOICE = "af_heart"
SPEED_MIN = 0.5
SPEED_MAX = 2.0

# Engine-internal language mapping: language tag → kokoro code.
# ONLY visible inside this module — callers never see kokoro codes.
_KOKORO_LANG_MAP: dict[str, str] = {"en-US": "a", "en-GB": "b"}
_PREFIX_LANGUAGE = {"af": "en-US", "am": "en-US", "bf": "en-GB", "bm": "en-GB"}
_PREFIX_GENDER = {"f": "female", "m": "male"}

_VOICE_NAMES = {
    "af_alloy": "Alloy",
    "af_aoede": "Aoede",
    "af_bella": "Bella",
    "af_heart": "Heart",
    "af_jessica": "Jessica",
    "af_kore": "Kore",
    "af_nicole": "Nicole",
    "af_nova": "Nova",
    "af_river": "River",
    "af_sarah": "Sarah",
    "af_sky": "Sky",
    "am_adam": "Adam",
    "am_echo": "Echo",
    "am_eric": "Eric",
    "am_fenrir": "Fenrir",
    "am_liam": "Liam",
    "am_michael": "Michael",
    "am_onyx": "Onyx",
    "am_puck": "Puck",
    "am_santa": "Santa",
    "bf_alice": "Alice",
    "bf_emma": "Emma",
    "bf_isabella": "Isabella",
    "bf_lily": "Lily",
    "bm_daniel": "Daniel",
    "bm_fable": "Fable",
    "bm_george": "George",
    "bm_lewis": "Lewis",
}

ENGLISH_VOICES: tuple[VoiceInfo, ...] = tuple(
    VoiceInfo(
        id=voice,
        name=name,
        language=_PREFIX_LANGUAGE[voice[:2]],
        gender=_PREFIX_GENDER[voice[1]],
    )
    for voice, name in _VOICE_NAMES.items()
)
_VOICES_BY_ID = {voice.id: voice for voice in ENGLISH_VOICES}

# Builds the kokoro pipeline for one kokoro language code. Replaceable in tests, so the
# adapter is tested without torch or a model.
PipelineFactory = Callable[[str], Any]


def engine_language(language: str) -> str:
    """Map a language tag to the engine's internal code (en-US when unknown)."""
    return _KOKORO_LANG_MAP.get(language, "a")


def _pick_device(requested: str) -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _kokoro_pipeline_factory(models_dir: Path, device: str) -> PipelineFactory:
    """Load the model once from local files; make one G2P pipeline per accent on demand."""
    import spacy

    if not spacy.util.is_package(SPACY_MODEL):
        # misaki would call spacy.cli.download here: a network call nobody started.
        raise ModelNotFoundError(
            f"the spaCy model {SPACY_MODEL} is not in {models_dir}; run the voice download"
        )
    from kokoro import KModel, KPipeline

    folder = kokoro_dir(models_dir)
    model = (
        KModel(
            repo_id=KOKORO_REPO,
            config=str(folder / "config.json"),
            model=str(folder / KOKORO_WEIGHTS),
        )
        .to(_pick_device(device))
        .eval()
    )

    def make(lang_code: str) -> Any:
        return KPipeline(lang_code=lang_code, repo_id=KOKORO_REPO, model=model)

    return make


def create_kokoro_engine(
    models_dir: Path,
    config: EngineConfig | None = None,
    *,
    pipeline_factory: PipelineFactory | None = None,
) -> KokoroEngine:
    """Create a Kokoro engine from the voice files in `models_dir`.

    This function is the plugin entry point. It must be atomic:
    succeed fully or raise EngineError and clean up.

    Raises:
        ModelNotFoundError: A voice file is missing; the user has to run the download.
        EngineError: The model could not be loaded.
    """
    config = config or EngineConfig()
    missing = missing_files(models_dir)
    if missing:
        raise ModelNotFoundError(
            f"{len(missing)} voice file(s) are missing in {models_dir}, for example "
            f"{missing[0].target}; run the voice download first"
        )
    prepare_environment(models_dir)
    try:
        factory = pipeline_factory or _kokoro_pipeline_factory(models_dir, config.device)
        engine = KokoroEngine(factory, kokoro_dir(models_dir) / "voices")
        engine.pipeline_for(engine_language(config.language))
        return engine
    except EngineError:
        raise
    except Exception as e:
        raise EngineError(f"Failed to create Kokoro engine: {e}") from e


def _speed(value: Any) -> float:
    try:
        speed = float(value)
    except (TypeError, ValueError):
        raise InvalidInputError(f"speed must be a number, got {value!r}") from None
    if not math.isfinite(speed) or not SPEED_MIN <= speed <= SPEED_MAX:
        raise InvalidInputError(f"speed must be between {SPEED_MIN} and {SPEED_MAX}, got {value}")
    return speed


class KokoroSession:
    """EngineSession implementation for Kokoro.

    Owns mutable execution state for synthesis.
    NOT thread-safe.
    """

    def __init__(self, engine: KokoroEngine) -> None:
        self._engine = engine
        self._disposed = False

    def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        """Synthesize audio from text using Kokoro."""
        if self._disposed:
            raise EngineError("Session disposed")
        if not request.text.strip():
            raise InvalidInputError("nothing to say: the text is empty")
        if request.format != PCM_FLOAT32:
            raise InvalidInputError(f"Kokoro returns {PCM_FLOAT32.mime} only")
        voice = _VOICES_BY_ID.get(request.voice.key)
        if voice is None:
            raise InvalidInputError(f"unknown Kokoro English voice {request.voice.key!r}")
        speed = _speed(request.parameters.values.get("speed", 1.0))

        try:
            pipeline = self._engine.pipeline_for(engine_language(voice.language))
            voice_file = str(self._engine.voice_file(voice.id))
            audio_parts: list[np.ndarray] = []
            segments: list[AudioSegment] = []
            # split_pattern=None: the caller sends one utterance; kokoro still cuts text
            # that is too long for one pass at its own punctuation-based limits.
            for segment in pipeline(
                request.text, voice=voice_file, speed=speed, split_pattern=None
            ):
                audio = segment.audio
                if audio is None:
                    continue
                if hasattr(audio, "numpy"):
                    audio = audio.numpy()
                audio = np.asarray(audio, dtype="float32").reshape(-1)
                if audio.size == 0:
                    continue
                audio_parts.append(audio)

                tokens = tuple(
                    TokenTiming(
                        text=str(tok.text),
                        whitespace=str(tok.whitespace or ""),
                        start=float(tok.start_ts or 0.0),
                        end=float(tok.end_ts or 0.0),
                    )
                    for tok in (getattr(segment, "tokens", None) or [])
                )
                segments.append(
                    AudioSegment(
                        graphemes=str(getattr(segment, "graphemes", "") or ""),
                        audio=audio.tobytes(),
                        sample_rate=SAMPLE_RATE,
                        tokens=tokens,
                    )
                )

            combined = (
                np.concatenate(audio_parts) if audio_parts else np.zeros(0, dtype="float32")
            ).astype("<f4", copy=False)
            return SynthesizedAudio(
                data=combined.tobytes(),
                format=PCM_FLOAT32,
                duration=Duration(seconds=len(combined) / SAMPLE_RATE),
                sample_rate=SAMPLE_RATE,
                segments=tuple(segments),
            )
        except EngineError:
            raise
        except Exception as e:
            raise EngineError(f"Synthesis failed: {e}") from e

    def dispose(self) -> None:
        """Release session resources. Idempotent."""
        self._disposed = True


class KokoroEngine:
    """Engine implementation for Kokoro.

    Factory for KokoroSession instances. One model, one G2P pipeline per accent.
    """

    api_version = API_VERSION

    def __init__(self, pipeline_factory: PipelineFactory, voices_dir: Path) -> None:
        self._factory = pipeline_factory
        self._voices_dir = voices_dir
        self._pipelines: dict[str, Any] = {}
        self._disposed = False

    def pipeline_for(self, lang_code: str) -> Any:
        """The pipeline for one kokoro language code, made on first use."""
        if self._disposed:
            raise EngineError("Engine disposed")
        if lang_code not in self._pipelines:
            self._pipelines[lang_code] = self._factory(lang_code)
        return self._pipelines[lang_code]

    def voice_file(self, voice_id: str) -> Path:
        """Local voice pack of a voice; never a name kokoro would download."""
        path = self._voices_dir / f"{voice_id}.pt"
        if not path.is_file():
            raise ModelNotFoundError(f"voice file {path} is missing; run the voice download")
        return path

    def createSession(self) -> KokoroSession:
        """Create a new KokoroSession."""
        if self._disposed:
            raise EngineError("Engine disposed")
        return KokoroSession(self)

    def listVoices(self) -> tuple[VoiceInfo, ...]:
        """List the English Kokoro voices."""
        if self._disposed:
            raise EngineError("Engine disposed")
        return ENGLISH_VOICES

    def dispose(self) -> None:
        """Release engine resources. Idempotent."""
        self._disposed = True
        self._pipelines.clear()
