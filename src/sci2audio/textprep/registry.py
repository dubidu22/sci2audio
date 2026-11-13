"""The built-in text steps, in the order they run.

The order is coarse to fine: every block step (whole-block edits) comes before every inline
step (edits inside a block), and when two edits overlap the earlier step's edit wins (Q15).
`check_registry` enforces the stage order; the order inside each stage is a choice, written
here so every rule PR places its step deliberately. Planned order for v1.0:

- block: page furniture (#63), reference list, placeholder notices for formulas, tables and
  figures, footnote texts (#64)
- inline: URLs, DOIs and e-mail addresses, citations (#66), footnote marks (#64), statistics
  then numbers (#67, D-190), symbols and units, abbreviations (#68), and last characters and
  hyphenation (#65): a one-character fix placed earlier would block the rules after it, so it
  only applies where no other rule rewrote the text (D-150). So the rules before it see the
  printed characters (ligatures, maths letters, TeX accents set apart, "eV˚A") and must
  match those forms themselves

No built-in v1.0 step proposes `ask` edits (the interface has no way to answer them before
UC-04); the conformance test enforces it. Plugins (`sci2audio.text_steps`) follow in v1.1.
"""

from __future__ import annotations

from collections.abc import Sequence

from sci2audio.textprep.characters import UnicodeStep
from sci2audio.textprep.citations import CitationStep
from sci2audio.textprep.footnotes import FootnoteStep, FootnoteTextStep
from sci2audio.textprep.furniture import FurnitureStep
from sci2audio.textprep.hyphens import LineEndHyphenStep
from sci2audio.textprep.links import LinkStep
from sci2audio.textprep.numbers import NumbersStep
from sci2audio.textprep.placeholders import FormulaNoticeStep, TableFigureNoticeStep
from sci2audio.textprep.references import ReferenceListStep
from sci2audio.textprep.statistics import StatisticsStep
from sci2audio.textprep.steps import Stage, TextStep, step_problems

BUILT_IN_STEPS: tuple[TextStep, ...] = (
    FurnitureStep(),
    ReferenceListStep(),
    FormulaNoticeStep(),
    TableFigureNoticeStep(),
    FootnoteTextStep(),
    LinkStep(),
    CitationStep(),
    FootnoteStep(),
    StatisticsStep(),
    NumbersStep(),
    # characters and hyphenation stay the last inline steps (D-150)
    UnicodeStep(),
    LineEndHyphenStep(),
)


def check_registry(steps: Sequence[TextStep]) -> None:
    """Raise ValueError unless the steps can run in this order.

    Each step's attributes are valid, the ids are unique and every block step comes before
    every inline step.
    """
    problems = []
    seen: set[str] = set()
    inline_seen = ""
    for step in steps:
        problems += [f"{step!r}: {problem}" for problem in step_problems(step)]
        step_id = getattr(step, "id", "")
        if step_id in seen:
            problems.append(f"step id {step_id!r} is used twice")
        seen.add(step_id)
        stage = getattr(step, "stage", None)
        if stage is Stage.INLINE and not inline_seen:
            inline_seen = step_id
        elif stage is Stage.BLOCK and inline_seen:
            problems.append(
                f"block step {step_id!r} comes after inline step {inline_seen!r}; "
                "block steps run first"
            )
    if problems:
        raise ValueError("invalid text-step order: " + "; ".join(problems))
