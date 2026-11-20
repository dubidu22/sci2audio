"""Text steps from other packages, through the `sci2audio.text_steps` entry point (#216, PE-10).

An entry point names a `TextStep` subclass or a callable with no arguments that returns a
`TextStep`; its name is the step's id. `load_plugin_steps` loads every entry point it can and
records a `PluginProblem` for each one it cannot, so one broken plugin never keeps the others
out. `installed_steps` puts the plugins after the built-in steps of their stage, by id: a
built-in edit wins an overlap (Q15), so a plugin adds to the reading and never overrides a
built-in rule (D-836).

Every plugin runs behind a guard. It gets a copy of the document, so a plugin that changes
the document it was given changes nothing the other steps see; it runs in a worker thread
with a time limit; and any exception but Ctrl+C counts as a failure, `SystemExit` and other
BaseExceptions included. The runner then drops the step's edits and records the problem, as
for any failing step (D-111). A thread cannot be stopped:
a plugin past its time limit is left running with its result thrown away (Q5 of the plan).
Nothing here runs at import time; the app loads the plugins once per `JobRunner`.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points

from sci2audio.core import Document, Edit
from sci2audio.textprep.registry import BUILT_IN_STEPS
from sci2audio.textprep.steps import (
    Category,
    Stage,
    StepContext,
    StepError,
    TextStep,
    step_problems,
)

PLUGIN_GROUP = "sci2audio.text_steps"
PLUGIN_TIMEOUT = 60.0  # seconds per plugin per document; built-in steps take well under one


@dataclass(frozen=True)
class PluginInfo:
    """A plugin step that loaded, for the report."""

    step: str  # the step's id, also the entry point's name
    category: Category
    distribution: str  # the installed package that holds the entry point; "" if unknown
    version: str
    entry_point: str  # "module:attribute"


@dataclass(frozen=True)
class PluginProblem:
    """An entry point whose step was not loaded, and why."""

    name: str  # the entry point's name
    distribution: str
    message: str


@dataclass(frozen=True)
class LoadedPlugins:
    """The plugin steps that loaded (guarded, by id) and the entry points that did not."""

    steps: tuple[TextStep, ...]
    plugins: tuple[PluginInfo, ...]
    problems: tuple[PluginProblem, ...]


class InstalledSteps(tuple[TextStep, ...]):
    """The steps a job runs, in run order, and what loading the plugins found.

    A tuple, so it goes wherever a sequence of steps goes; `run_steps` copies `plugins` and
    `problems` into its result, so the report lists them.
    """

    plugins: tuple[PluginInfo, ...]
    problems: tuple[PluginProblem, ...]

    def __new__(
        cls,
        steps: Iterable[TextStep],
        plugins: tuple[PluginInfo, ...] = (),
        problems: tuple[PluginProblem, ...] = (),
    ) -> InstalledSteps:
        made = super().__new__(cls, steps)
        made.plugins = plugins
        made.problems = problems
        return made


def load_plugin_steps(
    points: Iterable[EntryPoint] | None = None,
    *,
    reserved: Iterable[str] | None = None,
    timeout: float = PLUGIN_TIMEOUT,
) -> LoadedPlugins:
    """Load the steps of the `sci2audio.text_steps` entry points.

    `points` defaults to the installed entry points; `reserved` to the ids of the built-in
    steps, which no plugin may take.
    """
    if points is None:
        points = entry_points(group=PLUGIN_GROUP)
    taken = {step.id for step in BUILT_IN_STEPS} if reserved is None else set(reserved)
    problems: list[PluginProblem] = []
    found: dict[str, list[tuple[TextStep, PluginInfo]]] = {}
    seen: set[tuple[str, str]] = set()
    for point in points:
        if (point.name, point.value) in seen:  # one distribution on the path twice
            continue
        seen.add((point.name, point.value))
        distribution, version = _distribution(point)
        try:
            step = _step(point, taken, timeout)
        except _Rejected as rejected:
            problems.append(PluginProblem(point.name, distribution, str(rejected)))
            continue
        info = PluginInfo(step.id, step.category, distribution, version, point.value)
        step.plugin = info
        found.setdefault(step.id, []).append((step, info))
    steps: list[TextStep] = []
    plugins: list[PluginInfo] = []
    for step_id in sorted(found):
        if len(found[step_id]) > 1:  # neither wins: the result must not hang on install order
            problems += [
                PluginProblem(step_id, info.distribution, "more than one plugin has this id")
                for _, info in found[step_id]
            ]
            continue
        [(step, info)] = found[step_id]
        steps.append(step)
        plugins.append(info)
    return LoadedPlugins(tuple(steps), tuple(plugins), tuple(problems))


def installed_steps(
    built_in: Sequence[TextStep] = BUILT_IN_STEPS,
    entry_points: Iterable[EntryPoint] | None = None,
    *,
    timeout: float = PLUGIN_TIMEOUT,
) -> InstalledSteps:
    """The built-in steps with the plugins, each plugin after the built-in steps of its stage."""
    loaded = load_plugin_steps(
        entry_points, reserved=[step.id for step in built_in], timeout=timeout
    )
    ordered = [
        step
        for stage in (Stage.BLOCK, Stage.INLINE, Stage.MOVE)
        for steps in (built_in, loaded.steps)
        for step in steps
        if step.stage is stage
    ]
    return InstalledSteps(ordered, loaded.plugins, loaded.problems)


class _Rejected(Exception):
    pass


def _distribution(point: EntryPoint) -> tuple[str, str]:
    """The name and version of the package that holds the entry point; ("", "") if it does
    not say. A damaged install of someone else's package must not stop sci2audio."""
    try:
        dist = point.dist
        if dist is None:
            return "", ""
        metadata = dist.metadata
        # .get, not [...]: a missing field is None here, never a deprecation warning or a
        # KeyError
        return str(metadata.get("Name") or ""), str(metadata.get("Version") or "")
    except KeyboardInterrupt:
        raise
    except BaseException:
        return "", ""


def _said(error: BaseException) -> str:
    try:
        return f"{type(error).__name__}: {error}"
    except KeyboardInterrupt:
        raise
    except BaseException:
        return type(error).__name__


def _step(point: EntryPoint, taken: set[str], timeout: float) -> _GuardedStep:
    """The entry point's step behind the guard; _Rejected if it is not one this sci2audio
    can run.

    Everything that touches the plugin's objects is plugin code and may fail in any way: a
    property that raises, a BaseException that is not an Exception. The runner is made at
    start-up, so such a failure here would stop every command; it rejects the plugin
    instead. Only Ctrl+C gets through.
    """
    try:
        made = point.load()
    except KeyboardInterrupt:
        raise
    except BaseException as error:
        raise _Rejected(f"could not be loaded: {_said(error)}") from error
    try:
        if not callable(made):
            raise _Rejected(f"{point.value} is not a TextStep class or a factory")
        try:
            step = made()
        except KeyboardInterrupt:
            raise
        except BaseException as error:
            raise _Rejected(f"failed to make its step: {_said(error)}") from error
        if not isinstance(step, TextStep):
            raise _Rejected(f"did not give a TextStep, got {type(step).__name__}")
        if not _declares_version(step):
            raise _Rejected(
                "does not declare api_version; set api_version = 1 (the text-step contract "
                "it targets) in the step's class"
            )
        # the attributes are read once, into the guard; every later check and the runner
        # read the guard's copies, never the plugin's code again
        step = _GuardedStep(step, timeout, None)
    except (_Rejected, KeyboardInterrupt):
        raise
    except BaseException as error:
        raise _Rejected(f"failed while its attributes were read: {_said(error)}") from error
    if problems := step_problems(step):
        raise _Rejected("; ".join(problems))
    if point.name != step.id:
        raise _Rejected(f"entry point name {point.name!r} is not the step's id {step.id!r}")
    if step.id in taken:
        raise _Rejected(f"a built-in step has the id {step.id!r}")
    return step


def _declares_version(step: TextStep) -> bool:
    """True if the plugin names its contract itself; TextStep's own default does not count,
    or a step written for one contract would claim every later one."""
    if "api_version" in vars(step):
        return True
    for cls in type(step).__mro__:
        if cls is TextStep:
            return False
        if "api_version" in vars(cls):
            return True
    return False


def guarded(
    step: TextStep, *, timeout: float = PLUGIN_TIMEOUT, plugin: PluginInfo | None = None
) -> TextStep:
    """The step behind the plugin guard."""
    return _GuardedStep(step, timeout, plugin)


class _GuardedStep(TextStep):
    """A plugin step with its own `find`: a copy of the document, a worker thread, a limit.

    Takes the plugin's declared attributes; `handles` is TextStep's own, so a plugin's
    languages decide which jobs it runs in.
    """

    def __init__(self, step: TextStep, timeout: float, plugin: PluginInfo | None) -> None:
        self.step = step
        self.timeout = timeout
        self.plugin = plugin
        self.id = step.id
        self.languages = step.languages
        self.category = step.category
        self.stage = step.stage
        self.api_version = step.api_version

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        given = copy.deepcopy(document)
        result: dict[str, object] = {}

        def work() -> None:
            try:
                result["edits"] = self.step.find(given, context)
            except BaseException as error:  # handed to the job's thread below
                result["error"] = error

        worker = threading.Thread(target=work, name=f"text step {self.id}", daemon=True)
        worker.start()
        worker.join(self.timeout)
        if worker.is_alive():
            raise StepError(f"took longer than {self.timeout:g} s; its edits are left out")
        error = result.get("error")
        if isinstance(error, KeyboardInterrupt | Exception):
            raise error  # Ctrl+C stops the job; the runner reports an Exception as it is
        if isinstance(error, SystemExit):
            raise StepError(f"called SystemExit({error.code!r})") from error
        if isinstance(error, BaseException):  # a BaseException would end the job (S1)
            raise StepError(f"raised {_said(error)}") from error
        try:
            changed = given != document
        except KeyboardInterrupt:
            raise
        except BaseException as error:  # the plugin left in its copy what cannot compare
            raise StepError(f"left its copy of the document unreadable: {_said(error)}") from error
        if changed:
            raise StepError("changed the document it was given; a step may only propose edits")
        return result["edits"]  # type: ignore[return-value]  # checked by the runner

    def __repr__(self) -> str:
        return f"<text-step plugin {self.id}>"
