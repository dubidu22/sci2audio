"""What marks a display formula: its printed number, and letters set in a math font (Issue
#21 step 3, PR D2, D-93)."""

from __future__ import annotations

import re
import unicodedata

from sci2audio.core import TextLine

# an equation number as printed: "12", "16a", "A.2", "S1", "2.3"
_NUMBER = r"(?:[A-Z]\.?)?\d{1,3}(?:\.\d{1,2})*[a-z]?"
_ALONE = re.compile(rf"\s*\((?P<number>{_NUMBER})\)\s*")
_AT_END = re.compile(rf".*\S\s+\((?P<number>{_NUMBER})\)\s*")


def number_alone(line: TextLine) -> str | None:
    """The equation number a line holds and nothing else ("(16a)" gives "16a")."""
    found = _ALONE.fullmatch(line.text)
    return found["number"] if found else None


def number_at_end(line: TextLine) -> str | None:
    """The equation number that ends a longer line ("a = b (2)" gives "2")."""
    found = _AT_END.fullmatch(line.text)
    return found["number"] if found else None


def math_letters(lines: list[TextLine], fonts: tuple[str, ...]) -> float:
    """The share of the lines' letters set in a math font or that are math symbols."""
    total = maths = 0
    for line in lines:
        for run in line.runs:
            font = run.font.rsplit("+", 1)[-1]
            for ch in run.text:
                if ch.isspace():
                    continue
                total += 1
                maths += font.startswith(fonts) or unicodedata.category(ch) == "Sm"
    return maths / total if total else 0.0
