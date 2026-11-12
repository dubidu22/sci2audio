"""Where every pause and chunk lies in the book, in samples (pure; no files touched).

The M4B is the whole book on one timeline; a chapter's MP3 is the stretch from its start to
the next chapter's start. Every chapter begins with the chapter pause, so a jump to a
chapter mark lands just before the speech and every chapter file begins the same way.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from sci2audio.output.model import Chapter, OutputSettings, Spoken


@dataclass(frozen=True)
class Placed:
    """One chunk on the book's timeline: its pause starts at `pause_start`, its speech runs
    from `start` up to (not including) `end`, all in samples."""

    chapter: int
    pause_start: int
    start: int
    end: int


@dataclass(frozen=True)
class ChapterRange:
    """Chapter `index` covers samples `start` up to (not including) `end` of the book and
    chunks `first` up to (not including) `stop`."""

    index: int
    title: str
    start: int
    end: int
    first: int
    stop: int


@dataclass(frozen=True)
class Timeline:
    rate: int
    chunks: tuple[Placed, ...]
    chapters: tuple[ChapterRange, ...]

    @property
    def total(self) -> int:
        """The book's length in samples."""
        return self.chapters[-1].end if self.chapters else 0


def check_chapters(chapters: Sequence[Chapter], count: int) -> None:
    """Raise ValueError unless the chapters start at chunk 0, increase and stay in range."""
    if count == 0:
        raise ValueError("there is nothing to write: no audio chunks")
    if not chapters:
        raise ValueError("a book needs at least one chapter")
    firsts = [chapter.first for chapter in chapters]
    if firsts[0] != 0:
        raise ValueError(f"the first chapter must start at chunk 0, not {firsts[0]}")
    if any(b <= a for a, b in pairwise(firsts)):
        raise ValueError(f"chapters must start at increasing chunks, got {firsts}")
    if firsts[-1] >= count:
        raise ValueError(f"chapter starts at chunk {firsts[-1]}, but there are only {count}")


def samples(seconds: float, rate: int) -> int:
    """A length in seconds as a whole number of samples."""
    return round(seconds * rate)


def plan_timeline(
    chapters: Sequence[Chapter],
    spoken: Sequence[Spoken],
    frames: Sequence[int],
    rate: int,
    settings: OutputSettings,
) -> Timeline:
    """Place every chunk; `frames[i]` is the length of chunk `i` in samples."""
    check_chapters(chapters, len(spoken))
    if len(frames) != len(spoken):
        raise ValueError(f"{len(frames)} frame counts for {len(spoken)} chunks")
    if rate <= 0 or any(n < 0 for n in frames):
        raise ValueError("the sample rate must be > 0 and frame counts >= 0")
    starts = {chapter.first for chapter in chapters}
    chapter_pause = samples(settings.chapter_pause, rate)
    placed: list[Placed] = []
    position, chapter = 0, -1
    for index, (piece, length) in enumerate(zip(spoken, frames, strict=True)):
        if index in starts:
            chapter += 1
            pause = chapter_pause
        else:
            pause = samples(settings.seconds(piece.pause), rate)
        start = position + pause
        placed.append(Placed(chapter, position, start, start + length))
        position = start + length
    ranges = []
    bounds = [*(placed[c.first].pause_start for c in chapters), position]
    stops = [*(c.first for c in chapters[1:]), len(spoken)]
    for index, chapter_ in enumerate(chapters):
        ranges.append(
            ChapterRange(
                index,
                chapter_.title,
                bounds[index],
                bounds[index + 1],
                chapter_.first,
                stops[index],
            )
        )
    return Timeline(rate, tuple(placed), tuple(ranges))
