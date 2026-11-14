"""The text-step interface (D-57): what every text rule is and what it may do.

A text step looks at the document and proposes marked edits (`sci2audio.core.Edit`) on spans
inside one block; it never changes the text. The runner (`run_steps`) collects the edits of
all steps, settles overlaps and hands the accepted ones to `apply_edits`, so read-along, the
report and the per-category switches keep working. Internal in v1.0; plugins through the
`sci2audio.text_steps` entry point follow in v1.1 (PE-10).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from sci2audio.core import Document, Edit

TEXT_STEP_API = 1  # raised when the interface changes in a way old steps would break
ANY_LANGUAGE = "*"  # in `TextStep.languages`: the step works for every language

_STEP_ID = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_LANGUAGE = re.compile(r"\A[a-z]{2,3}\Z")


class Category(StrEnum):
    """What a step is about, as the report and the per-category switches name it (UC-02).

    The list is fixed; every step belongs to exactly one category. Every category is on by
    default except "Footnote texts": switched on, it leaves all footnotes out (Q2, D-142).
    """

    PAGE_FURNITURE = "page-furniture"  # TP-01
    CHARACTERS = "characters"  # IN-04, TP-02
    FOOTNOTES = "footnotes"  # TP-05: marks left out, notes introduced
    FOOTNOTE_TEXTS = "footnote-texts"  # TP-05: the notes themselves left out; off by default
    CITATIONS = "citations"  # TP-03, TP-04
    LINKS = "links"  # TP-07
    FORMULAS = "formulas"  # FX-01
    TABLES_AND_FIGURES = "tables-and-figures"  # FX-02, TP-12
    CODE = "code"  # code blocks (D-545)
    REFERENCES = "references"  # TP-06
    ABBREVIATIONS = "abbreviations"  # TP-08
    NUMBERS_AND_UNITS = "numbers-and-units"  # TP-09, TP-10, TP-11

    @property
    def label(self) -> str:
        """The name a person reads in the report and next to the switch."""
        return _LABELS[self]

    @property
    def on_by_default(self) -> bool:
        """True if the category's edits are used unless the user switches it off."""
        return self is not Category.FOOTNOTE_TEXTS


_LABELS = {
    Category.PAGE_FURNITURE: "Page furniture",
    Category.CHARACTERS: "Characters and hyphenation",
    Category.FOOTNOTES: "Footnotes",
    Category.FOOTNOTE_TEXTS: "Footnote texts",
    Category.CITATIONS: "Citations",
    Category.LINKS: "URLs, DOIs and e-mail addresses",
    Category.FORMULAS: "Formulas",
    Category.TABLES_AND_FIGURES: "Tables and figures",
    Category.CODE: "Code blocks",
    Category.REFERENCES: "Reference list",
    Category.ABBREVIATIONS: "Abbreviations",
    Category.NUMBERS_AND_UNITS: "Numbers, symbols, units and statistics",
}

# the categories a job starts with switched off (#70 takes its default switches from here)
DEFAULT_SWITCHED_OFF: frozenset[Category] = frozenset(
    category for category in Category if not category.on_by_default
)


class Stage(StrEnum):
    """How much of a block a step's edits cover; D-57's "stage" field.

    Block steps run before inline steps (coarse to fine), move steps last. An accepted block
    edit claims its block: no later edit in that block is used, not even a mark at its start
    or end, so a whole-block removal or notice always wins over the rules inside the block
    (D-105). A move step proposes only moves (`EditKind.MOVE`, #213) and only a move step
    proposes them: running last, a move never blocks a rule about the text; a move that
    conflicts is set aside and the block is read where it stands.
    """

    BLOCK = "block"  # every edit covers a whole block: furniture, reference list, notices
    INLINE = "inline"  # edits inside a block: citations, URLs, numbers, ...
    MOVE = "move"  # moves of whole blocks to a position in another block: footnotes (#213)


@dataclass(frozen=True)
class StepContext:
    """What a step may know about the job besides the document; no global state.

    The app fills it from the job's settings. Fields added later get defaults, so a step
    written against this version keeps working.
    """

    language: str  # the job's language, BCP 47 ("en", "en-GB")

    def __post_init__(self) -> None:
        if not self.language:
            raise ValueError("a step context needs the job's language, e.g. 'en'")


class TextStep(ABC):
    """One text rule. Subclasses set the class attributes and implement `find`.

    `find` returns the edits the step proposes for the document; each names the step's id
    and a reason a person can read in the report. The step must not change anything,
    reach the network or depend on anything but its arguments.
    """

    id: str  # kebab-case, unique among the steps of a run
    languages: tuple[str, ...]  # primary language tags ("en"), or (ANY_LANGUAGE,)
    category: Category
    stage: Stage
    api_version: int = TEXT_STEP_API

    @abstractmethod
    def find(self, document: Document, context: StepContext) -> list[Edit]:
        """The edits this step proposes for the document."""

    def handles(self, language: str) -> bool:
        """True if the step works for this language ("en-GB" matches "en")."""
        primary = language.split("-", 1)[0].lower()
        return ANY_LANGUAGE in self.languages or primary in self.languages

    def __repr__(self) -> str:
        return f"<text step {getattr(self, 'id', '?')}>"


def step_problems(step: TextStep) -> list[str]:
    """What is wrong with a step's declared attributes; empty if nothing."""
    problems = []
    step_id = getattr(step, "id", None)
    if not isinstance(step_id, str) or not _STEP_ID.match(step_id):
        problems.append(f"id must be kebab-case letters and digits, got {step_id!r}")
    version = getattr(step, "api_version", None)
    if version != TEXT_STEP_API:
        problems.append(f"api_version must be {TEXT_STEP_API}, got {version!r}")
    if not isinstance(getattr(step, "category", None), Category):
        problems.append(f"category must be a Category, got {getattr(step, 'category', None)!r}")
    if not isinstance(getattr(step, "stage", None), Stage):
        problems.append(f"stage must be a Stage, got {getattr(step, 'stage', None)!r}")
    languages = getattr(step, "languages", None)
    if (
        not isinstance(languages, tuple)
        or not languages
        or not all(lang == ANY_LANGUAGE or _LANGUAGE.match(str(lang)) for lang in languages)
    ):
        problems.append(
            f"languages must be a non-empty tuple of primary tags like 'en' or '*', "
            f"got {languages!r}"
        )
    return problems
