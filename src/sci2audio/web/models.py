"""The API's request and response bodies (pydantic), so the OpenAPI document is exact."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from sci2audio.textprep import DEFAULT_SWITCHED_OFF, Category


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


class TextIn(Strict):
    text: str = Field(min_length=1)
    name: str = Field(default="pasted text", max_length=200)


class ChapterOut(BaseModel):
    index: int
    title: str = Field(description="the heading as printed")
    blocks: list[int]
    first_page: int | None
    references: bool
    selected: bool
    utterances: int


class SettingsModel(Strict):
    """The settings kept between runs (D-139): every job setting but the chapters."""

    language: str = Field(default="", max_length=64)
    switched_off: list[Category] = Field(
        default_factory=lambda: sorted(DEFAULT_SWITCHED_OFF), max_length=64
    )
    voice: str = Field(default="", max_length=64)
    speed: float = 1.0
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
    speed: float | None = None
    output_folder: str | None = Field(default=None, max_length=4096)


class JobIn(Strict):
    kind: Literal["script", "audio"]
    document: str = Field(max_length=64)
    settings: JobSettingsIn = Field(default_factory=JobSettingsIn)
    overwrite: bool = Field(default=False, description="replace audiobook files that exist")


class FileOut(BaseModel):
    name: str = Field(description="the file name as written")
    size: int
    folder: str


class JobOut(BaseModel):
    id: str
    kind: Literal["script", "audio", "voices"]
    document: str | None
    state: Literal["running", "done", "failed", "cancelled"]
    started: str
    finished: str | None
    cancellable: bool
    settings: dict[str, Any] | None
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
    installed: bool
    plan: PlanOut


class DownloadIn(Strict):
    consent: bool
    plan: str = Field(max_length=64, description="the digest of the plan the person agreed to")
