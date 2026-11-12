"""Cut the listening script into utterances: what the voice says in one call (D-98, Q4).

An utterance is about a sentence of one block: its spoken text, and the span of the original
it stands for, so the app can make one `AudioChunk` per utterance and read-along can
highlight the original words (OU-02). The voice only ever gets the text, never a Document.

- Pieces of different blocks never share an utterance; a pause is an utterance of its own.
- White space, line breaks included, is read as one space (`spoken_text`), not an edit.
- A sentence ends after ".", "?" or "!" (closing quotes or brackets may follow) when white
  space and then an upper-case letter, a digit or an opening quote or bracket follow, except
  after an abbreviation of the language ("Fig.", "et al.", "e.g.") or a single initial.
- The voice takes only so much text per call (Kokoro: about 510 phoneme tokens). A sentence
  longer than `max_chars` is cut at the last ";" or ":" that fits, else the last comma,
  else a dash, else the last space; a single word longer than that is cut where it must be.
- Spans: kept text maps character by character, so a cut inside it is exact. A replacement
  is read as a whole where possible; its span belongs to the utterance that starts it, and
  an utterance that starts in the middle of one starts at its end. Spans in a block are in
  order and never overlap; removed text between pieces lies inside the span around it.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise

from sci2audio.core import ScriptPiece, Span
from sci2audio.textprep.spoken import spoken_text

DEFAULT_MAX_CHARS = 300  # well under Kokoro's per-call limit; #18 sets the voice's own

# words that end in a full stop without ending a sentence, lower case, by language
ABBREVIATIONS: dict[str, frozenset[str]] = {
    "en": frozenset(
        [
            "al.",
            "approx.",
            "ca.",
            "cf.",
            "ch.",
            "chap.",
            "dr.",
            "e.g.",
            "eq.",
            "eqs.",
            "esp.",
            "fig.",
            "figs.",
            "i.e.",
            "incl.",
            "jr.",
            "mr.",
            "mrs.",
            "ms.",
            "no.",
            "nos.",
            "p.",
            "pp.",
            "prof.",
            "ref.",
            "refs.",
            "resp.",
            "sec.",
            "secs.",
            "sr.",
            "st.",
            "tab.",
            "viz.",
            "vol.",
            "vs.",
        ]
    ),
}

_CLOSING = "\"')]\u201d\u2019"  # quotes and brackets that may follow a full stop
_OPENING = "\"'([{\u201c\u2018"  # ... and that may open the next sentence
_SENTENCE_END = re.compile(rf"[.?!]+[{re.escape(_CLOSING)}]*(?=\s+(\S))")
_INITIAL = re.compile(r"\A[A-Z]\.\Z")
_CLAUSE_MARKS = (";:", ",", "\u2013\u2014")  # in the order a long sentence is cut at them


@dataclass(frozen=True)
class Utterance:
    """What the voice says in one call, and the original span it stands for.

    A pause has no text and an empty span at its position.
    """

    text: str
    span: Span
    pause: bool = False


@dataclass(frozen=True)
class _Run:
    """The pieces of one block between pauses, as one string with a map to the original."""

    block: int
    text: str
    pieces: tuple[tuple[int, ScriptPiece], ...]  # (offset in text, piece)
    offsets: tuple[int, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "offsets", tuple(offset for offset, _ in self.pieces))

    def piece_at(self, index: int) -> tuple[int, ScriptPiece]:
        """The piece holding the character at `index`, with its offset in the text."""
        return self.pieces[bisect_right(self.offsets, index) - 1]

    def is_kept(self, piece: ScriptPiece) -> bool:
        return len(piece.text) == piece.span.end - piece.span.start

    def start_of(self, index: int) -> int:
        """The original offset where the character at `index` begins."""
        offset, piece = self.piece_at(index)
        if self.is_kept(piece):
            return piece.span.start + index - offset
        return piece.span.start if index == offset else piece.span.end

    def end_of(self, index: int) -> int:
        """The original offset just after the character at `index`."""
        offset, piece = self.piece_at(index)
        if self.is_kept(piece):
            return piece.span.start + index - offset + 1
        return piece.span.end

    def inside_replacement(self, index: int) -> tuple[int, int] | None:
        """The replacement's range in the text if `index` lies strictly inside one."""
        offset, piece = self.piece_at(index)
        end = offset + len(piece.text)
        if not self.is_kept(piece) and offset < index < end:
            return offset, end
        return None


def cut_utterances(
    pieces: Iterable[ScriptPiece], language: str = "en", max_chars: int = DEFAULT_MAX_CHARS
) -> tuple[Utterance, ...]:
    """The utterances of a listening script, in order (see the module docstring)."""
    if max_chars < 1:
        raise ValueError(f"max_chars must be at least 1, got {max_chars}")
    abbreviations = ABBREVIATIONS.get(language.split("-", 1)[0].lower(), frozenset())
    utterances: list[Utterance] = []
    for run_or_pause in _runs(pieces):
        if isinstance(run_or_pause, ScriptPiece):
            utterances.append(Utterance("", run_or_pause.span, pause=True))
            continue
        run = run_or_pause
        for start, end in _sentences(run.text, abbreviations):
            for a, b in _fitted(run, start, end, max_chars):
                if utterance := _utterance(run, a, b):
                    utterances.append(utterance)
    return tuple(utterances)


def _runs(pieces: Iterable[ScriptPiece]) -> list[_Run | ScriptPiece]:
    out: list[_Run | ScriptPiece] = []
    current: list[ScriptPiece] = []

    def flush() -> None:
        if current:
            entries, offset = [], 0
            for piece in current:
                entries.append((offset, piece))
                offset += len(piece.text)
            text = "".join(piece.text for piece in current)
            out.append(_Run(current[0].span.block, text, tuple(entries)))
            current.clear()

    for piece in pieces:
        if piece.pause:
            flush()
            out.append(piece)
            continue
        if current and current[0].span.block != piece.span.block:
            flush()
        if piece.text:
            current.append(piece)
    flush()
    return out


def _sentences(text: str, abbreviations: frozenset[str]) -> list[tuple[int, int]]:
    """Ranges of the text, one per sentence; white space stays with the sentence before."""
    cuts = [0]
    for match in _SENTENCE_END.finditer(text):
        following = match.group(1)[0]
        if not (following.isupper() or following.isdigit() or following in _OPENING):
            continue
        word_start = max(text.rfind(c, 0, match.start()) for c in " \t\n\r\f\v") + 1
        word = text[word_start : match.end()].lstrip(_OPENING).rstrip(_CLOSING)
        if word.lower() in abbreviations or _INITIAL.match(word):
            continue
        cuts.append(match.start(1))
    cuts.append(len(text))
    return [(a, b) for a, b in pairwise(cuts) if a < b]


def _counts(text: str) -> list[int]:
    """counts[i]: length of the spoken text of text[:i] (white space runs as one space)."""
    counts, spoken, pending_space = [0], 0, False
    for char in text:
        if char.isspace():
            pending_space = spoken > 0
        else:
            spoken += 1 + pending_space
            pending_space = False
        counts.append(spoken)
    return counts


def _fitted(run: _Run, start: int, end: int, max_chars: int) -> list[tuple[int, int]]:
    """Cut text[start:end] into ranges whose spoken text has at most max_chars."""
    out = []
    while True:
        counts = _counts(run.text[start:end])
        if counts[-1] <= max_chars:
            out.append((start, end))
            return out
        cut = start + _cut_point(run.text[start:end], counts, max_chars)
        cut = _outside_replacement(run, start, cut, counts, max_chars)
        out.append((start, cut))
        start = cut


def _cut_point(text: str, counts: list[int], max_chars: int) -> int:
    """Where to cut a text whose spoken length is over max_chars (an index > 0)."""
    fits = [i for i in range(1, len(text) + 1) if 0 < counts[i] <= max_chars]
    last_fit = fits[-1]  # at least one character always fits, as max_chars >= 1
    for marks in _CLAUSE_MARKS:
        for i in range(last_fit, 0, -1):
            if text[i - 1] in marks and (i == len(text) or text[i].isspace()):
                return i
    for i in range(last_fit, 0, -1):
        if text[i - 1].isspace() and counts[i] > 0:
            return i
    return last_fit


def _outside_replacement(run: _Run, start: int, cut: int, counts: list[int], max_chars: int) -> int:
    """Move a cut out of a replacement, to its start or end, where that still fits."""
    inside = run.inside_replacement(cut)
    if inside is None:
        return cut
    before, after = inside
    if before > start and counts[before - start] > 0:
        return before
    if after - start < len(counts) and counts[after - start] <= max_chars:
        return after
    return cut  # the replacement alone is too long to read in one call


def _utterance(run: _Run, start: int, end: int) -> Utterance | None:
    text = spoken_text([ScriptPiece(run.text[start:end], Span(run.block, 0, 0))])
    if not text:
        return None
    first = start + len(run.text[start:end]) - len(run.text[start:end].lstrip())
    last = start + len(run.text[start:end].rstrip()) - 1
    span = Span(run.block, run.start_of(first), run.end_of(last))
    return Utterance(text, span)
