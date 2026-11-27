"""Cut the listening script into utterances: what the voice says in one call (D-98, Q4).

An utterance is about a sentence of one block: its spoken text, and the span of the original
it stands for, so the app can make one `AudioChunk` per utterance and read-along can
highlight the original words (OU-02). The voice only ever gets the text, never a Document.

- Pieces of different blocks never share an utterance; a pause is an utterance of its own.
- White space, line breaks included, is read as one space (`spoken_text`), not an edit.
- A sentence ends after ".", "?" or "!" (closing quotes or brackets may follow) when white
  space and then an upper-case letter, a digit or an opening quote or bracket follow, except
  after an abbreviation of the language ("Fig.", "et al.", "e.g."; "No.", "p." and the like
  only before a number) or a single initial ("J. Smith"), and never inside a replacement. A
  single capital after a maths symbol ("x \u2208 N. This", #141) or a label word ("see
  Appendix C. It") is no initial, so its full stop ends the sentence (D-719).
- English (#477, D-744): an initial, and a dotted capital abbreviation of two or more letters
  ("U.S.", "J.R.R."), end a sentence only before a sentence opener of
  `data/en/sentence_openers.toml` ("set A. Then", "the U.S. The data"), not before a name
  ("J. Smith", "U.S. Census Bureau"). Its limit: "in the U.S. Researchers found" stays one
  utterance (a pause and the pitch move, no text is lost).
- A list marker (a dash or a bullet) that opens a line after ".", "?" or "!" starts the next
  sentence, as an opening quote does: "werden?\n- Welche" is cut before the dash (#652).
- Nothing to say is never an utterance (#652, `unspoken`): a sentence of only dashes,
  bullets, quote marks or brackets leads the sentence after it in its run (a list marker its
  item); with none after it, it leads nothing read with it and is left out, so a block of only
  "-" gives no utterance. A part of a cut sentence with nothing to say is left out too (its
  text stays inside the sentence's span on the page).
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
  waren 3. Die Studie lief."), after a label word ("Abbildung 1.") or between the same word
  twice ("Absatz 2. Absatz 3", "Art. 3. Art. 4", #479, as the numbers step reads it), never
  before a digit ("Am 3. 4. 2019"). Its limit: German capitalises nouns and the list holds
  none, so a sentence that starts with a noun after such a number stays in the same
  utterance ("Es waren 3. Studien zeigen das."): a pause and the pitch move, no text is lost.
- The voice takes only so much text per call (Kokoro: about 510 phoneme tokens). A sentence
  longer than `max_chars` is cut at the best place that fits (#460, D-719): after ";" or ":",
  else after a comma before a word that opens a clause (`data/<language>/clause_openers.toml`:
  "…, but", "…, dass"), else after any comma, else after a dash, else at a space. Within the
  best kind the cut nearest an even share of the rest wins, so parts keep about the same
  length, and no cut leaves a part under `MIN_PIECE` characters while another cut leaves none.
  A space between the words of a reading ("unter | anderem", "3 | Komma 5", "less than | or
  equal to", "newton | metres") ranks after every other space (#482): on a first run the
  reading is one replacement, on a second run plain words, so finding it from the text keeps
  the cut where the first run made it. A place inside an open bracket or quote ranks after
  every place outside one (#481). A single word longer than the limit is cut where it
  must be. Its limit: when every place near the even share lies inside a reading, a first
  run moves its cut out of the replacement and a second run cannot (the script text is the
  same, D-577).
  Every utterance after the first of a cut sentence is marked `continues` (D-157).
- Spans: kept text (a piece whose text is the document's original text of its span) maps
  character by character, so a cut inside it is exact. A replacement is read as a whole
  where it fits; its span belongs to the utterance that holds its first spoken character,
  and an utterance that starts after that, inside it, starts at its end. Spans in a block are in
  order and never overlap; removed text between pieces lies inside the span around it.
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import cache
from itertools import pairwise

from sci2audio.core import Document, ScriptPiece, Span
from sci2audio.textprep.readings import words_of
from sci2audio.textprep.spoken import spoken_text, unspoken
from sci2audio.textprep.wordlists import abbreviations, clause_openers, opens_sentence, units

# Kokoro speaks about 510 phoneme tokens per call. Measured on prose (#480, #494): English 0.97
# tokens per character, German 1.07 to 1.16, so 400 characters are about 464 tokens at the
# worst; a sentence spoken whole keeps the voice's own pause and pitch at its commas. Denser
# text (digits the voice reads out, symbols) can pass 510; the voice then splits it itself at
# punctuation, else at a space, and speaks all of it (slow tests of #494)
DEFAULT_MAX_CHARS = 400

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
    # the "e." of "e. V." (D-719); "et al." ends no sentence, as in English, unless the
    # citation removed after it ended one ("et al. (2019). Die", #488)
    return frozenset(words | {"o.", "j.", "az.", "fa.", "uabs.", "e.", "al."})


ABBREVIATIONS["de"] = _german_abbreviations()

# quotes and brackets that may follow a full stop; "«" closes a German "»" (#267)
_CLOSING = "\"')]\u201d\u2019\u00ab"
# ... and that may open the next sentence ("„" and "»", #227)
_OPENING = "\"'([{\u201c\u2018\u201e\u00bb"
_SENTENCE_END = re.compile(rf"[.?!]+[{re.escape(_CLOSING)}]*(?=\s+(\S))")
# German closes its quotes with U+201C (of U+201E ... U+201C), U+2018 (of U+201A ... U+2018) and,
# in Swiss «…», with U+00BB: after ".", "!" or "?" these end a sentence there too (#315, D-577,
# German only); in English they open a quote. The single guillemets U+203A and U+2039 quote
# inside »…« and «…»: either may close a quote, and either may open the next sentence
# (#333)
_SINGLE_GUILLEMETS = "\u203a\u2039"
_CLOSING_DE = _CLOSING + "\u201c\u2018\u00bb" + _SINGLE_GUILLEMETS
_OPENING_DE = _OPENING + _SINGLE_GUILLEMETS
_SENTENCE_END_DE = re.compile(rf"[.?!]+[{re.escape(_CLOSING_DE)}]*(?=\s+(\S))")
_INITIAL = re.compile(r"\A[A-Z]\.\Z")
# English: a dotted capital abbreviation of two or more letters ("U.S.", "U.K.", "J.R.R."); like
# a single initial, it ends a sentence only before a sentence opener ("the U.S. The data", but
# "U.S. Census Bureau", "J.R.R. Tolkien"; #477, D-744)
_DOTTED_CAPITALS = re.compile(r"\A(?:[A-Z]\.){2,}\Z")
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
    readings = _readings(language.split("-", 1)[0].lower())
    utterances: list[Utterance] = []
    for run_or_pause in _runs(document, pieces):
        if isinstance(run_or_pause, ScriptPiece):
            utterances.append(Utterance("", run_or_pause.span, pause=True))
            continue
        run = run_or_pause
        for start, end in _leading(run.text, _sentences(run, abbreviations, language)):
            continues = False  # the sentence's first utterance starts it
            for a, b in _fitted(run, start, end, max_chars, openers, pairs, readings):
                if unspoken(run.text[a:b]):
                    continue  # a part with nothing to say (#652): its sentence goes on
                if utterance := _utterance(run, a, b, continues):
                    utterances.append(utterance)
                    continues = True
    return tuple(utterances)


def _leading(text: str, sentences: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The sentences, each with nothing to say joined to the sentence after it, which it
    leads: a list marker its item, an opening quote or bracket its words (#652). One with
    no sentence after it in the run leads nothing that is read with it and is left out."""
    out, lead = [], None
    for start, end in sentences:
        if unspoken(text[start:end]):
            lead = start if lead is None else lead
            continue
        out.append((start if lead is None else lead, end))
        lead = None
    return out


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
    english = language.split("-", 1)[0].lower() == "en"
    closing = _CLOSING_DE if german else _CLOSING
    opening = _OPENING_DE if german else _OPENING
    glued = _GLUED_BEFORE_DE if german else _GLUED_BEFORE
    cuts = [0]
    for match in (_SENTENCE_END_DE if german else _SENTENCE_END).finditer(text):
        following = match.group(1)[0]
        if not (
            following.isupper()
            or following.isdigit()
            or following in opening
            or _list_marker(text, match.end(), match.start(1))
        ):
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
        if (
            _INITIAL.match(whole.lstrip(opening))
            and not _letter_of(text, begin, language)
            # English: an initial before a sentence opener ends its sentence ("set A. Then";
            # "J. Smith" does not, #477, D-744)
            and not (english and opens_sentence(text, match.end(), language))
        ):
            continue
        if (
            english
            and _DOTTED_CAPITALS.match(word)
            and not opens_sentence(text, match.end(), language)
        ):
            continue  # "U.S. Census Bureau"; "the U.S. The data" is cut (#477, D-744)
        if (
            german
            and _SHORT_NUMBER.match(word)
            and run.piece_at(match.start())[2]  # printed, not a step's words ("Fußnote 1.")
            and not _after_label(text, match.start() - len(word) + 1, language)
            and not _label_again(text, match.start() - len(word) + 1, match.end())
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


# what opens a list line: dashes and bullets (#652)
_LIST_MARKERS = frozenset("-\u2010\u2013\u2014\u2022\u00b7\u2023\u2043\u2219\u25aa\u25e6")


def _list_marker(text: str, gap: int, at: int) -> bool:
    """True if text[at] is a list marker that opens a line: a line break in the white space
    `text[gap:at]` before it and white space (or the end) after it ("werden?\n- Welche",
    #652). It opens the next sentence, as an opening quote does."""
    return (
        text[at] in _LIST_MARKERS
        and "\n" in text[gap:at]
        and (at + 1 == len(text) or text[at + 1].isspace())
    )


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


# the word after a full stop, with its own full stop if it has one
_NEXT_WORD = re.compile(r"\s+([^\W\d_]+\.?)")


def _label_again(text: str, start: int, end: int) -> bool:
    """True if the word right before the number at `start` comes again right after its full
    stop (`end`): "Es gilt Absatz 2. Absatz 3", "Art. 3. Art. 4" (#479). The number is that
    word's, no ordinal; the numbers step leaves it as printed for the same reason (D-719), and
    the words are compared exactly, as it compares them."""
    before = _WORD_BEFORE.search(text, max(0, start - 32), start)
    after = _NEXT_WORD.match(text, end)
    return before is not None and after is not None and before[1] == after[1]


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
    readings: re.Pattern[str] | None = None,
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
        cut = start + _cut_point(
            run.text[start:stop], counts, max_chars, left, openers, pairs, readings
        )
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
    after a dash, 4 at white space; None where no cut may fall (inside a word). `_cut_point`
    ranks white space inside a reading 5 (#482)."""
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
# apostrophe, which cannot tell opening from closing (#481)
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
    readings: re.Pattern[str] | None = None,
) -> int:
    """Where to cut a text whose spoken length is over max_chars (an index > 0).

    Every place in the window that fits is ranked (`_rank`); the best rank wins, so a piece
    may be shorter than the limit to end at a clause boundary (#460). Within a rank the cut
    nearest an even share of what is left of the sentence (`left`, spoken characters) wins, so
    parts keep about the same length; a cut that leaves a part under MIN_PIECE characters is
    taken only when every cut does. White space inside a reading (`readings`, `_joined`)
    ranks 5, after every other white space (#482). A place inside an open bracket or quote
    (`pairs`) ranks after every place outside one, so "(for example, | producing …)" is cut
    only when nothing outside fits."""
    # counts never decrease, and the first spoken character always fits (max_chars >= 1)
    last_fit = bisect_right(counts, max_chars) - 1
    inside = _inside(text, last_fit, pairs)
    joined = _joined(text, last_fit, readings)
    places = [
        # 0 to 4 as `_rank`, 5 white space inside a reading (every place in `joined` follows
        # white space, so `_rank` gives it 4), 6 to 11 the same inside a bracket
        (rank + (i in joined) + 6 * inside[i], i)
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


def _joined(text: str, last: int, readings: re.Pattern[str] | None) -> set[int]:
    """The places up to `last` after white space that joins the words of one reading (#482):
    white space with a digit right before or after it ("3 | Komma 5", "Seite | 12"), and white
    space inside a match of `readings` ("unter | anderem", "less than | or equal to") or right
    before the word that ends one ("per | second": `_readings` matches only "per " there)."""
    out: set[int] = set()
    word_end = 0  # where the last word before the white space ends
    for i in range(1, min(last, len(text) - 1) + 1):
        if not text[i - 1].isspace():
            word_end = i
        elif not text[i].isspace() and (
            text[i].isdigit() or (word_end > 0 and text[word_end - 1].isdigit())
        ):
            out.add(i)
    if readings is not None:
        # a reading that starts before `last` may end after it: look one reading further
        for match in readings.finditer(text, 0, min(len(text), last + _LONGEST_READING)):
            out.update(
                k
                for k in range(match.start() + 1, min(match.end(), last, len(text) - 1) + 1)
                if text[k - 1].isspace() and not text[k].isspace()
            )
    return out


# no reading of the lists is longer (the longest, "joules per kilogram per kelvin", has 30)
_LONGEST_READING = 64


@cache
def _readings(language: str) -> re.Pattern[str] | None:
    """The multi-word readings of the steps that a cut must not split, as one pattern (#482):
    the abbreviation list's readings with a space ("unter anderem", "for example"), the unit
    list's ("Grad Celsius", "pound per square inch"), two of its units side by side ("newton
    metres") and its words that join a unit to its neighbours ("Kilometer pro Stunde", "square
    metres", "R squared"), the numbers step's fractions ("17 out of 20", "ein Drittel"), the
    statistics step's operators ("less than or equal to", "kleiner oder gleich") and symbols
    ("confidence interval", "partielles Eta-Quadrat"), a power ("to the power of minus", "hoch
    minus") and a date ("dritten Mai", "3 May"). Built from the lists at first use, so a new
    entry is covered at once. None for a language without lists.

    A joining word matches with the white space on its side only (" per ", "square "), so its
    neighbour is never part of a match: a match never starts at a word that a longer word
    around it would have to give back, which keeps the search linear on any text (#616)."""
    # the number modules import this module (through the footnotes and links steps), so
    # their tables are read here, not at import
    from sci2audio.textprep.numbers import OUT_OF
    from sci2audio.textprep.numbers_de import FRACTIONS_OF_ONE, MONTHS

    listed, entries = units(language), abbreviations(language)
    if listed is None and entries is None:
        return None
    german = language == "de"
    statistics = words_of("statistics", "de" if german else "en")
    phrases = {
        reading.strip()
        for entry in entries or ()
        for reading in (entry.reads, entry.before_year, entry.after_paragraph)
    }
    for unit in listed.units if listed else ():
        phrases.update((unit.singular, unit.plural))
    phrases.update(statistics.signs.values(), statistics.arrows.values(), statistics.names)
    phrases.update(FRACTIONS_OF_ONE if german else ())
    phrases.update(["hoch minus"] if german else ["to the power of minus", "to the power of"])
    # each a whole match, bounded by what is not a letter or digit
    whole = [re.escape(phrase) for phrase in phrases if " " in phrase]
    if not german:
        whole.append(rf"(?<=\d\s){re.escape(OUT_OF)}(?=\s+\d)")  # "17 out of 20"
    names = "|".join(
        sorted(
            {
                re.escape(name)
                for unit in (listed.units if listed else ())
                if not unit.per_only
                for name in (unit.singular, unit.plural)
            },
            key=len,
            reverse=True,
        )
    )
    if names:
        whole.append(rf"(?:{names})(?:\s+(?:{names}))+")  # "newton metres", "N m"
    # each the white space on one side of a joining word, with the word
    joins = []
    words = listed.words if listed else {}
    if per := words.get("per"):
        joins.append(rf"(?<=\S)\s+{re.escape(per)}\s+(?=\S)")
    if listed and not listed.joined_powers:
        joins += [
            rf"(?<!\w){re.escape(words[key])}\s+(?=\S)"
            for key in ("square", "cubic")
            if key in words
        ]
    joins += [
        rf"(?<=\S)\s+{re.escape(words[key])}(?!\w)" for key in ("squared", "cubed") if key in words
    ]
    months = MONTHS if german else tuple(calendar.month_name[1:])
    joins.append(rf"(?<=\S)\s+(?-i:{'|'.join(months)})(?!\w)")  # "May", not "may"
    alternatives = sorted(whole, key=len, reverse=True)
    return re.compile(
        rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)|{'|'.join(joins)}", re.IGNORECASE
    )


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
