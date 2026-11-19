"""The API's request and response bodies (pydantic), so the OpenAPI document is exact."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from sci2audio.textprep import DEFAULT_SWITCHED_OFF, Category
from sci2audio.voices import PREVIEW_TEXT

# characters of a voice preview text: a short sample, a limit of its own (not the cutter's, #534)
PREVIEW_LIMIT = 300
# how fast the voice reads letters it spells out ("NLP"): the keys of app's LETTER_PACES (#295)
LetterPace = Literal["normal", "slower", "slowest"]
LETTER_PACE_HELP = "how fast the voice reads letters it spells out, as in NLP (#295)"
SUBTITLES_HELP = "also write SRT and WebVTT subtitles next to the audio files (#214)"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorOut(BaseModel):
    error: str = Field(description="what went wrong, for programs (e.g. busy, too-large)")
    message: str = Field(description="what went wrong, in words a person can act on")


class DocumentOut(BaseModel):
    id: str = Field(description="the first 16 hex digits of the file's SHA-256")
    name: str = Field(description="the file name as opened")
    size: int
    has_report: bool
    has_audio: bool
    speech_cache_bytes: int = Field(
        description="bytes of kept speech chunks; freed by DELETE …/chunks (D-158)"
    )


class KeptOut(BaseModel):
    """A file or folder the removal left, and why (#470, D-751)."""

    path: str
    reason: str = Field(
        description="changed, not-recorded, link, outside, shared, unreadable or kept-by-choice"
    )
    folder: str = Field(
        description="the audiobook folder it is in; equal to path when a whole folder stayed"
    )


class RemovedOut(BaseModel):
    """What removing a document took away and what stayed (D-358, D-751)."""

    id: str
    name: str = Field(description="the file name as opened")
    freed_bytes: int = Field(description="bytes of the working folder that were removed")
    audiobook_folder: str | None = Field(
        description="the folder of the document's latest audiobook; null when none was recorded"
    )
    deleted_files: int = Field(default=0, description="audiobook files deleted")
    deleted_bytes: int = Field(default=0, description="bytes of the audiobook files deleted")
    kept: list[KeptOut] = Field(
        default_factory=list,
        description="what stayed in the audiobook folders, and why; whole folders first",
    )
    kept_more: int = Field(default=0, description="further paths that stayed, not listed")


class TextIn(Strict):
    text: str = Field(min_length=1)
    name: str = Field(default="pasted text", max_length=200)


class ChapterOut(BaseModel):
    index: int
    title: str = Field(description="the heading as printed")
    blocks: list[int]
    first_page: int | None
    references: bool
    publisher: bool = Field(
        default=False,
        description="a publisher's page (imprint, colophon …), not read by default (#190); "
        "false in a report written before #376",
    )
    selected: bool
    utterances: int


class SettingsModel(Strict):
    """The settings kept between runs (D-139): every job setting but the chapters."""

    language: str = Field(default="", max_length=64)
    switched_off: list[Category] = Field(
        default_factory=lambda: sorted(DEFAULT_SWITCHED_OFF), max_length=64
    )
    voice: str = Field(default="", max_length=64)
    speed: float = Field(default=1.0, strict=True)  # true is no speed (#295 found it)
    letter_pace: LetterPace = Field(default="normal", description=LETTER_PACE_HELP)
    subtitles: StrictBool = Field(default=False, description=SUBTITLES_HELP)
    output_folder: str | None = Field(default=None, max_length=4096)


class CategoryOut(BaseModel):
    id: str
    label: str
    on_by_default: bool


class VoiceOut(BaseModel):
    id: str
    name: str
    language: str
    gender: str


class SpeedRange(BaseModel):
    min: float
    max: float


class SettingsOut(BaseModel):
    settings: SettingsModel
    warnings: list[str] = Field(description="what could not be read from the settings file")
    categories: list[CategoryOut]
    speed: SpeedRange
    voices: list[VoiceOut]
    default_voice: str
    default_output_folder: str


class JobSettingsIn(Strict):
    """The person's choices for one job; fields left out come from the saved settings."""

    language: str | None = Field(default=None, max_length=64)
    switched_off: list[Category] | None = Field(default=None, max_length=64)
    chapters: list[int] | None = Field(
        default=None, max_length=10_000, description="chapter indices; null = the default"
    )
    voice: str | None = Field(default=None, max_length=64)
    speed: float | None = Field(default=None, strict=True)
    letter_pace: LetterPace | None = Field(default=None, description=LETTER_PACE_HELP)
    subtitles: StrictBool | None = Field(default=None, description=SUBTITLES_HELP)
    output_folder: str | None = Field(default=None, max_length=4096)


class JobIn(Strict):
    kind: Literal["script", "audio"]
    document: str = Field(max_length=64)
    settings: JobSettingsIn = Field(default_factory=JobSettingsIn)
    overwrite: StrictBool = Field(
        default=False, description="replace audiobook files that exist; only `true` does"
    )


class FileOut(BaseModel):
    name: str = Field(description="the file name as written")
    size: int
    folder: str


class JobOut(BaseModel):
    id: str
    kind: Literal["script", "audio", "voices", "preview"]
    document: str | None
    state: Literal["running", "done", "failed", "cancelled"]
    started: str
    finished: str | None
    cancellable: bool
    settings: dict[str, Any] | None
    overwrite: bool = Field(
        description="the job was started with `overwrite`; resuming it sends the same (D-733)"
    )
    progress: dict[str, Any] | None
    error: ErrorOut | None
    files: list[FileOut]


class PlanFileOut(BaseModel):
    url: str
    target: str
    size: int
    sha256: str
    licence: str


class PlanOut(BaseModel):
    digest: str = Field(description="name this in the download request to consent to it")
    total_bytes: int
    missing_bytes: int
    licences: list[str]
    hosts: list[str] = Field(description="hosts the download talks to, redirects included")
    files: list[PlanFileOut]


class VoicesOut(BaseModel):
    voices: list[VoiceOut]
    default_voice: str
    installed: bool = Field(description="every voice pack is installed")
    installed_languages: list[str] = Field(
        description='the voice packs ("en", "de") whose files are all installed'
    )
    plan: PlanOut


class PositionIn(Strict):
    """Where the person stopped listening (#153)."""

    chapter: int = Field(
        ge=0,
        le=100_000,
        strict=True,
        description="the chapter, counted from 0 as the read-along file counts them",
    )
    time: float = Field(
        ge=0, le=10_000_000, allow_inf_nan=False, description="seconds on the book's timeline"
    )
    audiobook: str = Field(
        pattern=r"^[0-9a-f]{16}$",
        description="the stamp of the audiobook the page was drawn for (its read-along file)",
    )


class DownloadIn(Strict):
    consent: StrictBool = Field(description="only `true` starts the download")
    plan: str = Field(max_length=64, description="the digest of the plan the person agreed to")


class PreviewIn(Strict):
    """A voice preview (VA-05, D-249): one sentence with one voice at one speed."""

    voice: str = Field(default="", max_length=64, description='"" = the default voice')
    speed: float = Field(default=1.0, strict=True)
    letter_pace: LetterPace = Field(default="normal", description=LETTER_PACE_HELP)
    text: str = Field(default=PREVIEW_TEXT, min_length=1, max_length=PREVIEW_LIMIT)


class MarkerIn(Strict):
    """A marker on the sentence the page was reading (#474): the page names its chunk, never
    a span or a text."""

    chunk: int = Field(
        ge=0, le=10_000_000, strict=True, description="the read-along chunk of the sentence"
    )
    audiobook: str = Field(
        pattern=r"^[0-9a-f]{16}$",
        description="the stamp of the audiobook the page was drawn for (its read-along file)",
    )


class NoteIn(Strict):
    note: str = Field(
        max_length=4000,
        pattern=r"^[^\x00]*$",
        description='the marker\'s note, plain text ("" for none)',
    )


class MarkerOut(BaseModel):
    id: str = Field(description="16 hex digits")
    created: str = Field(description="when it was set, UTC")
    changed: str = Field(description="when it or its note last changed, UTC")
    text: str = Field(description="the sentence as printed when it was set")
    note: str = Field(description='its note ("" for none)')
    chunk: int | None = Field(
        description="the first chunk of its sentence in this audiobook, or null"
    )
    state: Literal["found", "not-read", "not-found"] = Field(
        description="found; in text this audiobook does not read; or not found in it"
    )
