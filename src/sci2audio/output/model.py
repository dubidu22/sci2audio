"""What output is given: the spoken chunks with their pauses, the chapters, the book's details
and the settings. The app builds these (#71); output never sees the `Document`."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from sci2audio.core import AudioChunk


class Pause(StrEnum):
    """The silence placed before a chunk; `OutputSettings` says how long each one is (VA-06).

    The app picks one per chunk: HEADING after a heading, PARAGRAPH for the first chunk of a
    new block, PAUSE_EDIT after a `pause` edit, SENTENCE between sentences of one block,
    CLAUSE where a long sentence was cut at a clause mark (Q4, #480). When two reasons meet,
    `Pause.strongest` picks the later kind in this list. The first chunk of a chapter always
    gets the chapter pause instead, whatever kind it carries.

    At a CLAUSE pause output also trims the voice's own silence at the end of the chunk before
    and at the start of the chunk itself (`wav.edge_trim`), so the pieces of a cut sentence
    sound joined: the gap is about the clause pause, like a comma inside a sentence spoken
    whole. NONE (no pause, no trim) is what plans made before #480 used for a cut.
    """

    NONE = "none"
    CLAUSE = "clause"
    SENTENCE = "sentence"
    PAUSE_EDIT = "pause_edit"
    PARAGRAPH = "paragraph"
    HEADING = "heading"

    @staticmethod
    def strongest(*kinds: Pause) -> Pause:
        """The strongest of the given kinds (in the order of the class), NONE if none given."""
        order = list(Pause)
        return max(kinds, key=order.index, default=Pause.NONE)


@dataclass(frozen=True)
class Spoken:
    """One chunk of the voice, the pause before it and the text the voice spoke (for the
    subtitles, #214: notices and replacements as spoken, not as printed).

    `continues` is true when the chunk goes on with the sentence of the chunk before it (the
    length limit cut the sentence, #480); the read-along file marks it as `joins`."""

    chunk: AudioChunk
    pause: Pause = Pause.SENTENCE
    text: str = ""
    continues: bool = False


@dataclass(frozen=True)
class Chapter:
    """A chapter: its title and the index of its first `Spoken` in the job."""

    title: str
    first: int

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("a chapter needs a title")
        if self.first < 0:
            raise ValueError(f"a chapter's first chunk must be >= 0, got {self.first}")


@dataclass(frozen=True)
class BookInfo:
    """What the files say about the book: title, authors, language and an optional cover."""

    title: str
    authors: tuple[str, ...] = ()
    language: str = "en"  # BCP 47, e.g. "en" or "en-GB"
    cover: Path | None = None  # a JPEG or PNG file

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("a book needs a title")
        if not self.language.strip():
            raise ValueError("a book needs a language, e.g. 'en'")


@dataclass(frozen=True)
class OutputSettings:
    """Pause lengths in seconds (Q8, D-61 left them open) and which files to write.

    `subtitles` adds an SRT and a WebVTT file next to each chapter MP3 and next to the M4B
    (#214, D-606)."""

    chapter_pause: float = 2.0  # at the start of every chapter
    heading_pause: float = 1.0  # after a heading
    paragraph_pause: float = 0.6  # between blocks
    pause_edit: float = 0.5  # for a `pause` edit of a text step
    # where a long sentence was cut (#480): a comma pause measured with the voices, between
    # Kokoro's German (0.10 to 0.20 s) and English (0.23 to 0.49 s) ones
    clause_pause: float = 0.25
    sentence_pause: float = 0.3  # between sentences of one block
    mp3: bool = True  # one MP3 per chapter
    m4b: bool = True  # one M4B with chapter marks
    mp3_bitrate: str = "64k"  # mono speech
    aac_bitrate: str = "64k"
    subtitles: bool = False  # .srt and .vtt next to the audio files

    def __post_init__(self) -> None:
        for name in (
            "chapter_pause",
            "heading_pause",
            "paragraph_pause",
            "pause_edit",
            "clause_pause",
            "sentence_pause",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not 0 <= value <= 60:
                raise ValueError(f"{name} must be between 0 and 60 seconds, got {value}")
            object.__setattr__(self, name, value)
        for name in ("mp3_bitrate", "aac_bitrate"):
            value = getattr(self, name)
            if not (value[:-1].isdigit() and value.endswith("k") and 8 <= int(value[:-1]) <= 320):
                raise ValueError(f"{name} must look like '64k' (8k to 320k), got {value!r}")
        if not (self.mp3 or self.m4b):
            raise ValueError("choose at least one of MP3 and M4B")

    def seconds(self, pause: Pause) -> float:
        """How long a pause of this kind lasts (the chapter pause is `chapter_pause`)."""
        return {
            Pause.NONE: 0.0,
            Pause.CLAUSE: self.clause_pause,
            Pause.SENTENCE: self.sentence_pause,
            Pause.PAUSE_EDIT: self.pause_edit,
            Pause.PARAGRAPH: self.paragraph_pause,
            Pause.HEADING: self.heading_pause,
        }[pause]


@dataclass(frozen=True)
class Written:
    """The files one run wrote, in the output folder."""

    m4b: Path | None
    mp3s: tuple[Path, ...]
    readalong: Path
    subtitles: tuple[Path, ...] = ()  # per chapter .srt and .vtt, then the book's
