"""Record what a plain-text file holds as `Content` (D-344), and decode text files (D-345).

A plain-text file becomes one page without positions. Each printed line that is not blank is
a text line; a run of such lines between blank lines is a paragraph. The first line of a
paragraph is tagged ``p``, each following one ``p``, ``br``: the shape an EPUB ``<p>`` with
``<br>`` elements gives, so layout joins them the same way. White space is folded as a browser
shows it (D-306); every other character is kept as stored.

Inside a paragraph, two kinds of line start an element of their own (#466). A line that opens
a list item is tagged ``ul, li`` or ``ol, li``, as Markdown's are, its wrapped lines ``br``
after that, the marker kept in its text. It opens with a bullet ("- ", "* ", "• ") or is one
of a run of two or more numbered lines ("1. ", "1) ") that count up by one, and it stands
where the shape says list: first in the paragraph, after an item, or after a line ending in
a colon. So a spaced dash wrapped to a line's start stays in its sentence, and "1.
Introduction" alone or a German date opening a paragraph ("3. Oktober 1990") stays text.
Markdown would make a lone "1." line an item; plain text differs on purpose, for those
German dates and ordinals. And the line after a title line is tagged ``p``: a short line in
capitals, or a short line without closing punctuation before a line that starts with a
capital (`_title`). A short line in capitals after a line that ends a sentence, with a line
after it, is tagged ``p`` too: a heading typed between two prose lines is cut before as well
as after (#570). Hard-wrapped prose keeps its lines together: none of its lines but the last
is short, measured against its longest line that holds a space.

`decode_text` is shared with the Markdown reader: a byte order mark decides the encoding; a
file without one is read as UTF-8 if it is valid UTF-8, else as Windows-1252 as the WHATWG
Encoding Standard decodes it, which never fails and loses no byte, and the source then says the
encoding was guessed (D-346). Empty, binary and too large files raise `ExtractionError` with a
message a person can act on (D-347); a file of more printed lines than `MAX_LINES` is too large
too, counted before the text is split (D-579), and so is one with a paragraph of more than
`MAX_PARAGRAPH` characters between blank lines (#607).
"""

from __future__ import annotations

import codecs
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sci2audio.core import Content, Page, Source, SourceFormat, TextLine, TextRun
from sci2audio.extraction.errors import ExtractionError
from sci2audio.extraction.markup import fold

MAX_TEXT = 64 * 1024 * 1024  # bytes of a text or Markdown file, as of one EPUB member (D-351)
# printed lines of a text file, blank ones included (#174, D-579): each costs about 425 bytes
# read and as much again in layout, so this bounds a file to about 210 MB, three times the
# hard-wrapped lines of the longest books (Shakespeare's works: about 170,000)
MAX_LINES = 500_000
# characters of one paragraph, its line ends included (#607, D-777, as `markup.MAX_LINE` and
# `markdown.MAX_BLOCK`): bytes and lines alone let one paragraph of 64 MB through, which took
# 1 GB to read and went on to layout and the text steps whole. At the limit a paragraph of
# one line peaks at 58 MB (tracemalloc), one of short lines at 19 MB.
MAX_PARAGRAPH = 4_000_000

# Byte order marks, longest first: a UTF-32 LE mark starts with the UTF-16 LE one. The names
# are the WHATWG ones where it has them (it has no UTF-32).
_MARKS = (
    (codecs.BOM_UTF32_LE, "utf-32-le", "utf-32le"),
    (codecs.BOM_UTF32_BE, "utf-32-be", "utf-32be"),
    (codecs.BOM_UTF8, "utf-8", "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le", "utf-16le"),
    (codecs.BOM_UTF16_BE, "utf-16-be", "utf-16be"),
)
# Windows-1252 as the WHATWG Encoding Standard decodes it: Python's cp1252 leaves five bytes
# unassigned; WHATWG maps them to the C1 controls of the same number, so no byte is lost.
_WINDOWS_1252 = "".join(
    bytes([byte]).decode("cp1252", errors="ignore") or chr(byte) for byte in range(256)
)
# Files that are not text, by their first bytes; a PDF gets a message of its own.
_PDF = b"%PDF-"
_BINARY = (
    b"PK\x03\x04",  # zip: EPUB, Word, OpenDocument
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",
    b"GIF89a",
    b"\x1f\x8b",  # gzip
)
_LINE_END = re.compile(r"\r\n|\r|\n")
_LINE = re.compile(r"[^\r\n]*(?:\r\n?|\n)?")  # one printed line and its line end
_BLANK = re.compile(r"[ \t\f]*(?:\r\n?|\n)?")  # a line `fold` empties: HTML's white space
# Structure inside a paragraph (#466): list markers, and where a title line ends
_BULLET = re.compile(r"[-*\u2022]\s+\S")
_NUMBERED = re.compile(r"(\d{1,3})([.)])\s+\S")
TITLE_SHARE = 0.6  # a title line is at most this share of its paragraph's longest line
_ENDS = ".!?:;,\u2026-\u2010\u2011\u2013\u2014/"  # a line ending in one of these runs on
_STOPS = (".", "!", "?", "\u2026")  # a line ending in one of these ends a sentence (#570)
# Common English and German abbreviations: a line ending in one does not end a sentence
# (#827). The textprep list cannot be imported here (layer rules); a space inside an entry
# may be left out ("z.B.", "e. g.").
_ABBREVIATIONS = (
    *("e. g.", "i. e.", "etc.", "cf.", "vs.", "viz.", "approx.", "et al.", "ca.", "resp."),
    *("Fig.", "Figs.", "Eq.", "Eqs.", "Ref.", "Refs.", "Sec.", "Ch.", "Vol.", "pp."),
    *("Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "Jr.", "Sr.", "St."),
    *("Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.", "Sep.", "Sept."),
    *("Oct.", "Okt.", "Nov.", "Dec.", "Dez."),
    *("Ala.", "Ariz.", "Ark.", "Calif.", "Colo.", "Conn.", "Del.", "Fla.", "Ga.", "Ill."),
    *("Ind.", "Kan.", "Ky.", "La.", "Md.", "Mass.", "Mich.", "Minn.", "Miss.", "Mo."),
    *("Mont.", "Neb.", "Nev.", "Okla.", "Ore.", "Pa.", "Tenn.", "Tex.", "Va.", "Vt."),
    *("Wash.", "Wis.", "Wyo."),
    *("z. B.", "d. h.", "u. a.", "o. ä.", "u. Ä.", "usw.", "bzw.", "vgl.", "evtl.", "ggf."),
    *("sog.", "inkl.", "bzgl.", "Abb.", "Tab.", "Nr.", "Hrsg.", "Jh.", "Mio.", "Mrd."),
)
_ABBREVIATION = re.compile(
    r"(?<![^\W\d_])(?:"  # not inside a word
    + "|".join(re.escape(a).replace(r"\ ", r"\s*") for a in _ABBREVIATIONS)
    + r")\Z"
)
# A German month after "am 3." makes the number an ordinal in a date ("3. Oktober", #848).
# English writes "3 July" or "July 3", never "3. July": an English month line stays a heading.
_MONTHS = frozenset(
    (
        *("januar", "jänner", "februar", "märz", "maerz", "april", "mai", "juni", "juli"),
        *("august", "september", "oktober", "november", "dezember"),
    )
)
# An English month line runs on inside a sentence as a German one does (#903); only German
# months make "am 3." an ordinal (`_ends_sentence`).
_ENGLISH_MONTHS = frozenset(
    (
        *("january", "february", "march", "april", "may", "june", "july", "august"),
        *("september", "october", "november", "december"),
    )
)
_DATE_MONTHS = _MONTHS | _ENGLISH_MONTHS
# A line ending in one of these words leads into the date on the next line ("... im" /
# "Oktober 2020"); any other word ends a title or author line before its date (#922).
_DATE_LEADS = frozenset(
    (
        *("a", "an", "the", "in", "on", "at", "of", "from", "since", "until", "till", "to"),
        *("by", "for", "during", "before", "after", "between", "through", "throughout"),
        *("around", "about", "as", "and", "or", "early", "late", "mid", "last", "next"),
        *("this", "each", "every", "into", "within", "circa"),
        *("im", "am", "vom", "von", "seit", "bis", "ab", "zum", "zur", "um", "für", "nach"),
        *("vor", "des", "der", "dem", "den", "die", "das", "ein", "eine", "einem", "einen"),
        *("eines", "einer", "und", "oder", "sowie", "anfang", "ende", "mitte", "letzten"),
        *("vergangenen", "kommenden", "nächsten", "diesem", "dieses", "jeden", "per"),
        *("zwischen", "während"),
    )
)
_WORD = re.compile(r"[^\W\d_]+")
# a word and at most a year as the whole of a line: "OKTOBER", "(Oktober 2020" (#893)
_MONTH_LINE = re.compile(r"\W*([^\W\d_]+)(?:\s+\d{1,4})?\W*")
_CLOSERS = "\"'\u201c\u201d\u2019\u00ab\u00bb\u2039\u203a)]}"  # looked through at a line's end
# looked through at a line's start
_OPENERS = "\"'\u201c\u201e\u2018\u201a\u00ab\u00bb\u2039\u203a([{"


@dataclass(frozen=True)
class Decoded:
    """A text file's text and how it was read (see `Source.encoding`)."""

    text: str
    encoding: str  # the WHATWG name, e.g. "utf-8"
    guessed: bool  # no byte order mark and not UTF-8: read as Windows-1252


def decode_text(data: bytes, name: str) -> Decoded:
    """The text of a text or Markdown file (D-345); ExtractionError for an empty, binary or
    too large file (D-347). `name` is the file name the messages start with."""
    if not data:
        raise ExtractionError(f"{name}: the file is empty")
    if len(data) > MAX_TEXT:
        raise ExtractionError(
            f"{name}: the file is too large; sci2audio reads text files up to"
            f" {MAX_TEXT // (1024 * 1024)} MB"
        )
    if data.startswith(_PDF):
        raise ExtractionError(
            f"{name}: this is a PDF, not a text file; open it with the .pdf ending"
        )
    if data.startswith(_BINARY):
        raise ExtractionError(f"{name}: not a text file")
    decoded = _decode(data)
    if "\x00" in decoded.text:
        raise ExtractionError(f"{name}: not a text file")
    return decoded


def _decode(data: bytes) -> Decoded:
    for mark, codec, label in _MARKS:
        if data.startswith(mark):
            text = data[len(mark) :].decode(codec, errors="replace")
            return Decoded(text, label, guessed=False)
    try:
        return Decoded(data.decode("utf-8"), "utf-8", guessed=False)
    except UnicodeDecodeError:
        text, _ = codecs.charmap_decode(data, "strict", _WINDOWS_1252)
        return Decoded(text, "windows-1252", guessed=True)


def line_count(text: str) -> int:
    """The printed lines of `text`, blank ones included, counted without splitting it: each
    line end (CR LF, CR or LF) ends a line, and text after the last line end is one more."""
    ends = text.count("\n") + text.count("\r") - text.count("\r\n")
    return ends + (1 if text and not text.endswith(("\n", "\r")) else 0)


def check_lines(text: str, name: str, limit: int, kind: str) -> None:
    """ExtractionError if `text` holds more than `limit` printed lines; `kind` names the
    files in the message ("text", "Markdown")."""
    if line_count(text) > limit:
        raise ExtractionError(
            f"{name}: the file is too large; sci2audio reads {kind} files of up to {limit:,} lines"
        )


def longest_paragraph(text: str) -> int:
    """The characters of the longest stretch of `text` between two blank lines, line ends
    included. A blank line holds only the white space `fold` removes, so a no-break space
    is text. A linear scan that copies no line."""
    longest = paragraph = 0
    for line in _LINE.finditer(text):
        start, end = line.span()
        if start == end:  # the empty match at the end of the text
            break
        if _BLANK.fullmatch(text, start, end):
            paragraph = 0
        else:
            paragraph += end - start
            longest = max(longest, paragraph)
    return longest


def source_of(data: bytes, name: str, kind: SourceFormat, decoded: Decoded) -> Source:
    """The `Source` of a text or Markdown file read as `decoded`."""
    return Source(
        name,
        kind,
        sha256=hashlib.sha256(data).hexdigest(),
        encoding=decoded.encoding,
        encoding_guessed=decoded.guessed,
    )


def extract_text(path: Path) -> Content:
    """Read the plain-text file at `path` into `Content`; ExtractionError if it can't be read."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise ExtractionError(f"{path.name}: cannot be opened ({error.strerror})") from error
    return read_text(data, path.name)


def read_text(data: bytes, name: str) -> Content:
    """Read plain-text bytes into `Content`; `name` is the bare file name the source keeps."""
    decoded = decode_text(data, name)
    check_lines(decoded.text, name, MAX_LINES, "text")
    if longest_paragraph(decoded.text) > MAX_PARAGRAPH:
        raise ExtractionError(
            f"{name}: the file holds a paragraph longer than {MAX_PARAGRAPH:,} characters"
            " (counted between blank lines)"
        )
    paragraphs: list[list[str]] = [[]]
    for printed in _LINE_END.split(decoded.text):
        if text := fold(printed):
            paragraphs[-1].append(text)
        elif paragraphs[-1]:
            paragraphs.append([])
    lines: list[TextLine] = []
    for paragraph, tags in zip(paragraphs, document_tags(paragraphs), strict=True):
        for text, line_tags in zip(paragraph, tags, strict=True):
            lines.append(TextLine(f"p1-l{len(lines) + 1}", (TextRun(text, tags=line_tags),)))
    if not lines:
        raise ExtractionError(f"{name}: the file holds no text")
    page = Page(1, lines=tuple(lines), order=tuple(line.id for line in lines))
    return Content(source=source_of(data, name, SourceFormat.TEXT, decoded), pages=(page,))


def document_tags(paragraphs: list[list[str]]) -> list[list[tuple[str, ...]]]:
    """The tags of each line of each plain-text paragraph (`_paragraph_tags`), and a cut before
    each mixed-case heading between two prose lines (`_mixed_heading`, #812) when the document
    holds at least two of them: one stray short line is a wrapped line, not a heading."""
    tagged = [_paragraph_tags(paragraph) for paragraph in paragraphs]
    if sum(len(found) for _, found in tagged) >= 2:
        for tags, found in tagged:
            for k in found:
                tags[k] = ("p",)
    return [tags for tags, _ in tagged]


def _paragraph_tags(paragraph: list[str]) -> tuple[list[tuple[str, ...]], list[int]]:
    """The tags of each line of a plain-text paragraph (#466): ``p`` for its first line and
    for a line after a title line (`_title`) and for a heading between two prose lines
    (`_heading`, after prose only: a list keeps its items), ``ul, li`` or ``ol, li`` for a
    line that opens a list item, and the tags of the line before plus ``br`` for any other
    line.

    A line with a list marker (`_items`) opens an item only where the shape says list: as
    the paragraph's first line, right after a line that opens or continues an item, or after
    a line ending in a colon. A spaced dash that a hard wrap put at a line's start ("Texte
    - meist unterwegs - und") stays inside its sentence (#561).

    Lines are short against the paragraph's longest line that holds a space: a lone long
    token (a URL, a DOI) on a line of its own does not make the filled lines short (M2).

    Also returns the lines in prose that have the shape of a mixed-case heading
    (`_mixed_heading`); `document_tags` decides whether they are cut before."""
    items = _items(paragraph)
    widths = [len(text) for text in paragraph if " " in text]
    longest = max(widths) if widths else max(map(len, paragraph), default=0)
    out: list[tuple[str, ...]] = []
    found: list[int] = []
    element: tuple[str, ...] = ("p",)  # the element the next wrapped line continues
    for k, text in enumerate(paragraph):
        anchored = k == 0 or element[0] != "p" or paragraph[k - 1].rstrip().endswith(":")
        if k in items and anchored:
            element = items[k]
            out.append(element)
        elif (
            k
            and not _title(
                paragraph[k - 1],
                text,
                longest,
                paragraph[k - 2] if k > 1 else None,
                paragraph[k + 1] if k + 1 < len(paragraph) else None,
            )
            and not (element[0] == "p" and _heading(paragraph, k, longest))
        ):
            out.append((*element, "br"))
            if element[0] == "p" and _mixed_heading(paragraph, k, longest):
                found.append(k)
        else:
            element = ("p",)
            out.append(element)
    return out, found


def _items(paragraph: list[str]) -> dict[int, tuple[str, ...]]:
    """The lines of the paragraph that may open a list item, by index, with their tags. Any
    line opening with a bullet ("- ", "* ", "• ") may; a numbered line ("1. ", "1) ") may in a
    run of two or more numbered lines of one style whose numbers go up by one, so a lone
    "1. Introduction" or a German date ("3. Oktober 1990 ...") stays text."""
    found: dict[int, tuple[str, ...]] = {}
    run: list[tuple[int, int, str]] = []  # (index, number, "." or ")")
    for k, text in enumerate(paragraph):
        if _BULLET.match(text):
            found[k] = ("ul", "li")
        elif numbered := _NUMBERED.match(text):
            number, style = int(numbered[1]), numbered[2]
            if not (run and number == run[-1][1] + 1 and style == run[-1][2]):
                found.update(_run(run))
                run = []
            run.append((k, number, style))
    found.update(_run(run))
    return found


def _run(run: list[tuple[int, int, str]]) -> dict[int, tuple[str, ...]]:
    return {k: ("ol", "li") for k, _, _ in run} if len(run) >= 2 else {}


def _title(line: str, after: str, longest: int, before: str | None, beyond: str | None) -> bool:
    """True if `line` is a title line, so `after` starts a paragraph of its own: it holds at
    least two letters, is no longer than `TITLE_SHARE` of the paragraph's longest line, and
    has no lower-case letter ("LISTENING TO PAPERS", "ABSTRACT:") or ends without punctuation,
    hyphen or dash before a line starting with a capital ("A pilot note" / "Written for ...").
    A line in capitals inside a running sentence is an acronym wrapped onto a line of its own,
    not a title (#827): it is not the paragraph's first line (`before` is None), the line
    `before` it does not end a sentence, and `after` starts in lower case ("... scans, e.g." /
    "PDF" / "files and ..."). A heading before "mRNA ..." or "this paper ..." still cuts.

    A German month, or a month and a year, inside a running sentence is the date it seems
    (#893): a line in capitals runs on into a line starting with a number ("am 3." /
    "OKTOBER" / "2020 kamen ...") and a mixed-case line into any line ("im" / "Oktober 2020"
    / "Die ..."). A month line in capitals before a capital keeps its cut after it: after a
    number's stop it may be a heading the date rule joined to the line before (#900).

    A long line ending in a word that leads into no date (`_DATE_LEADS`) before a month line
    is a title or author line, and its date a line of its own (#922): "A Study of ... on
    Phones" / "April 2020" / "The ..." cuts before and after the date, "... im" / "Oktober
    2020" / "Die ..." runs on. Only a date line without punctuation at its end before
    `beyond`, the line after it, starting with a capital: a date ending in a stop ("...
    dated" / "June 2020." / "The ...") or before a lower-case line ("... den Stand" /
    "Oktober 2020" / "wieder und ...") ends or goes on with the sentence it is in. A line
    ending in punctuation or a number keeps the rules above."""
    first = after.lstrip(_OPENERS)[:1]
    if not _short(line, longest):
        return (
            first.isupper()
            and beyond is not None
            and beyond.lstrip(_OPENERS)[:1].isupper()
            and after.rstrip(_CLOSERS)[-1:] not in _ENDS
            and _month_line(after)
            and _titled(line)
        )
    if _capitals(line):
        if before is None or _ends_sentence(before, line):
            return True
        return not first.islower() and not (first.isdigit() and _month_line(line))
    if line.rstrip(_CLOSERS)[-1:] in _ENDS:
        return False
    if (
        before is not None
        and not _short(before, longest)  # a title line before the date ends no sentence either
        and _month_line(line)
        and not _ends_sentence(before, line)
        and not _titled(before)
    ):
        return False
    return first.isupper()


def _titled(line: str) -> bool:
    """True if `line` ends in a word that is no lead into a date (`_DATE_LEADS`), looking
    through closing quotes and brackets: a title or author line before a date (#922)."""
    # Matched from the end of the reversed line: a search for a word at the line's end would
    # retry at every letter of the last word (quadratic). No lead is near 32 letters long.
    tail = _WORD.match(line.rstrip().rstrip(_CLOSERS)[-32:][::-1])
    return tail is not None and tail[0][::-1].lower() not in _DATE_LEADS


def _month_line(line: str) -> bool:
    """True if `line` is a German or English month alone or before a year, looking through
    brackets and quotes: "OKTOBER", "(Oktober 2020" (#893), "June 2020" (#903)."""
    found = _MONTH_LINE.fullmatch(line)
    return found is not None and found[1].lower() in _DATE_MONTHS


def _heading(paragraph: list[str], k: int, longest: int) -> bool:
    """True if line `k` is a heading set between two prose lines (#570): a short line in
    capitals (`_title`'s first kind, "RESULTS") after a line that ends a sentence, and not
    the paragraph's last line. A short last line in capitals ends the prose it follows (a
    licence in capitals), and one after a line that runs on stays in its sentence."""
    if not 0 < k < len(paragraph) - 1 or not _ends_sentence(paragraph[k - 1], paragraph[k]):
        return False
    return _short(paragraph[k], longest) and _capitals(paragraph[k])


def _mixed_heading(paragraph: list[str], k: int, longest: int) -> bool:
    """True if line `k` has the shape of a mixed-case heading between two prose lines (#812):
    after a line that ends a sentence, not the paragraph's last line, starting with a capital
    and a title line before the next line by `_title`'s second kind (short, no punctuation at
    its end, the next line starting with a capital): "Results" / "The data show ...". The
    next line's first word must also fit after it within the paragraph's longest line: a line
    a hard wrap left short because that word did not fit (a long name, a URL) is no heading."""
    if not 0 < k < len(paragraph) - 1 or not _ends_sentence(paragraph[k - 1], paragraph[k]):
        return False
    line, after = paragraph[k], paragraph[k + 1]
    return (
        line.lstrip(_OPENERS)[:1].isupper()
        and not _capitals(line)
        and len(line) + 1 + len(after.split(" ", 1)[0]) <= longest
        and _title(
            line,
            after,
            longest,
            paragraph[k - 1],
            paragraph[k + 2] if k + 2 < len(paragraph) else None,
        )
    )


def _ends_sentence(line: str, after: str) -> bool:
    """True if `line` ends a sentence: in a stop (`_STOPS`), looking through closing quotes
    and brackets, that is not the full stop of an abbreviation ("e.g.", "Calif.", #827).

    A number before a full stop ("approximately 3.", "am 3.") is judged by `after`, the next
    line (#848): one starting with a German month ("am 3." / "Oktober 2020", "OKTOBER") goes
    on with the sentence, so the stop is no sentence end. A next line starting in lower case
    needs no test here (#900): every caller cuts only before a line in capitals or starting
    with a capital, and a month line is matched in any case. Only the line's end and the
    next line's first word are looked at: this runs on every line."""
    line = line.rstrip(_CLOSERS)
    # every abbreviation and the character before it fit in the line's last 16 characters
    if not line.endswith(_STOPS) or _ABBREVIATION.search(line[-16:]):
        return False
    if line[-1] == "." and line[-2:-1].isdigit():
        word = _WORD.match(after.lstrip(_OPENERS))
        return not (word and word[0].lower() in _MONTHS)
    return True


def _short(line: str, longest: int) -> bool:
    """True if `line` holds at least two letters and is no longer than `TITLE_SHARE` of the
    paragraph's longest line."""
    return sum(c.isalpha() for c in line) >= 2 and len(line) <= TITLE_SHARE * longest


def _capitals(line: str) -> bool:
    """True if `line` holds a capital and no lower-case letter."""
    return not any(c.islower() for c in line) and any(c.isupper() for c in line)
