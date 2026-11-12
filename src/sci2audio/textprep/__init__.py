"""Text preparation: text steps that propose marked edits (D-57).

A `TextStep` proposes `Edit`s; `run_steps` runs the built-in steps (`BUILT_IN_STEPS`, coarse
to fine), settles overlapping edits (the earlier step wins) and keeps every proposal for the
report; `StepRun.script()` is the listening script.

Pipeline stage; may import only ``sci2audio.core``.
"""

from sci2audio.textprep.furniture import FurnitureStep
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
    TEXT_STEP_API,
    Category,
    Stage,
    StepContext,
    TextStep,
    step_problems,
)

__all__ = [
    "ANY_LANGUAGE",
    "BUILT_IN_STEPS",
    "PAUSE_MARK",
    "TEXT_STEP_API",
    "Category",
    "FurnitureStep",
    "Outcome",
    "Stage",
    "Status",
    "StepContext",
    "StepError",
    "StepProblem",
    "StepRun",
    "TextStep",
    "check_registry",
    "overlap",
    "run_steps",
    "spoken_text",
    "step_problems",
    "whole_block",
]
