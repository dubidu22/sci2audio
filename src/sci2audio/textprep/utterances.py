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
  utterance, which the length limit still caps), and never inside a replacement. A single
  capital after a maths symbol ("x \u2208 N. This", #141) or a label word ("see Appendix C.
  It") is no initial, so its full stop ends the sentence (D-719).
- A section number alone ("1.", "2.1.") starts the sentence of its title ("1. Introduction");
  its full stop ends nothing (D-719).
- When a step removed printed text that ended the sentence, the sentence ends there even after
  an abbreviation ("Smith et al. (2019). We": the year is not read, its full stop still counts,
  D-719). On a second run the removed text is gone, so the cut stays only where the rules
  above make it; the script is the same.
- The word before a full stop is found by looking back to the last white space, so a long
  block costs linear time (#268).
- German (#227, D-530): the abbreviations are those of the German lists that end no
  sentence, the units and magnitudes printed with a full stop ("Std.", "Mio."), the "o." of
  "o. J.", and "Az.", "Fa.", "UAbs." and the "e." of "e. V." (#406, D-719). After a number
  of one to three digits and a full stop (an ordinal no step read, "Er wurde 3. Sieger"), a
  sentence ends only before a sentence opener of `data/de/sentence_openers.toml` ("Es
  waren 3. Die Studie lief.") or after a label word ("Abbildung 1."), never before a digit
  ("Am 3. 4. 2019"). Its limit: German capitalises nouns and the list holds none, so a
  sentence that starts with a noun after such a number stays in the same utterance ("Es
  waren 3. Studien zeigen das."): a pause and the pitch move, no text is lost.
- The voice takes only so much text per call (Kokoro: about 510 phoneme tokens). A sentence
  longer than `max_chars` is cut at the best place that fits (#460, D-719): after ";" or ":",
  else after a comma before a word that opens a clause (`data/<language>/clause_openers.toml`:
  "…, but", "…, dass"), else after any comma, else after a dash, else at a space. Within the
  best kind the cut nearest an even share of the rest wins, so parts keep about the same
  length, and no cut leaves a part under `MIN_PIECE` characters while another cut leaves none.
  A place inside an open bracket or quote ranks after every place outside one (#481 review).
  A single word longer than the limit is cut where it must be. On a second run a cut beside a
  multi-word reading ("u. a." read "unter anderem", "3,5 %") can fall one word later, since the
  reading is then plain words; the script text is the same (D-577, #482).
  Every utterance after the first of a cut sentence is marked `continues` (D-157).
- Spans: kept text (a piece whose text is the document's original text of its span) maps
  character by character, so a cut inside it is exact. A replacement is read as a whole
  where it fits; its span belongs to the utterance that holds its first spoken character,
  and an utterance that starts after that, inside it, starts at its end. Spans in a block are in
  order and never overlap; removed text between pieces lies inside the span around it.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from sci2audio.core import Document, ScriptPiece, Span
from sci2audio.textprep.spoken import spoken_text
from sci2audio.textprep.wordlists import abbreviations, clause_openers, opens_sentence, units

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
    # "o. J." (no year) is left as printed by the abbreviations step, and so is its "o."; so
    # are "Az." before a file number (#406), "Fa." before a name, "UAbs." before its number and
    # the "e." of "e. V." (D-719)
    return frozenset(words | {"o.", "j.", "az.", "fa.", "uabs.", "e."})


ABBREVIATIONS["de"] = _german_abbreviations()

# quotes and brackets that may follow a full stop; "«" closes a German "»" (PR #267 review R4)
_CLOSING = "\"')]\u201d\u2019\u00ab"
# ... and that may open the next sentence ("„" and "»", #227)
_OPENING = "\"'([{\u201c\u2018\u201e\u00bb"
_SENTENCE_END = re.compile(rf"[.?!]+[{re.escape(_CLOSING)}]*(?=\s+(\S))")
# German closes its quotes with U+201C (of U+201E ... U+201C), U+2018 (of U+201A ... U+2018) and,
# in Swiss «…», with U+00BB: after ".", "!" or "?" these end a sentence there too (#315, D-577,
# German only); in English they open a quote. The single guillemets U+203A and U+2039 quote
# inside »…« and «…»: either may close a quote, and either may open the next sentence
# (PR #333 review R1-4)
_SINGLE_GUILLEMETS = "\u203a\u2039"
_CLOSING_DE = _CLOSING + "\u201c\u2018\u00bb" + _SINGLE_GUILLEMETS
_OPENING_DE = _OPENING + _SINGLE_GUILLEMETS
_SENTENCE_END_DE = re.compile(rf"[.?!]+[{re.escape(_CLOSING_DE)}]*(?=\s+(\S))")
_INITIAL = re.compile(r"\A[A-Z]\.\Z")
_DASHES = "\u2013\u2014"  # en and em dash
# what an abbreviation may be glued to: brackets, quotes, dashes and a slash ("(2022)[p.",
# "results\u2014e.g.", #91)
_GLUED_BEFORE = re.compile(f"[{re.escape(_OPENING + _CLOSING + '}' + _DASHES + '/')}]")
_GLUED_BEFORE_DE = re.compile(f"[{re.escape(_OPENING_DE + _CLOSING_DE + '}' + _DASHES + '/')}]")
# abbreviations that stand before a number ("No. 5", "p. 12"); before anything else their
# full stop may end a sentence ("The answer is no. Then ...")
_BEFORE_NUMBERS = frozenset({"no.", "nos.", "p.", "pp.", "vol."})
# German: a number of one to three digits with a full stop, an ordinal ("3. Sieger") or a
# number no step read; a sentence ends after it only before a sentence opener (#227, D-530)
_SHORT_NUMBER = re.compile(r"\A\d{1,3}\.\Z")
# a section number alone ("1.", "2.1."): with nothing before it, it starts the sentence of its
# title ("1. Introduction"), and its full stop ends nothing (D-719)
_NUMBER_ONLY = re.compile(r"\A\d{1,3}(?:\.\d{1,3})*\.\Z")
# a full stop and what may close it at the end of a removed stretch: the printed sentence ended
# there ("et al. (2019). We": the year goes with the full stop, D-719)
_ENDED = re.compile(rf"[.?!][{re.escape(_CLOSING_DE)}]*\Z")


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
    # offsets in the text where a piece starts after removed printed text that ended a sentence
    ended: frozenset[int] = frozenset()
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
    openers = clause_openers(language)
    pairs = _PAIRS_DE if language.lower().startswith("de") else _PAIRS_EN
    utterances: list[Utterance] = []
    for run_or_pause in _runs(document, pieces):
        if isinstance(run_or_pause, ScriptPiece):
            utterances.append(Utterance("", run_or_pause.span, pause=True))
            continue
        run = run_or_pause
        for start, end in _sentences(run, abbreviations, language):
            continues = False  # the sentence's first utterance starts it
            for a, b in _fitted(run, start, end, max_chars, openers, pairs):
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
            ended = frozenset(
                offset
                for (_, before), (offset, piece) in pairwise(entries)
                if before.span.end < piece.span.start
                and _ENDED.search(
                    document.text_of(
                        Span(piece.span.block, before.span.end, piece.span.start)
                    ).rstrip()
                )
            )
            out.append(_Run(current[0].span.block, text, tuple(entries), kept, ended))
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


def sentence_end(
    text: str, position: int, removed: Iterable[tuple[int, int]], language: str
) -> int:
    """Where the sentence that holds `position` of a block's printed text ends, by the
    cutter's own sentence rule (#213): the offset where the white space after it starts, or
    the end of the text's last word when the sentence runs to the end of the block.

    `removed` are ranges of `text` read as left out (footnote marks), so "end.¹ Next" ends
    after "end.". A removed range right at the end goes with the sentence, so the end lies
    after a mark printed after the full stop.
    """
    if not 0 <= position <= len(text):
        raise ValueError(f"position {position} is outside the text ({len(text)} characters)")
    gaps = sorted((start, end) for start, end in removed if start < end)
    pieces, cursor = [], 0
    for start, end in [*gaps, (len(text), len(text))]:
        if start > cursor:
            pieces.append(ScriptPiece(text[cursor:start], Span(0, cursor, start)))
        cursor = max(cursor, end)
    entries, offset = [], 0
    for piece in pieces:
        entries.append((offset, piece))
        offset += len(piece.text)
    joined = "".join(piece.text for piece in pieces)
    if not joined.strip():  # nothing printed but marks: after the last of them
        end = len(text.rstrip())
        return _past_removed(max([end, *(b for a, b in gaps if a < end)]), gaps)
    run = _Run(0, joined, tuple(entries), (True,) * len(pieces))
    # the position in the joined text: the kept characters before it
    at = sum(max(0, min(piece.span.end, position) - piece.span.start) for piece in pieces)
    abbreviations = ABBREVIATIONS.get(language.split("-", 1)[0].lower(), frozenset())
    sentences = _sentences(run, abbreviations, language)
    start, end = next(((a, b) for a, b in sentences if a <= at < b), sentences[-1])
    last = start + len(joined[start:end].rstrip())
    if last == start:  # only white space: the sentence ends where it starts
        return _past_removed(run.start_of(start) if start < len(joined) else len(text), gaps)
    return _past_removed(run.end_of(last - 1), gaps)


def _past_removed(position: int, gaps: Sequence[tuple[int, int]]) -> int:
    """`position`, moved past removed ranges that start right there."""
    for start, end in gaps:
        if start == position:
            position = end
    return position


def _sentences(
    run: _Run, abbreviations: frozenset[str], language: str = "en"
) -> list[tuple[int, int]]:
    """Ranges of the run's text, one per sentence; white space stays with the sentence
    before. A sentence end inside a replacement is not a cut: the replacement is read whole,
    and the fallback cut still keeps it under the limit."""
    text = run.text
    german = language.split("-", 1)[0].lower() == "de"
    closing = _CLOSING_DE if german else _CLOSING
    opening = _OPENING_DE if german else _OPENING
    glued = _GLUED_BEFORE_DE if german else _GLUED_BEFORE
    cuts = [0]
    for match in (_SENTENCE_END_DE if german else _SENTENCE_END).finditer(text):
        following = match.group(1)[0]
        if not (following.isupper() or following.isdigit() or following in opening):
            continue
        if match.end() in run.ended:
            # the printed sentence ended in text a step removed after this full stop
            cuts.append(match.start(1))
            continue
        # the word before the gap; any white space (a no-break space too) ends it. It is
        # found by looking back from the full stop, so a long block takes linear time (#268)
        begin = match.end()
        while begin and not text[begin - 1].isspace():
            begin -= 1
        whole = text[begin : match.end()].rstrip(closing)
        if _NUMBER_ONLY.match(text[cuts[-1] : match.end()].strip()):
            continue  # "1. Introduction": the section number starts its title's sentence
        # the abbreviation check looks past what is glued before it ("(2022)[p.", #91);
        # the initials check does not, or "DON'T." and "[1]A." would read as initials
        word = glued.split(whole)[-1]
        lowered = word.lower()
        if (
            lowered in abbreviations
            and not (lowered in _BEFORE_NUMBERS and not following.isdigit())
            # German: a single letter of a spaced form ("i." of "i. S. v.") only on its own,
            # not glued to a range ("lit. a\u2013d. Ob", the end of a sentence)
            and not (german and len(lowered) == 2 and lowered != whole.lower())
        ):
            continue
        if _INITIAL.match(whole.lstrip(opening)) and not _letter_of(text, begin, language):
            continue
        if (
            german
            and _SHORT_NUMBER.match(word)
            and run.piece_at(match.start())[2]  # printed, not a step's words ("Fußnote 1.")
            and not _after_label(text, match.start() - len(word) + 1, language)
            and not opens_sentence(text, match.end(), language)
        ):
            continue  # "Er wurde 3. Sieger", "Am 3. 4. 2019"; "Es waren 3. Die Studie" is cut
        cut = match.start(1)
        inside = run.inside_replacement(cut)
        if inside and text[inside[0] : cut].strip():  # replacement text before the cut
            continue
        cuts.append(cut)
    cuts.append(len(text))
    return [(a, b) for a, b in pairwise(cuts) if a < b]


_WORD_BEFORE = re.compile(r"(\S+)\s+\Z")


def _letter_of(text: str, start: int, language: str) -> bool:
    """True if the single capital at `start` is no initial: the word before it ends in a maths
    symbol ("x \u2208 N. This", "x= N. This", #141), or it is a label word ("See Appendix C.
    It", D-719)."""
    before = _WORD_BEFORE.search(text, max(0, start - 32), start)
    if before is None:
        return False
    symbol = unicodedata.category(before[1][-1]) == "Sm"  # "x \u2208 N.", "x= N." too
    return symbol or _after_label(text, start, language)


def _after_label(text: str, start: int, language: str) -> bool:
    """True if a label word of the unit list stands right before `start` ("Abbildung 1.",
    "Tabelle 3."): the number is the label's, no ordinal, and its full stop may end the
    sentence before any capital ("gibt Abbildung 1. PrivacyScore ist ...")."""
    listed = units(language)
    before = _WORD_BEFORE.search(text, max(0, start - 32), start)
    return listed is not None and before is not None and before[1].lower() in listed.labels


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


def _fitted(
    run: _Run,
    start: int,
    end: int,
    max_chars: int,
    openers: frozenset[str] = frozenset(),
    pairs: tuple[str, str] = ("", ""),
) -> list[tuple[int, int]]:
    """Cut text[start:end] into ranges whose spoken text has at most max_chars."""
    out = []
    left = -1  # spoken length of what is left of the sentence, counted once it must be cut
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
        if left < 0:
            left = _counts(run.text[start:end])[-1]
        cut = start + _cut_point(run.text[start:stop], counts, max_chars, left, openers, pairs)
        cut = _outside_replacement(run, start, cut, counts, max_chars)
        out.append((start, cut))
        left = max(0, left - counts[min(cut - start, len(counts) - 1)] - 1)
        start = cut


# a part of a long sentence this short sounds clipped: no cut leaves one when another cut
# leaves none (#460, D-719)
MIN_PIECE = 40
# white space, maybe an opening quote or bracket, then the next word
_WORD_AFTER = re.compile(r"\s+[\"'(\[\u201c\u2018\u201e\u201a\u00bb]?([^\W\d_]+)")


def _rank(text: str, i: int, openers: frozenset[str]) -> int | None:
    """How good a cut before text[i] is, best first: 0 after ";" or ":", 1 after a comma
    before a word that opens a clause ("…, but", "…, dass"), 2 after any other comma, 3
    after a dash, 4 at white space; None where no cut may fall (inside a word)."""
    mark = text[i - 1]
    if mark.isspace():
        return 4
    if not (i == len(text) or text[i].isspace()):
        return None
    if mark in ";:":
        return 0
    if mark == ",":
        word = _WORD_AFTER.match(text, i)
        return 1 if word is not None and word[1].lower() in openers else 2
    return 3 if mark in _DASHES else None


# what opens and closes a bracket or a quote, by language; never a straight quote or an
# apostrophe, which cannot tell opening from closing (#481 review S1)
_PAIRS_EN = ("([{\u201c\u00ab", ")]}\u201d\u00bb")
_PAIRS_DE = ("([{\u201e\u00bb", ")]}\u201c\u00ab")


def _inside(text: str, last: int, pairs: tuple[str, str]) -> list[bool]:
    """For each place up to `last`, whether it is inside an open bracket or quotation."""
    out, depth = [False], 0
    for char in text[:last]:
        if char in pairs[0]:
            depth += 1
        elif char in pairs[1]:
            depth = max(0, depth - 1)
        out.append(depth > 0)
    return out


def _cut_point(
    text: str,
    counts: list[int],
    max_chars: int,
    left: int | None = None,
    openers: frozenset[str] = frozenset(),
    pairs: tuple[str, str] = ("", ""),
) -> int:
    """Where to cut a text whose spoken length is over max_chars (an index > 0).

    Every place in the window that fits is ranked (`_rank`); the best rank wins, so a piece
    may be shorter than the limit to end at a clause boundary (#460). Within a rank the cut
    nearest an even share of what is left of the sentence (`left`, spoken characters) wins, so
    parts keep about the same length; a cut that leaves a part under MIN_PIECE characters is
    taken only when every cut does. A place inside an open bracket or quote (`pairs`) ranks
    after every place outside one, so "(for example, | producing …)" is cut only when nothing
    outside fits."""
    # counts never decrease, and the first spoken character always fits (max_chars >= 1)
    last_fit = bisect_right(counts, max_chars) - 1
    inside = _inside(text, last_fit, pairs)
    places = [
        (rank + 5 * inside[i], i)
        for i in range(last_fit, 0, -1)
        if counts[i] > 0 and (rank := _rank(text, i, openers)) is not None
    ]
    if not places:
        return last_fit
    left = counts[-1] if left is None else max(left, counts[-1])
    target = left / max(2, -(-left // max_chars))  # an even share over the parts it needs
    fair = [
        (rank, i)
        for rank, i in places
        if counts[i] >= MIN_PIECE and left - counts[i] - 1 >= MIN_PIECE
    ]
    pool = fair or places
    best = min(rank for rank, _ in pool)
    return min((i for rank, i in pool if rank == best), key=lambda i: (abs(counts[i] - target), -i))


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
