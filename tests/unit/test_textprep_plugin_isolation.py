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
import time
import traceback
from importlib.metadata import EntryPoint
from pathlib import Path

import broken_text_plugins as broken
import pytest

from sci2audio.app import JobRunner, JobSettings
from sci2audio.core import BlockKind
from sci2audio.testing import make_document
from sci2audio.textprep import StepContext, StepError, run_steps
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


def run_with(attribute: str, timeout: float = 5.0):
    step_id = getattr(broken, attribute).id
    entry = EntryPoint(step_id, f"broken_text_plugins:{attribute}", PLUGIN_GROUP)
    steps = installed_steps(entry_points=[entry], timeout=timeout)
    assert steps.problems == ()
    return run_steps(paper(), EN, steps)


def test_a_planted_object_whose_comparison_blocks_is_given_up(hang) -> None:
    started = time.monotonic()
    run = run_with("BlockingEqStep", timeout=0.2)
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


@pytest.mark.quarantined(
    issue=804,
    reason="no __del__ recorded by the final gc.collect() when many suites run at once",
)
@pytest.mark.parametrize("attribute", ["CyclicPlantStep", "CyclicErrorStep"])
def test_an_object_in_a_reference_cycle_is_freed_in_the_worker(attribute: str, calls) -> None:
    run = run_with(attribute)
    gc.collect()  # what the worker left for the collector would die here, in this thread
    assert [p.step for p in run.problems] == [getattr(broken, attribute).id]
    assert "__del__" in [dunder for dunder, _ in calls]
    assert outside_the_guard(calls) == []


def test_a_plugin_error_whose_str_blocks_is_given_up(hang) -> None:
    started = time.monotonic()
    run = run_with("SlowMessageStep", timeout=0.2)
    # clock-bound: the planted hang never ends; 3 s is 15 times the 0.2 s limit
    assert time.monotonic() - started < 3
    [problem] = run.problems
    assert problem.step == "slow-message"
    assert "took longer than 0.2 s" in problem.message
