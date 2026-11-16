"""Sentence boundaries of the listening script against hand-checked sentences (D-715, D-719).

The truth is a file of sentences, one per line, as printed (`tests/sentences/README.md`). The
system's sentence starts are the utterances that do not continue a sentence cut by length
(`Utterance.continues` false): where each starts in the original text. Both are compared word
by word:

- Words are compared by a key: NFKC, case folded, letters and digits only. So a line-end
  hyphen, a ligature, punctuation and a footnote mark's place do not stop two words matching.
- The system's words are the original text of every block in reading order that the script
  reads (an utterance or a notice stands for it), except footnotes, which move to their mark
  when read. A block nobody hears (furniture, a chapter not chosen) is left out, so the words
  around it are not compared across it. A word split by a hyphen at a line end ("ellip-" /
  "sis") is one word.
- Each truth segment (the lines between two `---`) is aligned on its own with difflib, so the
  order of segments does not matter (captions may stand anywhere). Only a gap between two
  words that match in one run of at least `MIN_RUN` words is compared: there both sides say
  whether a sentence starts. Gaps elsewhere (text the truth leaves out or the script reads
  differently) count neither way.
- At a compared gap: a truth start that the system also starts is a hit; a truth start the
  system does not start is missed (FN); a system start the truth does not have is extra (FP).
  A truth line starting "~ " marks an optional start: neither way.

An extra start at the first word of a block is a layout error (the block was cut there); one
inside a block is a sentence-rule error.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from sci2audio.app import JobSettings
from sci2audio.app.job import read_document
from sci2audio.app.script import prepare_script
from sci2audio.core import BlockKind, Document
from sci2audio.textprep import Utterance

MIN_RUN = 3  # a match shorter than this may be chance: its gaps are not compared
CONTEXT = 4  # words on each side in an error's `at`
_LEFT_OUT = frozenset({BlockKind.FOOTNOTE})
_WORD = re.compile(r"\S+")


def key(word: str) -> str:
    """What two words are compared by: NFKC, case folded, letters and digits only."""
    return "".join(c for c in unicodedata.normalize("NFKC", word).casefold() if c.isalnum())


@dataclass
class Truth:
    """The words of a sentence file, where sentences start, and its segments."""

    words: list[str] = field(default_factory=list)  # as written, keyed words only
    starts: set[int] = field(default_factory=set)  # word indices that start a sentence
    optional: set[int] = field(default_factory=set)  # starts that may or may not be heard
    segments: list[tuple[int, int]] = field(default_factory=list)  # [start, end) word ranges


def read_truth(path: Path) -> Truth:
    """Parse a sentence file (`tests/sentences/README.md`)."""
    truth = Truth()
    segment = 0
    pending: str | None = None  # the kind of start waiting for the next keyed word

    def close() -> None:
        nonlocal segment
        if len(truth.words) > segment:
            truth.segments.append((segment, len(truth.words)))
        segment = len(truth.words)

    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "@page")):
            continue
        if line == "---":
            close()
            pending = None
            continue
        optional = line.startswith("~ ")
        if optional:
            line = line[2:]
        elif line.startswith("~"):
            raise ValueError(f"{path.name}:{number}: write '~ ' with a space")
        # a start already waiting (a line with no keyed word) keeps the stronger kind
        pending = "optional" if optional and pending != "start" else "start"
        for word in line.split():
            if not key(word):
                continue
            if pending:
                (truth.optional if pending == "optional" else truth.starts).add(len(truth.words))
                pending = None
            truth.words.append(word)
    close()
    return truth


@dataclass(frozen=True)
class Words:
    """The system side: the document's words in reading order, where each is, and where the
    script starts a sentence."""

    keys: list[str]
    places: list[tuple[int, int]]  # (block, offset of the word's first character)
    first_in_block: list[bool]
    starts: set[int]


def system_words(document: Document, utterances: Iterable[Utterance]) -> Words:
    """The document's words and the script's sentence starts (see the module docstring)."""
    utterances = [u for u in utterances if not u.pause]
    heard = {u.span.block for u in utterances}
    keys: list[str] = []
    places: list[tuple[int, int]] = []
    first: list[bool] = []
    index_of: dict[int, list[tuple[int, int]]] = {}  # block -> [(offset, word index)]
    for number, block in enumerate(document.blocks):
        if block.kind in _LEFT_OUT or number not in heard:
            continue
        text = block.text
        matches = list(_WORD.finditer(text))
        entries: list[tuple[int, int]] = []
        joined = False
        for i, match in enumerate(matches):
            word = match.group()
            if joined:  # the second half of a word split at a line end
                keys[-1] += key(word)
                joined = False
                continue
            following = matches[i + 1] if i + 1 < len(matches) else None
            joined = (
                following is not None
                and word.endswith("-")
                and word[-2:-1].isalpha()
                and "\n" in text[match.end() : following.start()]
                and following.group()[:1].islower()
            )
            if not key(word) and not joined:
                continue
            entries.append((match.start(), len(keys)))
            keys.append(key(word))
            places.append((number, match.start()))
            first.append(not entries[:-1])
        index_of[number] = entries
    starts: set[int] = set()
    for utterance in utterances:
        if utterance.continues:
            continue
        entries = index_of.get(utterance.span.block, [])
        # the first word that ends after the utterance's start
        block_text = document.blocks[utterance.span.block].text
        for offset, index in entries:
            end = offset + len(_WORD.match(block_text, offset).group())
            if end > utterance.span.start:
                starts.add(index)
                break
    return Words(keys, places, first, starts)


@dataclass(frozen=True)
class Error:
    kind: str  # "FP" (a start the truth does not have) or "FN" (a start the script misses)
    at: str  # truth words around the gap: "before | after"
    layout: bool  # FP only: the extra start is a block's first word


@dataclass
class Score:
    hits: int = 0
    errors: list[Error] = field(default_factory=list)
    compared: int = 0  # gaps compared
    truth_gaps: int = 0  # gaps between two words of one segment

    @property
    def false_positives(self) -> int:
        return sum(e.kind == "FP" for e in self.errors)

    @property
    def false_negatives(self) -> int:
        return sum(e.kind == "FN" for e in self.errors)

    @property
    def precision(self) -> float:
        found = self.hits + self.false_positives
        return self.hits / found if found else 1.0

    @property
    def recall(self) -> float:
        wanted = self.hits + self.false_negatives
        return self.hits / wanted if wanted else 1.0

    @property
    def f1(self) -> float:
        both = self.precision + self.recall
        return 2 * self.precision * self.recall / both if both else 0.0

    @property
    def layout_false_positives(self) -> int:
        """Extra starts at a block's first word: the layout cut the block there."""
        return sum(e.kind == "FP" and e.layout for e in self.errors)

    def summary(self) -> str:
        """One line: precision, recall, F1, counts, extra starts by layout and by rule."""
        layout = self.layout_false_positives
        return (
            f"P {self.precision:.4f} R {self.recall:.4f} F1 {self.f1:.4f}: "
            f"{self.hits} found, {self.false_positives} extra ({layout} layout, "
            f"{self.false_positives - layout} rule), {self.false_negatives} missed, "
            f"coverage {self.coverage:.3f}"
        )

    @property
    def coverage(self) -> float:
        """The share of the truth's gaps that could be compared."""
        return self.compared / self.truth_gaps if self.truth_gaps else 1.0

    def add(self, other: Score) -> None:
        self.hits += other.hits
        self.errors.extend(other.errors)
        self.compared += other.compared
        self.truth_gaps += other.truth_gaps


def compare(truth: Truth, words: Words) -> Score:
    """Count hits, misses and extra starts at every gap both sides can be compared at."""
    score = Score()
    matcher = SequenceMatcher(None, autojunk=False)
    matcher.set_seq2(words.keys)
    truth_keys = [key(word) for word in truth.words]
    for begin, end in truth.segments:
        score.truth_gaps += end - begin - 1
        matcher.set_seq1(truth_keys[begin:end])
        for a, b, size in matcher.get_matching_blocks():
            if size < MIN_RUN:
                continue
            for k in range(1, size):
                i, j = begin + a + k, b + k
                score.compared += 1
                if i in truth.optional:
                    continue
                wanted, found = i in truth.starts, j in words.starts
                if wanted and found:
                    score.hits += 1
                elif wanted or found:
                    score.errors.append(
                        Error(
                            "FN" if wanted else "FP",
                            _context(truth.words, i),
                            layout=found and words.first_in_block[j],
                        )
                    )
    return score


def _context(words: Sequence[str], i: int) -> str:
    return " ".join(words[max(0, i - CONTEXT) : i]) + " | " + " ".join(words[i : i + CONTEXT])


def script_of(source: Path) -> tuple[Document, tuple[Utterance, ...]]:
    """The document and the utterances of every chapter, as a default job reads them."""
    settings = JobSettings()
    document = read_document(source, settings, lambda phase: None)
    return document, prepare_script(document, settings).utterances


def score_file(truth_path: Path, source: Path) -> tuple[str, Score]:
    """The document's language and its score against the sentence file."""
    document, utterances = script_of(source)
    return document.language, compare(read_truth(truth_path), system_words(document, utterances))


def stress_source(truth_path: Path) -> str:
    """The plain text a stress set is read from: a blank line ends a paragraph, the sentences
    of a paragraph are joined by a space; comments, page marks and "~ " are left out."""
    paragraphs: list[list[str]] = [[]]
    for raw in truth_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            if paragraphs[-1]:
                paragraphs.append([])
            continue
        if line.startswith(("#", "@page")) or line == "---":
            continue
        paragraphs[-1].append(line.removeprefix("~ "))
    return "\n\n".join(" ".join(lines) for lines in paragraphs if lines) + "\n"
