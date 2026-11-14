"""The voice an audio job speaks with, passed in as a `VoiceSource` (D-166).

The source names the engine and its version (for the chunk cache key, D-155) without
loading anything; `make` loads the engine only when a chunk has to be spoken, so a rerun
whose chunks are all cached never loads the model. `release` hands the engine back when
the job ends (the default disposes it; a server that keeps one engine loaded can pass its
own).

A source may speak several languages (D-469): `voice_for` picks the voice of a job from
the chosen voice and the job's language, `version_of` gives each voice's version (so one
language's model never changes another's cache keys, D-471), and `installed` tells
whether a voice's files are there (a job needs only its own voice pack, D-468).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

from sci2audio.voices import (
    DEFAULT_VOICE,
    DEFAULT_VOICES,
    GERMAN_VOICES,
    VOICES,
    Engine,
    create_kokoro_engine,
    missing_files,
    voice_pack,
)
from sci2audio.voices.download import GERMAN_REVISION, KOKORO_REVISION


def _dispose(engine: Engine) -> None:
    engine.dispose()


def _every_voice_installed(voice_id: str) -> bool:
    return True


def primary_language(tag: str) -> str:
    """The primary subtag of a BCP 47 tag, lower case ("de-DE" → "de")."""
    return tag.split("-")[0].strip().lower()


@dataclass(frozen=True)
class VoiceSource:
    """An engine the job can make on demand, and what identifies its sound."""

    engine: str  # e.g. "kokoro"
    version: str  # changes whenever the same text, voice and speed may sound different
    make: Callable[[], Engine]
    voices: tuple[str, ...]  # the voice ids it has, checked before any work
    default_voice: str
    release: Callable[[Engine], None] = field(default=_dispose)
    # several languages (D-469): the tag of each voice, the default voice per primary
    # subtag ("en", "de"); a language with no default here keeps the chosen voice
    languages: Mapping[str, str] = field(default_factory=dict)
    defaults: Mapping[str, str] = field(default_factory=dict)
    # a voice's version when it differs from `version` (another model, D-471)
    versions: Mapping[str, str] = field(default_factory=dict)
    # whether a voice's files are installed (D-468); checked before any speech
    installed: Callable[[str], bool] = field(default=_every_voice_installed)

    def __post_init__(self) -> None:
        if not self.engine or not self.version:
            raise ValueError("a voice source needs an engine name and a version")
        if self.default_voice not in self.voices:
            raise ValueError(f"the default voice {self.default_voice!r} is not in its voices")
        unknown = sorted(
            {*self.defaults.values(), *self.versions, *self.languages} - set(self.voices)
        )
        if unknown:
            raise ValueError(f"voices {unknown} are not in the source's voices")

    def version_of(self, voice_id: str) -> str:
        """What identifies the sound of one voice, for its chunk cache keys (D-155)."""
        return self.versions.get(voice_id, self.version)

    def voice_for(self, chosen: str, language: str) -> str:
        """The voice a job speaks with (D-469).

        `chosen` is the job's voice setting ("" = none). For a language with a default
        voice, the chosen voice is used only if it speaks that language, otherwise the
        language's default. A language without one keeps today's rule: the chosen voice,
        else `default_voice`.
        """
        primary = primary_language(language)
        default = self.defaults.get(primary)
        if default is None:
            return chosen or self.default_voice
        if chosen and primary_language(self.languages.get(chosen, "")) == primary:
            return chosen
        return default


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


def kokoro_german_version() -> str:
    """The pinned German model revision and the installed kokoro, misaki and espeak-ng
    (espeakng-loader) versions: the German voice pronounces through espeak-ng (#211)."""
    return (
        f"kokoro-de-thorsten@{GERMAN_REVISION[:12]};"
        f"kokoro {_installed('kokoro')};misaki {_installed('misaki')};"
        f"espeakng-loader {_installed('espeakng-loader')}"
    )


def kokoro_voice(models_dir: Path) -> VoiceSource:
    """Kokoro English and German from the voice files the voice setup put into
    `models_dir`.

    `create_kokoro_engine` sets the offline environment first (`HF_HUB_OFFLINE=1`, the
    spaCy model on `sys.path`) and never downloads anything (VA-04). English versions are
    the same as before the German voice came (D-471), so no English chunk is spoken again.
    """
    german = kokoro_german_version()
    return VoiceSource(
        engine="kokoro",
        version=kokoro_version(),
        make=lambda: create_kokoro_engine(models_dir),
        voices=tuple(voice.id for voice in VOICES),
        default_voice=DEFAULT_VOICE,
        languages={voice.id: voice.language for voice in VOICES},
        defaults=dict(DEFAULT_VOICES),
        versions={voice.id: german for voice in GERMAN_VOICES},
        installed=lambda voice_id: not missing_files(models_dir, (voice_pack(voice_id),)),
    )
