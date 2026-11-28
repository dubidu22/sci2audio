"""The API's request and response bodies (pydantic), so the OpenAPI document is exact."""

from __future__ import annotations

from datetime import datetime
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


class BookErrorOut(ErrorOut):
    """An error of the whole-book download (#725); `missing-chapters` names the chapters."""

    chapters: list[str] | None = Field(
        default=None, description="missing-chapters: the titles of the chapters not made yet"
    )


class JobErrorOut(ErrorOut):
    """Why a job ended without its result; `settings-changed` lists what differs (#726)."""

    changes: list[str] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description="settings-changed: the choices that differ from those the project's "
        "chapters were made with, in words; left out for any other error",
    )


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
    state: Literal["generated", "generating", "not-generated"] | None = Field(
        default=None,
        description="whether the chapter's audio is made (#726); null while the project has "
        "no chapter made",
    )


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


class UpdatesIn(Strict):
    """Turn the update check on or off (#217)."""

    enabled: StrictBool = Field(description="look for a new version once a day")


class UpdatesOut(BaseModel):
    """The update check (#217): the choice and the last check's result."""

    enabled: bool
    checked_at: datetime | None = Field(description="when the last check was made (UTC)")
    outcome: Literal["newer", "current", "failed"] | None
    latest: str | None = Field(description="the newest version the last answer named")
    release_url: str | None = Field(description="the newer version's release page, if any")


class PlayerSpeed(Strict):
    """The player's playback speed, kept for the next Listen page (#651)."""

    speed: float = Field(
        ge=0.5,
        le=3.0,
        strict=True,
        allow_inf_nan=False,
        description="times the voice's own speed, 0.5 to 3; kept rounded to 0.01",
    )


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
    keep_settings: StrictBool = Field(
        default=False,
        description="make the chapters added with the settings the project's chapters were "
        "made with (#726); only the chapters and the output folder are taken from `settings`",
    )


class FileOut(BaseModel):
    name: str = Field(description="the file name as written")
    size: int
    folder: str


class JobOut(BaseModel):
    id: str
    kind: Literal["script", "audio", "voices", "preview", "book"]
    document: str | None
    state: Literal["running", "done", "failed", "cancelled"]
    started: str
    finished: str | None
    cancellable: bool
    settings: dict[str, Any] | None
    overwrite: bool = Field(
        description="the job was started with `overwrite`; resuming it sends the same (D-733)"
    )
    keep_settings: bool = Field(
        default=False, description="the job was started with `keep_settings` (#726)"
    )
    progress: dict[str, Any] | None
    error: JobErrorOut | None
    files: list[FileOut]


class BookIn(Strict):
    """Which whole-book file to download (#725)."""

    kind: Literal["m4b", "mp3"] = Field(
        default="m4b", description="m4b: one file with chapter marks; mp3: one MP3 with ID3 ones"
    )
    partial_ok: StrictBool = Field(
        default=False, description="build it from the chapters made when others are missing"
    )


class BookOut(BaseModel):
    """The whole-book file: its name when it is built already (200), else the job that
    builds it (202), whose progress names the file once done."""

    name: str | None = Field(description="download it from …/audiobook/{name}?download=true")
    partial: bool = Field(description="chapters the person chose are missing from it")
    job: JobOut | None


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
    index: int | None = Field(
        default=None,
        ge=0,
        le=100_000,
        strict=True,
        description="the chapter's index in the document; with `within`, it places the "
        "position, as a chapter added before it moves `chapter` and `time` (#726)",
    )
    within: float | None = Field(
        default=None,
        ge=0,
        le=10_000_000,
        allow_inf_nan=False,
        description="seconds from the start of the chapter `index`",
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


class CaptureIn(Strict):
    """A capture on the sentence the page was reading (#397, ADR-008): the page names its
    chunk, never a span or a sentence's text."""

    type: Literal["mark", "note", "quote"] = Field(description="what is captured")
    chunk: int = Field(
        ge=0, le=10_000_000, strict=True, description="the read-along chunk of the sentence"
    )
    audiobook: str = Field(
        pattern=r"^[0-9a-f]{16}$",
        description="the stamp of the audiobook the page was drawn for (its read-along file)",
    )
    text: str = Field(
        default="",
        max_length=4000,
        pattern=r"^[^\x00]*$",
        description='a note\'s text, plain text; "" for a mark and a quote',
    )


class CaptureTextIn(Strict):
    text: str = Field(
        min_length=1, max_length=4000, pattern=r"^[^\x00]*$", description="the note's new text"
    )


class CaptureOut(BaseModel):
    id: str = Field(description="16 hex digits")
    type: Literal["mark", "note", "quote"] = Field(description="what was captured")
    created: str = Field(description="when it was set, UTC")
    changed: str = Field(description="when it last changed, UTC")
    sentence: str = Field(description="the sentence as printed when it was captured")
    text: str = Field(description='a note\'s text ("" for a mark and a quote)')
    chunk: int | None = Field(
        description="the first chunk of its sentence in this audiobook, or null"
    )
    state: Literal["found", "not-read", "not-found", "no-audiobook"] = Field(
        description="found; in text this audiobook does not read; not found in it; or the "
        "document has no audiobook now (a removal or an Undo from the Captures page, #398)"
    )
    page: int | None = Field(
        default=None,
        description="the PDF page on which its sentence starts (#888); null for a document "
        "without pages, a sentence not found, or no audiobook now",
    )


class CaptureExportIn(Strict):
    """Save the captures the Captures page shows as one file (#399, ADR-008 2.1 item 7)."""

    format: Literal["md", "ris", "csv"] = Field(
        description="md: Markdown (Obsidian); ris: RIS (Zotero); csv: the table of captures"
    )
    folder: str = Field(
        max_length=4096,
        pattern=r"^[^\x00]*$",
        description="the folder to save into, a full path; it must exist",
    )
    type: Literal["all", "note", "quote", "mark"] = Field(
        default="all", description="the page's type filter"
    )
    document: str = Field(
        default="", max_length=200, description='the page\'s document filter ("" for all)'
    )
    overwrite: StrictBool = Field(
        default=False,
        description="replace the file `file` names: only after the person said yes to it",
    )
    file: str = Field(
        default="",
        max_length=300,
        description="with overwrite: the file the 409 answer named and the person said yes "
        "to replacing; a request that would write another file is refused again",
    )


class CaptureExportOut(BaseModel):
    file: str = Field(description="the file's name")
    folder: str = Field(description="the folder it was saved in")
    path: str = Field(description="the file's full path")
    count: int = Field(description="how many captures it holds")


class CaptureTextOut(BaseModel):
    text: str = Field(description="the Markdown file's text, as Save Markdown file writes it")
    count: int = Field(description="how many captures it holds")


class ExportExistsOut(ErrorOut):
    """export-exists: nothing was written; the page asks before it sends `overwrite`."""

    file: str = Field(description="the name of the file that is there")
    folder: str = Field(description="the folder it is in")


class ExportRefusedOut(ErrorOut):
    """export-folder-refused: the folder took no file; export-file-refused: the new file
    was written in full but replacing the old one was refused for a reason other than a
    program holding it (a sticky folder, a locked or read-only file, #1003). The old file
    stays as it was and no other file is left."""

    file: str | None = Field(
        default=None, description="export-file-refused: the file that could not be replaced"
    )
    folder: str | None = Field(default=None, description="export-file-refused: its folder")


class ExportHeldOut(ErrorOut):
    """export-file-held: replacing the file was refused after the new one was written in
    full, as Windows refuses while another program holds it open (#990); it stays as it
    was and no other file is left."""

    file: str = Field(description="the name of the file that could not be replaced")
    folder: str = Field(description="the folder it is in")
