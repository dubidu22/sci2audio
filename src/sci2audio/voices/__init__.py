"""Voices: speech engines behind one plugin contract (D-46, D-52).

Pipeline stage; may import only ``sci2audio.core`` (and no other sci2audio stage).

- Contract (copied from Abogen, MIT): `Engine`, `EngineSession`, the value objects in
  `types` and the errors in `errors`.
- Kokoro English and German: `create_kokoro_engine(models_dir)`, `VOICES` (=
  `ENGLISH_VOICES` + `GERMAN_VOICES`), `DEFAULT_VOICES` per language, `voice_pack()`.
- The one user-started download, in one pack per language (`PACKS`): `download_plan()`,
  `download_voice_files()`, `missing_files()`, `installed_languages()`.
- `prepare_environment()`: the start-up settings (MPS fallback, Hugging Face offline).
- `speak_to_wav()` and `preview()`: 16-bit mono WAV files for the output stage.

Nothing here imports torch or kokoro at import time.
"""

from sci2audio.voices.download import (
    ENGLISH,
    GERMAN,
    PACKS,
    DownloadError,
    DownloadPlan,
    RemoteFile,
    download_plan,
    download_voice_files,
    installed_languages,
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
    DEFAULT_VOICES,
    ENGLISH_VOICES,
    GERMAN_DEFAULT_VOICE,
    GERMAN_VOICES,
    SAMPLE_RATE,
    SPEED_MAX,
    SPEED_MIN,
    VOICES,
    KokoroEngine,
    KokoroSession,
    create_kokoro_engine,
    voice_pack,
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
from sci2audio.voices.wav import (
    PREVIEW_TEXT,
    PREVIEW_TEXTS,
    preview,
    preview_text,
    speak_to_wav,
    write_wav,
)

__all__ = [
    "API_VERSION",
    "DEFAULT_VOICE",
    "DEFAULT_VOICES",
    "ENGLISH",
    "ENGLISH_VOICES",
    "GERMAN",
    "GERMAN_DEFAULT_VOICE",
    "GERMAN_VOICES",
    "PACKS",
    "PCM_FLOAT32",
    "PREVIEW_TEXT",
    "PREVIEW_TEXTS",
    "SAMPLE_RATE",
    "SPEED_MAX",
    "SPEED_MIN",
    "VOICES",
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
    "installed_languages",
    "missing_files",
    "prepare_environment",
    "preview",
    "preview_text",
    "speak_to_wav",
    "voice_pack",
    "write_wav",
]
