"""Characters a voice would stumble on, read as plain text (IN-04, FX-04, D-153).

PDF text keeps ligatures (ﬁ), mathematical letters (𝑥, 𝐀), soft hyphens, invisible
characters such as the zero-width space, and accents that TeX set apart from their letter
("Garc´ıa"). This step proposes one `replace` or `remove` edit per run of neighbouring
characters of the same kind, each with a reason that names them; the block text never
changes (D-57). White space is left alone: every kind of space is already read as one plain
space by `spoken_text` and the utterance cutter (D-151).

The step runs last among the inline steps (D-150): every other rule that rewrites the same
text wins, and writes plain text itself.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.textprep.steps import ANY_LANGUAGE, Category, Stage, StepContext, TextStep

SOFT_HYPHEN = "\u00ad"

# Format characters that show nothing and say nothing. ZWJ and ZWNJ (U+200D, U+200C) are not
# here: they carry meaning in emoji and in some scripts.
INVISIBLE = frozenset(
    "\u180e"  # Mongolian vowel separator (formerly a space)
    "\u200b"  # zero width space
    "\u200e\u200f"  # left-to-right and right-to-left marks
    "\u202a\u202b\u202c\u202d\u202e"  # bidirectional embeddings and overrides
    "\u2060"  # word joiner
    "\u2061\u2062\u2063\u2064"  # invisible function application, times, separator, plus
    "\u2066\u2067\u2068\u2069"  # bidirectional isolates
    "\ufeff"  # zero width no-break space (byte order mark)
)

# Spacing accents as TeX sets them before a letter, and the combining mark each stands for.
ACCENTS = {
    "\u00b4": "\u0301",  # ´ acute
    "\u00a8": "\u0308",  # ¨ diaeresis
    "\u02da": "\u030a",  # ˚ ring
    "\u02c7": "\u030c",  # ˇ caron
    "\u02dc": "\u0303",  # ˜ tilde
    "\u00af": "\u0304",  # ¯ macron
    "\u02d8": "\u0306",  # ˘ breve
    "\u02d9": "\u0307",  # ˙ dot above
    "\u00b8": "\u0327",  # ¸ cedilla
    "\u02db": "\u0328",  # ˛ ogonek
    "\u02dd": "\u030b",  # ˝ double acute
    "\u02c6": "\u0302",  # ˆ circumflex: only inside a word, a hat on a symbol is maths
}
_CIRCUMFLEX = "\u02c6"
_VOWELS = "aeiou"  # TeX sets a circumflex on these ("J´erˆome"); on others it is a maths hat
_DOTLESS = {"\u0131": "i", "\u0237": "j"}  # TeX puts accents on ı and ȷ
_LETTERLIKE_FIRST, _LETTERLIKE_LAST = "\u2100", "\u214f"  # the Letterlike Symbols block
_INFORMATION_SOURCE = "\u2139"  # ℹ: a letterlike symbol, but not a letter in text
# "it´s", "we´re": an acute used as an apostrophe, not an accent on the letter after it
_CONTRACTION = re.compile(r"(?:s|t|d|m|re|ve|ll)(?![^\W\d_])")

_CANDIDATE = re.compile(
    "[\ufb00-\ufb06\U0001d400-\U0001d7ff\u2100-\u214f"
    + re.escape(SOFT_HYPHEN + "".join(sorted(INVISIBLE)) + "".join(ACCENTS))
    + "]"
)


@dataclass
class _Run:
    """Neighbouring characters of one kind and what is read instead."""

    kind: str
    start: int
    end: int
    replacement: str


class UnicodeStep(TextStep):
    """Ligatures, math letters, soft hyphens, invisible characters and TeX accents."""

    id = "unicode-clean-up"
    languages = (ANY_LANGUAGE,)
    category = Category.CHARACTERS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        edits = []
        for index, block in enumerate(document.blocks):
            for run in _runs(block.text):
                original = block.text[run.start : run.end]
                kind = EditKind.REPLACE if run.replacement else EditKind.REMOVE
                edits.append(
                    Edit(
                        Span(index, run.start, run.end),
                        kind,
                        reason=_reason(run, original),
                        step=self.id,
                        replacement=run.replacement,
                    )
                )
        return edits


def _runs(text: str) -> list[_Run]:
    """The runs to change in a block's text, in order and without overlap."""
    runs: list[_Run] = []
    position = 0
    for match in _CANDIDATE.finditer(text):
        start = match.start()
        if start < position:  # taken by the previous unit (an accent and its letter)
            continue
        unit = _unit(text, start)
        if unit is None:
            continue
        position = unit.end
        last = runs[-1] if runs else None
        # a soft hyphen that took its line break ends a run: what follows is the next line
        if (
            last
            and last.kind == unit.kind
            and last.end == unit.start
            and text[last.end - 1] != "\n"
        ):
            last.end = unit.end
            last.replacement += unit.replacement
        else:
            runs.append(unit)
    return runs


def _unit(text: str, i: int) -> _Run | None:
    """What to do with the character at `i` (and the one after it, for an accent)."""
    char = text[i]
    if char == SOFT_HYPHEN:
        # before a line break it marks where the word was split: join it
        end = i + 2 if text[i + 1 : i + 2] == "\n" else i + 1
        return _Run("soft", i, end, "")
    if char in INVISIBLE:
        return _Run("invisible", i, i + 1, "")
    if char in ACCENTS:
        return _accent(text, i)
    folded = unicodedata.normalize("NFKC", char)
    if "\ufb00" <= char <= "\ufb06":
        return _Run("ligature", i, i + 1, folded)
    if len(folded) != 1 or folded == char:
        return None  # unassigned, or nothing plainer to read
    if "\U0001d400" <= char <= "\U0001d7ff":
        return _Run("math", i, i + 1, folded)
    # letterlike symbols (ℓ ℎ ℝ): only those that are one plain letter
    if char != _INFORMATION_SOURCE and folded.isascii() and folded.isalpha():
        return _Run("math", i, i + 1, folded)
    return None


def _accent(text: str, i: int) -> _Run | None:
    """An accent before its letter becomes the accented letter; a stray one is dropped.

    Invisible characters and soft hyphens between the accent and its neighbours are looked
    through (and taken into the edit), since they are not read either.
    """
    char = text[i]
    j = _skip_forward(text, i + 1)
    k = _skip_back(text, i - 1)
    after = text[j : j + 1]
    before = text[k : k + 1] if k >= 0 else ""
    # the letter as it will be read: a ligature or math letter after the accent is folded too
    folded = _unit(text, j) if after and after not in ACCENTS else None
    letters = folded.replacement if folded and folded.kind in ("ligature", "math") else after
    letter, rest = _DOTLESS.get(letters[:1], letters[:1]), letters[1:]
    if letter.isascii() and letter.isalpha():
        inside_word = before.isalpha()
        if char == _CIRCUMFLEX and not (inside_word and letter.lower() in _VOWELS):
            return None  # "ˆj", "vˆy": a hat in maths (review M1 of #98)
        if char == "\u00b4" and inside_word and _CONTRACTION.match(_read_on(text, j)):
            return None  # "it´s": an apostrophe
        composed = unicodedata.normalize("NFC", letter + ACCENTS[char])
        if len(composed) == 1:
            return _Run("accent", i, j + 1, composed + rest)
        return None
    # stray: no letter or digit on either side, so set apart or next to a sign ("¯±0"); a
    # sign this or another step reads as words gets a space before it, and the accent must
    # read the same either way (#67)
    if all(not c.isalnum() and c not in ACCENTS for c in (before, after)):
        return _Run("stray", i, i + 1, "")
    return None


def _skip_forward(text: str, j: int) -> int:
    """The first position from `j` on that is not an unread character."""
    while j < len(text):
        if text[j] in INVISIBLE:
            j += 1
        elif text[j] == SOFT_HYPHEN:
            j += 2 if text[j + 1 : j + 2] == "\n" else 1
        else:
            break
    return j


def _skip_back(text: str, k: int) -> int:
    """The last position from `k` back that is not an unread character; -1 if none."""
    while k >= 0:
        if text[k] in INVISIBLE or text[k] == SOFT_HYPHEN:
            k -= 1
        elif text[k] == "\n" and text[k - 1 : k] == SOFT_HYPHEN:
            k -= 2
        else:
            break
    return k


def _read_on(text: str, j: int, length: int = 4) -> str:
    """The next few letters from `j` as they will be read, folded.

    Unread characters are left out. An accent joins the letter after it when they compose
    ("ℓˇℓ" reads "lľ", as this step makes it, #160), else it is dropped, so it never ends a
    word.
    """
    read = []
    j = _skip_forward(text, j)
    while j < len(text) and len(read) < length:
        if text[j] in ACCENTS:
            k = _skip_forward(text, j + 1)
            letter = unicodedata.normalize("NFKC", text[k : k + 1])[:1]
            letter = _DOTLESS.get(letter, letter)
            composed = unicodedata.normalize("NFC", letter + ACCENTS[text[j]]) if letter else ""
            if len(composed) == 1 and letter.isascii() and letter.isalpha():
                read.append(composed)
                j = _skip_forward(text, k + 1)
                continue
        else:
            read.append(text[j])
        j = _skip_forward(text, j + 1)
    return unicodedata.normalize("NFKC", "".join(read))[:length]


def _shown(text: str) -> str:
    """Text for a reason: without the characters that are not read."""
    return "".join(c for c in text if c not in INVISIBLE and c not in (SOFT_HYPHEN, "\n"))


def _reason(run: _Run, original: str) -> str:
    if run.kind == "ligature":
        return f'ligature "{original}" read as "{run.replacement}"'
    if run.kind == "math":
        if any(_LETTERLIKE_FIRST <= char <= _LETTERLIKE_LAST for char in original):
            # "K" (Kelvin sign) looks like "K": name the characters (review N3 of #98)
            return f'mathematical characters {_names(original)} read as "{run.replacement}"'
        return f'mathematical characters "{original}" read as "{run.replacement}"'
    if run.kind == "accent":
        shown = _shown(original)
        return f'accent printed apart from its letter: "{shown}" read as "{run.replacement}"'
    if run.kind == "stray":
        return f'accent mark "{original}" without its letter not read'
    if run.kind == "soft":
        if original.endswith("\n"):
            return "soft hyphen at a line end: the word is joined"
        return "soft hyphen not read"
    return f"invisible character not read: {_names(original)}"


def _names(text: str) -> str:
    """Each distinct character of `text` by code point and name, in order."""
    return ", ".join(
        f"U+{ord(char):04X} {unicodedata.name(char, 'format character')}"
        for char in dict.fromkeys(text)
    )
