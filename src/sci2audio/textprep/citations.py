# ruff: noqa: RUF001, RUF002  (dashes, quotes and symbols are meant as papers print them)
"""Citations are not read where they are asides, and read briefly where the sentence needs
them (TP-03, TP-04, K2; D-171 to D-173).

Numeric citations are square brackets of whole numbers, lists and ranges ("[12]",
"[2–6, 16, 17]"), never glued to a word ("Tr[ρ]") and never after a maths or statistics
sign or word ("∈ [0, 1]", "CI [1, 3]"). An aside is removed; a citation that is part of the
sentence ("discussed in [26].", "Refs. [53, 58]", "[12] showed") is read as "reference 26",
"references 53 and 58"; a bracket holding only lead words and citations ("(see also [48,
135])") goes whole.

Author-year citations are brackets whose every ";"-part is a citation: optional lead words
("see", "e.g.,"), authors (names joined by ",", "and", "&", each maybe with "et al."), years
("2016a,b", "in press") and locators (", p. 8", ", Chapter 9"). Such a bracket goes; in a
mixed bracket only the citation parts go ("(RNNGs; Dyer et al., 2016)" reads "(RNNGs)");
used as the subject ("(Dasigi et al., 2019) note that") its names stay. A bracket of years
right after a name is a narrative citation ("Smith (2019) shows"): only the bracket goes, so
the names stay (TP-04). A page bracket glued to a citation ("(2022)[p. 8]") goes with it.

Brackets are worked outermost first: a bracket that goes takes everything inside it along,
and inside one that stays, its inner brackets are looked at in turn. "et al." stays as
printed; reading it is #68's. Every reason names the citation as printed (D-175).
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field

from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.textprep.links import SKIPPED_KINDS
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep

_MAX_BRACKET = 4000  # characters; a longer bracket is not a citation and is not parsed


@dataclass(frozen=True)
class CitationWords:
    """The words of one language that the citation rules use, lower case."""

    reference: str  # "reference 12"
    references: str  # "references 3 and 5"
    and_: str  # the last join of a list
    to: str  # a range "2 to 6"
    before: frozenset[str]  # words after which a numeric citation is part of the sentence
    refs: frozenset[str]  # "Ref." and the like, replaced along with the citation
    nouns: frozenset[str]  # words after which a bracketed author-year citation is a noun
    asides: tuple[str, ...]  # phrases after which a citation is an aside after all
    lead: tuple[str, ...]  # words that may stand before citations inside brackets
    maths: frozenset[str]  # words after which square brackets are an interval, not citations
    particles: frozenset[str]  # lower-case parts of names
    months: frozenset[str]  # never the first word of an author


# fmt: off
WORDS: dict[str, CitationWords] = {
    "en": CitationWords(
        reference="reference",
        references="references",
        and_="and",
        to="to",
        before=frozenset((
            "in", "by", "of", "from", "to", "see", "also", "and", "or", "with", "following",
            "than", "like", "unlike", "on", "under", "via", "cf.", "e.g.", "e.g.,", "i.e.",
            "i.e.,", "per", "within", "into", "about", "against",
        )),
        refs=frozenset(["ref.", "refs."]),
        nouns=frozenset((
            "in", "by", "of", "from", "to", "see", "with", "following", "than", "like", "unlike",
            "on", "under", "via", "cf.", "as", "per", "within", "into", "about", "against",
        )),
        asides=("so on", "and so forth"),
        lead=(
            "for a review, see",
            "for a review see",
            "for example,",
            "for example",
            "see also",
            "see, e.g.,",
            "see e.g.,",
            "see e.g.",
            "but see",
            "compare",
            "see",
            "cf.",
            "e.g.,",
            "e.g.",
            "i.e.,",
            "i.e.",
        ),
        maths=frozenset(["ci", "interval", "intervals", "range", "ranges"]),
        particles=frozenset((
            "van", "von", "de", "der", "den", "del", "della", "di", "da", "du", "la", "le", "ten",
            "ter", "dos", "das",
        )),
        months=frozenset((
            "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov",
            "dec", "january", "february", "march", "april", "june", "july", "august", "september",
            "october", "november", "december",
        )),
    ),
}
# fmt: on

_NUMBER = r"[1-9]\d{0,3}(?:[a-z](?![\w-]))?"
_ITEM = rf"{_NUMBER}(?:\s*[-–—]\s*{_NUMBER})?"
_NUMERIC = re.compile(rf"\s*{_ITEM}(?:\s*[,;]\s*{_ITEM})*\s*\Z")
_ITEMS = re.compile(rf"({_NUMBER})(?:\s*[-–—]\s*({_NUMBER}))?")
_MATHS_SIGNS = "=∈∉→←↦<>≤≥×±∼≈⊂⊆∪∩"
_YEAR = r"(?:1[5-9]\d\d|20\d\d)(?:[a-z](?:\s*,\s*[a-z](?![a-z]))*)?(?![\w])"
_YEARS = (
    rf"(?:{_YEAR}|in\s+press|n\.\s?d\.|forthcoming)"
    rf"(?:\s*,\s*(?:{_YEAR}|in\s+press|n\.\s?d\.|forthcoming))*"
)
_LOCATOR = (
    r"(?:\s*,\s*(?:pp?\.\s*\d+(?:\s*[-–—]\s*\d+)?|chapters?\s+\d+|ch(?:ap)?\.\s*\d+|"
    r"sec(?:tions?|s?\.)\s*\d+(?:\.\d+)*|§+\s*\d+(?:\.\d+)*|inter\s+alia))*"
)
_YEARS_ONLY = re.compile(rf"\s*{_YEARS}{_LOCATOR}\s*\Z", re.IGNORECASE)
_PAGE_ONLY = re.compile(r"\s*pp?\.\s*\d+(?:\s*[-–—]\s*\d+)?\s*\Z")
_LETTER = r"(?:[^\W\d_]|[̀-ͯ])"
_WORD = rf"{_LETTER}+(?:(?:[’'-]|-\n){_LETTER}+)*"
_NAME_WORD = rf"(?!(?:and|et)\b){_WORD}"
_GROUP = rf"{_NAME_WORD}(?:[ \t]+{_NAME_WORD}|\s*-\n{_LETTER}+)*(?:\s+et\s+al\.)?"
_AUTHORS = rf"{_GROUP}(?:\s*,\s*(?:(?:and|&)\s+)?{_GROUP}|\s+(?:and|&)\s+{_GROUP})*"
_SPACE = re.compile(r"\s+")
_SENTENCE_START = re.compile(r"(?:\A\s*|[.!?][\"'”’)\]]*\s+)\Z")


def _part_pattern(words: CitationWords) -> re.Pattern[str]:
    leads = "|".join(
        re.escape(lead).replace(r"\ ", r"\s+") for lead in sorted(words.lead, key=len, reverse=True)
    )
    return re.compile(
        rf"\A\s*(?:(?:{leads})\s+)*(?P<authors>{_AUTHORS})"
        rf"(?:\s*\(\s*{_YEARS}{_LOCATOR}\s*\)|\s*,?\s+{_YEARS}{_LOCATOR}|\s*,\s*{_YEARS}{_LOCATOR})"
        rf"(?P<tail>{_LOCATOR})\s*\Z",
        re.IGNORECASE,
    )


def _numeric_aside_pattern(words: CitationWords) -> re.Pattern[str]:
    leads = "|".join(
        re.escape(lead).replace(r"\ ", r"\s+") for lead in sorted(words.lead, key=len, reverse=True)
    )
    bracket = rf"(?:(?:{leads})\s+)*\[{_NUMERIC.pattern[:-2]}\]"
    return re.compile(rf"\s*{bracket}(?:\s*(?:,|;|and)\s*{bracket})*\s*\Z", re.IGNORECASE)


@dataclass
class _Bracket:
    open: int  # index of "(" or "["
    close: int  # index of ")" or "]"
    children: list[_Bracket] = field(default_factory=list)


def brackets(text: str) -> list[_Bracket]:
    """The matched round and square brackets of a text as a tree, outermost first."""
    stack: list[tuple[int, str, list[_Bracket]]] = []
    roots: list[_Bracket] = []
    for position, char in enumerate(text):
        if char in "([":
            stack.append((position, char, []))
        elif char in ")]" and stack and stack[-1][1] == "(["[")]".index(char)]:
            opened, _, children = stack.pop()
            node = _Bracket(opened, position, children)
            (stack[-1][2] if stack else roots).append(node)
        elif char in ")]":
            # an unmatched closing bracket: brackets still open below it stay open
            continue
    while stack:  # unclosed brackets: their matched children count on their own
        _, _, children = stack.pop()
        (stack[-1][2] if stack else roots).extend(children)
    roots.sort(key=lambda node: node.open)
    return roots


class CitationStep(TextStep):
    """Remove citations that are asides; read briefly the ones the sentence needs."""

    id = "citations"
    languages = ("en",)
    category = Category.CITATIONS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        words = WORDS[context.language.split("-", 1)[0].lower()]
        rules = _Rules(words)
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind in SKIPPED_KINDS or not block.text.strip():
                continue
            for start, end, kind, replacement, reason in rules.block(block.text):
                if kind is EditKind.REPLACE:
                    edits.append(Edit(Span(index, start, end), kind, reason, self.id, replacement))
                else:
                    edits.append(Edit(Span(index, start, end), kind, reason, self.id))
        return edits


_Found = tuple[int, int, EditKind, str, str]  # start, end, kind, replacement, reason


class _Rules:
    def __init__(self, words: CitationWords) -> None:
        self.words = words
        self.part = _part_pattern(words)
        self.numeric_aside = _numeric_aside_pattern(words)

    def block(self, text: str) -> list[_Found]:
        found: list[_Found] = []
        for node in brackets(text):
            self._visit(text, node, found)
        found.sort()
        return _settled(text, found)

    def _visit(self, text: str, node: _Bracket, found: list[_Found]) -> None:
        handled = self._decide(text, node)
        if handled is None:
            for child in node.children:
                self._visit(text, child, found)
            return
        found += handled
        for child in node.children:  # inner brackets of kept text are still looked at
            if not any(start <= child.open and child.close < end for start, end, *_ in handled):
                self._visit(text, child, found)

    def _decide(self, text: str, node: _Bracket) -> list[_Found] | None:
        inside = text[node.open + 1 : node.close]
        if len(inside) > _MAX_BRACKET:
            return None
        if text[node.open] == "[":
            return self._numeric(text, node, inside)
        if self.numeric_aside.match(inside):
            return [self._removed(text, node.open, node.close + 1, "citation")]
        if _YEARS_ONLY.match(inside) and (names := self._names_before(text, node.open)):
            end = self._glued_page(text, node.close + 1)
            printed = _printed(f"{names} {text[node.open : end]}")
            reason = f'year of the citation "{printed}" is not read; the names stay (TP-04)'
            start, end = _with_space(text, node.open, end)
            return [(start, end, EditKind.REMOVE, "", reason)]
        parts = self._parts(text, node)
        if parts is None:
            return None
        cited = [self._is_citation(text, part) for part in parts]
        if not any(cited):
            return None
        if all(cited):
            end = self._glued_page(text, node.close + 1)
            if self._is_subject(text, node.open, end):
                return self._subject(text, node, parts, end, "is the subject of the sentence")
            if self._previous_word(text, node.open) in self.words.nouns:
                return self._subject(text, node, parts, end, "is part of the sentence")
            return [self._removed(text, node.open, end, "citation")]
        return self._mixed(text, node, parts, cited)

    # numeric citations

    def _numeric(self, text: str, node: _Bracket, inside: str) -> list[_Found] | None:
        if not _NUMERIC.match(inside):
            if _PAGE_ONLY.match(inside) and re.search(r"[\"”’']\s*\Z", text[: node.open]):
                return [self._removed(text, node.open, node.close + 1, "page reference")]
            return None
        glued = text[node.open - 1 : node.open]
        if glued and (glued.isalnum() or glued in ")]"):
            return None
        before = text[: node.open].rstrip()
        previous = before.split()[-1] if before.split() else ""
        if previous and (
            previous[-1] in _MATHS_SIGNS
            or previous.lower() in self.words.maths
            or previous.endswith("%")
        ):
            return None
        printed = _printed(text[node.open : node.close + 1])
        word = re.sub(r"\A\W*\d*", "", previous).lower()  # "8See" -> "see", "(see" -> "see"
        start = node.open
        if previous.lower() in self.words.refs:
            start = len(before) - len(previous)
            printed = _printed(text[start : node.close + 1])
        elif (
            word not in self.words.before
            or any(before.lower().endswith(aside) for aside in self.words.asides)
        ) and not self._is_subject(text, node.open, node.close + 1):
            return [self._removed(text, node.open, node.close + 1, "numeric citation")]
        spoken = self._spoken(inside)
        if before.endswith("("):  # "( [53] discusses": no space after the bracket
            start = len(before)
        if _SENTENCE_START.search(text[:start]):
            spoken = spoken[0].upper() + spoken[1:]
        reason = f'citation "{printed}" is part of the sentence: read as "{spoken}" (TP-04)'
        return [(start, node.close + 1, EditKind.REPLACE, spoken, reason)]

    def _spoken(self, inside: str) -> str:
        items = []
        single = True
        for match in _ITEMS.finditer(inside):
            first, last = match.group(1), match.group(2)
            if last:
                items.append(f"{first} {self.words.to} {last}")
                single = False
            else:
                items.append(first)
        if len(items) > 1:
            single = False
        noun = self.words.reference if single else self.words.references
        if len(items) == 1:
            return f"{noun} {items[0]}"
        return f"{noun} {', '.join(items[:-1])} {self.words.and_} {items[-1]}"

    # author-year citations

    def _parts(self, text: str, node: _Bracket) -> list[tuple[int, int]] | None:
        """The ";"-parts of a bracket's text as spans; brackets inside are not split."""
        cuts = [node.open + 1]
        depth = 0
        for position in range(node.open + 1, node.close):
            char = text[position]
            if char in "([":
                depth += 1
            elif char in ")]":
                depth -= 1
            elif char == ";" and depth == 0:
                cuts.append(position)
        if not re.search(
            r"\b(?:1[5-9]\d\d|20\d\d)|in\s+press|n\.\s?d\.", text[node.open : node.close]
        ):
            return None
        cuts.append(node.close)
        parts = []
        for number, (start, end) in enumerate(itertools.pairwise(cuts)):
            parts.append((start + (1 if number else 0), end))
        return self._split_after_brackets(text, parts)

    def _split_after_brackets(
        self, text: str, parts: list[tuple[int, int]]
    ) -> list[tuple[int, int]]:
        """Split a part at a comma right after a bracket when every piece is a citation.

        Hardt writes "(Khullar (2020), Zhang et al. (2019); ...)".
        """
        result = []
        for start, end in parts:
            if self._is_citation(text, (start, end)):
                result.append((start, end))
                continue
            pieces = []
            cursor = start
            depth = 0
            for position in range(start, end):
                char = text[position]
                if char in "([":
                    depth += 1
                elif char in ")]":
                    depth -= 1
                elif char == "," and depth == 0 and text[:position].rstrip().endswith(")"):
                    pieces.append((cursor, position))
                    cursor = position + 1
            pieces.append((cursor, end))
            if len(pieces) > 1 and all(self._is_citation(text, piece) for piece in pieces):
                result += pieces
            else:
                result.append((start, end))
        return result

    def _is_citation(self, text: str, part: tuple[int, int]) -> bool:
        piece = text[part[0] : part[1]]
        match = self.part.match(piece)
        if match is None:
            return False
        # an acronym is an author only right before ", 2020" ("(WHO, 2020)", not "BERT (")
        acronym = piece[match.end("authors") :].lstrip().startswith(",")
        return self._names_ok(match.group("authors"), acronym)

    def _names_ok(self, authors: str, acronym: bool) -> bool:
        tokens = [
            token.rstrip(",")
            for token in re.split(r"\s+|(?<=,)", authors.replace("-\n", "-"))
            if token.strip(",")
        ]
        names = [t for t in tokens if t.lower() not in {"and", "&", "et", "al."}]
        if not names or names[0].lower().rstrip(".") in self.words.months:
            return False
        for name in names:
            if name.lower() in self.words.particles:
                continue
            if not _is_name(name) and not (acronym and re.fullmatch(r"[A-Z]{2,6}", name)):
                return False
        return True

    def _part_authors(self, text: str, part: tuple[int, int]) -> tuple[int, int]:
        match = self.part.match(text[part[0] : part[1]])
        if match is None:  # only called on parts the pattern matched
            raise ValueError(f"not a citation part: {text[part[0] : part[1]]!r}")
        return part[0] + match.start("authors"), part[0] + match.end("authors")

    def _names_before(self, text: str, position: int) -> str:
        """The name or "et al." right before a bracket of years, or "" if none."""
        before = text[:position]
        found = re.search(rf"({_LETTER}+-\n)?(\S+)\s*\Z", before)
        if not found:
            return ""
        word = found.group(2)
        if word == "al." and re.search(r"(\S+)\s+et\s+al\.\s*\Z", before):
            author = re.search(r"(\S+)\s+et\s+al\.\s*\Z", before)
            return _printed(f"{author.group(1)} et al.") if author else ""
        joined = (found.group(1) or "").replace("-\n", "-") + word
        bare = re.sub(r"(?:[’']s?)\Z", "", joined)
        if not (_is_name(bare) or re.fullmatch(r"[A-Z]{2,6}", bare)):
            return ""
        # "Sag and Hankamer (1984)": the reason names both authors
        pair = re.search(r"(\S+)\s+(?:and|&)\s+\S+\s*\Z", before)
        if pair and _is_name(pair.group(1)):
            return _printed(pair.group())
        return joined

    def _previous_word(self, text: str, position: int) -> str:
        """The word before a position, lower case, without brackets or a glued footnote mark."""
        words = text[:position].split()
        return re.sub(r"\A\W*\d*", "", words[-1]).lower() if words else ""

    def _glued_page(self, text: str, end: int) -> int:
        """The end of a page bracket glued to a citation ("(2022)[p. 8]"), or `end`."""
        page = re.match(r"[\[(]\s*pp?\.\s*\d+(?:\s*[-–—]\s*\d+)?\s*[\])]", text[end:])
        return end + page.end() if page else end

    def _is_subject(self, text: str, start: int, end: int) -> bool:
        """True if the citation starts a sentence (or a bracket) and a lower-case word follows."""
        before = text[:start]
        starts = bool(_SENTENCE_START.search(before)) or before.rstrip().endswith("(")
        return starts and bool(re.match(r"\s+[a-z]", text[end:]))

    def _subject(
        self, text: str, node: _Bracket, parts: list[tuple[int, int]], end: int, role: str
    ) -> list[_Found]:
        """A citation the sentence needs ("(Dasigi et al., 2019) note", "such as (Qin et al.,
        2022) could"): keep its names, remove the rest (TP-04)."""
        printed = _printed(text[node.open : end])
        reason = f'citation "{printed}" {role}: only its names are read (TP-04)'
        names = [self._part_authors(text, part) for part in parts]
        found: list[_Found] = [(node.open, names[0][0], EditKind.REMOVE, "", reason)]
        for number in range(1, len(names)):
            join = f" {self.words.and_} " if number == len(names) - 1 else ", "
            found.append((names[number - 1][1], names[number][0], EditKind.REPLACE, join, reason))
        found.append((names[-1][1], end, EditKind.REMOVE, "", reason))
        return [item for item in found if item[0] < item[1]]

    def _mixed(
        self, text: str, node: _Bracket, parts: list[tuple[int, int]], cited: list[bool]
    ) -> list[_Found]:
        """In a bracket that also holds other text only the citation parts go."""
        found: list[_Found] = []
        number = 0
        while number < len(parts):
            if not cited[number]:
                number += 1
                continue
            last = number
            while last + 1 < len(parts) and cited[last + 1]:
                last += 1
            if number > 0:  # from the ";" before the run to the run's end
                start = parts[number][0] - 1
                end = parts[last][1]
            else:  # at the opening bracket: up to the next kept part, its ";" included
                start = parts[number][0]
                end = parts[last + 1][0]
                while end < parts[last + 1][1] and text[end].isspace():
                    end += 1
                while start < end and text[start].isspace():
                    start += 1
            printed = _printed(text[parts[number][0] : parts[last][1]])
            reason = f'citation "{printed}" is not read; the rest of the brackets stays (TP-03)'
            found.append((start, end, EditKind.REMOVE, "", reason))
            number = last + 1
        return found

    def _removed(self, text: str, start: int, end: int, what: str) -> _Found:
        printed = _printed(text[start:end])
        reason = f'{what} "{printed}" is not read (TP-03)'
        start, end = _with_space(text, start, end)
        return (start, end, EditKind.REMOVE, "", reason)


def _is_name(word: str) -> bool:
    """A word that can be (part of) an author's name: capital first, then lower case.

    Every capital letter must be followed by a lower-case letter ("McKinney", "DeepMind"),
    so "CoNLL" and "BERT" are not names; after a hyphen a lower-case part is allowed
    ("Spe-nader", "Pastor-Serrano").
    """
    if not word or not word[0].isupper():
        return False
    for number, segment in enumerate(re.split(r"[-’']", word)):
        if not segment:
            return False
        letters = [char for char in segment if not "̀" <= char <= "ͯ"]
        if not all(char.isalpha() for char in letters):
            return False
        if number == 0 and not letters[0].isupper():
            return False
        for position, char in enumerate(letters):
            if char.isupper() and not (
                position + 1 < len(letters) and letters[position + 1].islower()
            ):
                return False
    return True


def _with_space(text: str, start: int, end: int) -> tuple[int, int]:
    """Take the white space before the removal along, or after it at the start of a block."""
    space_start = start
    while space_start > 0 and text[space_start - 1].isspace():
        space_start -= 1
    if space_start > 0:
        return space_start, end
    while end < len(text) and text[end].isspace():
        end += 1
    return 0, end


def _settled(text: str, found: list[_Found]) -> list[_Found]:
    """Drop edits that overlap an earlier one (white space taken along twice)."""
    result: list[_Found] = []
    for item in sorted(found, key=lambda item: (item[0], item[1])):
        if result and item[0] < result[-1][1]:
            start = result[-1][1]
            if start >= item[1] or text[item[0] : start].strip():
                continue
            item = (start, *item[1:])
        result.append(item)
    return result


def _printed(text: str) -> str:
    return _SPACE.sub(" ", text).strip()
