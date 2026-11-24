"""No code of a text-step plugin runs outside the guard's worker threads (#693, META-03).

A hostile plugin hands over traced objects at every point where it can: its id and
languages, the step its factory makes, its category and stage, what `find` raises, the list
it returns, the edits in it, their offsets and texts, and objects planted in its copies of
the document and the context. Each traced dunder records the thread it runs in. The job's
thread may make the guard wait, but it must never run one of them: a plugin's code there
runs outside the time limit and outside any `try`, so it could hang or stop the job.
"""

import gc
import json
import threading
import time
import traceback
from importlib.metadata import EntryPoint
from pathlib import Path

import broken_text_plugins as broken
import pytest

from sci2audio.app import JobRunner, JobSettings
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, StepError, plugins, run_steps
from sci2audio.textprep.api import PLUGIN_GROUP
from sci2audio.textprep.plugins import installed_steps

EN = StepContext("en")
WORKERS = ("loading text step ", "text step ")  # the thread names the guard gives

# the case, and whether the plugin ends as a problem rather than a step that runs
CASES = {
    "id": False,
    "languages": False,
    "step": False,
    "category": True,
    "stage": True,
    "exception": True,
    "system-exit": True,
    "base-exception": True,
    "list": False,
    "edit": False,
    "offsets": False,
    "replacement": False,
    "document": True,
    "context": False,
}


@pytest.fixture(autouse=True)
def calls():
    KEPT.clear()
    gc.collect()  # objects of an earlier test die now, not while this one records
    broken.CALLS.clear()
    yield broken.CALLS
    broken.CALLS.clear()


@pytest.fixture
def hang():
    broken.HANG.clear()
    yield
    broken.HANG.set()


def paper():
    return make_document(
        [(BlockKind.PARAGRAPH, "Smith & Jones agree."), (BlockKind.PARAGRAPH, "A second one.")]
    )


# The steps live as long as a job's runner, and the plugin's step object with them, so its
# own `__del__` runs where the runner is dropped (docs/plugins.md); this list keeps them
# until the test has looked.
KEPT: list[object] = []


def hostile_steps(case: str):
    attribute = case.replace("-", "_")
    entry = EntryPoint("hostile", f"broken_text_plugins:HOSTILE.{attribute}", PLUGIN_GROUP)
    steps = installed_steps(entry_points=[entry], timeout=5.0, load_timeout=5.0)
    KEPT.append(steps)
    return steps


def outside_the_guard(calls: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(dunder, thread) for dunder, thread in calls if not thread.startswith(WORKERS)]


def problems_of_a_run(case: str, strict: bool) -> list[str]:
    steps = hostile_steps(case)
    try:
        run = run_steps(paper(), EN, steps, strict=strict)
    except StepError as error:
        "".join(traceback.format_exception(error))  # what a crash report would show
        return ["hostile"]
    run.script()
    return [p.name for p in steps.problems] + [p.step for p in run.problems]


def problems_of_a_job(case: str, folder: Path) -> list[str]:
    source = folder / "note.txt"
    source.write_text("Smith & Jones agree.\n", encoding="utf-8")
    job = JobRunner(hostile_steps(case)).run_script(source, JobSettings(), folder / "w")
    job.files.report_markdown.read_text(encoding="utf-8")
    data = json.loads(job.files.report_json.read_text(encoding="utf-8"))
    return [problem["step"] for problem in data.get("problems", [])]


@pytest.mark.parametrize("path", ["run", "strict-run", "job-and-report"])
@pytest.mark.parametrize("case", CASES)
def test_no_plugin_object_is_touched_outside_a_guard_worker(
    case: str, path: str, calls, tmp_path: Path
) -> None:
    if path == "job-and-report":
        problems = problems_of_a_job(case, tmp_path)
    else:
        problems = problems_of_a_run(case, strict=path == "strict-run")
    assert outside_the_guard(calls) == []
    assert ("hostile" in problems) is CASES[case]


def test_the_tracer_records_the_worker_threads(calls) -> None:
    run_steps(paper(), EN, hostile_steps("list"))
    assert calls
    assert all(thread.startswith(WORKERS) for _, thread in calls)


# ---- the cases #693 names ---------------------------------------------------------------


def steps_of(attribute: str, **timeouts: float):
    step_id = getattr(broken, attribute).id
    entry = EntryPoint(step_id, f"broken_text_plugins:{attribute}", PLUGIN_GROUP)
    steps = installed_steps(entry_points=[entry], **timeouts)
    assert steps.problems == ()
    return steps


def run_with(attribute: str, timeout: float = 5.0):
    return run_steps(paper(), EN, steps_of(attribute, timeout=timeout))


def test_a_planted_object_whose_comparison_blocks_is_given_up(hang) -> None:
    steps = steps_of("BlockingEqStep", timeout=0.2)
    started = time.monotonic()  # loading has its own limit, and a full collection after it
    run = run_steps(paper(), EN, steps)
    # clock-bound: the planted hang never ends; 3 s is 15 times the 0.2 s limit
    assert time.monotonic() - started < 3
    [problem] = run.problems
    assert problem.step == "blocking-eq"
    assert "took longer than 0.2 s" in problem.message


def test_an_offset_whose_index_raises_is_read_as_a_plain_int() -> None:
    run = run_with("NoIndexStep")
    assert run.problems == ()
    [edit] = [edit for edit in run.accepted if edit.step == "no-index"]
    assert [type(n) for n in (edit.span.block, edit.span.start, edit.span.end)] == [int] * 3
    assert "Smith" not in "".join(piece.text for piece in run.script())


class _Held:
    """A cycle whose finalizer keeps its collection running until it is released."""

    def __init__(self, inside: threading.Event, release: threading.Event) -> None:
        self.inside, self.release, self.me = inside, release, self

    def __del__(self) -> None:
        self.inside.set()
        self.release.wait(10)  # a bound only, so a broken test cannot hang the suite


@pytest.fixture
def collector_busy(monkeypatch):
    """Another thread inside `gc.collect()`, as in the #804 repro: there CPython's
    `gc.collect()` returns at once without collecting. `busy(until_worker_tried=True)`
    releases it once a guard worker's `gc.collect()` has returned, so that call frees
    nothing on every run; without, it stays inside until the test ends. Automatic
    collection is off meanwhile, so no other thread collects by chance."""
    collect = gc.collect
    tried = threading.Event()
    release = threading.Event()
    threads: list[threading.Thread] = []

    def collect_and_tell(*args):
        freed = collect(*args)
        if threading.current_thread().name.startswith("text step "):
            tried.set()
        return freed

    def busy(until_worker_tried: bool) -> None:
        inside = threading.Event()

        def hold() -> None:
            _Held(inside, release)
            collect()

        threads.append(threading.Thread(target=hold, name="busy collector", daemon=True))
        if until_worker_tried:
            threads.append(
                threading.Thread(target=lambda: tried.wait(10) and release.set(), daemon=True)
            )
        for thread in threads:
            thread.start()
        assert inside.wait(10)

    was_enabled = gc.isenabled()
    gc.disable()
    monkeypatch.setattr(gc, "collect", collect_and_tell)
    try:
        yield busy
    finally:
        release.set()
        for thread in threads:
            thread.join(10)
        if was_enabled:
            gc.enable()


@pytest.mark.parametrize("busy", [False, True], ids=["alone", "another-thread-collecting"])
@pytest.mark.parametrize("attribute", ["CyclicPlantStep", "CyclicErrorStep"])
def test_an_object_in_a_reference_cycle_is_freed_in_the_worker(
    attribute: str, busy: bool, calls, collector_busy
) -> None:
    steps = steps_of(attribute, timeout=5.0)
    if busy:
        collector_busy(until_worker_tried=True)
    run = run_steps(paper(), EN, steps)
    # freed before the run returned, with no collection of this thread's
    assert "__del__" in [dunder for dunder, _ in calls]
    gc.collect()  # what the worker still left for the collector would die here, in this thread
    assert outside_the_guard(calls) == []
    assert [p.step for p in run.problems] == [getattr(broken, attribute).id]


def test_a_worker_that_cannot_collect_gives_up_with_a_clear_problem(
    calls, collector_busy, monkeypatch
) -> None:
    steps = steps_of("ZetaStep", timeout=5.0)
    monkeypatch.setattr(plugins, "PLUGIN_COLLECT_TIMEOUT", 0.2)
    collector_busy(until_worker_tried=False)
    started = time.monotonic()
    run = run_steps(paper(), EN, steps)
    # clock-bound: the other thread never leaves its collection; 3 s is 15 times the bound
    assert time.monotonic() - started < 3
    [problem] = run.problems
    assert problem.step == "zeta"
    assert "not freed within 0.2 s" in problem.message


def test_a_young_collection_in_the_worker_is_not_taken_for_its_full_one(calls, monkeypatch) -> None:
    """A collection that is due runs in whichever thread checks for one, the worker
    included, and is often a young one: it can free a fresh canary in the worker while an
    older cycle of the plugin stays. Here the worker's first two `gc.collect()` calls meet
    another thread's young collection, so they return at once; before the second, a young
    collection runs in the worker, standing for the one CPython would run there."""
    steps = steps_of("AgedCycleStep", timeout=5.0)
    collect = gc.collect
    tries: list[None] = []

    def while_another_thread_collects() -> int:
        inside, release = threading.Event(), threading.Event()

        def hold() -> None:
            _Held(inside, release)
            collect(0)

        other = threading.Thread(target=hold, name="young collector", daemon=True)
        other.start()
        assert inside.wait(10)
        freed = collect()
        release.set()
        other.join(10)
        return freed

    def guard_collect(*args):
        if args or not threading.current_thread().name.startswith("text step "):
            return collect(*args)  # the plugin's own young collection, and everyone else's
        tries.append(None)
        if len(tries) == 2:
            collect(0)
        return while_another_thread_collects() if len(tries) <= 2 else collect()

    was_enabled = gc.isenabled()
    gc.disable()
    monkeypatch.setattr(gc, "collect", guard_collect)
    try:
        run = run_steps(paper(), EN, steps)
        # freed before the run returned, with no collection of this thread's
        assert "__del__" in [dunder for dunder, _ in calls]
    finally:
        monkeypatch.undo()
        if was_enabled:
            gc.enable()
    gc.collect()  # what the worker still left for the collector would die here, in this thread
    assert outside_the_guard(calls) == []
    assert run.problems == ()


def test_a_finalizer_that_hangs_in_the_collection_after_the_call_is_given_up(
    calls, hang, monkeypatch
) -> None:
    steps = steps_of("HangingFinalizerStep", timeout=5.0)
    others = steps_of("CyclicPlantStep", timeout=5.0)
    monkeypatch.setattr(plugins, "PLUGIN_COLLECT_TIMEOUT", 0.2)
    monkeypatch.setattr(plugins, "_hung_collection", None)
    started = time.monotonic()
    run = run_steps(paper(), EN, steps)
    # clock-bound: the planted finalizer never ends; 3 s is 15 times the bound
    assert time.monotonic() - started < 3
    [problem] = run.problems
    assert problem.step == "hanging-finalizer"
    assert "not freed within 0.2 s after its call: the collection after it" in problem.message
    # the collector stays held by that finalizer, and so nothing is freed anywhere: a later
    # plugin neither waits for it nor takes the blame
    later = run_steps(paper(), EN, others)
    [problem] = later.problems
    assert problem.step == "cyclic-plant"
    assert "changed the document" in problem.message
    assert outside_the_guard(calls) == []


def test_a_plugin_error_whose_str_blocks_is_given_up(hang) -> None:
    steps = steps_of("SlowMessageStep", timeout=0.2)
    started = time.monotonic()  # loading has its own limit, and a full collection after it
    run = run_steps(paper(), EN, steps)
    # clock-bound: the planted hang never ends; 3 s is 15 times the 0.2 s limit
    assert time.monotonic() - started < 3
    [problem] = run.problems
    assert problem.step == "slow-message"
    assert "took longer than 0.2 s" in problem.message
