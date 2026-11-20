"""The public text-step interface: everything a plugin may rely on (#216, PE-10, D-57).

A plugin is a `TextStep` subclass that proposes marked edits (`Edit`) and never changes the
text; another package makes it known through the `sci2audio.text_steps` entry point (see
docs/plugins.md). The names in `__all__` are the contract `TEXT_STEP_API` numbers. A change
that would break a step written against them raises `TEXT_STEP_API`: a field removed or
renamed, a new required argument, stricter checks in `Edit` or `Span`, a new abstract
method. Additions do not: a field with a default, a new `Category`, a new `EditKind` no
step has to use. A plugin names the contract it targets with `api_version` in its own
class, and is not loaded by a sci2audio with another one.

Everything else in sci2audio may change in any release: the runner and its results, the
registry and the built-in steps, the utterance cutter. The conformance suite every plugin
should pass is `sci2audio.testing` (`check_text_step`).
"""

from sci2audio.core import (
    Block,
    BlockKind,
    Document,
    Edit,
    EditKind,
    FurnitureRole,
    Part,
    Section,
    Span,
)
from sci2audio.textprep.plugins import (
    PLUGIN_GROUP,
    LoadedPlugins,
    PluginInfo,
    PluginProblem,
    load_plugin_steps,
)
from sci2audio.textprep.steps import (
    ANY_LANGUAGE,
    TEXT_STEP_API,
    Category,
    Stage,
    StepContext,
    TextStep,
)

__all__ = [
    "ANY_LANGUAGE",
    "PLUGIN_GROUP",
    "TEXT_STEP_API",
    "Block",
    "BlockKind",
    "Category",
    "Document",
    "Edit",
    "EditKind",
    "FurnitureRole",
    "LoadedPlugins",
    "Part",
    "PluginInfo",
    "PluginProblem",
    "Section",
    "Span",
    "Stage",
    "StepContext",
    "TextStep",
    "load_plugin_steps",
]
