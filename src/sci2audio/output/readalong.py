"""The read-along file (OU-02, Q9): when each chunk is spoken and which original words it
reads. Owned by output; written down in docs/readalong-format.md.

Format "sci2audio-readalong", version 1. Times are seconds (3 decimals) on the M4B's
timeline; inside a chapter's MP3 a time is `start - chapter.start`. Each chunk points at the
original text it reads with its span: block index and character offsets into the block's
text, so the player (#78) highlights the document's own words. A newer version that changes
the meaning of a field gets a new version number; readers refuse versions they don't know.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sci2audio.core import Span
from sci2audio.output.model import Spoken
from sci2audio.output.timeline import Timeline

FORMAT = "sci2audio-readalong"
VERSION = 1


class ReadAlongError(ValueError):
    """A read-along file this version cannot read."""


@dataclass(frozen=True)
class ChapterTimes:
    title: str
    mp3: str | None  # file name in the output folder, None when no MP3s were written
    start: float
    end: float
    first_chunk: int


@dataclass(frozen=True)
class ChunkTimes:
    chapter: int
    start: float
    end: float
    span: Span


@dataclass(frozen=True)
class ReadAlong:
    sample_rate: int
    duration: float
    m4b: str | None
    chapters: tuple[ChapterTimes, ...]
    chunks: tuple[ChunkTimes, ...]


def build(
    timeline: Timeline, spoken: Sequence[Spoken], m4b: str | None, mp3s: Sequence[str] | None
) -> ReadAlong:
    """The read-along data for a timeline; `mp3s` holds one file name per chapter."""
    rate = timeline.rate
    chapters = tuple(
        ChapterTimes(
            c.title,
            mp3s[c.index] if mp3s is not None else None,
            _seconds(c.start, rate),
            _seconds(c.end, rate),
            c.first,
        )
        for c in timeline.chapters
    )
    chunks = tuple(
        ChunkTimes(p.chapter, _seconds(p.start, rate), _seconds(p.end, rate), s.chunk.span)
        for p, s in zip(timeline.chunks, spoken, strict=True)
    )
    return ReadAlong(rate, _seconds(timeline.total, rate), m4b, chapters, chunks)


def to_json(data: ReadAlong) -> str:
    """The file's text, keys in a fixed order."""
    out: dict[str, Any] = {
        "format": FORMAT,
        "version": VERSION,
        "sample_rate": data.sample_rate,
        "duration": data.duration,
        "m4b": data.m4b,
        "chapters": [
            {
                "title": c.title,
                "mp3": c.mp3,
                "start": c.start,
                "end": c.end,
                "first_chunk": c.first_chunk,
            }
            for c in data.chapters
        ],
        "chunks": [
            {
                "chapter": c.chapter,
                "start": c.start,
                "end": c.end,
                "block": c.span.block,
                "start_char": c.span.start,
                "end_char": c.span.end,
            }
            for c in data.chunks
        ],
    }
    # compact: a long book has tens of thousands of chunks
    return json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"


def from_json(text: str) -> ReadAlong:
    """Read a read-along file's text; raise ReadAlongError if it is not version 1."""
    try:
        data = json.loads(text)
        if data.get("format") != FORMAT:
            raise ReadAlongError(f"not a sci2audio read-along file (format {data.get('format')!r})")
        if data.get("version") != VERSION:
            raise ReadAlongError(
                f"read-along version {data.get('version')!r} is not supported; this sci2audio "
                f"reads version {VERSION}"
            )
        return ReadAlong(
            int(data["sample_rate"]),
            float(data["duration"]),
            data["m4b"],
            tuple(
                ChapterTimes(
                    str(c["title"]),
                    c["mp3"],
                    float(c["start"]),
                    float(c["end"]),
                    int(c["first_chunk"]),
                )
                for c in data["chapters"]
            ),
            tuple(
                ChunkTimes(
                    int(c["chapter"]),
                    float(c["start"]),
                    float(c["end"]),
                    Span(int(c["block"]), int(c["start_char"]), int(c["end_char"])),
                )
                for c in data["chunks"]
            ),
        )
    except ReadAlongError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise ReadAlongError(f"broken read-along file: {error}") from None


def read_readalong(path: Path) -> ReadAlong:
    """Read a read-along file from disk (for the player, #78)."""
    return from_json(path.read_text(encoding="utf-8"))


def _seconds(samples: int, rate: int) -> float:
    return round(samples / rate, 3)
