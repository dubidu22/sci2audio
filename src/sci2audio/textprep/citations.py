# ruff: noqa: RUF001, RUF002, RUF003  (dashes, quotes and symbols are meant as papers print them)
"""Citations are not read where they are asides, and read briefly where the sentence needs
them (TP-03, TP-04, K2; D-171 to D-173).

Numeric citations are square brackets of whole numbers, lists and ranges ("[12]",
"[2–6, 16, 17]"), never glued to a word ("Tr[ρ]") and never after a maths or statistics
sign or word ("∈ [0, 1]", "CI [1, 3]", "CI: [1, 3]"), nor joined on to such a bracket
("CIs [1, 3] and [2, 4]", D-450). An aside is removed; a citation that is part of the
sentence ("discussed in [26].", "Refs. [53, 58]", "[12] showed") is read as "reference 26",
"references 53 and 58"; a bracket holding only lead words and citations ("(see also [48,
135])") goes whole. Alphanumeric keys ("[MH17]", "[Knu84]", "[GKL+19]"; #254, D-646) are read
the same way, a needed key as printed ("reference MH17", "Quelle MH17"), but only where the
document prints each key of the bracket as an entry's label at a line's start ("[MH17]
Maass, M.: …"), so that names of things shaped like keys ("[Mn12] clusters", "[EU27]") stay
as printed (review B1 of PR #377); look-alikes ("[PM10]") stay as printed in any case.

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

A bracket of identifiers only, such as grant numbers ("(0801700)", "(grant no. DMS-1912345)"),
goes (#285, D-547). The other brackets are then judged on the text without them, as a second
run sees it: "Smith (527794) (2019)" reads "Smith"; an identifier beside citations in one
bracket goes with them, and a bracket left with only lead words ("(see (527794))") goes whole.

Brackets are worked outermost first: a bracket that goes takes everything inside it along,
and inside one that stays, its inner brackets are looked at in turn. "et al." stays as
printed; reading it is #68's. Every reason names the citation as printed (D-175).
"""

from __future__ import annotations

import bisect
import itertools
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.textprep.abbreviations import reads_full_stop
from sci2audio.textprep.characters import INVISIBLE, SOFT_HYPHEN
from sci2audio.textprep.furniture import edits_around, hidden_removals, read_around
from sci2audio.textprep.links import (
    link_removals,
    only_links_after,
    only_links_before,
    without_links,
)
from sci2audio.textprep.numbers_de import YEAR_WORDS
from sci2audio.textprep.placeholders import read_as_prose
from sci2audio.textprep.statistics import OPERATORS, interval_openings
from sci2audio.textprep.statistics_de import OPERATORS_DE, READ_WORDS
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep
from sci2audio.textprep.utterances import ABBREVIATIONS
from sci2audio.textprep.wording import Wording, wording_for

# looks at a block's brackets beyond the first: one per bracket the text holds, since each
# look that changes something decides at least one more level of a nest (D-577, D-588)
_LOOK_BRACKETS = re.compile(r"[(\[]")
_MAX_BRACKET = 4000  # characters; a longer bracket is not a citation and is not parsed
_EDITS_LOOKED_BACK = 16  # inner edits read back before a bracket of years (D-599)
_HUNG = 24  # characters read back for a separator a removal leaves hanging (#372)
_LOOK_WORK = 8  # how many times its own length all looks at a block may read (D-599)


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
    # words that may stand before an identifier in brackets: "(grant no. DMS-1912345)" (#285)
    funding: str = r"(?!)"
    and_word: str = "and"  # between two identifiers: "(0801700 and 527794)"
    or_word: str = "or"  # a list of citation brackets with it is no one citation (#414)
    # a page after a numeric citation's source, and how it is read: "[12, p. 3]" (#257)
    page_lead: str = r"pp?\.|pages?"
    page_words: tuple[str, str] = ("page", "pages")
    # German writes every noun with a capital: a capital word before a year bracket names an
    # author only after one of these words (or at a sentence start), not after an article or
    # an inflected adjective ("die neue Studie (2019)", "Die Olympischen Spiele (2016)")
    name_leads: frozenset[str] | None = None
    # a season, a term or a noun that stands before a year ("Sommer", "Wintersemester",
    # "Ausgabe"): alone with a plain year, as a bracket's only part, it dates something and
    # is no author ("(Sommer 2019)" stays; "(Sommer, 2019)", "(Sommer et al. 2019)", "(vgl.
    # Sommer 2019)" and "(Sommer 2019; Koch 2020)" still cite, #483)
    periods: frozenset[str] = frozenset()


# a page: digits, or Roman numerals of the front matter ("S. XV", "pp. iv–vi", #455); no "d" or
# "m", so a name after "S." ("S. Mill") is never a page. A citation's pattern ignores case
_PAGE = r"(?:\d+|(?=[ivxlc])c{0,3}(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})(?![^\W\d_]))"

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
            rf"pp?\.\s*{_PAGE}(?:\s*[-–—]\s*{_PAGE})?|chapters?\s+\d+|ch(?:ap)?\.\s*\d+|"
            r"sec(?:tions?|s?\.)\s*\d+(?:\.\d+)*|§+\s*\d+(?:\.\d+)*|inter\s+alia"
        ),
        funding=(
            r"(?:grant\s+agreement|grants?|awards?|contracts?|projects?)(?:\s+(?:nos?\.|numbers?))?"
            r"|nos?\."
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
            "eines", "im", "am", "zum", "zur", "vom", "beim", "ins", "ans",
        )),
        joins=r"und|u\.|&",
        others=r"et\s+al\.|u\.\s?a\.",
        other_words=frozenset(["et", "al.", "u.", "a.", "u.a."]),
        undated=r"im\s+Druck|in\s+press|o\.\s?J\.|n\.\s?d\.|in\s+Vorbereitung|forthcoming",
        dated=r"im\s+Druck|in\s+press|o\.\s?J\.|n\.\s?d\.",
        page=r"(?:S|pp?)\.\s*\d+(?:\s*[-–—]\s*\d+)?(?:\s*ff?\.)?",
        locators=(
            rf"(?:S|pp?)\.\s*{_PAGE}(?:\s*[-–—]\s*{_PAGE})?(?:\s*ff?\.)?|Kap(?:itel|\.)\s*\d+|"
            r"Abschn(?:itt|\.)\s*\d+(?:\.\d+)*|§+\s*\d+(?:\.\d+)*|Rn\.\s*\d+(?:\s*[-–—]\s*\d+)?"
        ),
        funding=(
            r"(?:Förderkennzeichen|Fördernummer|FKZ|Projekt(?:nummer|nr\.)?|Grant)(?:\s+Nr\.)?"
            r"|Nr\."
        ),
        and_word="und",
        or_word="oder",
        page_lead=r"S\.|Seiten?|pp?\.",
        page_words=("Seite", "Seiten"),
        name_leads=frozenset((
            "wie", "siehe", "gegen", "unter", "über", "oder", "aber", "sowie", "haben", "zeigen",
            "zeigten", "fanden", "finden", "schreiben", "beschreiben", "argumentieren", "betonen",
            "nennen", "kamen", "kommen", "folgen", "folgend", "nachdem", "seit", "bereits",
        )),
        periods=YEAR_WORDS | frozenset((
            "ausgabe", "auflage", "stand", "fassung", "version", "jahrgang", "semester", "quartal",
            "saison", "spielzeit", "welle", "erhebung", "erhebungswelle", "zensus", "mikrozensus",
            "haushaltsjahr", "geschäftsjahr", "berichtsjahr", "kalenderjahr", "schuljahr",
            "studienjahr",
        )),
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
# alphanumeric keys (alpha style "[Knu84]", "[GKL+19]"; LNI "[MH17]", "[Fa14]"; #254, D-646): a
# capital, one to three more letters, maybe "+", two digits, maybe a letter. Two letters at
# least, so "[C60]" and "[CO2]" are never keys; no ranges and no mix with numbers
_KEY = r"[A-Z][A-Za-z]{1,3}\+?\d{2}[a-z]?(?![\w+])"
_KEYS = re.compile(rf"\s*{_KEY}(?:\s*[,;]\s*{_KEY})*\s*\Z")
_KEY_ITEMS = re.compile(_KEY)
# shaped like keys, but they name a thing (particulate matter, an ion, a product); a bracket
# holding one stays as printed (D-646)
KEY_LOOK_ALIKES = frozenset(("PM10", "PM25", "SO42", "Win10", "Win11", "COVID19"))
# "↔" too: the numbers step reads "←−→" as it, and "x ←−→ [2]" keeps its bracket (#593 F2)
_MATHS_SIGNS = "=∈∉→←↔↦<>≤≥×±∼≈⊂⊆∪∩"
_YEAR = r"(?:1[5-9]\d\d|20\d\d)(?:[a-z](?:\s*,\s*[a-z](?![a-z]))*)?(?![\w])"
_LETTER = r"(?:[^\W\d_]|[̀-ͯ])"
_WORD = rf"{_LETTER}+(?:(?:[’'-]|-\n){_LETTER}+)*"
_SPACE = re.compile(r"\s+")
_FIVE_DIGITS = re.compile(r"\d{5}")  # every identifier holds a run of five digits (#313)
_PUNCTUATION_ONLY = re.compile(r"[\s,;:.]+")  # between and after lead words
_DECIMAL_COMMA = re.compile(r"\d,\d")
_SQUARE = re.compile(r"\[([^\[\]]*)\]")  # what a square bracket holds
_UNREAD = re.compile(r"[\s.,;:!?]*")  # what a removal may leave to a link's
_NUMBER_GLUED_AFTER = re.compile(r"[.,]?\d")  # a number glued to a bracket's end
_LOWER_NEXT = re.compile(r"\s+[a-z]")
_AFTER_START = re.compile(r"[.!?,;:]+(?:\s+|\Z)")
_LOOK_BACK = 300  # characters looked at before a bracket, so a long block costs linear time
_GLUES = ".,0123456789"  # what a removal must not join to a digit after it (#308)
_CLOSE_AHEAD = re.compile(r"\s*\)")
_PLAIN_YEAR = re.compile(r"\s+(?:1[5-9]\d\d|20\d\d)\s*")  # a year alone, no comma or letter
_FULL_STOP_INSIDE = re.compile(r"[\d)]\s*\.\s*\Z")  # "(See Smith (2019).)", not "n.d."


_SLASHED = re.compile(r"(\d{4})[a-z]?/(\d{4})")


def _no_period(text: str) -> bool:
    """A slashed year is the year of the edition used only when it is more than a year later:
    "2019/2020" is a winter term or a season, never a reprint (#481 review)."""
    return all(int(b) - int(a) > 1 for a, b in _SLASHED.findall(text))


def _years(words: CitationWords) -> str:
    """Years or their stand-ins, joined by commas: "2016a,b", "2019, in press"; a year may
    carry the year of the edition used after a slash: "1974/2004" (#455, D-719)."""
    one = rf"(?:{_YEAR}(?:/{_YEAR})?|{words.undated})"
    return rf"{one}(?:\s*,\s*{one})*"


def _locator(words: CitationWords) -> str:
    return rf"(?:\s*,\s*(?:{words.locators}))*"


def _authors(words: CitationWords) -> str:
    """Names joined by commas, "and" or a slash ("Heydorn/Koneffke", #455), each group maybe
    with "et al." after it."""
    words_only = words.joins.replace("|&", "").replace(r"\.", "")  # "and", "und|u"
    name_word = rf"(?!(?:{words_only}|et)\b){_WORD}"
    group = rf"{name_word}(?:[ \t]+{name_word}|\s*-\n{_LETTER}+)*(?:\s+(?:{words.others}))?"
    joins = words.joins
    return rf"{group}(?:\s*,\s*(?:(?:{joins})\s+)?{group}|\s+(?:{joins})\s+{group}|/{group})*"


def _part_pattern(words: CitationWords) -> re.Pattern[str]:
    leads = "|".join(
        re.escape(lead).replace(r"\ ", r"\s+") for lead in sorted(words.lead, key=len, reverse=True)
    )
    years, locator = _years(words), _locator(words)
    return re.compile(
        # a join word after the ";" before it: "(Smith, 2019; and Lee, 2018)" (#415)
        rf"\A\s*(?:(?:{words.and_word}|&)\s+)?(?:(?:{leads})\s+)*(?P<authors>{_authors(words)})"
        rf"(?:\s*\(\s*{years}{locator}\s*\)|\s*,?\s+{years}{locator}|\s*,\s*{years}{locator})"
        # a full stop may end the part: "(See Smith (2019).)" (D-447, #145)
        rf"(?P<tail>{locator})\s*\.?\s*\Z",
        re.IGNORECASE,
    )


def _numeric_aside_pattern(words: CitationWords) -> re.Pattern[str]:
    leads = "|".join(
        re.escape(lead).replace(r"\ ", r"\s+") for lead in sorted(words.lead, key=len, reverse=True)
    )
    bracket = rf"(?:(?:{leads})\s+)*\[(?:{_NUMERIC.pattern[:-2]}|{_KEYS.pattern[:-2]})\]"
    joins = words.joins.replace("|&", "")
    return re.compile(rf"\s*{bracket}(?:\s*(?:,|;|{joins})\s*{bracket})*\s*\Z", re.IGNORECASE)


@dataclass
class _Bracket:
    open: int  # index of "(" or "["
    close: int  # index of ")" or "]"
    children: list[_Bracket] = field(default_factory=list)


# a code of letters and digits, maybe joined by "-" or "/", with a run of five digits or more:
# "0801700", "DMS-1912345", "01IS18026A"; not "OPP-115", "COVID-19", "12,345" or "12 345"
_IDENTIFIER = r"(?=[^\W_]*(?:[-/][^\W_]+)*?\d{5})[^\W_]+(?:[-/][^\W_]+)*"


def _identifiers_pattern(words: CitationWords) -> re.Pattern[str]:
    """A bracket's inside that is only identifiers, each maybe after a funding word (#285)."""
    one = rf"(?:(?:{words.funding})\s*)?{_IDENTIFIER}(?![^\W_])"
    join = rf"\s*(?:[,;&]|{words.and_word}\b)\s*"
    return re.compile(rf"\s*{one}(?:{join}{one})*\s*\Z", re.IGNORECASE)


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
            ABBREVIATIONS.get(language, frozenset()) | words.abbreviations,
            language,
            listed_keys(document),
        )
        hidden = hidden_removals(document, context)  # read as a second run reads (#434)
        edits = []
        for index, block in enumerate(document.blocks):
            if not read_as_prose(block, context) or not block.text.strip():
                continue
            unread = hidden.get(index, [])
            text, kept = read_around(block.text, unread)
            links = link_removals(text, block.kind, block.label, language)
            found = []
            for start, end, kind, replacement, reason in rules.block(text, links):
                if kind is EditKind.REPLACE:
                    found.append(Edit(Span(index, start, end), kind, reason, self.id, replacement))
                else:
                    found.append(Edit(Span(index, start, end), kind, reason, self.id))
            edits += edits_around(found, kept, unread)
        return edits


_Found = tuple[int, int, EditKind, str, str]  # start, end, kind, replacement, reason


class _Rules:
    def __init__(
        self,
        words: CitationWords,
        wording: Wording,
        abbreviations: frozenset[str],
        language: str = "en",
        keys: frozenset[str] = frozenset(),
    ) -> None:
        self.words = words
        self.keys = keys  # the keys the document's entries print (#254, review B1 of PR #377)
        self.wording = wording
        self.abbreviations = abbreviations
        self.part = _part_pattern(words)
        self.numeric_aside = _numeric_aside_pattern(words)
        self.years_only = re.compile(rf"\s*{_years(words)}{_locator(words)}\s*\Z", re.IGNORECASE)
        self.page_only = re.compile(rf"\s*(?:{words.page})\s*\Z")
        # a page after a citation's year: ", S. 1", ", p. 5" (#455)
        self.page_after = re.compile(rf"\d\s*,\s*(?:{words.page_lead})\s*\S")
        # one source and its page: "[12, p. 3]", "[12, S. 3–5]", "[MH17, S. 3]" (#257, D-668)
        self.paged = re.compile(
            rf"\s*(?P<source>{_NUMBER}|{_KEY})\s*,\s*(?:{words.page_lead})\s*"
            r"(?P<first>[1-9]\d{0,4})(?:\s*[-–—]\s*(?P<last>[1-9]\d{0,4}))?\s*\Z"
        )
        # what joins two square brackets of a list: "[1], [2]", "[2] and [3]", "[2], and [3]"
        # (#257, #414); "or" joins none, and a list joined on to a bracket by it is no list
        self.list_gap = re.compile(rf"\s*,\s*|(?:\s*,)?\s+(?P<join>{words.and_word})\s+")
        self.or_after = re.compile(rf"(?:\s*,)?\s+{words.or_word}\s+\[")
        self._lists: dict[int, list[_Bracket]] = {}  # this look only
        self._paired: set[int] = set()  # the later brackets of lists, this look only
        self._numbered: set[int] = set()  # the square brackets decided, this look only
        self.identifiers = _identifiers_pattern(words)
        leads = "|".join(
            re.escape(lead).replace(r"\ ", r"\s+")
            for lead in sorted(words.lead, key=len, reverse=True)
        )
        joins = rf"[,;]|&|\b{words.and_word}\b"
        # what a removal at a bracket's start may stand after, and what it then leaves hanging
        self.lead_before = re.compile(rf"\(\s*(?:(?:{leads})\s*)*\Z", re.IGNORECASE)
        self.hung_ahead = re.compile(rf"\s*(?:{joins})(?=\s*[^\s)\]])", re.IGNORECASE)
        # a separator before a removal at a bracket's end
        self.hung_behind = re.compile(rf"\s*(?:{joins})\s*\Z", re.IGNORECASE)
        self.lead_only = {
            "",
            *(" ".join(_PUNCTUATION_ONLY.sub(" ", lead).split()) for lead in words.lead),
        }
        self.glued_page = re.compile(rf"[\[(]\s*(?:{words.page})\s*[\])]")
        self.dated = re.compile(rf"\b(?:1[5-9]\d\d|20\d\d)|{words.dated}")
        self.others_end = re.compile(rf"(\S+)\s+(?:{words.others})\s*\Z")
        self.pair_end = re.compile(rf"(\S+)\s+(?:{words.joins})\s+\S+\s*\Z")
        self.not_names = {*words.other_words, *re.sub(r"\\", "", words.joins).split("|")}
        # what sets off an inner bracket as an item of the bracket's list (#372, #415)
        self.item_after = re.compile(r"\s*[;,]")
        self.item_separator = re.compile(rf"\s*(?:[;,]\s*)+(?:(?:{words.and_word}|&)\s+)?")
        self.item_before = re.compile(rf"[;,]\s*(?:(?:{words.and_word}|&)\s+)?\Z")
        self._intervals_of: tuple[str | None, frozenset[int]] = (None, frozenset())
        # a sign as the statistics step reads it counts as the sign: "x equals [12]" is "x =
        # [12]" after the first run, so a second run decides the same (#101)
        said = OPERATORS_DE if language == "de" else OPERATORS
        phrases = sorted(set(said.values()), key=len, reverse=True)
        self.said_sign = re.compile(rf"(?<!\w)(?:{'|'.join(map(re.escape, phrases))})\Z")
        self.language = language

    def block(self, text: str, links: list[tuple[int, int]] | None = None) -> list[_Found]:
        """The edits for one block's text; `links` are the spans the links step removes.

        A second run sees the text without this step's removals and the links': "Lee (Smith,
        2019) (2019)" is "Lee (2019)" then, "(Smith, 2019, https://x.org)" is "(Smith, 2019)"
        and "(see (527794))" is "(see)". So the brackets are decided again on that text, look
        after look, until a look changes nothing, however deep the nest; a later look's edit
        takes along the earlier ones inside it (#285 review round 1; #306, #308, #309, D-577,
        D-588). The looks are bounded by the text's brackets, which no look adds, and all
        looks together read at most a fixed multiple of the text: a nest that needs more stays
        as printed, so no shape costs quadratic time (D-599).
        """
        links = sorted(links or [])
        found = self._once(text, links, ())
        looks = len(_LOOK_BRACKETS.findall(text))
        # the work all looks may do: a fixed multiple of the text, so no shape that needs a
        # look per level costs quadratic time; a nest still unsettled then stays as printed
        # (#330 review round 2, D-599)
        budget = _LOOK_WORK * (len(text) + _LOOK_BACK)
        gone = [(a, b) for a, b, _, _, why in found if why.startswith(_IDENTIFIER_REASON)]
        if gone:
            # identifiers first, with every other bracket decided anew on the text without
            # them, as before D-577: "(527794) (Müller, 2019) zeigt" keeps "Müller" as the
            # subject (#285); this look comes on top of the others
            found = self._identifiers_looked_past(text, found, gone, links)
        while looks > 0:
            looks -= 1
            removed = _joined(
                sorted([(a, b) for a, b, kind, *_ in found if kind is EditKind.REMOVE] + links)
            )
            if not removed:
                break
            # the text as a second run reads it: removals cut, readings written in
            rewrite = _Rewrite(
                text,
                sorted(
                    [(a, b, "") for a, b in removed]
                    + [(a, b, r) for a, b, kind, r, _ in found if kind is EditKind.REPLACE]
                ),
            )
            if rewrite.text is None:
                break  # a reading overlaps a removal: no look past them
            budget -= len(rewrite.text)
            back: list[_Found] = []
            for start, end, kind, replacement, reason in self._once(rewrite.text, [], rewrite.at):
                first, last = rewrite.printed(start, True), rewrite.printed(end, False)
                if first is None or last is None or first >= last:
                    continue  # inside a reading of the look before: that reading stands
                # a later edit never holds a link's span, which is the links step's own edit
                pieces = _around(links, first, last)
                if kind is EditKind.REPLACE and len(pieces) != 1:
                    continue  # a reading cannot be split; the bracket stays as the look before
                back += [(a, b, kind, replacement, reason) for a, b in pieces]
            later = _merged(found, back)
            if later == found:
                break
            if budget < 0:
                return _unsettled_as_printed(text, found, later)
            found = later
        return found

    def _identifiers_looked_past(
        self,
        text: str,
        found: list[_Found],
        gone: list[tuple[int, int]],
        links: list[tuple[int, int]],
    ) -> list[_Found]:
        """The edits once the brackets are decided again on the text without the removed
        identifiers; an identifier inside an edit of that look goes with it (#285 review
        round 1)."""
        read, cuts = _without(text, gone)
        read_links = [(cuts.read(start), cuts.read(end)) for start, end in links]
        back = [
            (cuts.printed(start, True), cuts.printed(end, False), kind, replacement, reason)
            for start, end, kind, replacement, reason in self._once(read, read_links, cuts.at)
        ]
        starts = [start for start, *_ in back]
        kept = []
        for item in found:
            if not item[4].startswith(_IDENTIFIER_REASON):
                continue
            at = bisect.bisect_right(starts, item[0]) - 1
            if at < 0 or back[at][1] < item[1]:
                kept.append(item)
        return sorted(kept + back)

    def _once(self, text: str, links: list[tuple[int, int]], cuts: Sequence[int]) -> list[_Found]:
        found: list[_Found] = []
        self._runs: dict[int, int] = {}  # for `_before_removals`, this look only
        self._paired, self._numbered = set(), set()
        self._link_starts = {end: start for start, end in links}  # for `_numeric`
        roots = brackets(text)
        self._lists = self._bracket_lists(text, roots)
        for node in roots:
            self._visit(text, node, found, cuts)
        found.sort()
        settled = _settled(text, self._unhung(text, _settled(text, found), _pairs(roots)))
        return _clear_of_links(text, _shells(text, self._tidied(text, settled)), links)

    def _unhung(self, text: str, found: list[_Found], pairs: dict[int, int]) -> list[_Found]:
        """Removals that would leave a separator hanging at a bracket's edge take it along:
        "((527794); 2019)" reads "(2019)", "(see (527794) and Lee, 2019)" reads "(see Lee,
        2019)", "(527794, (Smith, 2019))" reads "(527794)" (#305). A removal that would glue
        a full stop, a comma or a digit to a digit after it is not made: ". .(Müller,
        2019)12.345" would read as a decimal on a second run (#308, D-577). `pairs` maps each
        matched bracket's opening to its closing and back: only a bracket around the removal
        has an edge, so "and (see [12]))" keeps its "and"."""
        # removals side by side count as one: "( (Müller, 2019) [12]; [1,2; 3,4])" (#272);
        # where each run of them ends, and the edit after it, worked out once (linear time)
        past, after = [0] * len(found), [0] * len(found)
        for number in reversed(range(len(found))):
            past[number], after[number] = found[number][1], number + 1
            if (
                found[number][2] is EditKind.REMOVE
                and number + 1 < len(found)
                and found[number + 1][2] is EditKind.REMOVE
                and _adjacent(text, found[number][1], found[number + 1][0])
            ):
                past[number], after[number] = past[number + 1], after[number + 1]
        result: list[_Found] = []
        firsts: list[int] = []  # where the run of removals of each kept edit starts
        lasts: list[int] = []  # where the kept text before that run ends
        for number, (start, end, kind, replacement, reason) in enumerate(found):
            if kind is EditKind.REMOVE and self._would_glue(text, start, end):
                continue
            if (
                result
                and result[-1][2] is EditKind.REMOVE
                and _adjacent(text, result[-1][1], start)
            ):
                first, last = firsts[-1], lasts[-1]
            else:
                first, last = start, result[-1][1] if result else 0
            if kind is EditKind.REMOVE:
                following = found[number + 1][0] if number + 1 < len(found) else len(text)
                beyond = found[after[number]][0] if after[number] < len(found) else len(text)
                ahead = self.hung_ahead.match(text, end, following)
                lead = ahead and self.lead_before.search(text, max(last, first - _LOOK_BACK), first)
                closing = _CLOSE_AHEAD.match(text, past[number], beyond)
                if lead and pairs.get(lead.start(), -1) >= past[number]:
                    end = ahead.end()  # "(see (527794) and Lee": " and" goes with it
                    if not text[start].isspace():  # "((527794); 2019)": the space after "; "
                        end += len(text[end:following]) - len(text[end:following].lstrip())
                elif (
                    closing
                    and pairs.get(closing.end() - 1, len(text)) < first
                    and (
                        behind := self.hung_behind.search(
                            text, max(last, start - _LOOK_BACK), start
                        )
                    )
                ):
                    start = behind.start()  # "(527794, (Smith, 2019))": ", " goes with it
            result.append((start, end, kind, replacement, reason))
            firsts.append(first)
            lasts.append(last)
        return result

    def _would_glue(self, text: str, start: int, end: int) -> bool:
        """True if removing text[start:end] joins a full stop, comma or digit to a digit after
        it; not the full stop of an abbreviation read in words ("vgl.(527794)2019")."""
        return (
            start > 0
            and text[start - 1] in _GLUES
            and end < len(text)
            and text[end].isdigit()
            and not (text[start - 1] == "." and reads_full_stop(text, start, self.language))
        )

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
                    ((last in ".!?" and after in ".,;:") or (last in ",;" and after in ",;"))
                    and not (after != "." and self._abbreviation_before(text, kept_end, start))
                    # "Kap." is read "Kapitel", its full stop with it: the sentence keeps its
                    # own ("Siehe Kap. (Müller, 2019). Dann", #227)
                    and not (
                        last == "."
                        and last_at >= 0
                        and reads_full_stop(text, last_at + 1, self.language)
                    )
                ):
                    item[1] = end + 1  # "et al. (2019). Then" reads "et al. Then"
            kept_end = item[1]
            if kind is EditKind.REPLACE:
                last, last_at = replacement[-1:] or last, -1
        return [(a, b, kind, replacement, why) for a, b, kind, replacement, why in result]

    def _abbreviation_before(self, text: str, kept_end: int, start: int) -> bool:
        """True if the kept text before `start` ends with an abbreviation ("et al.")."""
        words = text[max(kept_end, start - _LOOK_BACK) : start].split()
        return bool(words) and words[-1].lstrip("([").lower() in self.abbreviations

    def _visit(self, text: str, root: _Bracket, found: list[_Found], cuts: Sequence[int]) -> None:
        """Decide a bracket, then the inner brackets of what stays; no recursion, so a deep
        nest of brackets cannot overflow the stack."""
        # every bracket decided once, inner ones first, so an outer bracket can be judged on
        # what its inner brackets read (#271); a loop, not recursion, for deep nests
        order, stack = [], [root]
        while stack:
            node = stack.pop()
            order.append(node)
            stack += node.children
        decided: dict[int, list[_Found] | None] = {}
        for node in reversed(order):
            decided[node.open] = self._decide(text, node, decided, cuts, found)
        pending = [root]
        while pending:
            node = pending.pop()
            handled = decided[node.open]
            if handled is None:
                pending += reversed(node.children)
                continue
            found += handled
            pending += reversed(
                [  # inner brackets of kept text are still looked at, unless this bracket's
                    # edits already hold theirs (a nest that keeps an inner citation's names)
                    child
                    for child in node.children
                    if not any(
                        start <= child.open and child.close < end for start, end, *_ in handled
                    )
                    and not _covered(decided[child.open], handled)
                ]
            )

    def _decide(
        self,
        text: str,
        node: _Bracket,
        decided: dict[int, list[_Found] | None],
        cuts: Sequence[int] = (),
        found: Sequence[_Found] = (),
    ) -> list[_Found] | None:
        if node.close - node.open - 1 > _MAX_BRACKET:
            # too long to parse, unless it is short once its inner brackets' edits are made:
            # a nest of any depth is decided inner first (D-588)
            return self._cited_once_inner_citations_go(text, node, decided)
        inside = text[node.open + 1 : node.close]
        if text[node.open] == "[":
            return self._numeric(
                text, node, inside, _before_removals(text, node.open, found, self._runs)
            )
        if self._identifiers_only(text, node, decided):
            # "(0801700)", "(grant no. DMS-1912345)": a grant or award number, no quantity
            # (#285, D-547); the script and the read-along keep it as printed
            printed = _printed(text[node.open : node.close + 1])
            reason = (
                f'{_IDENTIFIER_REASON} "{printed}", such as a grant number, is not read (TP-03)'
            )
            start, end = self._with_space(text, node.open, node.close + 1)
            return [(start, end, EditKind.REMOVE, "", reason)]
        if (_cut_inside(cuts, node) and self._only_lead_left(inside)) or self._lead_around_gone(
            text, node, decided
        ):
            # "((Smith, 2019); (Lee, 2018)) is cited" names them all, as the flat form does
            # (#372, D-668); a list of names is the only reading here that replaces anything
            nest = self._cited_once_inner_citations_go(text, node, decided) or []
            if any(kind is EditKind.REPLACE for _, _, kind, *_ in nest) or _keeps_text(nest, node):
                # ... and so does one: "((Smith, 2019)) is cited" reads "Smith" (#415, D-791)
                return nest
            # "(see (527794))" without its identifier is "(see)": a pointer to nothing
            return [self._removed(text, node.open, node.close + 1, "bracket of lead words")]
        if self.numeric_aside.match(inside):
            if any(
                self._decimal_interval(inner)
                or (_KEYS.match(inner) is not None and _keys(inner, self.keys) is None)
                for inner in _SQUARE.findall(inside)
            ):
                # "([1,2; 3,4])": an interval stays on its own, so the aside does too and each
                # inner bracket is judged alone ("([12]; [1,2; 3,4])" keeps the interval); a
                # second run, after "(Müller, 2019) [1,2; 3,4]" lost its citation, decides the
                # same (#266, D-534)
                return None
            return [self._removed(text, node.open, node.close + 1, "citation")]
        if (
            self.years_only.match(inside)
            and _no_period(inside)
            and (
                names := self._names_before(
                    text, _before_removals(text, node.open, found, self._runs)
                )
            )
        ):
            end = self._glued_page(text, node.close + 1)
            printed = _printed(f"{names} {text[node.open : end]}")
            reason = f'year of the citation "{printed}" is not read; the names stay (TP-04)'
            start, end = self._with_space(text, node.open, end)
            return [(start, end, EditKind.REMOVE, "", reason)]
        if _FULL_STOP_INSIDE.search(inside) and not self._starts_sentence(text, node.open):
            return None  # "It holds (Smith, 2019.)": its full stop ends the sentence outside
        parts = self._parts(text, node)
        named = [part for part in parts or () if self._is_citation(text, part)]
        cited = self._cited(text, parts or [], named)
        if not cited or not all(cited):
            whole = self._cited_once_inner_citations_go(text, node, decided)
            if whole is not None:
                return whole
        if parts is None:
            return None
        if not any(cited):
            return None
        if all(cited):
            end = self._glued_page(text, node.close + 1)
            names = [self._part_authors(text, part) for part in named]
            if self._is_subject(text, node.open, end):
                return self._subject(text, node, names, end, "is the subject of the sentence")
            if self._previous_word(text, node.open) in self.words.nouns:
                return self._subject(text, node, names, end, "is part of the sentence")
            return [self._removed(text, node.open, end, "citation")]
        return self._mixed(text, node, parts, cited)

    def _identifiers_only(
        self, text: str, node: _Bracket, decided: dict[int, list[_Found] | None]
    ) -> bool:
        """True if a bracket holds only identifiers, as read once its inner brackets' edits
        are made: "(527794 (Smith, 2019))" is "(527794)" then, which a second run removes
        (#285 review round 2). A bracket with inner brackets is read only if its own text,
        outside them, has a run of five digits, so a deep nest costs no more than before
        (#313)."""
        if not node.children:
            return bool(self.identifiers.match(text, node.open + 1, node.close))
        own = text[node.open + 1 : node.children[0].open] + "".join(
            text[before.close + 1 : after.open]
            for before, after in itertools.pairwise([*node.children, _Bracket(node.close, 0)])
        )
        return bool(_FIVE_DIGITS.search(own)) and bool(
            self.identifiers.match(self._read_inside(text, node, decided))
        )

    def _lead_around_gone(
        self, text: str, node: _Bracket, decided: dict[int, list[_Found] | None]
    ) -> bool:
        """True if a bracket holds only lead words besides inner brackets that go whole:
        "(see (see (527794)))" is "(see)" once the inner ones go, which a second run removes;
        judged inner first, so a nest of them goes in one look (#305, D-577). Only the
        bracket's own text is read, so a deep nest costs linear time (#313)."""
        if not node.children:
            return False
        own = text[node.open + 1 : node.children[0].open] + "".join(
            text[before.close + 1 : after.open]
            for before, after in itertools.pairwise([*node.children, _Bracket(node.close, 0)])
        )
        if len(own) > _LOOK_BACK or not self._only_lead_left(own):
            return False
        return all(
            any(
                kind is EditKind.REMOVE and start <= child.open and child.close < end
                for start, end, kind, *_ in decided.get(child.open) or ()
            )
            for child in node.children
        )

    @staticmethod
    def _read_inside(text: str, node: _Bracket, decided: dict[int, list[_Found] | None]) -> str:
        """A bracket's inside as read once its inner brackets' edits are made, each reading
        written into its own span; "" if an inner bracket stays or an edit does not fit."""
        inside = list(text[node.open + 1 : node.close])
        for child in node.children:
            edits = decided.get(child.open)
            if not edits:
                return ""
            for start, end, _kind, replacement, _reason in edits:
                if start <= node.open or end > node.close or len(replacement) > end - start:
                    return ""
                inside[start - node.open - 1 : end - node.open - 1] = replacement.ljust(end - start)
        return "".join(inside)

    def _cited(
        self, text: str, parts: list[tuple[int, int]], named: list[tuple[int, int]]
    ) -> list[bool]:
        """Which parts go as citations: those `named`, and next to them identifiers ("(Smith,
        2019; 527794)"), as a second run, seeing "(527794)", would remove those (#285 review
        round 1)."""
        cited = set(named)
        return [
            part in cited or (bool(cited) and bool(self.identifiers.match(text, *part)))
            for part in parts
        ]

    def _only_lead_left(self, inside: str) -> bool:
        """True if a bracket's inside is only lead words ("see", "e.g.,", "vgl.") and
        punctuation, or nothing."""
        words = _PUNCTUATION_ONLY.sub(" ", inside.lower()).split()
        return " ".join(words) in self.lead_only

    def _cited_once_inner_citations_go(
        self, text: str, node: _Bracket, decided: dict[int, list[_Found] | None]
    ) -> list[_Found] | None:
        """The bracket as one citation if it is one as a second run sees it, once the
        citations in its own inner brackets, round or square, are read: "((Müller, 2019)
        Schmidt, 2020)" is "( Schmidt, 2020)" then, and "(vgl. (Müller, 2019) Schmidt, 2020)"
        is "(vgl. Müller Schmidt, 2020)", so both runs remove it whole; a bracket left empty
        ("((Müller, 2019))") goes too (#271). A separator that an inner removal leaves at the
        bracket's edge, or after its lead words, goes with it as the #305 rule takes it along:
        "((Smith, 2019), Lee, 2020)" is "(Lee, 2020)", so a nest of any depth is decided inner
        first in one look (D-588)."""
        inner = node.children
        if not inner:
            return None
        edits = sorted(edit for child in inner for edit in decided.get(child.open) or ())
        starts = [start for start, *_ in edits]
        years = self._years_after_inner_names(text, inner, decided, edits, starts)
        for child in inner:
            at = bisect.bisect_right(starts, child.open) - 1
            if child.open in years:
                continue  # read as printed, after the names: "(see Smith (2019))"
            if not decided.get(child.open) and not (at >= 0 and child.close < edits[at][1]):
                # an inner bracket that stays as printed: no citation around it; one inside a
                # sibling's edit ("(Smith, 2019)[p. 4]") goes with that sibling
                return None
        read = _Read.of(text, node, edits)
        if read is None:
            return None  # an inner edit before the look-back, or the nest is too long
        end = self._glued_page(text, node.close + 1)
        subject = self._is_subject(text, node.open, end)
        role = "is the subject of the sentence" if subject else "is part of the sentence"
        if (subject or self._previous_word(text, node.open) in self.words.nouns) and (
            self._only_items(text, node)
        ):
            # a bracket of inner citations only, besides lead words, separators and a year
            # shell's year, names every one of them, as the flat form does: "((Smith, 2019)
            # (Lee, 2018)) is cited", "(see (Smith, 2019); (Lee, 2018)) is cited" and
            # "((Smith, 2019) 2021) is cited" (#415, D-791; "((Smith, 2019)) is cited" read
            # "is cited." before, D-605)
            listed = self._listed_inner_names(text, node, decided)
            if len(listed) == len(inner):
                names = sorted(name for _, child_names in listed for name in child_names)
                taken = {edit for child, _ in listed for edit in decided.get(child.open) or ()}
                kept = [edit for edit in edits if edit not in taken]
                return self._with_inner(self._subject(text, node, names, end, role), kept)
        self._separators_left(text, node, read)
        names = None
        rest = read.text[read.open + 1 : read.close]
        if rest.strip() and not (self._year_shell(text, node) and _YEAR_ONLY.fullmatch(rest)):
            local = _Bracket(read.open, read.close)
            parts = self._parts(read.text, local)
            named = [part for part in parts or () if self._is_citation(read.text, part)]
            if not parts or not all(self._cited(read.text, parts, named)):
                return None
            names = [
                (read.printed(start), read.printed(end - 1) + 1)
                for start, end in (self._part_authors(read.text, part) for part in named)
            ]
        if subject or self._previous_word(text, node.open) in self.words.nouns:
            # "((Smith, 2019) Jones, 2020) is cited" reads "Jones is cited" on both runs; an
            # inner citation listed with the others keeps its names, as in the flat form:
            # "((Smith, 2019); Jones, 2020) is cited" reads "Smith and Jones" (#278, D-605),
            # and so does every inner citation of the list: "((Smith, 2019); (Lee, 2018))
            # is cited" reads "Smith and Lee" (#372, D-668)
            listed = self._listed_inner_names(text, node, decided)
            if names is None and len(listed) < len(node.children):
                return None  # "((Smith, 2019)) is cited": nothing left to name, as before
            if listed:
                names = sorted(
                    [name for _, child_names in listed for name in child_names] + (names or [])
                )
                # the listed brackets' own removals give way to the names' edits
                taken = {edit for child, _ in listed for edit in decided.get(child.open) or ()}
                edits = [edit for edit in edits if edit not in taken]
            return self._with_inner(self._subject(text, node, names, end, role), edits)
        return [self._removed(text, node.open, end, "citation")]

    def _listed_inner_names(
        self, text: str, node: _Bracket, decided: dict[int, list[_Found] | None]
    ) -> list[tuple[_Bracket, list[tuple[int, int]]]]:
        """The inner brackets that are items of the bracket's list and are citations as a
        whole, each with its names' spans: "((Smith, 2019); (Lee, 2018); Jones, 2020)" lists
        the two first ones, "(Jones, 2020; (Smith, 2019))" the last one (#278, #372). An item
        is set off on each side by ";" or "," (maybe with a join word after it: "; and"), by
        the bracket's edge or by white space before another item ("((Smith, 2019) (Lee,
        2018))"), and the first item maybe by lead words ("(see (Smith, 2019); (Lee, 2018))",
        #415, D-791); any other inner bracket ("((Smith, 2019) Jones, 2020)") is not listed
        and reads as before. In a year shell the year counts as the edge (#375)."""
        listed = []
        bounds = [node.open, *(i for child in node.children for i in (child.open, child.close))]
        bounds.append(node.children[-1].close + 1 if self._year_shell(text, node) else node.close)
        for number, child in enumerate(node.children):
            before = text[bounds[2 * number] + 1 : child.open]
            after = text[child.close + 1 : bounds[2 * number + 3]]
            ahead = self.item_after.match(after) is not None or not after.strip()
            # or the bracket's edge, or lead words: before the first item ("(see (Smith, 2019);
            # (Lee, 2018))"); before a later one they make no list, as the rest's parts then
            # hold "see"
            behind = self.item_before.search(before) is not None or self._only_lead_left(before)
            if not (ahead and behind):
                continue
            if not decided.get(child.open):
                continue
            parts = self._parts(text, child)
            named = [part for part in parts or () if self._is_citation(text, part)]
            if not parts or len(named) != len(parts):
                continue
            listed.append((child, [self._part_authors(text, part) for part in named]))
        return listed

    @staticmethod
    def _year_shell(text: str, node: _Bracket) -> bool:
        """True if the bracket is a year shell around inner brackets: "((Smith, 2019); (Lee,
        2020) 2021)" is "( 2021)" once they go, so it goes with them; as the subject, it names
        them all (#375, D-668), and so it does around one: "((Smith, 2019) 2021) is cited"
        reads "Smith is cited" (#415, D-791). As an aside, one inner bracket in a year shell
        goes whole, as in `_shells` (#339)."""
        if not node.children:
            return False
        return _SHELL_YEAR.fullmatch(text, node.children[-1].close + 1, node.close + 1) is not None

    def _only_items(self, text: str, node: _Bracket) -> bool:
        """True if a bracket's own text, outside its inner brackets, is only lead words at its
        start, separators between them ("; and"), and a year shell's year at its end (#415).
        Only the bracket's own text is read, which no other bracket's look reads, so a deep
        nest costs linear time (#313, D-599)."""
        if not node.children:
            return False
        last = node.close
        if self._year_shell(text, node):
            last = node.children[-1].close + 1
        gaps = [text[node.open + 1 : node.children[0].open]] + [
            text[before.close + 1 : after.open]
            for before, after in itertools.pairwise(node.children)
        ]
        gaps.append(text[node.children[-1].close + 1 : last])
        if gaps[0].strip() and not self._only_lead_left(gaps[0]):
            return False
        return all(
            not gap.strip() or self.item_separator.fullmatch(gap) is not None for gap in gaps[1:]
        )

    def _years_after_inner_names(
        self,
        text: str,
        inner: list[_Bracket],
        decided: dict[int, list[_Found] | None],
        edits: list[_Found],
        starts: list[int],
    ) -> set[int]:
        """The inner brackets of years that follow a name once the inner edits before them are
        made: "(see (Smith, 2019) (2019))" is "(see Smith (2019))" then, which a second run
        decides as one citation; read so in this look, a nest of them is decided inner first
        (#330 review round 2, D-599). `edits` are sorted and apart, `starts` theirs; only the
        look-back before each bracket is read."""
        years = set()
        for child in inner:
            if decided.get(child.open) or not self.years_only.match(
                text[child.open + 1 : child.close]
            ):
                continue
            last = bisect.bisect_left(starts, child.open)
            if not last or edits[last - 1][1] > child.open:
                continue  # no inner edit before it, or one around it
            # the look-back as a second run reads it, gathered back from the bracket across
            # the edits before it; a few edits at most, so each bracket costs constant time
            pieces, right, size = [], child.open, 0
            for start, end, _kind, replacement, _reason in reversed(
                edits[max(0, last - _EDITS_LOOKED_BACK) : last]
            ):
                kept = text[max(end, right - _LOOK_BACK + size) : right]
                pieces += [kept, replacement]
                size += len(kept) + len(replacement)
                right = start
                if size >= _LOOK_BACK:
                    break
            else:
                pieces.append(text[max(0, right - _LOOK_BACK + size) : right])
            read = "".join(reversed(pieces))[-_LOOK_BACK:]
            if self._names_before(read, len(read)):
                years.add(child.open)
        return years

    def _separators_left(self, text: str, node: _Bracket, read: _Read) -> None:
        """Blank, in `read`, a separator that an inner removal leaves hanging at the bracket's
        start, after its lead words, or at its end (D-588): "((Smith, 2019), Lee, 2020)" and
        "(Lee, 2020; (Smith, 2019))" are "(Lee, 2020)" then; so does a run of such removals
        (#372)."""
        removed = read.removals
        if not removed:
            return
        last = node.close  # after the last printed character inside
        while last > node.open + 1 and text[last - 1].isspace():
            last -= 1
        for number, (start, _end, at) in enumerate(removed):
            if start <= node.open + 1 or self.lead_before.fullmatch(text, node.open, start):
                # a run of removals set off by separators leaves each of them hanging:
                # "((Smith, 2019); (Lee, 2018); Jones, 2020)" is "(Jones, 2020)" (#372)
                for _start, _end, next_at in removed[number + 1 :]:
                    hung = self.hung_ahead.match(read.text, at + 1, read.close)
                    if not hung or read.text[hung.end() : next_at].strip():
                        break
                    read.blank(hung.start(), hung.end())
                    at = next_at
                if hung := self.hung_ahead.match(read.text, at + 1, read.close):
                    read.blank(hung.start(), hung.end())
                break
        kept = re.compile(r"\s*").match(read.text, read.open + 1).end()  # the first kept item
        for _start, _end, at in removed:
            # one between two items: "(Jones, 2020; (Smith, 2019); Kim, 2017)" is "(Jones,
            # 2020; Kim, 2017)" then (#372); each look reads only the few characters around
            behind = self.hung_behind.search(read.text, max(read.open + 1, at - _HUNG), at)
            ahead = self.hung_ahead.match(read.text, at + 1, read.close)
            if behind and ahead and kept < behind.start():
                read.blank(ahead.start(), ahead.end())
        for number in range(len(removed) - 1, -1, -1):
            start, end, at = removed[number]
            if start < last <= end:
                for _start, _end, previous_at in reversed(removed[:number]):
                    hung = self.hung_behind.search(read.text, max(read.open + 1, at - _HUNG), at)
                    if not hung or read.text[previous_at + 1 : hung.start()].strip():
                        break
                    read.blank(hung.start(), hung.end())
                    at = previous_at
                if hung := self.hung_behind.search(read.text, read.open + 1, at):
                    read.blank(hung.start(), hung.end())
                break

    @staticmethod
    def _with_inner(outer: list[_Found], inner: list[_Found]) -> list[_Found] | None:
        """A nest's own edits and those of its inner brackets that stay in its kept names:
        "(see (Smith, 2019) and Lee, 2020) found it" keeps "Smith" of the inner bracket, so
        its ", 2019)" goes with the outer edits; an inner edit inside an outer one goes with
        it. None if two cross, so the nest stays as before (#279 review round 2)."""
        kept = []
        for edit in inner:
            if any(start <= edit[0] and edit[1] <= end for start, end, *_ in outer):
                continue
            if any(edit[0] < end and start < edit[1] for start, end, *_ in outer):
                return None
            kept.append(edit)
        return sorted(outer + kept)

    # numeric citations

    def _numeric(
        self, text: str, node: _Bracket, inside: str, at: int | None = None
    ) -> list[_Found] | None:
        """A square bracket of numbers; `at` is where it stands once the brackets before it
        that this look removes are gone ("(Smith, 2019)[12][12] it" is "[12] it" then, which
        a second run reads as the subject, #308, D-577)."""
        at = node.open if at is None else at
        keys = _keys(inside, self.keys)
        if keys is None and not _NUMERIC.match(inside) and self._paged(inside) is None:
            if self.page_only.match(inside) and re.search(
                r"[\"”’']\s*\Z", _before(text, node.open)
            ):
                return [self._removed(text, node.open, node.close + 1, "page reference")]
            return None
        # after removals that start with a space it stands where they stood, after that
        # space: "Lee (Smith, 2019)[12]" judges "[12]" as "Lee [12]" (#338, D-605)
        # ... and so it does after a removed link's bracket: "Text (see https://x.org)[12]"
        edge = at
        if at == node.open:
            kept = len(text[:at].rstrip())
            edge = self._link_starts.get(kept, self._link_starts.get(at, at))
        glued = (
            "" if edge < node.open and text[edge : edge + 1].isspace() else text[edge - 1 : edge]
        )
        if glued and (glued.isalnum() or glued in ")]"):
            return None
        if _NUMBER_GLUED_AFTER.match(text, node.close + 1):
            return None  # "[1; 3],1": read "3,1" would be a decimal on a second run
        if self._decimal_interval(inside):
            return None  # "[1,2; 3,4]": two German decimals, an interval, not sources
        if self._not_citations(text, node.open):
            return None
        if node.open in self._paired:
            return []  # a later bracket of a list: decided with the first (#257, #414)
        self._numbered.add(node.open)
        # a list of brackets is one citation, decided here at its first: "[1], [2] and [3]"
        listed = self._list(node)
        end = node.close + 1
        if listed is not None:
            end = listed[-1].close + 1
            inside = ", ".join(text[item.open + 1 : item.close] for item in [node, *listed])
        window = max(0, node.open - _LOOK_BACK)
        # judged on the words before it as a second run sees them, past the removals
        before = text[window : min(edge, node.open)].rstrip()
        previous = before.split()[-1] if before.split() else ""
        printed = _printed(text[node.open : end])
        word = re.sub(r"\A\W*\d*", "", previous).lower()  # "8See" -> "see", "(see" -> "see"
        start = node.open
        if previous.lower() in self.words.refs or previous in self.words.ref_words:
            start = window + len(before) - len(previous)
            if edge < node.open:
                # "Ref. (see https://x.org) [3, 4]": the reading takes the place of "Ref." and
                # the bracket goes, so neither edit crosses the removal between them
                return self._read_at_ref_word(
                    text, node.open, end, inside, start, start + len(previous)
                )
            printed = _printed(text[start:end])
        elif (
            word not in self.words.before
            or any(before.lower().endswith(aside) for aside in self.words.asides)
        ) and not self._is_subject(text, at, end):
            if listed is not None and self._needed_pair(text, node, listed):
                # an aside joined by "and" to a second bracket, which the "and" makes needed:
                # both are needed, read as one ("between [1] and [3]" is "between references
                # 1 and 3", #257, D-668); an aside starts no sentence
                spoken = self._spoken(inside)
                reason = (
                    f'citations "{printed}" are part of the sentence: read as "{spoken}" (TP-04)'
                )
                return [(node.open, end, EditKind.REPLACE, spoken, reason)]
            what = "citation key" if keys else "numeric citation"
            if listed is not None:
                # an aside list goes whole, as one bracket "[1–3]" does (#414, D-791)
                what = "list of citation keys" if keys else "list of numeric citations"
            return [self._removed(text, node.open, end, what)]
        spoken = self._spoken(inside)
        if before.endswith("("):  # "( [53] discusses": no space after the bracket
            start = window + len(before)
        if self._starts_sentence(text, at if start == node.open else start):
            spoken = spoken[0].upper() + spoken[1:]
        reason = f'citation "{printed}" is part of the sentence: read as "{spoken}" (TP-04)'
        if edge < node.open and not text[start - 1 : start].isspace():
            spoken = " " + spoken  # the removal before took the space: "and (Smith, 2019)[12]"
        return [(start, end, EditKind.REPLACE, spoken, reason)]

    def _bracket_lists(self, text: str, roots: list[_Bracket]) -> dict[int, list[_Bracket]]:
        """The lists of square brackets in this look, each by its first bracket's opening: its
        later brackets (#257, D-668; #414, D-791).

        A list is a run of two or more square brackets of one kind (whole numbers, lists and
        ranges, or listed keys; no page, no German decimal interval) set off only by "," and
        "and": "[1], [2] and [3]", "[1, 2], [3]", "[MH17], [Fa14] and [Ka20]", and "[1] and [2],
        [3]" too (read "references 1 and 2, here" bracket by bracket before).
        A later bracket that a number is glued after ends the run before it. Whether the
        brackets are citations at all (no interval, no label's number) is decided at the first
        one in `_numeric`, as for one bracket: with only "," and "and" between them, a later
        bracket is an interval only after an interval ("CIs [1, 3], [2, 4]"), and a label word
        or sign stands only before the first (no counterexample in 8,000 random texts,
        `plans/b9-mutants/search_414h.py`). A run joined on by "or" to a further bracket
        ("[1], [2] or [3]") is no list, so its brackets read as before (#414). One pass over the
        square brackets in text order, each gap read once, so a block of n brackets costs O(n)."""
        squares: list[_Bracket] = []
        stack = list(roots)
        while stack:
            node = stack.pop()
            if text[node.open] == "[":
                squares.append(node)
            stack += node.children
        squares.sort(key=lambda node: node.open)
        lists: dict[int, list[_Bracket]] = {}
        first = 0
        while first < len(squares):
            head, last = squares[first], first
            kind = self._item_kind(text, head)
            while kind is not None and last + 1 < len(squares):
                ahead = squares[last + 1]
                gap = self.list_gap.fullmatch(text, squares[last].close + 1, ahead.open)
                if (
                    gap is None
                    or self._item_kind(text, ahead) != kind
                    or _NUMBER_GLUED_AFTER.match(text, ahead.close + 1)
                ):
                    break
                last += 1
            if last > first and not self.or_after.match(text, squares[last].close + 1):
                lists[head.open] = squares[first + 1 : last + 1]
            first = last + 1
        return lists

    def _item_kind(self, text: str, node: _Bracket) -> str | None:
        """What a square bracket holds as an item of a list: "numbers", "keys" or None."""
        inside = text[node.open + 1 : node.close]
        if self._decimal_interval(inside):
            return None
        if _keys(inside, self.keys) is not None:
            return "keys"
        return "numbers" if _NUMERIC.match(inside) else None

    def _list(self, node: _Bracket) -> list[_Bracket] | None:
        """The list that starts at `node`, its later brackets now taken along, or None if it
        starts no list. Siblings are decided left to right (`_visit`), so no later bracket of
        a list is decided before its first (never in 10,000 random texts,
        `plans/b9-mutants/search_414k.py`)."""
        found = self._lists.get(node.open)
        if found is None:
            return None
        self._paired.update(item.open for item in found)
        return found

    def _needed_pair(self, text: str, node: _Bracket, listed: list[_Bracket]) -> bool:
        """True for a list of two brackets joined by "and", when "and" makes a citation after
        it needed: then the first is needed too (#257, D-668)."""
        if len(listed) != 1 or self.words.and_word not in self.words.before:
            return False
        gap = self.list_gap.fullmatch(text, node.close + 1, listed[0].open)
        return gap is not None and gap["join"] is not None

    def _paged(self, inside: str) -> tuple[str, str] | None:
        """One source and its page, as the source and the page's reading: "12, p. 3" is "12"
        and "page 3", "12, S. 3–5" "12" and "Seiten 3 bis 5" (#257, D-668)."""
        match = self.paged.match(inside)
        if match is None:
            return None
        source = match["source"]
        if not _NUMERIC.match(source) and _keys(source, self.keys) is None:
            return None
        page, pages = self.words.page_words
        if match["last"]:
            return source, f"{pages} {match['first']} {self.wording.range_to} {match['last']}"
        return source, f"{page} {match['first']}"

    def _read_at_ref_word(
        self, text: str, opening: int, closed: int, inside: str, start: int, end: int
    ) -> list[_Found]:
        """A numeric citation (or a list of them, from `opening` to `closed`) after its
        reference word with a removal between them: the reading in place of the word, the
        brackets removed."""
        spoken = self._spoken(inside)
        if self._starts_sentence(text, start):
            spoken = spoken[0].upper() + spoken[1:]
        printed = _printed(text[start:end] + " " + text[opening:closed])
        reason = f'citation "{printed}" is part of the sentence: read as "{spoken}" (TP-04)'
        return [
            (start, end, EditKind.REPLACE, spoken, reason),
            (opening, closed, EditKind.REMOVE, "", reason),
        ]

    def _decimal_interval(self, inside: str) -> bool:
        """True if a square bracket holding `inside` is a German interval of decimals
        ("1,2; 3,4"), not sources (#101)."""
        return self.language == "de" and ";" in inside and bool(_DECIMAL_COMMA.search(inside))

    def _not_citations(self, text: str, position: int) -> bool:
        """True if the square bracket at `position` holds an interval or a label's number, not
        citations: after a maths sign, a maths word ("CI", "CI:", "CIs", D-450), a label word
        ("Eq.") or a percentage, or where the statistics step reads a confidence interval
        joined on to one ("CIs [1, 3] and [2, 4]", #151): only a pair it reads, so "CI [1, 3]
        and [12]" still cites reference 12."""
        before = text[max(0, position - _LOOK_BACK) : position].rstrip()
        previous = before.split()[-1] if before.split() else ""
        if self.said_sign.search(before):
            return True
        if previous and (
            previous[-1] in _MATHS_SIGNS
            or previous.lower().rstrip(":") in self.words.maths
            # "95 %-KI [1; 3]": the word after a hyphen
            or previous.lower().rstrip(":").rsplit("-", 1)[-1] in self.words.maths
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
        """The reading of a needed citation: "references 53 and 58", "Quelle MH17" (a key as
        printed, D-646); with its page: "reference 12, page 3" (#257, D-668)."""
        paged = self._paged(inside)
        if paged is not None:
            return f"{self._spoken(paged[0])}, {paged[1]}"
        keys = _keys(inside, self.keys)
        items = list(keys or ())
        single = True
        for match in () if keys else _ITEMS.finditer(inside):
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
            if number and not text[start + 1 : end].strip():
                continue  # an empty part: "(Jones, 2020; ; Smith, 2019)" lists two (#415)
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
        if match is None or not _no_period(piece):
            return False
        # an acronym is an author only right before ", 2020" ("(WHO, 2020)", not "BERT (") or
        # with a page after the year ("(WBGU 2011, S. 1)", #455); "(EU 2016)" stays as printed
        after = piece[match.end("authors") :]
        if self._dated_period(text, part, piece, match):
            return False
        acronym = after.lstrip().startswith(",") or self.page_after.search(after) is not None
        return self._names_ok(match.group("authors"), acronym)

    def _dated_period(
        self, text: str, part: tuple[int, int], piece: str, match: re.Match[str]
    ) -> bool:
        """True for a bracket that is only a season, term or the like and a year: "(Sommer
        2019)", "(Wintersemester 2019)", "(Ausgabe 2018)" (#483)."""
        return (
            match["authors"].lower() in self.words.periods
            and not piece[: match.start("authors")].strip()
            and _PLAIN_YEAR.fullmatch(piece, match.end("authors")) is not None
            and text[part[0] - 1 : part[0]] == "("
            and text[part[1] : part[1] + 1] == ")"
        )

    def _names_ok(self, authors: str, acronym: bool) -> bool:
        tokens = [
            token.rstrip(",")
            for token in re.split(r"\s+|(?<=,)|/", authors.replace("-\n", "-"))
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
        # as read: a soft hyphen or zero-width space hides no name ("Ft\u00adt (1998)"), as
        # the Unicode step drops it and a second run sees "Ftt (1998)" (#253)
        bare = "".join(c for c in bare if c not in INVISIBLE and c != SOFT_HYPHEN)
        if not (_is_name(bare) or re.fullmatch(r"[A-Z]{2,6}", bare)):
            return ""
        if self.language == "de" and bare in READ_WORDS:
            return ""  # "χ² (1998)" reads "Chi-Quadrat (1998)": no author's name
        # "Sag and Hankamer (1984)": the reason names both authors
        pair = self.pair_end.search(before)
        if pair and _is_name(pair.group(1)):
            return _printed(pair.group())
        # "the Olympics (2016)": after an article the word names a thing, not an author
        # (D-448, #110); "et al." or a second author (above) still make it a citation
        article = re.search(r"(\S+)\s+\Z", before[: found.start()])
        if article and article.group(1).lower() in self.words.articles:
            return ""
        if self.words.name_leads is not None and not self._led_to_a_name(before[: found.start()]):
            return ""
        return joined

    def _led_to_a_name(self, before: str) -> bool:
        """For a language that capitalises nouns: True if the words before a capital word
        lead to a name ("wie Müller", "von Anna Müller", a sentence start), not to a noun
        ("die neue Studie", "Die Olympischen Spiele")."""
        before = before[-_LOOK_BACK:]
        words = without_links(before, self.language).split()[-3:]  # a link is no word here
        while words and _is_name(words[-1]) and words[-1].lower() not in self.words.articles:
            words.pop()  # a first name or another capital word: "Anna Müller"
        if not words:
            return True
        head = before
        for _ in range(len(without_links(before, self.language).split()[-3:]) - len(words)):
            head = re.sub(r"\S+\s*\Z", "", head)
        if only_links_before(head, len(head), self.language):
            return True  # "https://x.org Müller (2019)" starts with the name once the link goes
        word = words[-1].lower()
        leads = self.words.name_leads or frozenset()
        if word in self.words.articles:
            return False
        if word in leads or not word[-1:].isalpha():
            return True  # "laut Müller", "(Müller", "Ergebnis: Müller"
        return not re.search(r"(?:e|en|er|es|em)\Z", word)  # "neue", "seiner", ...

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
        self, text: str, node: _Bracket, names: list[tuple[int, int]], end: int, role: str
    ) -> list[_Found]:
        """A citation the sentence needs ("(Dasigi et al., 2019) note", "such as (Qin et al.,
        2022) could"): keep its names (spans of `text`), remove the rest (TP-04)."""
        printed = _printed(text[node.open : end])
        reason = f'citation "{printed}" {role}: only its names are read (TP-04)'
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
        if end - start > _MAX_BRACKET + 2:
            # a nest longer than any bracket the step parses, decided inner first (D-588):
            # its ends name it, so a deep nest costs linear time
            printed = f"{_printed(text[start : start + 60])} … {_printed(text[end - 60 : end])}"
        else:
            printed = _printed(text[start:end])
        reason = f'{what} "{printed}" is not read (TP-03)'
        start, end = self._with_space(text, start, end)
        return (start, end, EditKind.REMOVE, "", reason)

    def _with_space(self, text: str, start: int, end: int) -> tuple[int, int]:
        """Take the white space before the removal along, or after it at the start of a block.

        At the start of a sentence the punctuation after it goes instead: "It holds. (Smith,
        2019). Then" reads "It holds. Then", not "It holds.. Then".
        """
        if self._starts_sentence(text, start) or only_links_before(text, start, self.language):
            punctuation = _AFTER_START.match(text, end)
            if punctuation and only_links_after(text, end, self.language):
                return start, end  # the links' removal takes the punctuation before them
            if punctuation:
                stop = punctuation.end()
                if text[stop - 1].isspace() and only_links_after(text, stop, self.language):
                    # "(Müller, o. J.). https://x.org)": the link takes the space before it
                    stop = end + len(punctuation.group().rstrip())
                return start, stop
            # the white space before belongs to the sentence before, which another step may
            # have removed with it ("https://x.org. [1; 3],1", #101): take the space after
            if start > 0:
                after = _SPACE.match(text, end)
                return start, after.end() if after else end
        return _with_space(text, start, end)


_IDENTIFIER_REASON = "identifier"  # how an identifier's removal starts its reason


def _pairs(roots: list[_Bracket]) -> dict[int, int]:
    """Each matched bracket's opening mapped to its closing, and its closing to its opening."""
    pairs, stack = {}, list(roots)
    while stack:
        node = stack.pop()
        pairs[node.open], pairs[node.close] = node.close, node.open
        stack += node.children
    return pairs


def _keeps_text(found: list[_Found], node: _Bracket) -> bool:
    """True if `found` are edits of the bracket that keep some of its text (its names)."""
    return bool(found) and not (
        len(found) == 1 and found[0][0] <= node.open and node.close < found[0][1]
    )


def _adjacent(text: str, end: int, position: int) -> bool:
    """True if only white space stands between `end` and `position`."""
    return end <= position and not text[end:position].strip()


def _before_removals(
    text: str, position: int, found: Sequence[_Found], runs: dict[int, int]
) -> int:
    """`position` moved back over the removals right before it that this look already
    made: "Lee (2019a) (2019b)" judges "(2019b)" after "Lee", as a second run sees it, so a
    row of year brackets goes in one look (#308, D-577). `found` holds the edits of the
    brackets before, in text order; `runs` remembers where a run of removals that ends at a
    position starts, so a long row costs linear time."""
    passed = []
    for start, end, kind, *_ in reversed(found):
        if end > position:
            continue
        if kind is not EditKind.REMOVE or text[end:position].strip():
            break
        passed.append(end)
        if end in runs:
            position = runs[end]
            break
        position = start
    for end in passed:
        runs[end] = position
    return position


def _cut_inside(cuts: Sequence[int], node: _Bracket) -> bool:
    """True if a removed identifier stood inside the bracket (`cuts` are sorted)."""
    at = bisect.bisect_right(cuts, node.open)
    return at < len(cuts) and cuts[at] <= node.close


def _without(text: str, gone: Sequence[tuple[int, int]]) -> tuple[str, _Cuts]:
    """The text without the removed spans (sorted, apart), and where the removals stood in
    it."""
    pieces, at, total, starts, cursor = [], [], [], [], 0
    for start, end in gone:
        pieces.append(text[cursor:start])
        starts.append(start)
        at.append(start - (total[-1] if total else 0))
        total.append((total[-1] if total else 0) + end - start)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), _Cuts(at, total, starts)


class _Read:
    """A bracket as read once its inner edits are made, with the look-back before it: a
    removal is one space, a reading is written in (padded to its span if shorter; each piece
    keeps its own place, so a longer one shifts nothing). Built from the bracket's own
    text, so a nest of any depth costs linear time (D-588)."""

    def __init__(self) -> None:
        self.text = ""
        self.open = 0  # the opening bracket in `text`
        self.close = 0  # the closing bracket in `text`
        self.starts: list[int] = []  # where each piece starts in `text`
        self.origins: list[int] = []  # ... and in the printed text
        self.removals: list[tuple[int, int, int]] = []  # printed start, end; place in `text`

    @classmethod
    def of(cls, text: str, node: _Bracket, edits: list[_Found]) -> _Read | None:
        read, pieces = cls(), []
        cursor = max(0, node.open - _LOOK_BACK)
        size = 0
        for start, end, _kind, replacement, _reason in edits:
            if start < cursor:
                return None  # an edit that starts before the look-back: not read here
            edited = replacement.ljust(end - start) if replacement else " "
            for origin, piece in ((cursor, text[cursor:start]), (start, edited)):
                if origin == start and piece is edited and not replacement:
                    read.removals.append((start, end, size))
                read.starts.append(size)
                read.origins.append(origin)
                pieces.append(piece)
                size += len(piece)
            cursor = end
        read.starts.append(size)
        read.origins.append(cursor)
        pieces.append(text[cursor : node.close + 1])
        read.text = "".join(pieces)
        read.open = node.open - max(0, node.open - _LOOK_BACK)
        read.close = len(read.text) - 1
        if read.close - read.open - 1 > _MAX_BRACKET:
            return None
        return read

    def printed(self, position: int) -> int:
        """A position of `text` in the printed text (a removal's space: its start)."""
        piece = bisect.bisect_right(self.starts, position) - 1
        return self.origins[piece] + position - self.starts[piece]

    def blank(self, start: int, end: int) -> None:
        self.text = self.text[:start] + " " * (end - start) + self.text[end:]


class _Rewrite:
    """A text with edits made (sorted, apart: start, end, replacement), and how a position in
    it maps back to the printed text."""

    def __init__(self, printed: str, edits: list[tuple[int, int, str]]) -> None:
        pieces, cursor, shift = [], 0, 0
        self.at: list[int] = []  # where each edit's reading starts in the new text
        self.size: list[int] = []  # how long the reading is
        self.span: list[tuple[int, int]] = []  # the printed span it replaces
        self.text: str | None = None
        for start, end, replacement in edits:
            if start < cursor:
                return  # overlapping edits: no text
            pieces += [printed[cursor:start], replacement]
            self.at.append(start - shift)
            self.size.append(len(replacement))
            self.span.append((start, end))
            shift += end - start - len(replacement)
            cursor = end
        pieces.append(printed[cursor:])
        self.text = "".join(pieces)

    def printed(self, position: int, start: bool) -> int | None:
        """A position of the new text in the printed text; None inside a reading. An edit's
        start next to a removal lands after it, its end before it, so no edit holds part of
        one; next to a reading, outside it."""
        low = bisect.bisect_left(self.at, position)
        high = bisect.bisect_right(self.at, position)
        if low and self.at[low - 1] + self.size[low - 1] > position:
            return None  # inside the reading of an earlier edit
        before = position
        if low:
            end = self.span[low - 1][1]
            before = position + end - (self.at[low - 1] + self.size[low - 1])
        if not start or high == low:
            return before
        last = high - 1  # the edits that start here: removals, then maybe a reading
        return self.span[last][0] if self.size[last] else self.span[last][1]


_OPENS = {"(": ")", "[": "]"}
_SHELL_YEAR = re.compile(rf"\s+{_YEAR}\s*[)\]]")
_YEAR_ONLY = re.compile(rf"\s*{_YEAR}\s*")  # a year shell's inside once its citations go


def _shells(text: str, found: list[_Found]) -> list[_Found]:
    """Removals that leave nothing but the brackets around them take those brackets along,
    however many: "((((Müller 2019))))" goes whole in one look, as a second run would remove
    the empty brackets, and a nest deeper than the bracket cap costs no look per cap's depth
    (D-588). Only brackets and white space: a removal that keeps names ("(" of "(Smith,
    2019)" read "Smith") stands next to them, so it never meets an empty bracket. A bracket
    that holds the removal and a year after it is a year shell and goes too (#339)."""
    result: list[_Found] = []
    for number, (start, end, kind, replacement, reason) in enumerate(found):
        if kind is EditKind.REMOVE:
            low = result[-1][1] if result else 0
            high = found[number + 1][0] if number + 1 < len(found) else len(text)
            first, last = start, end
            while True:
                left, right = first, last
                while left > low and text[left - 1].isspace():
                    left -= 1
                while right < high and text[right].isspace():
                    right += 1
                if left > low and right < high and _OPENS.get(text[left - 1]) == text[right]:
                    first, last = left - 1, right + 1
                    continue
                # a year shell: "((Smith, 2019) 2020)" is "( 2020)" once the citation goes,
                # a bare year in brackets, so it goes with it, however deep (#339, D-605)
                shell = _SHELL_YEAR.match(text, last, high) if left > low else None
                if shell and _OPENS.get(text[left - 1]) == text[shell.end() - 1 : shell.end()]:
                    first, last = left - 1, shell.end()
                else:
                    break
            start, end = first, last
        result.append((start, end, kind, replacement, reason))
    return result


def _unsettled_as_printed(text: str, found: list[_Found], later: list[_Found]) -> list[_Found]:
    """The edits of the last look, but none in an outermost bracket where the two last looks
    differ: the work budget ran out before it settled, so it stays as printed (D-599)."""
    roots = brackets(text)
    opens = [root.open for root in roots]
    regions = []
    for start, end, *_ in sorted(set(found) ^ set(later)):
        low, high = start, max(end, start + 1)
        first = bisect.bisect_right(opens, start) - 1
        if first >= 0 and roots[first].close >= start:
            low = roots[first].open
        last = bisect.bisect_left(opens, high) - 1
        if last >= 0 and roots[last].close >= start:
            high = max(high, roots[last].close + 1)
        regions.append((low, high))
    regions = _joined(sorted(regions))
    lows = [low for low, _ in regions]
    kept = []
    for edit in later:
        at = bisect.bisect_right(lows, max(edit[0], edit[1] - 1)) - 1
        if at < 0 or regions[at][1] <= edit[0]:
            kept.append(edit)
    return kept


def _joined(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sorted spans with the ones that touch or overlap joined."""
    result: list[tuple[int, int]] = []
    for start, end in spans:
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        elif start < end:
            result.append((start, end))
    return result


def _around(links: list[tuple[int, int]], start: int, end: int) -> list[tuple[int, int]]:
    """The span from `start` to `end` without the (sorted) link spans inside it."""
    pieces, cursor = [], start
    at = bisect.bisect_left(links, (start, start))
    while at < len(links) and links[at][0] < end:
        if links[at][1] <= end:
            if cursor < links[at][0]:
                pieces.append((cursor, links[at][0]))
            cursor = max(cursor, links[at][1])
        at += 1
    if cursor < end:
        pieces.append((cursor, end))
    return pieces


def _merged(earlier: list[_Found], later: list[_Found]) -> list[_Found]:
    """The edits of two looks: a later edit wins and takes along the earlier ones inside it
    (both lists sorted, each without overlaps). A later edit never crosses an earlier one nor
    lies inside it: `_Rewrite.printed` puts its ends outside every removal and drops an edit
    that ends inside a reading (PR #330 review round 1, R1-4)."""
    ends = [end for _, end, *_ in earlier]
    inside = set()
    for start, end, *_ in later:
        at = bisect.bisect_right(ends, start)
        while at < len(earlier) and earlier[at][0] < end:
            inside.add(at)
            at += 1
    return sorted([edit for k, edit in enumerate(earlier) if k not in inside] + later)


@dataclass
class _Cuts:
    """Where removals stood in the text without them, and how much was removed up to and
    including each one."""

    at: list[int]
    total: list[int]
    starts: list[int]  # where each removal starts in the printed text

    def printed(self, position: int, start: bool) -> int:
        """A position in the text without removals as one in the printed text: an edit's
        start at a removal's place lands after it, its end before it, so no edit holds part
        of one."""
        index = (bisect.bisect_right if start else bisect.bisect_left)(self.at, position)
        return position + (self.total[index - 1] if index else 0)

    def read(self, position: int) -> int:
        """A printed position outside the removals as one in the text without them."""
        index = bisect.bisect_right(self.starts, position)
        return position - (self.total[index - 1] if index else 0)


def _covered(edits: list[_Found] | None, handled: list[_Found]) -> bool:
    """True if every edit is one of `handled` or lies inside one of them."""
    return bool(edits) and all(
        edit in handled or any(start <= edit[0] and edit[1] <= end for start, end, *_ in handled)
        for edit in edits or ()
    )


def _clear_of_links(text: str, found: list[_Found], links: list[tuple[int, int]]) -> list[_Found]:
    """Removals that leave to the links step the white space and punctuation its removals
    take: "https://x.org, (Smith, 2020)." or "(Smith, 2020), https://x.org." would otherwise
    have the citation's removal set aside, and a second run remove it (#101).

    An edit that still overlaps a link's span is left out: the links step runs first, so
    its edit would be set aside anyway, and the next look must see the text as a second run
    does, with the link gone and the citation still there. "Lee (see https://x.org/a(b)(Smith,
    2019)": the link takes "(Smith," and the next look reads "Lee (2019)" (D-630)."""
    if not links:
        return found
    starts = [start for start, _ in links]
    result = []
    for start, end, kind, replacement, reason in found:
        if kind is EditKind.REMOVE:
            at = bisect.bisect_right(starts, start) - 1
            if at >= 0 and start < links[at][1] and _UNREAD.fullmatch(text, start, links[at][1]):
                start = links[at][1]
            at = bisect.bisect_left(starts, end) - 1
            if (
                at >= 0
                and start <= links[at][0] < end <= links[at][1]
                and _UNREAD.fullmatch(text, links[at][0], end)
            ):
                end = links[at][0]
        at = bisect.bisect_left(starts, end) - 1
        if start < end and (at < 0 or links[at][1] <= start):
            result.append((start, end, kind, replacement, reason))
    return result


def _keys(inside: str, listed: frozenset[str]) -> list[str] | None:
    """The alphanumeric keys a square bracket holds ("MH17, Fa14"), or None if it holds
    anything else, a look-alike ("PM10") or a key no entry of the document prints (#254,
    D-646; review B1 of PR #377)."""
    if not _KEYS.match(inside):
        return None
    keys = _KEY_ITEMS.findall(inside)
    if any(key in KEY_LOOK_ALIKES or key not in listed for key in keys):
        return None
    return keys


# an entry's label at a line's start and its first author: "[MH17] Maass, M.: …", "[Knu84] D.
# Knuth. …" (#254, review B1 of PR #377); a sentence that starts with a key ("[MH17] zeigen
# das.") is no entry, or a second run would find its own key listed
_KEY_ENTRY = re.compile(
    rf"^\[({_KEY})\][ \t]+(?:[A-Z]\.(?:\s?-?[A-Z]\.)*\s?[A-Z][^\W\d_]|[A-Z][^\W\d_]+,\s[A-Z]\.)",
    re.MULTILINE,
)


def listed_keys(document: Document) -> frozenset[str]:
    """The keys the document prints as entry labels at a line's start, in any block."""
    return frozenset(
        match.group(1) for block in document.blocks for match in _KEY_ENTRY.finditer(block.text)
    )


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
