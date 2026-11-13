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
cannot end a URL, or in "." before a word that looks like the rest of an address (D-170).
Every reason names the link as printed, without the line breaks inside it (D-175).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

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
            r"@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})",
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
_TRAILING = ".,;:!?'\"’”*"  # punctuation at a URL's end belongs to the sentence
_PAIRS = {")": "(", "]": "[", ">": "<"}
_SPACE = re.compile(r"\s+")
_POINTER_WORDS = 6  # the most words after a link that a pointer sentence may have
_SENTENCE_START = re.compile(r"(?:\A|[.!?][\"'”’)\]]*\s+)\Z")
_SENTENCE_END = re.compile(r"\A[.!?]?(?:\s|\Z)")


@dataclass(frozen=True)
class _Link:
    start: int
    end: int
    kind: str


class LinkStep(TextStep):
    """Remove URLs, DOIs, arXiv identifiers and e-mail addresses, repairing the sentence."""

    id = "links"
    languages = ("en",)
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
        runs = _runs(find_links(text), text, words)
        if not runs:
            return []
        if _only_links(text, runs, label if kind is BlockKind.FOOTNOTE else ""):
            printed = "; ".join(_printed(text, run) for run in runs)
            reason = f"the text holds nothing but links ({printed}) and is not read (TP-07)"
            return [Edit(Span(index, 0, len(text)), EditKind.REMOVE, reason, self.id)]
        edits = []
        claimed = 0  # where the previous removal ended: repairs never reach back over it
        for run in runs:
            start, end, repair = _repair(text, run, words, claimed)
            if len(run) > 1:
                repair = re.sub(r" it(?=[ ,])", " them", repair)
            start, end = _with_space(text, start, end, claimed)
            end = _whole_sentence(text, start, end)
            edits.append(
                Edit(
                    Span(index, start, end),
                    EditKind.REMOVE,
                    f"{_named(text, run)} not read{repair} (TP-07)",
                    self.id,
                )
            )
            claimed = end
        return edits


def find_links(text: str) -> list[_Link]:
    """The links in a text, in order, never overlapping."""
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
            end = _trimmed(text, match.start(), _token_end(text, match.end()))
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


def _token_end(text: str, position: int) -> int:
    """Where the address starting before `position` ends, line breaks inside it joined."""
    end = position
    while True:
        while end < len(text) and re.match(_URL_CHARS, text[end]):
            end += 1
        gap = re.match(r"[ \t]*\n\s*", text[end:])
        if not gap:
            return end
        rest = re.match(rf"{_URL_CHARS}+", text[end + gap.end() :])
        if not rest or not _continues(text[:end], rest.group()):
            return end
        end += gap.end() + rest.end()


def _continues(before: str, word: str) -> bool:
    """True if a URL ending at a line break with `before` goes on with `word` (D-170)."""
    last = before[-1:]
    if last in _ENDS_NOTHING:
        return bool(re.match(r"[\w/.~%-]", word))
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


def _only_links(text: str, runs: list[list[_Link]], label: str) -> bool:
    """True if nothing but links, punctuation and the footnote's label is in the text."""
    rest = []
    cursor = 0
    for run in runs:
        rest.append(text[cursor : run[0].start])
        cursor = run[-1].end
    rest.append(text[cursor:])
    left = "".join(rest).strip()
    if label and left.startswith(label):
        left = left[len(label) :]
    joins = re.compile(r"\b(?:and|or)\b", re.IGNORECASE)
    left = joins.sub("", left)
    return all(unicodedata.category(char)[0] in "PZ" or char.isspace() for char in left)


def _repair(text: str, run: list[_Link], words: LinkWords, claimed: int) -> tuple[int, int, str]:
    """The span to remove for a run, and what the reason says about the repair."""
    start, end = run[0].start, run[-1].end
    before, after = text[claimed:start], text[end:]
    # 1. a bracket that holds only the run and lead words
    leads = "|".join(re.escape(lead) for lead in sorted(words.lead, key=len, reverse=True))
    befores = "|".join(re.escape(word) for word in sorted(words.before, key=len, reverse=True))
    # "(see https://...)", "(available at https://...)", "(found at https://...)"
    words_before = "|".join(re.escape(word) for word in words.introducers)
    introduced = rf"(?:{leads}|(?:(?:{words_before})\s+){{0,2}}(?:{befores}))"
    opened = re.search(rf"([(\[<])\s*(?:{introduced}\s*)?\Z", before, re.IGNORECASE)
    if opened:
        closing = {"(": ")", "[": "]", "<": ">"}[opened.group(1)]
        closed = re.match(rf"\s*{re.escape(closing)}", after)
        if closed:
            stop = end + closed.end()
            # "shown in [https://...], it" reads "shown, it", not "shown in, it"
            word = re.search(
                rf"(?<![\w.-])({befores})\s*\Z",
                text[claimed : claimed + opened.start()],
                re.IGNORECASE,
            )
            if word and re.match(r"[.,;:!?]|\Z", text[stop:]):
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
        ending = _SENTENCE_END.match(after)
        if _SENTENCE_START.search(text[:label_start]) and ending:
            stop = end + len(ending.group().rstrip())
            return label_start, stop, f'; with the label "{name}" the whole sentence goes'
        return label_start, end, f'; the label "{name}" goes too'
    # 3. a colon right before it
    colon = re.search(r":\s*\Z", before)
    if colon:
        return claimed + colon.start(), end, "; the colon before it goes too"
    # 4. a preposition or verb right before it
    word = re.search(rf"(?<![\w.-])({befores})\s+\Z", before, re.IGNORECASE)
    if word and re.fullmatch(pointers, word.group(1), re.IGNORECASE):
        pointed = _pointer(text, claimed + word.start(), end, word.group(1))
        if pointed:
            return pointed
    if word:
        return (
            claimed + word.start(),
            end,
            f'; "{word.group(1)}" before it goes too, so the sentence still reads',
        )
    return start, end, ""


def _pointer(text: str, start: int, end: int, word: str) -> tuple[int, int, str] | None:
    """A sentence or bracket that a pointer word starts only points to the link: it goes whole.

    "See https://... for details." and "(see https://... for the code)" are not read at all.
    Only a short rest qualifies: a longer one may say more than where the link leads.
    """
    if _SENTENCE_START.search(text[:start]):
        ending = re.search(r"[.!?](?=[\"'”’)\]]*(?:\s|\Z))", text[end:])
        stop = end + ending.end() if ending else len(text)
        if _short(text[end:stop]):
            return (
                start,
                stop,
                f'; "{word}" starts a sentence that only points to it, so the sentence goes whole',
            )
    opened = re.search(r"([(\[])\s*\Z", text[:start])
    if opened:
        closing = {"(": ")", "[": "]"}[opened.group(1)]
        closed = re.match(rf"[^()\[\]]*?{re.escape(closing)}", text[end:])
        if closed and _short(text[end : end + closed.end()]):
            return (
                opened.start(),
                end + closed.end(),
                f'; "{word}" starts a bracket that only points to it, so the bracket goes whole',
            )
    return None


def _short(rest: str) -> bool:
    """At most six words and no clause inside: "for details", "for the code and data"."""
    return len(rest.split()) <= _POINTER_WORDS and not re.search(r"[,;:]", rest)


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
    elif not text[:space_start].strip():
        start = 0 if claimed == 0 else space_start
        while end < len(text) and text[end].isspace():
            end += 1
    return start, end


def _whole_sentence(text: str, start: int, end: int) -> int:
    """A removal that starts a sentence takes the punctuation right after it along.

    "https://x.org/a. Then" reads "Then", not ". Then"; "https://x.org/a, then" reads "then".
    """
    if not _SENTENCE_START.search(text[:start]):
        return end
    stop = re.match(r"[.!?,;:]+(?:\s+|\Z)", text[end:])
    return end + stop.end() if stop else end


def _printed(text: str, run: list[_Link]) -> str:
    """The links of a run as printed: line breaks inside an address dropped (D-175)."""
    shown = []
    for link in run:
        raw = text[link.start : link.end]
        shown.append(_SPACE.sub(" ", raw).strip() if "mail" in link.kind else _SPACE.sub("", raw))
    return " and ".join(f'"{link}"' for link in shown)


def _named(text: str, run: list[_Link]) -> str:
    """What the reason calls the run: 'URL "https://..." is' or 'links "a" and "b" are'."""
    kinds = {_KIND_NAMES[link.kind] for link in run}
    if len(run) == 1:
        return f"{_KIND_NAMES[run[0].kind][0]} {_printed(text, run)} is"
    name = next(iter(kinds))[1] if len(kinds) == 1 else "links"
    return f"{name} {_printed(text, run)} are"
