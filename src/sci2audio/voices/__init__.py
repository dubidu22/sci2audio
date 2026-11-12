"""Voices: speech engines behind one plugin contract (D-46, D-52).

Pipeline stage; may import only ``sci2audio.core`` (and no other sci2audio stage).

- Contract (copied from Abogen, MIT): `Engine`, `EngineSession`, the value objects in
  `types` and the errors in `errors`.
- Kokoro English: `create_kokoro_engine(models_dir)`, `ENGLISH_VOICES`.
- The one user-started download: `download_plan()` and `download_voice_files()`.
- `prepare_environment()`: the start-up settings (MPS fallback, Hugging Face offline).
- `speak_to_wav()` and `preview()`: 16-bit mono WAV files for the output stage.

Nothing here imports torch or kokoro at import time.
"""

from sci2audio.voices.download import (
    DownloadError,
    DownloadPlan,
    RemoteFile,
    download_plan,
    download_voice_files,
    missing_files,
)
from sci2audio.voices.engine import API_VERSION, Engine, EngineSession
from sci2audio.voices.errors import (
    CancelledError,
    ConfigurationError,
    EngineError,
    InternalError,
    InvalidInputError,
    ModelLoadError,
    ModelNotFoundError,
    NetworkError,
)
from sci2audio.voices.kokoro_engine import (
    DEFAULT_VOICE,
    ENGLISH_VOICES,
    SAMPLE_RATE,
    SPEED_MAX,
    SPEED_MIN,
    KokoroEngine,
    KokoroSession,
    create_kokoro_engine,
)
from sci2audio.voices.runtime import prepare_environment
from sci2audio.voices.types import (
    PCM_FLOAT32,
    AudioFormat,
    AudioSegment,
    Duration,
    EngineConfig,
    ParameterValues,
    SynthesisRequest,
    SynthesizedAudio,
    TokenTiming,
    VoiceInfo,
    VoiceSelection,
)
from sci2audio.voices.wav import PREVIEW_TEXT, preview, speak_to_wav, write_wav

__all__ = [
    "API_VERSION",
    "DEFAULT_VOICE",
    "ENGLISH_VOICES",
    "PCM_FLOAT32",
    "PREVIEW_TEXT",
    "SAMPLE_RATE",
    "SPEED_MAX",
    "SPEED_MIN",
    "AudioFormat",
    "AudioSegment",
    "CancelledError",
    "ConfigurationError",
    "DownloadError",
    "DownloadPlan",
    "Duration",
    "Engine",
    "EngineConfig",
    "EngineError",
    "EngineSession",
    "InternalError",
    "InvalidInputError",
    "KokoroEngine",
    "KokoroSession",
    "ModelLoadError",
    "ModelNotFoundError",
    "NetworkError",
    "ParameterValues",
    "RemoteFile",
    "SynthesisRequest",
    "SynthesizedAudio",
    "TokenTiming",
    "VoiceInfo",
    "VoiceSelection",
    "create_kokoro_engine",
    "download_plan",
    "download_voice_files",
    "missing_files",
    "prepare_environment",
    "preview",
    "speak_to_wav",
    "write_wav",
]
