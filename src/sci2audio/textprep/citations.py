# ruff: noqa: RUF001, RUF002, RUF003  (dashes, quotes and symbols are meant as papers print them)
"""Citations are not read where they are asides, and read briefly where the sentence needs
them (TP-03, TP-04, K2; D-171 to D-173).

Numeric citations are square brackets of whole numbers, lists and ranges ("[12]",
"[2–6, 16, 17]"), never glued to a word ("Tr[ρ]") and never after a maths or statistics
sign or word ("∈ [0, 1]", "CI [1, 3]", "CI: [1, 3]"), nor joined on to such a bracket
("CIs [1, 3] and [2, 4]", D-450). An aside is removed; a citation that is part of the
sentence ("discussed in [26].", "Refs. [53, 58]", "[12] showed") is read as "reference 26",
"references 53 and 58"; a bracket holding only lead words and citations ("(see also [48,
135])") goes whole.

Author-year citations are brackets whose every ";"-part is a citation: optional lead words
("see", "e.g.,"), authors (names joined by ",", "and", "&", each maybe with "et al."), years
("2016a,b", "in press") and locators (", p. 8", ", Chapter 9"). Such a bracket goes; in a
mixed bracket only the citation parts go ("(RNNGs; Dyer et al., 2016)" reads "(RNNGs)");
used as the subject ("(Dasigi et al., 2019) note that") its names stay. A bracket of years
right after a name is a narrative citation ("Smith (2019) shows"): only the bracket goes, so
the names stay (TP-04); after an article the word names a thing, not an author ("the
Olympics (2016)", D-448), unless "et al." or a second author shows a citation. A bracket of
lead words and a narrative citation goes whole ("(see Smith (2019))"), a full stop inside
it too when the bracket starts a sentence (D-447). A page bracket glued to a citation
("(2022)[p. 8]") goes with it.

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
from sci2audio.textprep.statistics import interval_openings
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.utterances import ABBREVIATIONS
from sci2audio.textprep.wording import Wording, wording_for

_MAX_BRACKET = 4000  # characters; a longer bracket is not a citation and is not parsed


@dataclass(frozen=True)
class CitationWords:
    """The words of one language that the citation rules use, lower case."""

    before: frozenset[str]  # words after which a numeric citation is part of the sentence
    refs: frozenset[str]  # "Ref." and the like, replaced along with the citation
    ref_words: frozenset[str]  # "Reference [12]", replaced along only when capitalised
    nouns: frozenset[str]  # words after which a bracketed author-year citation is a noun
    asides: tuple[str, ...]  # phrases after which a citation is an aside after all
    lead: tuple[str, ...]  # words that may stand before citations inside brackets
    maths: frozenset[str]  # words after which square brackets are an interval, not citations
    numbered: frozenset[str]  # words after which square brackets hold a label's number
    particles: frozenset[str]  # lower-case parts of names
    months: frozenset[str]  # never the first word of an author
    articles: frozenset[str]  # before a name, a year bracket is no citation: "the Olympics (2016)"
    # patterns (regular expressions, matched in any case) for what a citation prints
    joins: str  # between two authors: "and", "&"
    others: str  # after the authors: "et al."
    other_words: frozenset[str]  # the words of `others`, never names: "et", "al."
    undated: str  # in place of a year: "in press", "n.d.", "forthcoming"
    dated: str  # what makes a bracket worth parsing besides a year: "in press", "n.d."
    page: str  # a page: "p. 8", "pp. 8–10"
    locators: str  # after the year: ", p. 8", ", Chapter 9", ", inter alia"
    abbreviations: frozenset[str] = frozenset()  # a full stop after these ends no sentence


# fmt: off
WORDS: dict[str, CitationWords] = {
    "en": CitationWords(
        before=frozenset((
            "in", "by", "of", "from", "to", "see", "also", "and", "or", "with", "following",
            "than", "like", "unlike", "on", "under", "via", "cf.", "e.g.", "e.g.,", "i.e.",
            "i.e.,", "per", "within", "into", "about", "against",
        )),
        refs=frozenset(["ref.", "refs."]),
        ref_words=frozenset(["Reference", "References"]),
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
        maths=frozenset(["ci", "cis", "interval", "intervals", "range", "ranges"]),
        numbered=frozenset((
            "eq.", "eqs.", "equation", "equations", "fig.", "figs.", "figure", "figures",
            "tab.", "table", "tables", "sec.", "section", "sections", "step", "steps", "line",
            "lines", "algorithm", "chapter", "appendix", "theorem", "lemma",
        )),
        particles=frozenset((
            "van", "von", "de", "der", "den", "del", "della", "di", "da", "du", "la", "le", "ten",
            "ter", "dos", "das",
        )),
        months=frozenset((
            "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov",
            "dec", "january", "february", "march", "april", "june", "july", "august", "september",
            "october", "november", "december",
        )),
        articles=frozenset(["the", "a", "an"]),
        joins=r"and|&",
        others=r"et\s+al\.",
        other_words=frozenset(["et", "al."]),
        undated=r"in\s+press|n\.\s?d\.|forthcoming",
        dated=r"in\s+press|n\.\s?d\.",
        page=r"pp?\.\s*\d+(?:\s*[-–—]\s*\d+)?",
        locators=(
            r"pp?\.\s*\d+(?:\s*[-–—]\s*\d+)?|chapters?\s+\d+|ch(?:ap)?\.\s*\d+|"
            r"sec(?:tions?|s?\.)\s*\d+(?:\.\d+)*|§+\s*\d+(?:\.\d+)*|inter\s+alia"
        ),
    ),
    "de": CitationWords(
        before=frozenset((
            "in", "bei", "von", "vom", "aus", "nach", "gemäß", "laut", "siehe", "auch", "und",
            "oder", "mit", "wie", "als", "durch", "auf", "über", "unter", "vgl.", "zu", "zur",
            "zum", "im", "beim", "seit", "gegenüber", "etwa", "bzw.", "sowie",
        )),
        refs=frozenset(["ref.", "refs.", "lit."]),
        ref_words=frozenset(["Quelle", "Quellen", "Referenz", "Referenzen", "Literatur"]),
        nouns=frozenset((
            "in", "bei", "von", "vom", "aus", "nach", "gemäß", "laut", "siehe", "mit", "wie",
            "als", "durch", "auf", "über", "unter", "vgl.", "zu", "zur", "zum", "im", "beim",
            "seit", "gegenüber",
        )),
        asides=("und so weiter", "usw.", "etc."),
        lead=(
            "für einen überblick siehe",
            "für einen überblick vgl.",
            "zum beispiel",
            "siehe auch",
            "siehe z. b.",
            "siehe z.b.",
            "siehe etwa",
            "aber siehe",
            "siehe",
            "vgl. auch",
            "vgl. z. b.",
            "vgl. z.b.",
            "vgl. etwa",
            "vgl. dazu",
            "vgl.",
            "z. b.",
            "z.b.",
            "u. a.",
            "u.a.",
            "etwa",
            "s.",
        ),
        maths=frozenset((
            "ki", "kis", "ci", "cis", "intervall", "intervalle", "konfidenzintervall",
            "konfidenzintervalle", "bereich", "bereiche", "wertebereich", "spanne",
        )),
        numbered=frozenset((
            "gl.", "gleichung", "gleichungen", "abb.", "abbildung", "abbildungen", "tab.",
            "tabelle", "tabellen", "abschn.", "abschnitt", "abschnitte", "kap.", "kapitel",
            "schritt", "schritte", "zeile", "zeilen", "algorithmus", "anhang", "satz", "lemma",
            "fig.", "eq.", "sec.",
        )),
        particles=frozenset((
            "van", "von", "de", "der", "den", "del", "della", "di", "da", "du", "la", "le", "ten",
            "ter", "dos", "das", "zu", "zur", "vom",
        )),
        months=frozenset((
            "jan", "feb", "mär", "märz", "apr", "mai", "jun", "juni", "jul", "juli", "aug", "sep",
            "sept", "okt", "nov", "dez", "januar", "jänner", "februar", "april", "august",
            "september", "oktober", "november", "dezember",
        )),
        articles=frozenset((
            "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer",
            "eines",
        )),
        joins=r"und|u\.|&",
        others=r"et\s+al\.|u\.\s?a\.",
        other_words=frozenset(["et", "al.", "u.", "a.", "u.a."]),
        undated=r"im\s+Druck|in\s+press|o\.\s?J\.|n\.\s?d\.|in\s+Vorbereitung|forthcoming",
        dated=r"im\s+Druck|in\s+press|o\.\s?J\.|n\.\s?d\.",
        page=r"(?:S|pp?)\.\s*\d+(?:\s*[-–—]\s*\d+)?(?:\s*ff?\.)?",
        locators=(
            r"(?:S|pp?)\.\s*\d+(?:\s*[-–—]\s*\d+)?(?:\s*ff?\.)?|Kap(?:itel|\.)\s*\d+|"
            r"Abschn(?:itt|\.)\s*\d+(?:\.\d+)*|§+\s*\d+(?:\.\d+)*|Rn\.\s*\d+(?:\s*[-–—]\s*\d+)?"
        ),
        abbreviations=frozenset((
            "a.", "abb.", "abschn.", "al.", "aufl.", "b.", "bd.", "bspw.", "bzw.", "ca.", "d.",
            "d.h.", "dr.", "etc.", "evtl.", "f.", "ff.", "ggf.", "gl.", "h.", "hrsg.", "inkl.",
            "insb.", "j.", "jh.", "kap.", "nr.", "o.", "o.j.", "prof.", "s.", "sog.", "tab.",
            "u.", "u.a.", "usw.", "vgl.", "vs.", "z.", "z.b.",
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
_LETTER = r"(?:[^\W\d_]|[̀-ͯ])"
_WORD = rf"{_LETTER}+(?:(?:[’'-]|-\n){_LETTER}+)*"
_SPACE = re.compile(r"\s+")
_LOWER_NEXT = re.compile(r"\s+[a-z]")
_AFTER_START = re.compile(r"[.!?,;:]+(?:\s+|\Z)")
_LOOK_BACK = 300  # characters looked at before a bracket, so a long block costs linear time
_FULL_STOP_INSIDE = re.compile(r"[\d)]\s*\.\s*\Z")  # "(See Smith (2019).)", not "n.d."


def _years(words: CitationWords) -> str:
    """Years or their stand-ins, joined by commas: "2016a,b", "2019, in press"."""
    one = rf"(?:{_YEAR}|{words.undated})"
    return rf"{one}(?:\s*,\s*{one})*"


def _locator(words: CitationWords) -> str:
    return rf"(?:\s*,\s*(?:{words.locators}))*"


def _authors(words: CitationWords) -> str:
    """Names joined by commas and "and", each group maybe with "et al." after it."""
    words_only = words.joins.replace("|&", "").replace(r"\.", "")  # "and", "und|u"
    name_word = rf"(?!(?:{words_only}|et)\b){_WORD}"
    group = rf"{name_word}(?:[ \t]+{name_word}|\s*-\n{_LETTER}+)*(?:\s+(?:{words.others}))?"
    joins = words.joins
    return rf"{group}(?:\s*,\s*(?:(?:{joins})\s+)?{group}|\s+(?:{joins})\s+{group})*"


def _part_pattern(words: CitationWords) -> re.Pattern[str]:
    leads = "|".join(
        re.escape(lead).replace(r"\ ", r"\s+") for lead in sorted(words.lead, key=len, reverse=True)
    )
    years, locator = _years(words), _locator(words)
    return re.compile(
        rf"\A\s*(?:(?:{leads})\s+)*(?P<authors>{_authors(words)})"
        rf"(?:\s*\(\s*{years}{locator}\s*\)|\s*,?\s+{years}{locator}|\s*,\s*{years}{locator})"
        # a full stop may end the part: "(See Smith (2019).)" (D-447, #145)
        rf"(?P<tail>{locator})\s*\.?\s*\Z",
        re.IGNORECASE,
    )


def _numeric_aside_pattern(words: CitationWords) -> re.Pattern[str]:
    leads = "|".join(
        re.escape(lead).replace(r"\ ", r"\s+") for lead in sorted(words.lead, key=len, reverse=True)
    )
    bracket = rf"(?:(?:{leads})\s+)*\[{_NUMERIC.pattern[:-2]}\]"
    joins = words.joins.replace("|&", "")
    return re.compile(rf"\s*{bracket}(?:\s*(?:,|;|{joins})\s*{bracket})*\s*\Z", re.IGNORECASE)


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
    languages = ("en", "de")
    category = Category.CITATIONS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        words = WORDS[context.language.split("-", 1)[0].lower()]
        language = context.language.split("-", 1)[0].lower()
        rules = _Rules(
            words,
            wording_for(context.language),
            ABBREVIATIONS.get(language, words.abbreviations),
            language,
        )
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
    def __init__(
        self,
        words: CitationWords,
        wording: Wording,
        abbreviations: frozenset[str],
        language: str = "en",
    ) -> None:
        self.words = words
        self.wording = wording
        self.abbreviations = abbreviations
        self.part = _part_pattern(words)
        self.numeric_aside = _numeric_aside_pattern(words)
        self.years_only = re.compile(rf"\s*{_years(words)}{_locator(words)}\s*\Z", re.IGNORECASE)
        self.page_only = re.compile(rf"\s*(?:{words.page})\s*\Z")
        self.glued_page = re.compile(rf"[\[(]\s*(?:{words.page})\s*[\])]")
        self.dated = re.compile(rf"\b(?:1[5-9]\d\d|20\d\d)|{words.dated}")
        self.others_end = re.compile(rf"(\S+)\s+(?:{words.others})\s*\Z")
        self.pair_end = re.compile(rf"(\S+)\s+(?:{words.joins})\s+\S+\s*\Z")
        self.not_names = {*words.other_words, *re.sub(r"\\", "", words.joins).split("|")}
        self._intervals_of: tuple[str | None, frozenset[int]] = (None, frozenset())
        self.language = language

    def block(self, text: str) -> list[_Found]:
        found: list[_Found] = []
        for node in brackets(text):
            self._visit(text, node, found)
        found.sort()
        return self._tidied(text, _settled(text, found))

    def _tidied(self, text: str, found: list[_Found]) -> list[_Found]:
        """Removals that would leave two marks side by side take one along (M2 of the #66
        review): "Smith et al. (2019). Then" reads "Smith et al. Then"; "noise [12], [3]." reads
        "noise."; "x. [12]. [3]." reads "x."."""
        result = [list(item) for item in found]
        kept_end = 0  # end of the text kept before the next edit
        last, last_at, first_after = "", -1, 0  # the last mark heard, where, and the edit after
        before_last = ""
        for index, item in enumerate(result):
            start, end, kind, replacement = item[0], item[1], item[2], item[3]
            mark_at = _last_mark_at(text, kept_end, start)
            if mark_at >= 0:
                heard = text[max(kept_end, mark_at - _LOOK_BACK) : mark_at].rstrip()
                before_last = heard[-1] if heard else last  # what was heard before that mark
                last, last_at, first_after = text[mark_at], mark_at, index
            after = text[end : end + 1]
            following = result[index + 1][0] if index + 1 < len(result) else len(text) + 1
            if kind is EditKind.REMOVE and last and after and end + 1 <= following:
                if last in ",;:" and after in ".!?" and last_at >= 0:
                    result[first_after][0] = last_at  # "noise, [3]." reads "noise."
                    if before_last == ".":  # "e.g., [3]." reads "e.g."
                        item[1] = end + 1
                elif (
                    (last in ".!?" and after in ".,;:") or (last in ",;" and after in ",;")
                ) and not (after != "." and self._abbreviation_before(text, kept_end, start)):
                    item[1] = end + 1  # "et al. (2019). Then" reads "et al. Then"
            kept_end = item[1]
            if kind is EditKind.REPLACE:
                last, last_at = replacement[-1:] or last, -1
        return [(a, b, kind, replacement, why) for a, b, kind, replacement, why in result]

    def _abbreviation_before(self, text: str, kept_end: int, start: int) -> bool:
        """True if the kept text before `start` ends with an abbreviation ("et al.")."""
        words = text[max(kept_end, start - _LOOK_BACK) : start].split()
        return bool(words) and words[-1].lstrip("([").lower() in self.abbreviations

    def _visit(self, text: str, root: _Bracket, found: list[_Found]) -> None:
        """Decide a bracket, then the inner brackets of what stays; no recursion, so a deep
        nest of brackets cannot overflow the stack."""
        pending = [root]
        while pending:
            node = pending.pop()
            handled = self._decide(text, node)
            if handled is None:
                pending += reversed(node.children)
                continue
            found += handled
            pending += reversed(
                [  # inner brackets of kept text are still looked at
                    child
                    for child in node.children
                    if not any(
                        start <= child.open and child.close < end for start, end, *_ in handled
                    )
                ]
            )

    def _decide(self, text: str, node: _Bracket) -> list[_Found] | None:
        inside = text[node.open + 1 : node.close]
        if len(inside) > _MAX_BRACKET:
            return None
        if text[node.open] == "[":
            return self._numeric(text, node, inside)
        if self.numeric_aside.match(inside):
            return [self._removed(text, node.open, node.close + 1, "citation")]
        if self.years_only.match(inside) and (names := self._names_before(text, node.open)):
            end = self._glued_page(text, node.close + 1)
            printed = _printed(f"{names} {text[node.open : end]}")
            reason = f'year of the citation "{printed}" is not read; the names stay (TP-04)'
            start, end = self._with_space(text, node.open, end)
            return [(start, end, EditKind.REMOVE, "", reason)]
        if _FULL_STOP_INSIDE.search(inside) and not self._starts_sentence(text, node.open):
            return None  # "It holds (Smith, 2019.)": its full stop ends the sentence outside
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
            if self.page_only.match(inside) and re.search(
                r"[\"”’']\s*\Z", _before(text, node.open)
            ):
                return [self._removed(text, node.open, node.close + 1, "page reference")]
            return None
        glued = text[node.open - 1 : node.open]
        if glued and (glued.isalnum() or glued in ")]"):
            return None
        if self._not_citations(text, node.open):
            return None
        window = max(0, node.open - _LOOK_BACK)
        before = text[window : node.open].rstrip()
        previous = before.split()[-1] if before.split() else ""
        printed = _printed(text[node.open : node.close + 1])
        word = re.sub(r"\A\W*\d*", "", previous).lower()  # "8See" -> "see", "(see" -> "see"
        start = node.open
        if previous.lower() in self.words.refs or previous in self.words.ref_words:
            start = window + len(before) - len(previous)
            printed = _printed(text[start : node.close + 1])
        elif (
            word not in self.words.before
            or any(before.lower().endswith(aside) for aside in self.words.asides)
        ) and not self._is_subject(text, node.open, node.close + 1):
            return [self._removed(text, node.open, node.close + 1, "numeric citation")]
        spoken = self._spoken(inside)
        if before.endswith("("):  # "( [53] discusses": no space after the bracket
            start = window + len(before)
        if self._starts_sentence(text, start):
            spoken = spoken[0].upper() + spoken[1:]
        reason = f'citation "{printed}" is part of the sentence: read as "{spoken}" (TP-04)'
        return [(start, node.close + 1, EditKind.REPLACE, spoken, reason)]

    def _not_citations(self, text: str, position: int) -> bool:
        """True if the square bracket at `position` holds an interval or a label's number, not
        citations: after a maths sign, a maths word ("CI", "CI:", "CIs", D-450), a label word
        ("Eq.") or a percentage, or where the statistics step reads a confidence interval
        joined on to one ("CIs [1, 3] and [2, 4]", #151): only a pair it reads, so "CI [1, 3]
        and [12]" still cites reference 12."""
        before = text[max(0, position - _LOOK_BACK) : position].rstrip()
        previous = before.split()[-1] if before.split() else ""
        if previous and (
            previous[-1] in _MATHS_SIGNS
            or previous.lower().rstrip(":") in self.words.maths
            or _is_label_word(previous.lstrip("(["), self.words.numbered)
            or previous.endswith("%")
        ):
            return True
        return position in self._intervals(text)

    def _intervals(self, text: str) -> frozenset[int]:
        """The statistics step's interval brackets in this block, worked out once."""
        if self._intervals_of[0] != text:
            self._intervals_of = (text, interval_openings(text, self.language))
        return self._intervals_of[1]

    def _spoken(self, inside: str) -> str:
        items = []
        single = True
        for match in _ITEMS.finditer(inside):
            first, last = match.group(1), match.group(2)
            if last:
                items.append(f"{first} {self.wording.range_to} {last}")
                single = False
            else:
                items.append(first)
        if len(items) > 1:
            single = False
        noun = self.wording.reference if single else self.wording.references
        if len(items) == 1:
            return f"{noun} {items[0]}"
        return (
            f"{noun} {self.wording.list_comma.join(items[:-1])}{self.wording.list_and}{items[-1]}"
        )

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
        if not self.dated.search(text[node.open : node.close]):
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
                elif char == "," and depth == 0 and _before(text, position).rstrip().endswith(")"):
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
        names = [t for t in tokens if t.lower() not in self.not_names]
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
        before = _before(text, position)
        found = re.search(rf"({_LETTER}+-\n)?(\S+)\s*\Z", before)
        if not found:
            return ""
        word = found.group(2)
        others = self.others_end.search(before)
        if others:  # "Smith et al. (2019)"
            return _printed(before[others.start() :])
        joined = (found.group(1) or "").replace("-\n", "-") + word
        bare = re.sub(r"(?:[’']s?)\Z", "", joined)
        if not (_is_name(bare) or re.fullmatch(r"[A-Z]{2,6}", bare)):
            return ""
        # "Sag and Hankamer (1984)": the reason names both authors
        pair = self.pair_end.search(before)
        if pair and _is_name(pair.group(1)):
            return _printed(pair.group())
        # "the Olympics (2016)": after an article the word names a thing, not an author
        # (D-448, #110); "et al." or a second author (above) still make it a citation
        article = re.search(r"(\S+)\s+\Z", before[: found.start()])
        if article and article.group(1).lower() in self.words.articles:
            return ""
        return joined

    def _previous_word(self, text: str, position: int) -> str:
        """The word before a position, lower case, without brackets or a glued footnote mark."""
        words = _before(text, position).split()
        return re.sub(r"\A\W*\d*", "", words[-1]).lower() if words else ""

    def _glued_page(self, text: str, end: int) -> int:
        """The end of a page bracket glued to a citation ("(2022)[p. 8]"), or `end`."""
        page = self.glued_page.match(text, end)
        return page.end() if page else end

    def _is_subject(self, text: str, start: int, end: int) -> bool:
        """True if the citation starts a sentence (or a bracket) and a lower-case word follows."""
        starts = self._starts_sentence(text, start) or _before(text, start).rstrip().endswith("(")
        return starts and bool(_LOWER_NEXT.match(text, end))

    def _starts_sentence(self, text: str, position: int) -> bool:
        """True at the start of the block or after a sentence end, but not after an
        abbreviation ("cf. [4]", "Eq. [3]", "et al. (2019)")."""
        window = max(0, position - _LOOK_BACK)
        before = text[window:position]
        stripped = before.rstrip()
        if not stripped:
            return window == 0
        if len(stripped) == len(before):
            return False
        core = stripped.rstrip("\"'”’)]")
        if not core or core[-1] not in ".!?":
            return False
        if core[-1] == ".":
            word = core.split()[-1].lstrip("\"'([{“‘").lower()
            if word in self.abbreviations:
                return False
        return True

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
            join = self.wording.list_and if number == len(names) - 1 else self.wording.list_comma
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
        start, end = self._with_space(text, start, end)
        return (start, end, EditKind.REMOVE, "", reason)

    def _with_space(self, text: str, start: int, end: int) -> tuple[int, int]:
        """Take the white space before the removal along, or after it at the start of a block.

        At the start of a sentence the punctuation after it goes instead: "It holds. (Smith,
        2019). Then" reads "It holds. Then", not "It holds.. Then".
        """
        if self._starts_sentence(text, start):
            punctuation = _AFTER_START.match(text, end)
            if punctuation:
                return start, punctuation.end()
        return _with_space(text, start, end)


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


def _is_label_word(word: str, numbered: frozenset[str]) -> bool:
    """A capitalised label word ("Eq.", "Fig.", "Table"): "the EM algorithm [5]" and "the
    first step [7]" are citations, "Algorithm [5]" is a number."""
    return word[:1].isupper() and word.lower() in numbered


def _last_mark_at(text: str, kept_end: int, start: int) -> int:
    """Where the last character other than white space in text[kept_end:start] stands, or
    -1 if there is none."""
    window = max(kept_end, start - _LOOK_BACK)
    kept = text[window:start].rstrip()
    return window + len(kept) - 1 if kept else -1


def _before(text: str, position: int) -> str:
    """The text just before a position, as much as the rules look at."""
    return text[max(0, position - _LOOK_BACK) : position]


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
