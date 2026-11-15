"""Subtitles (OU-04, #214): SRT and WebVTT cues of the spoken text, on the read-along's times.

Pure; `write_audiobook` writes the files. Cues come from the same `Timeline` as the
read-along file, so their times are the read-along's own numbers (D-606):

- A cue never spans two chunks. A chunk is a sentence, or a piece of a long sentence cut at
  a clause mark (textprep's utterances), so cues end at sentence ends. Pauses get no cue.
- A cue holds at most `LINES` lines of at most `LINE` characters. A word longer than a line
  (a URL, a DOI) gets a line of its own and is never cut.
- A chunk that fits one cue is one cue, from the chunk's start to its end. A longer chunk is
  cut into the fewest cues that fit: after the last ";" or ":" that fits, else the last ",",
  else the last space; a clause mark counts only when the cue before it is at least half
  full, so no cue is a stub. The chunk's time is shared out by characters: the first cue
  starts at the chunk's start, the last ends at its end, and the cues meet in between
  (estimates: the voice gives no word times).
- Times are whole milliseconds, rounded as the read-along rounds (3 decimals of a second).
  Inside a chapter's file a time is `time - chapter start`, the read-along's rule for MP3s.
- The text is the chunk's spoken text (notices and replacements as spoken), white space
  read as one space.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from sci2audio.output.model import Spoken
from sci2audio.output.timeline import Timeline

LINE = 42  # characters of one line
LINES = 2  # lines of one cue
_CLAUSE_MARKS = ((";", ":"), (",",))  # cut after these first, in this order


@dataclass(frozen=True)
class Cue:
    """One cue: chunk `chunk` of the book shows `lines` from `start` to `end` (ms)."""

    chunk: int
    start: int
    end: int
    lines: tuple[str, ...]


def milliseconds(samples: int, rate: int) -> int:
    """A point on the timeline in whole milliseconds, as the read-along rounds it."""
    return round(round(samples / rate, 3) * 1000)


def wrap(words: Sequence[str]) -> tuple[str, ...] | None:
    """`words` as at most LINES lines of at most LINE characters, the two lines as even as
    can be; None if they don't fit. A single word longer than a line is a line of its own."""
    if not words:
        return None
    whole = " ".join(words)
    if len(whole) <= LINE or len(words) == 1:
        return (whole,)
    best: tuple[str, str] | None = None
    for cut in range(1, len(words)):
        first, second = " ".join(words[:cut]), " ".join(words[cut:])
        fits = all(len(line) <= LINE or " " not in line for line in (first, second))
        if fits and (best is None or max(len(first), len(second)) < max(map(len, best))):
            best = (first, second)
    return best


def split(text: str) -> list[tuple[str, ...]]:
    """The cues' lines for one chunk's text, in order (see the module docstring)."""
    words = text.split()
    pieces: list[tuple[str, ...]] = []
    while words:
        if (lines := wrap(words)) is not None:
            pieces.append(lines)
            break
        count = _longest_fit(words)
        cut = _clause_cut(words, count) or count
        # the first `count` words fit one cue, so every shorter start does: wrap gives lines
        pieces.append(cast("tuple[str, ...]", wrap(words[:cut])))
        words = words[cut:]
    return pieces


def _longest_fit(words: Sequence[str]) -> int:
    """How many words from the start fit one cue (at least one)."""
    count = 1
    while count < len(words) and wrap(words[: count + 1]) is not None:
        count += 1
    return count


def _clause_cut(words: Sequence[str], count: int) -> int | None:
    """The word count after the last clause mark within the first `count` words, preferring
    ";" and ":" to ","; None when there is none in the second half of the cue."""
    half = LINE * LINES // 2
    for marks in _CLAUSE_MARKS:
        for cut in range(count, 0, -1):
            if len(" ".join(words[:cut])) < half:
                break
            if words[cut - 1].endswith(marks):
                return cut
    return None


def cues(timeline: Timeline, spoken: Sequence[Spoken], chapter: int | None = None) -> list[Cue]:
    """The cues of the whole book, or of chapter `chapter` with times from its start."""
    rate = timeline.rate
    if chapter is None:
        first, stop, origin = 0, len(spoken), 0
    else:
        part = timeline.chapters[chapter]
        first, stop, origin = part.first, part.stop, milliseconds(part.start, rate)
    out: list[Cue] = []
    for index in range(first, stop):
        placed = timeline.chunks[index]
        start = milliseconds(placed.start, rate) - origin
        end = milliseconds(placed.end, rate) - origin
        pieces = split(spoken[index].text)
        total = sum(len(" ".join(lines)) for lines in pieces)
        done = 0
        at = start
        for number, lines in enumerate(pieces):
            done += len(" ".join(lines))
            until = end if number == len(pieces) - 1 else start + (end - start) * done // total
            out.append(Cue(index, at, until, lines))
            at = until
    return out


def _time(ms: int, mark: str) -> str:
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, rest = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{mark}{rest:03d}"


def to_srt(items: Sequence[Cue]) -> str:
    """SubRip: cues numbered from 1, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, a blank line between
    cues. SRT has no escapes; an arrow `-->` in the text is shown as `->` so no reader takes
    the line for a time line."""
    blocks = []
    for number, cue in enumerate(items, start=1):
        text = "\n".join(line.replace("-->", "->") for line in cue.lines)
        blocks.append(f"{number}\n{_time(cue.start, ',')} --> {_time(cue.end, ',')}\n{text}\n")
    return "\n".join(blocks)


def to_vtt(items: Sequence[Cue]) -> str:
    """WebVTT: the `WEBVTT` header, `HH:MM:SS.mmm --> HH:MM:SS.mmm`, `&`, `<` and `>`
    escaped (so no `-->` is left in a cue's text)."""
    blocks = ["WEBVTT\n"]
    for cue in items:
        text = "\n".join(_escape(line) for line in cue.lines)
        blocks.append(f"{_time(cue.start, '.')} --> {_time(cue.end, '.')}\n{text}\n")
    return "\n".join(blocks)


def _escape(line: str) -> str:
    return line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
