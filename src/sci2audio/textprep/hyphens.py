"""Words hyphenated at a line end, read as one word (TP-02).

Layout keeps the printed lines, so "develop-" / "ment" arrives as "develop-\\nment". A plain
line break is read as a space by the utterance cutter (D-98); a hyphen at a line end is this
step's decision. One written rule, tested on every line-end hyphen of the corpus papers
(`tests/regression/line-end-hyphens-en.toml`). For a hyphen (- or U+2010) followed by a
line break, with *before* the word ending in the hyphen and *after* the word starting the
next line, the first rule that applies decides:

1. Not letters on both sides ("2019-/2020", "COVID-/19", "J.-/P."): keep the hyphen; if no
   letter or digit follows, or white space comes before, no edit.
2. Suspended hyphen: *after* is a conjunction of the language ("and", "or", "nor"; German
   "und", "oder", "bis", "sowie", ...: "pre-/and post-test", "Wohnungs-/und Sozialarbeit"): no
   edit, the line break is read as a space, as printed.
3. The document's own spelling: the form it prints more often outside line ends, joined
   ("development") or hyphenated ("pre-training"), wins; a tie keeps the hyphen.
4. A compound by its look: *before* is one letter ("x-/axis"), ends in a capital ("PP-"),
   already holds a hyphen ("state-of-the-/art"), or *after* starts with a capital
   ("non-/English"): keep the hyphen.
5. *before* is "self", or *after* is a word that mostly ends a compound (`SECOND_WORDS`):
   keep the hyphen. English only: German writes such compounds closed ("kontextabhängig").
6. Otherwise join.

Joining removes the hyphen and the line break; keeping removes only the line break, so
"state-of-the-art" is read as one word. English (D-152) and German (#96, D-475): the words
of rules 2 and 5 come from the language's row of `WORDS`; the rest is the same rule. Rule 4's
capital test holds for German too: a line-end split never capitalises the rest of a word, so
"Corona-/Pandemie" is a hyphen the author wrote and "Sozial-/arbeit" a split word. No word
list of the language's vocabulary (D-149). Runs last among the inline steps (D-150).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from sci2audio.core import BlockKind, Document, Edit, EditKind, Span
from sci2audio.textprep.characters import ACCENTS
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep

HYPHENS = "-\u2010"  # hyphen-minus and HYPHEN
SUSPENDED = frozenset({"and", "or", "nor"})  # "pre- and post-test"
SELF = "self"
SECOND_WORDS = frozenset(
    {
        "based", "related", "specific", "dependent", "independent", "driven", "oriented",
        "aware", "grained", "level", "free", "scale", "wide", "sized", "term", "order",
    }
)  # fmt: skip


@dataclass(frozen=True)
class HyphenWords:
    """The words of one language that rules 2 and 5 look for, lower case."""

    suspended: frozenset[str]  # rule 2: conjunctions after a suspended hyphen
    self_words: frozenset[str] = frozenset()  # rule 5: a first part that keeps its hyphen
    second_words: frozenset[str] = frozenset()  # rule 5: words that mostly end a compound
    # rule 2: conjunctions printed short, which count only with their full stop ("u.")
    abbreviated: frozenset[str] = frozenset()
    # rule 2: conjunctions that count only before a second word ("als" before "auch"; a bare
    # "als" is often the rest of a split word: "Materi-/als")
    paired: tuple[tuple[str, str], ...] = ()


WORDS: dict[str, HyphenWords] = {
    "en": HyphenWords(SUSPENDED, frozenset({SELF}), SECOND_WORDS),
    # "Kinder-/und Jugendhilfe", "Ein-/oder Ausgang", "Haus-/noch Gartenarbeit" (#96);
    # "Kinder-/u. Jugendhilfe", "Lehr-/vs. Lernprozesse", "sowohl Lehr-/als auch Lernprozesse"
    "de": HyphenWords(
        frozenset(
            {"und", "oder", "bis", "sowie", "bzw", "beziehungsweise", "noch", "respektive"}
            | {"versus"}
        ),
        abbreviated=frozenset({"u", "o", "vs", "resp"}),
        paired=(("als", "auch"),),
    ),
}
# a "-" at a line end in a formula is a minus, in a table often an empty cell, in code part
# of the code (D-545)
SKIPPED_KINDS = frozenset({BlockKind.FORMULA, BlockKind.TABLE, BlockKind.CODE})

# a TeX accent set apart ("Kl\u00a8aui") is part of its word (review S1 of #98)
_ACCENT_CLASS = re.escape("".join(ACCENTS))
_LETTERS = rf"(?:[^\W\d_]|[{_ACCENT_CLASS}])+"
_CHAIN = rf"{_LETTERS}(?:[{HYPHENS}]{_LETTERS})*"  # letters, maybe joined by hyphens
_LINE_END = re.compile(rf"[{HYPHENS}]\n")
_BEFORE = re.compile(rf"{_CHAIN}\Z")
_AFTER = re.compile(_CHAIN)
_WORD = re.compile(rf"(?<![^\W\d_])(?<![{_ACCENT_CLASS}]){_CHAIN}")
_MASKED_LINE_END = re.compile(rf"[{HYPHENS}\u00ad]\n")
_TOKEN_BEFORE = re.compile(r"\S+\Z")
_TOKEN_AFTER = re.compile(r"\S+")
_LOOK_BACK = 200  # longest word looked at before a hyphen


class LineEndHyphenStep(TextStep):
    """Join a word split by a hyphen at a line end, or keep a real hyphen (TP-02)."""

    id = "line-end-hyphens"
    languages = ("en", "de")
    category = Category.CHARACTERS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        words = WORDS[context.language.split("-", 1)[0].lower()]
        spelling: Counter[str] | None = None
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind in SKIPPED_KINDS or not _LINE_END.search(block.text):
                continue
            if spelling is None:
                spelling = printed_words(document)
            for match in _LINE_END.finditer(block.text):
                edit = self._decide(block.text, match.start(), index, spelling, words)
                if edit is not None:
                    edits.append(edit)
        return edits

    def _decide(
        self, text: str, hyphen: int, block: int, spelling: Counter[str], words: HyphenWords
    ) -> Edit | None:
        """The edit for the hyphen at `hyphen` (a line break follows it), if any."""
        line_break = hyphen + 1
        previous = text[hyphen - 1 : hyphen]
        following = text[line_break + 1 : line_break + 2]
        if not (_is_letter(previous) and _is_letter(following)):
            if not previous or previous.isspace() or not following.isalnum():
                return None  # a dash between words, or nothing to join to
            before = _TOKEN_BEFORE.search(text, max(0, hyphen - _LOOK_BACK), hyphen)
            after = _TOKEN_AFTER.match(text, line_break + 1)
            word = (
                f"{before.group() if before else ''}{text[hyphen]}{after.group() if after else ''}"
            )
            return self._keep(block, line_break, word, "next to a digit or mark")
        before_match = _BEFORE.search(text, max(0, hyphen - _LOOK_BACK), hyphen)
        after_match = _AFTER.match(text, line_break + 1)
        if before_match is None or after_match is None:  # unreachable: letters on both sides
            return None
        before, after = before_match.group(), after_match.group()
        # the parts as they are read: accents left out, ligatures as their letters
        first_after = _plain(re.split(f"[{HYPHENS}]", after, maxsplit=1)[0])
        last_before = _plain(re.split(f"[{HYPHENS}]", before)[-1])
        hyphenated = f"{before}{text[hyphen]}{after}"
        # "and" itself split at the next line end ("and-\nab") is not a conjunction
        split_again = text[after_match.end() : after_match.end() + 1] in tuple(HYPHENS)
        one_word = not re.search(f"[{HYPHENS}]", after)
        if _suspended(first_after.lower(), text, after_match.end(), words) and (
            one_word and not split_again
        ):
            return None
        joined_count = spelling[_key(before + after)]
        hyphenated_count = spelling[_key(hyphenated)]
        if joined_count or hyphenated_count:
            if hyphenated_count >= joined_count:
                return self._keep(block, line_break, hyphenated, "the document prints it so")
            return self._join(block, hyphen, before + after, "the document prints it so")
        if (
            len(last_before) == 1
            or last_before[-1:].isupper()
            or re.search(f"[{HYPHENS}]", before)
            or first_after[:1].isupper()
        ):
            return self._keep(block, line_break, hyphenated, "a compound")
        if last_before.lower() in words.self_words or first_after.lower() in words.second_words:
            return self._keep(block, line_break, hyphenated, "a compound")
        return self._join(block, hyphen, before + after, "")

    def _keep(self, block: int, line_break: int, word: str, why: str) -> Edit:
        return Edit(
            Span(block, line_break, line_break + 1),
            EditKind.REMOVE,
            reason=f'hyphen at a line end kept, read as one word: "{word}" ({why})',
            step=self.id,
        )

    def _join(self, block: int, hyphen: int, word: str, why: str) -> Edit:
        because = f" ({why})" if why else ""
        return Edit(
            Span(block, hyphen, hyphen + 2),
            EditKind.REMOVE,
            reason=f'word split at a line end joined: "{word}"{because}',
            step=self.id,
        )


def _suspended(word: str, text: str, end: int, words: HyphenWords) -> bool:
    """True if `word`, which ends at `end`, is a conjunction after a suspended hyphen (rule 2):
    a listed word; a short form with its full stop ("u.", "vs."); or a paired word before its
    partner ("als auch")."""
    if word in words.suspended:
        return True
    if word in words.abbreviated:
        return text[end : end + 1] == "."
    return any(
        word == first and re.match(rf"\s+{second}\b", text[end:], re.IGNORECASE) is not None
        for first, second in words.paired
    )


def printed_words(document: Document) -> Counter[str]:
    """How often each word is printed in the document, outside line-end hyphens.

    Words are letters, maybe joined by hyphens ("pre-training"), compared without case and
    as they are read (`_plain`: a ligature counts as its letters, an accent is left out).
    """
    counts: Counter[str] = Counter()
    for block in document.blocks:
        text = _MASKED_LINE_END.sub("\x00", block.text)  # a split word is no evidence
        counts.update(_key(word) for word in _WORD.findall(text))
    return counts


def _key(word: str) -> str:
    return _plain(word).replace("\u2010", "-").casefold()


def _plain(word: str) -> str:
    """The word as it is read: TeX accents and combining marks left out, ligatures and
    maths letters folded ("Kl\u00a8aui" and "Kl\u00e4ui" are both "Klaui", "\ufb01" is "fi")."""
    unaccented = "".join(char for char in word if char not in ACCENTS)
    folded = unicodedata.normalize("NFKD", unaccented)
    return "".join(char for char in folded if not unicodedata.combining(char))


def _is_letter(char: str) -> bool:
    return char.isalpha() or (bool(char) and char in ACCENTS)
