"""The voice an audio job speaks with, passed in as a `VoiceSource` (D-166).

The source names the engine and its version (for the chunk cache key, D-155) without
loading anything; `make` loads the engine only when a chunk has to be spoken, so a rerun
whose chunks are all cached never loads the model. `release` hands the engine back when
the job ends (the default disposes it; a server that keeps one engine loaded can pass its
own).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

from sci2audio.voices import DEFAULT_VOICE, ENGLISH_VOICES, Engine, create_kokoro_engine
from sci2audio.voices.download import KOKORO_REVISION


def _dispose(engine: Engine) -> None:
    engine.dispose()


@dataclass(frozen=True)
class VoiceSource:
    """An engine the job can make on demand, and what identifies its sound."""

    engine: str  # e.g. "kokoro"
    version: str  # changes whenever the same text, voice and speed may sound different
    make: Callable[[], Engine]
    voices: tuple[str, ...]  # the voice ids it has, checked before any work
    default_voice: str
    release: Callable[[Engine], None] = field(default=_dispose)

    def __post_init__(self) -> None:
        if not self.engine or not self.version:
            raise ValueError("a voice source needs an engine name and a version")
        if self.default_voice not in self.voices:
            raise ValueError(f"the default voice {self.default_voice!r} is not in its voices")


def _installed(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "missing"


def kokoro_version() -> str:
    """The pinned Kokoro model revision and the installed kokoro and misaki versions."""
    return (
        f"kokoro-82m@{KOKORO_REVISION[:12]};"
        f"kokoro {_installed('kokoro')};misaki {_installed('misaki')}"
    )


def kokoro_voice(models_dir: Path) -> VoiceSource:
    """Kokoro English from the voice files the voice setup put into `models_dir`.

    `create_kokoro_engine` sets the offline environment first (`HF_HUB_OFFLINE=1`, the
    spaCy model on `sys.path`) and never downloads anything (VA-04).
    """
    return VoiceSource(
        engine="kokoro",
        version=kokoro_version(),
        make=lambda: create_kokoro_engine(models_dir),
        voices=tuple(voice.id for voice in ENGLISH_VOICES),
        default_voice=DEFAULT_VOICE,
    )
