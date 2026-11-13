"""Text preparation: text steps that propose marked edits (D-57).

A `TextStep` proposes `Edit`s; `run_steps` runs the built-in steps (`BUILT_IN_STEPS`, coarse
to fine), settles overlapping edits (the earlier step wins) and keeps every proposal for the
report; `StepRun.script()` is the listening script, and `cut_utterances` cuts it into what
the voice says in one call each.

Pipeline stage; may import only ``sci2audio.core``.
"""

from sci2audio.textprep.footnotes import FootnoteStep, FootnoteTextStep
from sci2audio.textprep.furniture import FurnitureStep
from sci2audio.textprep.placeholders import FormulaNoticeStep, TableFigureNoticeStep
from sci2audio.textprep.references import (
    REFERENCE_TITLES,
    ReferenceListStep,
    is_reference_title,
)
from sci2audio.textprep.registry import BUILT_IN_STEPS, check_registry
from sci2audio.textprep.runner import (
    Outcome,
    Status,
    StepError,
    StepProblem,
    StepRun,
    overlap,
    run_steps,
    whole_block,
)
from sci2audio.textprep.spoken import PAUSE_MARK, spoken_text
from sci2audio.textprep.steps import (
    ANY_LANGUAGE,
    DEFAULT_SWITCHED_OFF,
    TEXT_STEP_API,
    Category,
    Stage,
    StepContext,
    TextStep,
    step_problems,
)
from sci2audio.textprep.utterances import (
    ABBREVIATIONS,
    DEFAULT_MAX_CHARS,
    Utterance,
    cut_utterances,
)
from sci2audio.textprep.wording import WORDING, Wording, wording_for

__all__ = [
    "ABBREVIATIONS",
    "ANY_LANGUAGE",
    "BUILT_IN_STEPS",
    "DEFAULT_MAX_CHARS",
    "DEFAULT_SWITCHED_OFF",
    "PAUSE_MARK",
    "REFERENCE_TITLES",
    "TEXT_STEP_API",
    "WORDING",
    "Category",
    "FootnoteStep",
    "FootnoteTextStep",
    "FormulaNoticeStep",
    "FurnitureStep",
    "Outcome",
    "ReferenceListStep",
    "Stage",
    "Status",
    "StepContext",
    "StepError",
    "StepProblem",
    "StepRun",
    "TableFigureNoticeStep",
    "TextStep",
    "Utterance",
    "Wording",
    "check_registry",
    "cut_utterances",
    "is_reference_title",
    "overlap",
    "run_steps",
    "spoken_text",
    "step_problems",
    "whole_block",
    "wording_for",
]
