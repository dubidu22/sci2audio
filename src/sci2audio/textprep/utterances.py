"""Cut the listening script into utterances: what the voice says in one call (D-98, Q4).

An utterance is about a sentence of one block: its spoken text, and the span of the original
it stands for, so the app can make one `AudioChunk` per utterance and read-along can
highlight the original words (OU-02). The voice only ever gets the text, never a Document.

- Pieces of different blocks never share an utterance; a pause is an utterance of its own.
- White space, line breaks included, is read as one space (`spoken_text`), not an edit.
- A sentence ends after ".", "?" or "!" (closing quotes or brackets may follow) when white
  space and then an upper-case letter, a digit or an opening quote or bracket follow, except
  after an abbreviation of the language ("Fig.", "et al.", "e.g."; "No.", "p." and the like
  only before a number) or a single initial ("J. Smith"; so "set A. Then" stays one
  utterance, which the length limit still caps), and never inside a replacement.
- German (#227, D-530): the abbreviations are those of the German lists that end no
  sentence, the units and magnitudes printed with a full stop ("Std.", "Mio.") and the "o."
  of "o. J.". After a number of one to three digits and a full stop (an ordinal no step read,
  "Er wurde 3. Sieger"), a sentence ends only before a sentence opener of
  `data/de/sentence_openers.toml` ("Es waren 3. Die Studie lief."), never before a digit
  ("Am 3. 4. 2019"). Its limit: German capitalises nouns and the list holds none, so a
  sentence that starts with a noun after such a number stays in the same utterance ("Es
  waren 3. Studien zeigen das."): a pause and the pitch move, no text is lost.
- The voice takes only so much text per call (Kokoro: about 510 phoneme tokens). A sentence
  longer than `max_chars` is cut at the last ";" or ":" that fits, else the last comma,
  else a dash, else the last space; a single word longer than that is cut where it must be.
  Every utterance after the first of a cut sentence is marked `continues` (D-157).
- Spans: kept text (a piece whose text is the document's original text of its span) maps
  character by character, so a cut inside it is exact. A replacement is read as a whole
  where it fits; its span belongs to the utterance that holds its first spoken character,
  and an utterance that starts after that, inside it, starts at its end. Spans in a block are in
  order and never overlap; removed text between pieces lies inside the span around it.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise

from sci2audio.core import Document, ScriptPiece, Span
from sci2audio.textprep.spoken import spoken_text
from sci2audio.textprep.wordlists import abbreviations, opens_sentence, units

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


def _german_abbreviations() -> frozenset[str]:
    """German: the abbreviation list's dotted words that end no sentence ("abb.", "z.",
    "b.", "o."), and the units and magnitudes printed with a full stop ("std.", "mio."),
    lower case; built from the lists, so a new entry is covered at once (#227)."""
    words: set[str] = set()
    for entry in abbreviations("de") or ():
        if entry.can_end_sentence:
            continue
        for form in entry.printed:
            words.update(token.lower() for token in form.split() if token.endswith("."))
            if " " not in form:
                words.add(form.lower())
    listed = units("de")
    for unit in listed.units if listed else ():
        words.update(form.lower() for form in unit.printed if form.endswith("."))
    # "o. J." (no year) is left as printed by the abbreviations step, and so is its "o."
    return frozenset(words | {"o.", "j."})


ABBREVIATIONS["de"] = _german_abbreviations()

_CLOSING = "\"')]\u201d\u2019"  # quotes and brackets that may follow a full stop
_OPENING = "\"'([{\u201c\u2018\u201e"  # ... and that may open the next sentence ("„", #227)
_SENTENCE_END = re.compile(rf"[.?!]+[{re.escape(_CLOSING)}]*(?=\s+(\S))")
_INITIAL = re.compile(r"\A[A-Z]\.\Z")
_LAST_WORD = re.compile(r"\S+\Z")
_DASHES = "\u2013\u2014"  # en and em dash
# what an abbreviation may be glued to: brackets, quotes, dashes and a slash ("(2022)[p.",
# "results\u2014e.g.", #91)
_GLUED_BEFORE = re.compile(f"[{re.escape(_OPENING + _CLOSING + '}' + _DASHES + '/')}]")
# abbreviations that stand before a number ("No. 5", "p. 12"); before anything else their
# full stop may end a sentence ("The answer is no. Then ...")
_BEFORE_NUMBERS = frozenset({"no.", "nos.", "p.", "pp.", "vol."})
_CLAUSE_MARKS = (";:", ",", "\u2013\u2014")  # in the order a long sentence is cut at them
# German: a number of one to three digits with a full stop, an ordinal ("3. Sieger") or a
# number no step read; a sentence ends after it only before a sentence opener (#227, D-530)
_SHORT_NUMBER = re.compile(r"\A\d{1,3}\.\Z")


@dataclass(frozen=True)
class Utterance:
    """What the voice says in one call, and the original span it stands for.

    A pause has no text and an empty span at its position. `continues` is true when the
    utterance goes on with a sentence that the length limit cut (Q4): the app gives it no
    pause before it (D-116), while a new sentence gets the sentence pause.
    """

    text: str
    span: Span
    pause: bool = False
    continues: bool = False


@dataclass(frozen=True)
class _Run:
    """The pieces of one block between pauses, as one string with a map to the original."""

    block: int
    text: str
    pieces: tuple[tuple[int, ScriptPiece], ...]  # (offset in text, piece)
    kept: tuple[bool, ...]  # per piece: the original text, not a replacement
    offsets: tuple[int, ...] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "offsets", tuple(offset for offset, _ in self.pieces))

    def piece_at(self, index: int) -> tuple[int, ScriptPiece, bool]:
        """The piece holding the character at `index`, its offset in the text, and whether
        it is kept original text."""
        number = bisect_right(self.offsets, index) - 1
        offset, piece = self.pieces[number]
        return offset, piece, self.kept[number]

    def start_of(self, index: int) -> int:
        """The original offset where the character at `index` begins."""
        offset, piece, kept = self.piece_at(index)
        if kept:
            return piece.span.start + index - offset
        # a replacement's span goes to the utterance that starts it, white space before
        # its first spoken character included
        starts_it = not piece.text[: index - offset].strip()
        return piece.span.start if starts_it else piece.span.end

    def end_of(self, index: int) -> int:
        """The original offset just after the character at `index`."""
        offset, piece, kept = self.piece_at(index)
        if kept:
            return piece.span.start + index - offset + 1
        return piece.span.end

    def inside_replacement(self, index: int) -> tuple[int, int] | None:
        """The replacement's range in the text if `index` lies strictly inside one."""
        offset, piece, kept = self.piece_at(index)
        end = offset + len(piece.text)
        if not kept and offset < index < end:
            return offset, end
        return None


def cut_utterances(
    document: Document,
    pieces: Iterable[ScriptPiece],
    language: str | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[Utterance, ...]:
    """The utterances of the document's listening script, in order (see the module docstring).

    The document tells kept text from replacements (a piece is kept when its text is the
    original text of its span); `language` defaults to the document's.
    """
    if max_chars < 1:
        raise ValueError(f"max_chars must be at least 1, got {max_chars}")
    language = language or document.language
    abbreviations = ABBREVIATIONS.get(language.split("-", 1)[0].lower(), frozenset())
    utterances: list[Utterance] = []
    for run_or_pause in _runs(document, pieces):
        if isinstance(run_or_pause, ScriptPiece):
            utterances.append(Utterance("", run_or_pause.span, pause=True))
            continue
        run = run_or_pause
        for start, end in _sentences(run, abbreviations, language):
            continues = False  # the sentence's first utterance starts it
            for a, b in _fitted(run, start, end, max_chars):
                if utterance := _utterance(run, a, b, continues):
                    utterances.append(utterance)
                    continues = True
    return tuple(utterances)


def _runs(document: Document, pieces: Iterable[ScriptPiece]) -> list[_Run | ScriptPiece]:
    out: list[_Run | ScriptPiece] = []
    current: list[ScriptPiece] = []

    def flush() -> None:
        if current:
            entries, offset = [], 0
            for piece in current:
                entries.append((offset, piece))
                offset += len(piece.text)
            text = "".join(piece.text for piece in current)
            kept = tuple(piece.text == document.text_of(piece.span) for piece in current)
            out.append(_Run(current[0].span.block, text, tuple(entries), kept))
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


def _sentences(
    run: _Run, abbreviations: frozenset[str], language: str = "en"
) -> list[tuple[int, int]]:
    """Ranges of the run's text, one per sentence; white space stays with the sentence
    before. A sentence end inside a replacement is not a cut: the replacement is read whole,
    and the fallback cut still keeps it under the limit."""
    text = run.text
    german = language.split("-", 1)[0].lower() == "de"
    cuts = [0]
    for match in _SENTENCE_END.finditer(text):
        following = match.group(1)[0]
        if not (following.isupper() or following.isdigit() or following in _OPENING):
            continue
        # the word before the gap; any white space (a no-break space too) ends it
        whole = _LAST_WORD.search(text, 0, match.end()).group().rstrip(_CLOSING)
        # the abbreviation check looks past what is glued before it ("(2022)[p.", #91);
        # the initials check does not, or "DON'T." and "[1]A." would read as initials
        word = _GLUED_BEFORE.split(whole)[-1]
        lowered = word.lower()
        if lowered in abbreviations and not (
            lowered in _BEFORE_NUMBERS and not following.isdigit()
        ):
            continue
        if _INITIAL.match(whole.lstrip(_OPENING)):
            continue
        if german and _SHORT_NUMBER.match(word) and not opens_sentence(text, match.end(), language):
            continue  # "Er wurde 3. Sieger", "Am 3. 4. 2019"; "Es waren 3. Die Studie" is cut
        cut = match.start(1)
        inside = run.inside_replacement(cut)
        if inside and text[inside[0] : cut].strip():  # replacement text before the cut
            continue
        cuts.append(cut)
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
        # look only as far as the limit needs, so a long text costs linear time, not
        # quadratic: widen the window until its spoken text is over the limit
        width = 2 * max_chars + 2
        while True:
            stop = min(end, start + width)
            counts = _counts(run.text[start:stop])
            if counts[-1] > max_chars or stop == end:
                break
            width *= 2
        if counts[-1] <= max_chars:
            out.append((start, end))
            return out
        cut = start + _cut_point(run.text[start:stop], counts, max_chars)
        cut = _outside_replacement(run, start, cut, counts, max_chars)
        out.append((start, cut))
        start = cut


def _cut_point(text: str, counts: list[int], max_chars: int) -> int:
    """Where to cut a text whose spoken length is over max_chars (an index > 0)."""
    # counts never decrease, and the first spoken character always fits (max_chars >= 1)
    last_fit = bisect_right(counts, max_chars) - 1
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


def _utterance(run: _Run, start: int, end: int, continues: bool) -> Utterance | None:
    text = spoken_text([ScriptPiece(run.text[start:end], Span(run.block, 0, 0))])
    if not text:
        return None
    first = start + len(run.text[start:end]) - len(run.text[start:end].lstrip())
    last = start + len(run.text[start:end].rstrip()) - 1
    span = Span(run.block, run.start_of(first), run.end_of(last))
    return Utterance(text, span, continues=continues)
