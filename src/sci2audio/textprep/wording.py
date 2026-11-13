"""Every word the text steps add to the script, in one table per language (Q3, D-145).

The steps of #64 add short notices where something is not read ("Table 2 is skipped.") and
introduce each footnote ("Footnote 1."); the citations step of #66 reads a numeric citation
the sentence needs as "reference 12" (D-172). Their wording lives here, and only here, so a
language added later (the German interface, #79) adds one row and changes no step. v1.0
reads English notices only (D-50, Q10).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sci2audio.core import BlockKind

_GLUED = re.compile(r"([^\W\d_]+\.)(\S+)")  # "Fig.3": a short word, then its number


@dataclass(frozen=True)
class Wording:
    """The words of the notices and footnote introductions in one language."""

    skipped_one: str  # "{} is skipped."
    skipped_many: str  # "{} are skipped."
    list_comma: str  # ", " between names of a list
    list_and: str  # " and " before the last name
    unnamed: Mapping[BlockKind, str]  # a placeholder that nothing names
    formula: str  # "Formula {}": a formula named by its printed number
    footnote: str  # "Footnote {}.": a note introduced by its number or letter
    footnote_unnamed: str  # "Footnote.": a note with a symbol mark or none
    reference: str  # "reference 12": a numeric citation the sentence needs (D-172)
    references: str  # "references 3 and 5"
    range_to: str  # "references 2 to 6"
    # label words printed in short, read in full: "Fig. 3" is read "Figure 3"
    label_words: Mapping[str, str] = field(default_factory=dict)

    def skipped(self, names: Sequence[str], kind: BlockKind) -> str:
        """The notice for a placeholder with these names, or the unnamed one."""
        if not names:
            return self.unnamed[kind]
        if len(names) == 1:
            return self.skipped_one.format(names[0])
        listed = self.list_comma.join(names[:-1]) + self.list_and + names[-1]
        return self.skipped_many.format(listed)

    def label(self, printed: str) -> str:
        """A caption label as it is read: its first word in full if it is printed short.

        The word is looked up in any case ("FIG. 3" is read "Figure 3"), and a short word
        printed against its number is split from it ("Fig.3" is read "Figure 3").
        """
        words = {short.casefold(): full for short, full in self.label_words.items()}
        word, space, rest = printed.partition(" ")
        if not space and (glued := _GLUED.match(word)) and glued[1].casefold() in words:
            word, space, rest = glued[1], " ", glued[2]
        return words.get(word.casefold(), word) + space + rest


ENGLISH = Wording(
    skipped_one="{} is skipped.",
    skipped_many="{} are skipped.",
    list_comma=", ",
    list_and=" and ",
    unnamed={
        BlockKind.TABLE: "A table is skipped.",
        BlockKind.FIGURE: "A figure is skipped.",
        BlockKind.FORMULA: "A formula is skipped.",
    },
    formula="Formula {}",
    footnote="Footnote {}.",
    footnote_unnamed="Footnote.",
    reference="reference",
    references="references",
    range_to="to",
    label_words={
        "Fig.": "Figure",
        "Figs.": "Figures",
        "Tab.": "Table",
        "Tabs.": "Tables",
        "Eq.": "Equation",
        "Eqs.": "Equations",
        "Alg.": "Algorithm",
    },
)

WORDING: Mapping[str, Wording] = {"en": ENGLISH}  # by primary language tag


def wording_for(language: str) -> Wording:
    """The wording for a job's language ("en-GB" uses "en"); English where none exists."""
    return WORDING.get(language.split("-", 1)[0].lower(), ENGLISH)
