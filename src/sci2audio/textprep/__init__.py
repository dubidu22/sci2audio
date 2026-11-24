"""Text preparation: text steps that propose marked edits (D-57).

A `TextStep` proposes `Edit`s; `run_steps` runs the built-in steps (`BUILT_IN_STEPS`, coarse
to fine), settles overlapping edits (the earlier step wins) and keeps every proposal for the
report; `StepRun.script()` is the listening script, and `cut_utterances` cuts it into what
the voice says in one call each. `installed_steps` adds the plugins of the
`sci2audio.text_steps` entry point (#216); plugin authors use `sci2audio.textprep.api`, the
public part of this package.

Pipeline stage; may import only ``sci2audio.core``.
"""

from sci2audio.textprep.abbreviations import AbbreviationStep
from sci2audio.textprep.characters import UnicodeStep
from sci2audio.textprep.citations import CitationStep
from sci2audio.textprep.footnotes import AffiliationMarkStep, FootnoteStep, FootnoteTextStep
from sci2audio.textprep.furniture import FurnitureStep, HiddenRunStep
from sci2audio.textprep.hyphens import LineEndHyphenStep
from sci2audio.textprep.links import LinkStep
from sci2audio.textprep.numbers import NumbersStep
from sci2audio.textprep.placeholders import (
    CodeNoticeStep,
    FormulaNoticeStep,
    TableFigureNoticeStep,
    notice_read,
    read_over,
)
from sci2audio.textprep.plugins import (
    PLUGIN_GROUP,
    PLUGIN_TIMEOUT,
    InstalledSteps,
    LoadedPlugins,
    PluginInfo,
    PluginProblem,
    installed_steps,
    load_plugin_steps,
)
from sci2audio.textprep.references import (
    GERMAN_REFERENCE_TITLES,
    REFERENCE_NAMES,
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
from sci2audio.textprep.spoken import PAUSE_MARK, spoken_text, unspoken
from sci2audio.textprep.statistics import StatisticsStep
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
from sci2audio.textprep.units import UnitStep
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
    "GERMAN_REFERENCE_TITLES",
    "PAUSE_MARK",
    "PLUGIN_GROUP",
    "PLUGIN_TIMEOUT",
    "REFERENCE_NAMES",
    "REFERENCE_TITLES",
    "TEXT_STEP_API",
    "WORDING",
    "AbbreviationStep",
    "AffiliationMarkStep",
    "Category",
    "CitationStep",
    "CodeNoticeStep",
    "FootnoteStep",
    "FootnoteTextStep",
    "FormulaNoticeStep",
    "FurnitureStep",
    "HiddenRunStep",
    "InstalledSteps",
    "LineEndHyphenStep",
    "LinkStep",
    "LoadedPlugins",
    "NumbersStep",
    "Outcome",
    "PluginInfo",
    "PluginProblem",
    "ReferenceListStep",
    "Stage",
    "StatisticsStep",
    "Status",
    "StepContext",
    "StepError",
    "StepProblem",
    "StepRun",
    "TableFigureNoticeStep",
    "TextStep",
    "UnicodeStep",
    "UnitStep",
    "Utterance",
    "Wording",
    "check_registry",
    "cut_utterances",
    "installed_steps",
    "is_reference_title",
    "load_plugin_steps",
    "notice_read",
    "overlap",
    "read_over",
    "run_steps",
    "spoken_text",
    "step_problems",
    "unspoken",
    "whole_block",
    "wording_for",
]
