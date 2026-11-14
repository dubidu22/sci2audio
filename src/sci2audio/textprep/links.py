# ruff: noqa: RUF001  (dashes, quotes and symbols are meant as papers print them)
"""URLs, DOIs, arXiv identifiers and e-mail addresses are not read (TP-07, D-167 to D-170).

A voice spells a link character by character ("h t t p s colon slash slash ..."), which
buries the sentence. This step proposes one `remove` edit per run of neighbouring links
("https://a.org and www.b.org" is one run) and repairs the sentence around it, so no
"available at ." or "Contact:." is left (D-168). The first rule that applies decides what
goes with the run:

1. a bracket that holds only the run (and words like "see" or "available at") goes whole;
2. a label before it ("Contact:", "E-mail:", "Code:", ...) goes with it, and the whole
   sentence goes when the label starts it and the run ends it;
3. another colon right before it goes with it ("University of Oxford: https://...");
4. a preposition or verb right before it goes with it ("released at https://...");
5. otherwise only the run goes.

The white space before the removed text goes too (after it, at the start of a block). A
block that holds nothing but links, or a footnote that holds nothing but its mark and links,
loses its whole text in one edit, so no lone "Footnote 5." is read (#64's intro is set aside).

A URL broken at a line end continues on the next line when it ends in a character that
cannot end a URL, or in "." before a word that looks like the rest of an address (D-170);
after a character that cannot end a URL, a next-line word that is a common English word
with no character of an address ("and", "the") goes on the sentence instead (D-449, #109).
Every reason names the link as printed, without the line breaks inside it (D-175).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from functools import cache

from sci2audio.core import BlockKind, Document, Edit, EditKind, Span
from sci2audio.textprep.steps import Category, Stage, StepContext, TextStep

# blocks a placeholder notice or the furniture step already covers as a whole (D-128)
SKIPPED_KINDS = frozenset(
    {BlockKind.FURNITURE, BlockKind.TABLE, BlockKind.FORMULA, BlockKind.FIGURE}
)


@dataclass(frozen=True)
class LinkWords:
    """The words of one language that the sentence repair looks for, lower case."""

    labels: tuple[str, ...]  # "contact" in "Contact: j.doe@..."
    before: tuple[str, ...]  # prepositions and verbs that go with a link after them
    lead: tuple[str, ...]  # words that may stand with a link alone inside brackets
    joins: tuple[str, ...]  # words that join two links into one run
    introducers: tuple[str, ...]  # words before such a word in a bracket: "(found at ...)"
    pointers: tuple[str, ...]  # a sentence they start only points to the link: "See ... for"
    # common words that go on the sentence after a URL cut at a line end, never a path (#109)
    sentence_words: frozenset[str]
    purposes: frozenset[str]  # words that start a short purpose after a pointer: "for details"
    fillers: tuple[str, ...]  # words a pointer sentence may hold besides its links: "also"
    # words that open an access note going with the link before it: "(abgerufen am 3.5.2017)"
    access: tuple[str, ...] = ()


# Common English words that start the rest of a sentence, never a path segment (#109,
# D-449): after "https://x.org/" and a line break, "and more text" is the sentence again.
_SENTENCE_WORDS = frozenset((
    "a", "about", "after", "all", "also", "an", "and", "are", "as", "at", "be", "because",
    "been", "before", "being", "both", "but", "by", "can", "could", "did", "do", "does",
    "each", "either", "for", "from", "had", "has", "have", "he", "her", "here", "his", "how",
    "however", "i", "if", "in", "into", "is", "it", "its", "may", "might", "more", "most",
    "much", "must", "my", "neither", "no", "nor", "not", "now", "of", "on", "once", "only",
    "or", "other", "our", "she", "should", "since", "so", "some", "such", "than", "that",
    "the", "their", "them", "then", "there", "these", "they", "this", "those", "though",
    "thus", "to", "too", "under", "unless", "until", "up", "upon", "us", "was", "we", "were",
    "what", "when", "where", "whether", "which", "while", "who", "whom", "whose", "why",
    "will", "with", "within", "without", "would", "yet", "you", "your",
))  # fmt: skip

# ... and the German ones: "https://x.org/" cut at a line end, then "und mehr"
_SENTENCE_WORDS_DE = frozenset((
    "aber", "als", "also", "am", "an", "auch", "auf", "aus", "bei", "bis", "da", "dass", "dem",
    "den", "der", "des", "die", "dies", "diese", "diesem", "diesen", "dieser", "dieses",
    "doch", "dort", "durch", "ein", "eine", "einem", "einen", "einer", "eines", "er", "es",
    "für", "hat", "haben", "hier", "im", "in", "ist", "jedoch", "kann", "können", "man", "mit",
    "nach", "nicht", "noch", "nur", "ob", "oder", "sich", "sie", "sind", "so", "sowie", "um",
    "und", "unter", "vom", "von", "vor", "war", "waren", "weil", "welche", "wenn", "werden",
    "wie", "wir", "wird", "wurde", "wurden", "zu", "zudem", "zum", "zur", "über", "abrufbar",
    "erreichbar", "verfügbar", "zugänglich",
))  # fmt: skip

WORDS: dict[str, LinkWords] = {
    "en": LinkWords(
        labels=(
            "available at",
            "available from",
            "available online",
            "code",
            "contact",
            "correspondence",
            "corresponding author",
            "data",
            "doi",
            "e-mail",
            "email",
            "emails",
            "e-mails",
            "github",
            "home page",
            "homepage",
            "link",
            "links",
            "mail",
            "online",
            "project page",
            "project website",
            "repository",
            "software",
            "source code",
            "url",
            "urls",
            "web",
            "web page",
            "webpage",
            "website",
        ),
        before=(
            "at",
            "from",
            "on",
            "via",
            "in",
            "under",
            "to",
            "as",
            "see",
            "see also",
            "visit",
            "using",
            "through",
            "cf.",
            "here",
        ),
        lead=(
            "see also",
            "see",
            "cf.",
            "e.g.,",
            "e.g.",
            "at",
            "from",
            "via",
            "available at",
            "available from",
            "available online at",
            "online at",
            "online:",
            "url:",
            "doi:",
            "code:",
            "data:",
            "e-mail:",
            "email:",
            "website:",
        ),
        joins=(",", ";", "/", "and", "or", "&", ", and", ", or"),
        introducers=(
            "accessible",
            "archived",
            "available",
            "deposited",
            "downloadable",
            "found",
            "freely",
            "hosted",
            "located",
            "online",
            "publicly",
            "published",
            "released",
        ),
        pointers=("see also", "see", "visit", "cf."),
        sentence_words=_SENTENCE_WORDS,
        purposes=frozenset({"for", "to", "about", "regarding"}),
        fillers=("also",),
    ),
    "de": LinkWords(
        labels=(
            "abrufbar unter",
            "code",
            "daten",
            "datensatz",
            "datensätze",
            "doi",
            "e-mail",
            "e-mail-adresse",
            "e-mails",
            "email",
            "erreichbar unter",
            "github",
            "homepage",
            "internet",
            "internetseite",
            "kontakt",
            "korrespondenz",
            "korrespondenzadresse",
            "link",
            "links",
            "mail",
            "online",
            "online verfügbar",
            "programmcode",
            "projektseite",
            "quellcode",
            "repositorium",
            "repository",
            "software",
            "url",
            "urls",
            "verfügbar unter",
            "web",
            "webseite",
            "website",
        ),
        before=(
            "unter",
            "auf",
            "bei",
            "über",
            "via",
            "von",
            "aus",
            "an",
            "in",
            "siehe",
            "siehe auch",
            "vgl.",
            "s.",
            "z. b.",
            "z.b.",
            "etwa",
            "hier",
        ),
        lead=(
            "siehe auch",
            "siehe",
            "vgl. auch",
            "vgl.",
            "s.",
            "z. b.",
            "z.b.",
            "etwa",
            "unter",
            "auf",
            "bei",
            "via",
            "verfügbar unter",
            "abrufbar unter",
            "erreichbar unter",
            "online unter",
            "online:",
            "url:",
            "doi:",
            "code:",
            "daten:",
            "e-mail:",
            "email:",
            "webseite:",
            "website:",
        ),
        joins=(",", ";", "/", "und", "oder", "sowie", "&", ", und", ", oder", ", sowie"),
        introducers=(
            "abrufbar",
            "einsehbar",
            "erhältlich",
            "erreichbar",
            "frei",
            "hinterlegt",
            "online",
            "öffentlich",
            "veröffentlicht",
            "verfügbar",
            "zugänglich",
        ),
        pointers=("siehe auch", "siehe", "vgl. auch", "vgl.", "s."),
        sentence_words=_SENTENCE_WORDS_DE,
        purposes=frozenset({"für", "zu", "zum", "zur", "über", "bezüglich", "mit"}),
        fillers=("auch",),
        access=(
            "abgerufen am",
            "abgerufen",
            "abruf am",
            "abrufdatum",
            "aufgerufen am",
            "aufgerufen",
            "besucht am",
            "letzter abruf am",
            "letzter abruf",
            "letzter zugriff am",
            "letzter zugriff",
            "stand",
            "zugegriffen am",
            "zugriff am",
            "zugriff",
            "zuletzt abgerufen am",
            "zuletzt abgerufen",
            "zuletzt aufgerufen am",
            "zuletzt aufgerufen",
            "zuletzt besucht am",
        ),
    ),
}

# top-level domains for a bare "host.tld/path" without "www." or a scheme
_TLDS = (
    "ai|app|at|au|be|ca|ch|cn|co|com|cz|de|dev|dk|edu|es|eu|fi|fr|gov|info|int|io|it|jp|kr|"
    "me|mil|net|nl|no|nz|org|pl|pt|ru|se|uk|us"
)
_URL_CHARS = r"[^\s<>\"“”‘’{}|\\^`]"
_START = re.compile(
    "|".join(
        [
            r"(?P<url>(?<![\w@/.-])(?:(?:https?|ftp)://|(?:https?|ftp):(?=[ \t]*\n\s*//)|www\.))",
            r"(?P<mailto>(?<![\w/.-])mailto:)",
            r"(?P<doi>(?<![\w/.-])(?:doi:\s?)?10\.\d{4,9}/)",
            r"(?P<arxiv>(?<![\w/.-])arxiv:\s?(?:\d{4}\.\d{4,5}|[a-z][a-z.-]*/\d{7})(?:v\d+)?)",
            r"(?P<mail>(?<![\w.+-])(?:\{[\w.+-]+(?:\s*,\s*[\w.+-]+)*\}|[\w+-]+(?:\.[\w+-]+)*)"
            # the top-level domain is all lower or all upper case: "x@ucla.edu.The end"
            r"@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?-i:[a-z]{2,}|[A-Z]{2,}(?![a-z])))",
            rf"(?P<host>(?<![\w@/.-])(?:[a-z0-9-]+\.)+(?:{_TLDS})/)",
        ]
    ),
    re.IGNORECASE,
)
_KIND_NAMES = {
    "url": ("URL", "URLs"),
    "host": ("URL", "URLs"),
    "mailto": ("e-mail address", "e-mail addresses"),
    "mail": ("e-mail address", "e-mail addresses"),
    "doi": ("DOI", "DOIs"),
    "arxiv": ("arXiv identifier", "arXiv identifiers"),
}
_ENDS_NOTHING = "/-_~=&?#%"  # a URL cut after one of these goes on in the next line
_PATH_LIKE = re.compile(r"[/._\-=?#&%~\d]")  # a next-line word with one of these is address
_TRAILING = ".,;:!?'\"’”*"  # punctuation at a URL's end belongs to the sentence
_PAIRS = {")": "(", "]": "[", ">": "<"}
_SPACE = re.compile(r"\s+")
_POINTER_WORDS = 6  # the most words after a link that a pointer sentence may have
_SENTENCE_START = re.compile(r"(?:\A|[.!?][\"'”’)\]]*\s+)\Z")
_AFTER_START = re.compile(r"[.!?,;:]+(?:\s+|\Z|(?=[A-Z\])\"'”’]))")
_STOP = re.compile(r"[.!?](?=[\"'”’)\]]*(?:\s|\Z))")  # the full stop that ends a sentence
_LEADING_SPACE = re.compile(r"\s*")
_LOOK_BACK = 300  # characters looked at before a link, so a long block costs linear time


@dataclass(frozen=True)
class _Link:
    start: int
    end: int
    kind: str
    printed_end: int = -1  # where the link as printed ends, if an access note follows it


class LinkStep(TextStep):
    """Remove URLs, DOIs, arXiv identifiers and e-mail addresses, repairing the sentence."""

    id = "links"
    languages = ("en", "de")
    category = Category.LINKS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        words = WORDS[context.language.split("-", 1)[0].lower()]
        edits = []
        for index, block in enumerate(document.blocks):
            if block.kind in SKIPPED_KINDS or not block.text.strip():
                continue
            edits += self._block_edits(index, block.text, block.kind, block.label, words)
        return edits

    def _block_edits(
        self, index: int, text: str, kind: BlockKind, label: str, words: LinkWords
    ) -> list[Edit]:
        links = _with_access_notes(
            text, find_links(text, _after_label(text, kind, label), words), words
        )
        runs = _runs(links, text, words)
        if not runs:
            return []
        if _only_links(text, runs, label if kind is BlockKind.FOOTNOTE else "", words):
            printed = "; ".join(_printed(text, run) for run in runs)
            reason = f"the text holds nothing but links ({printed}) and is not read (TP-07)"
            return [Edit(Span(index, 0, len(text)), EditKind.REMOVE, reason, self.id)]
        edits = []
        claimed = 0  # where the previous removal ended: repairs never reach back over it
        sentence_at = -1  # ... if that removal started a sentence, so the next one does too
        position = 0
        while position < len(runs):
            run = runs[position]
            start, end, repair = _repair(text, run, words, claimed, sentence_at)
            position += 1
            # a repair that reaches over later runs takes them into the same edit
            while position < len(runs) and runs[position][0].start < end:
                end = max(end, runs[position][-1].end)
                run = run + runs[position]
                position += 1
            if len(run) > 1:
                repair = re.sub(r" it(?=[ ,])", " them", repair)
            at_start = _starts_sentence(text, start, sentence_at)
            stop = _AFTER_START.match(text, end) if at_start else None
            if stop and start > 0:
                # "Foo. https://x.org/a. Bar" reads "Foo. Bar": the punctuation after it goes
                end = stop.end()
                if not text[end - 1 : end].isspace() and end < len(text):
                    # "Foo. https://x.org/a.)" reads "Foo.)": the space before goes instead
                    start, _ = _with_space(text, start, start, claimed)
            else:
                start, end = _with_space(text, start, end, claimed)
                end = _whole_sentence(text, start, end, sentence_at)
                start, join = _dangling_join(text, start, end, claimed, words)
                repair += join
            noted = any(link.printed_end >= 0 for link in run)
            access = "; the access note after it goes too" if noted else ""
            edits.append(
                Edit(
                    Span(index, start, end),
                    EditKind.REMOVE,
                    f"{_named(text, run)} not read{access}{repair} (TP-07)",
                    self.id,
                )
            )
            claimed = end
            sentence_at = end if at_start else -1
        return _tidied(text, edits)


def _with_access_notes(text: str, links: list[_Link], words: LinkWords) -> list[_Link]:
    """Each link with the access note right after it taken along: "https://x.org (abgerufen
    am 12.03.2020)" or "https://x.org, Zugriff am 3. Mai 2017" (German words only)."""
    pattern = _access_pattern(words)
    if pattern is None:
        return links
    result = []
    for number, link in enumerate(links):
        note = pattern.match(text, link.end)
        following = links[number + 1].start if number + 1 < len(links) else len(text)
        if note and note.end() <= following:
            link = replace(link, end=note.end(), printed_end=link.end)
        result.append(link)
    return result


_DATE = (
    r"(?:\d{1,2}\.\s?\d{1,2}\.\s?(?:\d{4}|\d{2})(?!\d)|\d{4}-\d{2}-\d{2}(?!\d)"
    r"|(?:\d{1,2}\.\s*)?[^\W\d_]+\.?\s+\d{4}(?!\d))"
)


@cache
def _access_pattern(words: LinkWords) -> re.Pattern[str] | None:
    """An access note after a link: in brackets with a number in it, or after a comma up
    to its date."""
    if not words.access:
        return None
    listed = "|".join(
        re.escape(word).replace(r"\ ", r"\s+")
        for word in sorted(words.access, key=len, reverse=True)
    )
    return re.compile(
        rf"\s*[(\[]\s*(?:{listed})(?!\w)[^()\[\]\d]{{0,40}}\d[^()\[\]]{{0,40}}[)\]]"
        rf"|\s*,\s*(?:{listed})(?!\w)\s*:?\s*{_DATE}",
        re.IGNORECASE,
    )


def _dangling_join(
    text: str, start: int, end: int, claimed: int, words: LinkWords
) -> tuple[int, str]:
    """A join word left with nothing after it goes too: "(vgl. Suchmaschinen und z. B.
    https://archive.org/)" reads "(vgl. Suchmaschinen)", not "(vgl. Suchmaschinen und)"."""
    if end < len(text) and text[end] not in ".,;:!?)]":
        return start, ""
    joins = [w for w in words.joins if w.isalpha()]
    listed = "|".join(re.escape(w) for w in sorted(joins, key=len, reverse=True))
    window = max(claimed, start - _LOOK_BACK)
    left = re.search(rf"\s+({listed})\s*\Z", text[window:start], re.IGNORECASE)
    if not left or not text[window : window + left.start()].strip():
        return start, ""
    return window + left.start(), f'; "{left.group(1)}" before it goes too'


def _tidied(text: str, edits: list[Edit]) -> list[Edit]:
    """A comma or semicolon that several removals leave before a full stop goes with the
    first of them: "x, https://a.org (see https://b.org)." reads "x."."""
    kept_end, mark_at, first_after = 0, -1, 0
    spans = [[edit.span.start, edit.span.end] for edit in edits]
    for index, (start, end) in enumerate(spans):
        kept = text[max(kept_end, start - _LOOK_BACK) : start].rstrip()
        if kept:
            mark_at, first_after = max(kept_end, start - _LOOK_BACK) + len(kept) - 1, index
        if mark_at >= 0 and text[mark_at] in ",;" and text[end : end + 1] in (".", "!", "?"):
            spans[first_after][0] = min(spans[first_after][0], mark_at)
        kept_end = end
    return [
        replace(edit, span=Span(edit.span.block, start, end))
        for edit, (start, end) in zip(edits, spans, strict=True)
    ]


def _after_label(text: str, kind: BlockKind, label: str) -> int:
    """Where a footnote's text starts after the mark that opens it, so that a link set
    close to the mark ("5https://...") is found as if a space stood there (#36, D-278);
    0 for any other block."""
    lead = len(text) - len(text.lstrip())
    if kind is BlockKind.FOOTNOTE and label and text.startswith(label, lead):
        return lead + len(label)
    return 0


def find_links(text: str, after: int = 0, words: LinkWords | None = None) -> list[_Link]:
    """The links in a text, in order, never overlapping; the first `after` characters
    (a footnote's mark) are read as white space, so they hold no link and don't hide one.
    `words` gives the language's sentence words for a URL cut at a line end (English if
    none)."""
    sentence_words = (words or WORDS["en"]).sentence_words
    text = " " * after + text[after:]
    links: list[_Link] = []
    for match in _START.finditer(text):
        if links and match.start() < links[-1].end:
            continue
        kind = match.lastgroup or "url"
        if kind == "mail":
            end = match.end()
        elif kind == "arxiv":
            end = _trimmed(text, match.start(), match.end())
        else:
            end = _trimmed(text, match.start(), _token_end(text, match.end(), sentence_words))
        if end > match.start():
            links.append(_Link(match.start(), end, kind))
    return [link for link in links if _plausible(text, link)]


def _plausible(text: str, link: _Link) -> bool:
    """False for a scheme or prefix with nothing after it ("https://" alone)."""
    body = _SPACE.sub("", text[link.start : link.end])
    if link.kind == "url":
        return bool(re.search(r"(?://|www\.)[^/\s]*[a-z0-9]", body, re.IGNORECASE))
    if link.kind == "mailto":
        return "@" in body
    if link.kind in ("doi", "host"):
        return len(body) > body.find("/") + 1
    return True


def _token_end(text: str, position: int, sentence_words: frozenset[str]) -> int:
    """Where the address starting before `position` ends, line breaks inside it joined."""
    end = position
    while True:
        while end < len(text) and re.match(_URL_CHARS, text[end]):
            end += 1
        gap = re.match(r"[ \t]*\n\s*", text[end:])
        if not gap:
            return end
        rest = re.match(rf"{_URL_CHARS}+", text[end + gap.end() :])
        if not rest or not _continues(text[max(0, end - 8) : end], rest.group(), sentence_words):
            return end
        end += gap.end() + rest.end()


def _continues(before: str, word: str, sentence_words: frozenset[str]) -> bool:
    """True if a URL ending at a line break with `before` goes on with `word` (D-170)."""
    last = before[-1:]
    if last in _ENDS_NOTHING:
        # the rest of the address, unless a plain word that goes on the sentence (#109)
        plain = not _PATH_LIKE.search(word) and word.lower() in sentence_words
        return bool(re.match(r"[\w/.~%-]", word)) and not plain
    if last == ":":
        return bool(re.search(r"(?:https?|ftp):\Z", before, re.IGNORECASE)) and word.startswith(
            "//"
        )
    if last == ".":
        return bool(re.match(r"[a-z0-9]", word)) and (
            "/" in word or bool(re.fullmatch(r"\d+[.,;:)\]]*", word))
        )
    return False


def _trimmed(text: str, start: int, end: int) -> int:
    """`end` without the sentence's punctuation and unmatched closing brackets."""
    while end > start:
        last = text[end - 1]
        if last in _TRAILING or last.isspace():
            end -= 1
        elif last in _PAIRS:
            inside = text[start:end]
            if inside.count(_PAIRS[last]) >= inside.count(last):
                break
            end -= 1
        else:
            break
    return end


def _runs(links: list[_Link], text: str, words: LinkWords) -> list[list[_Link]]:
    """Neighbouring links joined by a comma, "and", "or" or "/" form one run."""
    runs: list[list[_Link]] = []
    for link in links:
        if runs:
            gap = _SPACE.sub(" ", text[runs[-1][-1].end : link.start]).strip().lower()
            if gap == "" or gap in words.joins:
                runs[-1].append(link)
                continue
        runs.append([link])
    return runs


def _only_links(text: str, runs: list[list[_Link]], label: str, words: LinkWords) -> bool:
    """True if nothing but links, punctuation, the words that join or lead to links ("and",
    "see", "z. B.") and the footnote's label is in the text."""
    rest = []
    cursor = 0
    for run in runs:
        rest.append(text[cursor : run[0].start])
        cursor = run[-1].end
    rest.append(text[cursor:])
    left = "".join(rest).strip()
    if label and left.startswith(label):
        left = left[len(label) :]
    left = _link_words(words).sub(" ", left)
    return all(unicodedata.category(char)[0] in "PZ" or char.isspace() for char in left)


@cache
def _link_words(words: LinkWords) -> re.Pattern[str]:
    """The words that join or lead to links, as whole words in any case."""
    found = {w for w in (*words.joins, *words.lead, *words.pointers) if any(c.isalpha() for c in w)}
    listed = "|".join(
        re.escape(w.strip(" ,")).replace(r"\ ", r"\s*")
        for w in sorted(found, key=len, reverse=True)
    )
    return re.compile(rf"(?<!\w)(?:{listed})(?!\w)", re.IGNORECASE)


def _repair(
    text: str, run: list[_Link], words: LinkWords, claimed: int, sentence_at: int = -1
) -> tuple[int, int, str]:
    """The span to remove for a run, and what the reason says about the repair."""
    start, end = run[0].start, run[-1].end
    before = text[max(claimed, start - _LOOK_BACK) : start]
    claimed = max(claimed, start - _LOOK_BACK)  # positions in `before` count from here
    # 1. a bracket that holds only the run and lead words
    leads = "|".join(re.escape(lead) for lead in sorted(words.lead, key=len, reverse=True))
    befores = "|".join(re.escape(word) for word in sorted(words.before, key=len, reverse=True))
    # "(see https://...)", "(available at https://...)", "(found at https://...)"
    words_before = "|".join(re.escape(word) for word in words.introducers)
    introduced = rf"(?:{leads}|(?:(?:{words_before})\s+){{0,2}}(?:{befores}))"
    opened = re.search(rf"([(\[<])\s*(?:{introduced}\s*)?\Z", before, re.IGNORECASE)
    if opened:
        closing = {"(": ")", "[": "]", "<": ">"}[opened.group(1)]
        closed = re.compile(rf"\s*{re.escape(closing)}").match(text, end)
        if closed:
            stop = closed.end()
            # "shown in [https://...], it" reads "shown, it", not "shown in, it"
            word = re.search(
                rf"(?<![\w.-])({befores})\s*\Z",
                text[claimed : claimed + opened.start()],
                re.IGNORECASE,
            )
            if word and re.compile(r"[.,;:!?]|\Z").match(text, stop):
                return (
                    claimed + word.start(),
                    stop,
                    f'; the brackets around it and "{word.group(1)}" before them go too',
                )
            return claimed + opened.start(), stop, "; the brackets around it go too"
    # 2. a label before it, maybe with a pointer: "Code: https://...", "Code: see https://..."
    labels = "|".join(re.escape(label) for label in sorted(words.labels, key=len, reverse=True))
    pointers = "|".join(re.escape(word) for word in sorted(words.pointers, key=len, reverse=True))
    labelled = re.search(
        rf"(?<![\w-])(?P<label>(?:{labels})\s*\*?\s*:)\s*(?:(?:{pointers})\s+)?\Z",
        before,
        re.IGNORECASE,
    )
    if labelled:
        label_start = claimed + labelled.start()
        name = _SPACE.sub(" ", labelled.group("label"))
        stop = (
            _only_pointers_after(text, end, words)
            if _starts_sentence(text, label_start, sentence_at)
            else None
        )
        if stop is not None:
            return label_start, stop, f'; with the label "{name}" the whole sentence goes'
        return label_start, end, f'; the label "{name}" goes too'
    # 3. a colon right before it
    colon = re.search(r":\s*\Z", before)
    if colon:
        return claimed + colon.start(), end, "; the colon before it goes too"
    # 4. a preposition or verb right before it
    word = re.search(rf"(?<![\w.-])({befores})\s+\Z", before, re.IGNORECASE)
    if word and re.fullmatch(pointers, word.group(1), re.IGNORECASE):
        pointed = _pointer(text, claimed + word.start(), end, word.group(1), words, sentence_at)
        if pointed:
            return pointed
    if word:
        return (
            claimed + word.start(),
            end,
            f'; "{word.group(1)}" before it goes too, so the sentence still reads',
        )
    return start, end, ""


def _pointer(
    text: str, start: int, end: int, word: str, words: LinkWords, sentence_at: int = -1
) -> tuple[int, int, str] | None:
    """A sentence or bracket that a pointer word starts only points to the link: it goes whole.

    "See https://... for details." and "(see https://... for the code)" are not read at all.
    Only a short rest qualifies: a longer one may say more than where the link leads.
    """
    if _starts_sentence(text, start, sentence_at):
        ending = _STOP.search(text, end)
        stop = ending.end() if ending else len(text)
        if _short(text[end:stop], words):
            return (
                start,
                stop,
                f'; "{word}" starts a sentence that only points to it, so the sentence goes whole',
            )
    window = max(0, start - _LOOK_BACK)
    opened = re.search(r"([(\[])\s*\Z", text[window:start])
    if opened:
        closing = {"(": ")", "[": "]"}[opened.group(1)]
        closed = re.compile(rf"[^()\[\]]*?{re.escape(closing)}").match(text, end)
        if closed and _short(text[end : closed.end() - 1], words):
            return (
                window + opened.start(),
                closed.end(),
                f'; "{word}" starts a bracket that only points to it, so the bracket goes whole',
            )
    return None


def _only_pointers_after(text: str, end: int, words: LinkWords) -> int | None:
    """The end of the sentence if after the link it holds only more links and the words
    that join or point to them ("Contact: a@b.org or see https://c.org/x."), else None."""
    ending = _STOP.search(text, end)
    stop = ending.end() if ending else len(text)
    if stop - end > _LOOK_BACK:
        return None
    return stop if _link_words_only(text[end:stop], words) else None


def _without_links(rest: str, words: LinkWords) -> str:
    for link in reversed(find_links(rest, words=words)):
        rest = rest[: link.start] + " " + rest[link.end :]
    return rest


def _link_words_only(rest: str, words: LinkWords) -> bool:
    """True if, links left out, the text holds only words that join or point to links."""
    allowed = {*words.joins, *words.before, *words.pointers, *words.lead, *words.fillers}
    return all(word in allowed for word in _words(_without_links(rest, words)))


def _short(rest: str, words: LinkWords) -> bool:
    """What follows a pointer and its link: nothing, more links and their words ("and also
    www.b.org/y"), or a short purpose and no clause ("for details", "to learn more")."""
    if len(rest) > _LOOK_BACK:
        return False
    bare = _without_links(rest, words)
    allowed = {*words.joins, *words.before, *words.pointers, *words.lead, *words.fillers}
    left = _words(bare)
    while left and left[0] in allowed:  # "(or www.b.org/x) for details"
        left.pop(0)
    if not left:
        return True
    return (
        len(left) <= _POINTER_WORDS
        and left[0] in words.purposes
        and not re.search(r"[,;:]|[.!?]\s", bare)
    )


def _words(text: str) -> list[str]:
    """The words of a text, lower case, without punctuation."""
    return re.sub(r"[^\w\s.-]|(?<!\w)[.-]|[.-](?!\w)", " ", text).lower().split()


def _with_space(text: str, start: int, end: int, claimed: int) -> tuple[int, int]:
    """Take the white space before the removal along, or after it at the start of a block.

    A comma or semicolon left before a full stop, another comma or a closing bracket goes
    too: "(Smith, 2019, https://...)" reads "(Smith, 2019)".
    """
    space_start = start
    while space_start > claimed and text[space_start - 1].isspace():
        space_start -= 1
    if space_start > claimed or (space_start == claimed and claimed > 0):
        start = space_start
        if (
            start > claimed
            and text[start - 1] in ",;"
            and text[end : end + 1] in (".", ",", ";", ")", "]")
        ):
            start -= 1
            while start > claimed and text[start - 1].isspace():
                start -= 1
    elif _LEADING_SPACE.match(text).end() >= space_start:
        start = 0 if claimed == 0 else space_start
        while end < len(text) and text[end].isspace():
            end += 1
    return start, end


def _whole_sentence(text: str, start: int, end: int, sentence_at: int = -1) -> int:
    """A removal that starts a sentence takes the punctuation right after it along.

    "https://x.org/a. Then" reads "Then", not ". Then"; "https://x.org/a, then" reads "then".
    """
    if not _starts_sentence(text, start, sentence_at):
        return end
    stop = _AFTER_START.match(text, end)
    return stop.end() if stop else end


def _starts_sentence(text: str, position: int, sentence_at: int = -1) -> bool:
    """True at the start of the block or after a sentence end; also right after a removal
    that started a sentence (`sentence_at`, where that removal ended)."""
    if 0 <= sentence_at <= position and not text[sentence_at:position].strip():
        return True
    window = max(0, position - _LOOK_BACK)
    before = text[window:position]
    if window == 0 and not before.strip():
        return True
    return bool(_SENTENCE_START.search(before)) and bool(before.strip())


def _printed(text: str, run: list[_Link]) -> str:
    """The links of a run as printed: line breaks inside an address dropped (D-175)."""
    shown = []
    for link in run:
        raw = text[link.start : link.end if link.printed_end < 0 else link.printed_end]
        shown.append(_SPACE.sub(" ", raw).strip() if "mail" in link.kind else _SPACE.sub("", raw))
    return " and ".join(f'"{link}"' for link in shown)


def _named(text: str, run: list[_Link]) -> str:
    """What the reason calls the run: 'URL "https://..." is' or 'links "a" and "b" are'."""
    kinds = {_KIND_NAMES[link.kind] for link in run}
    if len(run) == 1:
        return f"{_KIND_NAMES[run[0].kind][0]} {_printed(text, run)} is"
    name = next(iter(kinds))[1] if len(kinds) == 1 else "links"
    return f"{name} {_printed(text, run)} are"
