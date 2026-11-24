"""Text steps from other packages, through the `sci2audio.text_steps` entry point (#216, PE-10).

An entry point names a `TextStep` subclass or a callable with no arguments that returns a
`TextStep`; its name is the step's id. `load_plugin_steps` loads every entry point it can and
records a `PluginProblem` for each one it cannot, so one broken plugin never keeps the others
out. `installed_steps` puts the plugins after the built-in steps of their stage, by id: a
built-in edit wins an overlap (Q15), so a plugin adds to the reading and never overrides a
built-in rule (D-836).

Every plugin runs behind a guard. It gets copies of the document and the context, so a
plugin that changes what it was given changes nothing the other steps see; it runs in a
worker thread with a time limit; and any exception but Ctrl+C counts as a failure,
`SystemExit` and other BaseExceptions included. The runner then drops the step's edits and
records the problem, as for any failing step (D-111). Loading a plugin (its import, its
factory, its attributes) runs in a worker thread with a time limit too: the app loads the
plugins when it starts, so a plugin that hangs there would stop every command (#684). A
thread cannot be stopped: a plugin past its time limit is left running with its result
thrown away (Q5 of the plan). Nothing here runs at import time; the app loads the plugins
once per `JobRunner`.

No object of the plugin's leaves a worker (#693): any of them may run plugin code when it
is compared, hashed, shown or dropped, and only the worker is under the time limit. So the
worker hands back plain built-in values (copies of the id and languages, edits rebuilt from
plain ints and strs) or the text of a failure, never what the plugin returned or raised;
what a call left in reference cycles is freed before the worker returns, in the worker
unless another thread's collection took it first, and never in the job's thread; if that
cannot be made sure within `PLUGIN_COLLECT_TIMEOUT`, the call fails (#804). Not covered
is what outlives a call: the plugin's step object lives as long as the job's steps, and
what the plugin keeps on it or in its module's globals is freed wherever that is dropped,
so a finalizer (`__del__`) of such an object may run in the job's thread.
"""

from __future__ import annotations

import copy
import gc
import threading
import time
import weakref
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from sci2audio.core import Document, Edit, EditKind, Span
from sci2audio.textprep.registry import BUILT_IN_STEPS
from sci2audio.textprep.steps import (
    TEXT_STEP_API,
    Category,
    Stage,
    StepContext,
    StepError,
    TextStep,
    step_problems,
)

PLUGIN_GROUP = "sci2audio.text_steps"
PLUGIN_TIMEOUT = 60.0  # seconds per plugin per document; built-in steps take well under one
# seconds per entry point: on the start-up path of every command, yet room for a heavy import
# on a slow disk (D-845)
PLUGIN_LOAD_TIMEOUT = 30.0
# seconds the guard waits, after a plugin's call and on top of its limit, for the cycles the
# call left to be freed; past it the call fails rather than leave them to the job (#804)
PLUGIN_COLLECT_TIMEOUT = 5.0


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


class PluginError(StepError):
    """A plugin's `find` raised an Exception; the message is that exception as text."""


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
    steps, which no plugin may take. Each entry point has `PLUGIN_LOAD_TIMEOUT` to load.
    """
    return _load(points, reserved, timeout, PLUGIN_LOAD_TIMEOUT)


def _load(
    points: Iterable[EntryPoint] | None,
    reserved: Iterable[str] | None,
    timeout: float,
    load_timeout: float,
) -> LoadedPlugins:
    if points is None:
        points = entry_points(group=PLUGIN_GROUP)
    taken = {step.id for step in BUILT_IN_STEPS} if reserved is None else set(reserved)
    problems: list[PluginProblem] = []
    found: dict[str, list[tuple[TextStep, PluginInfo]]] = {}
    seen: set[tuple[str, str]] = set()
    # (distribution, top-level package) -> the entry point whose load ran out of time, and
    # its worker: while that worker lives it holds the package's import lock, so another
    # entry point of the package could only wait out its own limit too (#694)
    hung: dict[tuple[str, str], tuple[str, threading.Thread]] = {}
    for point in points:
        if (point.name, point.value) in seen:  # one distribution on the path twice
            continue
        seen.add((point.name, point.value))
        distribution, version = _distribution(point)
        package = (distribution, point.value.partition(":")[0].strip().partition(".")[0])
        if package in hung and hung[package][1].is_alive():
            message = (
                f"left out: {hung[package][0]!r} of the same package {package[1]!r} took "
                f"longer than {load_timeout:g} s to load"
            )
            problems.append(PluginProblem(point.name, distribution, message))
            continue
        try:
            step = _step(point, taken, timeout, load_timeout)
        except _TimedOut as timed_out:
            hung[package] = (point.name, timed_out.worker)
            message = f"took longer than {load_timeout:g} s to load; left out"
            problems.append(PluginProblem(point.name, distribution, message))
            continue
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
    load_timeout: float | None = None,
) -> InstalledSteps:
    """The built-in steps with the plugins, each plugin after the built-in steps of its stage.

    `load_timeout` defaults to `PLUGIN_LOAD_TIMEOUT` as it is when the function is called.
    """
    loaded = _load(
        entry_points,
        [step.id for step in built_in],
        timeout,
        PLUGIN_LOAD_TIMEOUT if load_timeout is None else load_timeout,
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


class _TimedOut(Exception):
    def __init__(self, worker: threading.Thread) -> None:
        super().__init__()
        self.worker = worker  # still running


@dataclass(frozen=True)
class _Failure:
    """Why a call in the worker failed, as plain text made in the worker."""

    message: str
    raised: bool = False  # the plugin's find raised an Exception; `message` is its text


# The guard worker whose collection after a call did not end, and its state. While it stays
# inside that collection the collector frees nothing in any thread, the job's included, so
# later calls do not wait for it. One per process, as the collector is (#804).
_hung_collection: tuple[threading.Thread, dict[str, Any]] | None = None


def _in_worker[T](call: Callable[[], T], timeout: float, name: str) -> T | _Failure:
    """`call()` in a daemon thread: its result, which must hold only built-in values, or a
    _Failure; _TimedOut if the call is still running after `timeout` seconds. What the call
    raised never reaches this thread, only its text: an exception holds the frames it
    passed, and so the plugin's objects. Ctrl+C there is raised here anew. The thread
    cannot be stopped and is left to finish on its own; a daemon thread never keeps the
    program from ending.

    After the call the thread makes sure the garbage the call left in cycles is freed, and
    this thread sleeps until then, up to `PLUGIN_COLLECT_TIMEOUT` seconds more: the limit
    is for the plugin's code, and a full collection of a large program takes its own time.
    If it is not sure by then, the result is a _Failure."""
    global _hung_collection
    result: dict[str, Any] = {"collecting": False}
    called, collected, settled = threading.Event(), threading.Event(), threading.Event()
    late: list[str] = []
    limit = PLUGIN_COLLECT_TIMEOUT

    def work() -> None:
        try:
            result["value"] = call()
        except KeyboardInterrupt:
            result["interrupted"] = True
        except BaseException as error:  # a path the call does not turn into a _Failure
            result["value"] = _Failure(f"failed: {_said(error)}")
        called.set()
        # what the call left in reference cycles is freed only by the collector, which would
        # otherwise run its finalizers in whatever thread triggers it next: the job's
        result["freed"] = _cycles_freed(limit, result)
        collected.set()

    def watch() -> None:
        # the job's thread sleeps until the cycles are freed or a limit has passed: awake, it
        # could run a collection that is due, and with it the plugin's finalizers
        if not called.wait(timeout):
            late.append("call")
        elif "interrupted" not in result and not collected.wait(limit):
            late.append("collection")
        settled.set()

    worker = threading.Thread(target=work, name=name, daemon=True)
    worker.start()
    threading.Thread(target=watch, name=f"{name} (limits)", daemon=True).start()
    if not settled.wait(timeout + limit + 1.0):  # the watch itself was held up
        late.append("call" if not called.is_set() else "collection")
    if late[:1] == ["call"]:
        raise _TimedOut(worker)
    if "interrupted" in result:
        raise KeyboardInterrupt
    if late and result["collecting"]:  # inside its own collection: a finalizer of it hangs
        _hung_collection = (worker, result)
        return _Failure(
            f"its objects were not freed within {limit:g} s after its call: the collection "
            f"after it did not end"
        )
    if late or not result["freed"]:
        return _Failure(
            f"its objects were not freed within {limit:g} s after its call: another thread "
            f"kept the garbage collector busy"
        )
    return result["value"]


def _cycles_freed(limit: float, state: dict[str, Any]) -> bool:
    """True once every reference cycle that existed when this was called is freed, False if
    that cannot be made sure within `limit` seconds. `state["collecting"]` is True while
    this thread is inside `gc.collect()`.

    While another thread is inside a collection, `gc.collect()` returns 0 at once and frees
    nothing (#804), so only a call that found something was a collection of this thread's
    own, and that is a full one, started after the call; a garbage canary makes sure there
    is something to find. That the canary is gone proves nothing: a collection that is due
    runs in whichever thread checks for one, this one included, and is often a young one
    that leaves older cycles. Two more full collections ended anywhere prove it too: the
    second started after the first ended, so after this was called. While a guard worker
    hangs inside its collection nothing is freed anywhere, so this does not wait for it.
    """
    full_before = _full_collections()
    deadline = time.monotonic() + limit
    canary = _canary()
    while True:
        if canary() is None:
            canary = _canary()
        state["collecting"] = True
        found = gc.collect()
        state["collecting"] = False
        if found or _full_collections() >= full_before + 2:
            return True
        if _collector_held_by_a_hung_worker():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.001)  # lets the thread that is collecting finish


def _full_collections() -> int:
    """How many full collections have ended; CPython counts one as it ends."""
    return gc.get_stats()[2]["collections"]


def _collector_held_by_a_hung_worker() -> bool:
    hung = _hung_collection
    return hung is not None and hung[0].is_alive() and hung[1]["collecting"]


class _Canary:
    me: object


def _canary() -> weakref.ref[_Canary]:
    """A weakref to a new cycle of no use, left for the collector."""
    canary = _Canary()
    canary.me = canary
    return weakref.ref(canary)


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


def _step(point: EntryPoint, taken: set[str], timeout: float, load_timeout: float) -> _GuardedStep:
    """The entry point's step behind the guard; _Rejected if it is not one this sci2audio
    can run, _TimedOut if loading it takes longer than `load_timeout` seconds."""
    step = _in_worker(
        lambda: _loaded(point, taken, timeout), load_timeout, f"loading text step {point.name}"
    )
    if isinstance(step, _Failure):
        raise _Rejected(step.message)
    return step


def _loaded(point: EntryPoint, taken: set[str], timeout: float) -> _GuardedStep | _Failure:
    """`_made`, with a rejection as plain text: the _Rejected and the plugin's exception it
    was raised from die here, in the worker."""
    try:
        return _made(point, taken, timeout)
    except _Rejected as rejected:
        return _Failure(str.__str__(rejected.args[0]))


def _made(point: EntryPoint, taken: set[str], timeout: float) -> _GuardedStep:
    """The plugin's step, imported, made, checked and copied into the guard; _Rejected if
    it fails or breaks a rule. Runs in the loading worker, so it may be given up.

    Everything that touches the plugin's objects is plugin code and may fail or hang in any
    way: a property that raises, a BaseException that is not an Exception, an id whose repr
    raises, a version whose `!=` never returns. Checking the attributes is such code too.
    The runner is made at start-up, so such a failure here would stop every command; it
    rejects the plugin instead. Only Ctrl+C gets through. What leaves this function holds
    plain `str` and `tuple` copies, so the caller can hash, sort and show them safely.
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
        guard = _GuardedStep(step, timeout, None)
        if problems := step_problems(guard):
            raise _Rejected("; ".join(problems))
        guard.keep_plain_copies()
        if point.name != guard.id:
            raise _Rejected(f"entry point name {point.name!r} is not the step's id {guard.id!r}")
        if guard.id in taken:
            raise _Rejected(f"a built-in step has the id {guard.id!r}")
        return guard
    except (_Rejected, KeyboardInterrupt):
        raise
    except BaseException as error:
        raise _Rejected(f"failed while its attributes were read: {_said(error)}") from error


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
    """A plugin step with its own `find`: copies of its input, a worker thread, a limit.

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

    def keep_plain_copies(self) -> None:
        """Replace the checked values with plain built-in ones: a str or tuple subclass of
        the plugin's would run its own methods wherever the id is hashed, sorted or shown.
        `step_problems` checks with isinstance and str(), which an object can pass without
        being a str, a Category or a Stage; such a value is rejected here."""
        languages = tuple(self.languages)
        if not all(issubclass(type(language), str) for language in languages):
            names = ", ".join(type(language).__name__ for language in languages)
            raise _Rejected(
                f"languages must be a non-empty tuple of primary tags like 'en' or '*', "
                f"got a tuple of {names}"
            )
        for name, kind in (("category", Category), ("stage", Stage)):
            if type(getattr(self, name)) is not kind:
                raise _Rejected(
                    f"{name} must be a {kind.__name__}, got a {type(getattr(self, name)).__name__}"
                )
        self.id = str.__str__(self.id)
        self.languages = tuple(str.__str__(language) for language in languages)
        self.api_version = TEXT_STEP_API  # step_problems found it equal

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        try:
            edits = _in_worker(
                lambda: _run(self.step, document, context), self.timeout, f"text step {self.id}"
            )
        except _TimedOut:
            raise StepError(
                f"took longer than {self.timeout:g} s; its edits are left out"
            ) from None
        if isinstance(edits, _Failure):
            raise (PluginError if edits.raised else StepError)(edits.message)
        return edits  # checked further by the runner

    def __repr__(self) -> str:
        return f"<text-step plugin {self.id}>"


def _run(step: TextStep, document: Document, context: StepContext) -> list[Edit] | _Failure:
    """The plugin's `find` on copies of the document and the context, in the worker: its
    edits rebuilt from plain values, or why it failed. The copies, what `find` returned
    and what it raised are compared, read and dropped here."""
    given, its_context = copy.deepcopy(document), copy.deepcopy(context)
    try:
        edits = step.find(given, its_context)
    except KeyboardInterrupt:
        raise
    except Exception as error:  # the runner shows it as it is
        return _Failure(_said(error), raised=True)
    except SystemExit as error:
        return _Failure(f"called SystemExit({_shown(error.code)})")
    except BaseException as error:  # a BaseException would end the job
        return _Failure(f"raised {_said(error)}")
    try:
        changed = bool(given != document)
    except KeyboardInterrupt:
        raise
    except BaseException as error:  # the plugin left in its copy what cannot compare
        return _Failure(f"left its copy of the document unreadable: {_said(error)}")
    if changed:
        return _Failure("changed the document it was given; a step may only propose edits")
    try:
        return _plain_edits(edits)
    except _Rejected as rejected:
        return _Failure(str.__str__(rejected.args[0]))
    except KeyboardInterrupt:
        raise
    except BaseException as error:  # an edit's own code failed while it was read
        return _Failure(f"failed while its edits were read: {_said(error)}")


def _shown(value: object) -> str:
    try:
        return repr(value)
    except KeyboardInterrupt:
        raise
    except BaseException:
        return type(value).__name__


def _plain_edits(edits: object) -> list[Edit]:
    """The edits rebuilt from exact ints, strs and EditKinds; _Rejected if they are not a
    list of Edit. A subclass's own methods (`__eq__`, `__index__`, `__hash__` ...) would
    run wherever the runner compares, slices or sorts them."""
    if not isinstance(edits, list) or not all(isinstance(edit, Edit) for edit in edits):
        raise _Rejected(f"find must return a list of Edit, got {type(edits).__name__}")
    plain = []
    for edit in edits:
        kind = edit.kind
        if type(kind) is not EditKind:
            raise _Rejected(f"find returned an edit whose kind is not an EditKind, got {kind!r}")
        to = edit.to
        try:
            plain.append(
                Edit(
                    _plain_span(edit.span, "span"),
                    kind,
                    reason=_plain_text(edit.reason, "reason"),
                    step=_plain_text(edit.step, "step"),
                    replacement=_plain_text(edit.replacement, "replacement"),
                    to=None if to is None else _plain_span(to, "target"),
                )
            )
        except ValueError as error:  # core's own check, on the plain values
            raise _Rejected(f"find returned an edit that breaks the rules: {error}") from None
    return plain


def _plain_span(span: object, field: str) -> Span:
    if not isinstance(span, Span):
        raise _Rejected(f"find returned an edit whose {field} is not a Span")
    return Span(*(_whole(getattr(span, name), field) for name in ("block", "start", "end")))


def _whole(number: object, field: str) -> int:
    if not issubclass(type(number), int):
        raise _Rejected(
            f"find returned an edit whose {field} holds a {type(number).__name__}, "
            f"not a whole number"
        )
    return int.__index__(number)  # type: ignore[arg-type]  # an exact int, without its override


def _plain_text(text: object, field: str) -> str:
    if not issubclass(type(text), str):
        raise _Rejected(f"find returned an edit whose {field} is not a str")
    return str.__str__(text)  # type: ignore[arg-type]
