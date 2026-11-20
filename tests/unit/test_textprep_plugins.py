"""Text-step plugins: discovery through the entry point, order, and the guard (#216, PE-10)."""

import subprocess
import sys
import time
from importlib.metadata import EntryPoint
from pathlib import Path

import broken_text_plugins as broken
import pytest
from core_strategies import documents
from example_text_plugin import AmpersandStep
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.core import BlockKind
from sci2audio.testing import check_text_step, make_document
from sci2audio.textprep import (
    BUILT_IN_STEPS,
    Category,
    Stage,
    StepContext,
    StepError,
    check_registry,
    run_steps,
)
from sci2audio.textprep.api import (
    PLUGIN_GROUP,
    LoadedPlugins,
    PluginInfo,
    PluginProblem,
    load_plugin_steps,
)
from sci2audio.textprep.plugins import guarded, installed_steps

EN = StepContext("en")


def point(name: str, value: str) -> EntryPoint:
    return EntryPoint(name=name, value=value, group=PLUGIN_GROUP)


def broken_point(step_id: str, attribute: str) -> EntryPoint:
    return point(step_id, f"broken_text_plugins:{attribute}")


AMPERSAND = point("ampersand-and", "example_text_plugin:AmpersandStep")


def ids(loaded: LoadedPlugins) -> list[str]:
    return [step.id for step in loaded.steps]


def problem_for(loaded: LoadedPlugins, name: str) -> str:
    [found] = [problem for problem in loaded.problems if problem.name == name]
    return found.message


# ---- discovery ---------------------------------------------------------------------------


def test_a_class_and_a_factory_both_load() -> None:
    for value in ("example_text_plugin:AmpersandStep", "example_text_plugin:make_step"):
        loaded = load_plugin_steps([point("ampersand-and", value)])
        assert ids(loaded) == ["ampersand-and"]
        assert loaded.problems == ()
        assert loaded.plugins == (PluginInfo("ampersand-and", Category.CHARACTERS, "", "", value),)


def test_plugins_run_after_the_built_in_steps_of_their_stage_sorted_by_id() -> None:
    steps = installed_steps(
        entry_points=[
            broken_point("zeta", "ZetaStep"),
            broken_point("alpha", "AlphaStep"),
            broken_point("a-block-plugin", "BlockPlugin"),
        ]
    )
    check_registry(steps)
    order = [step.id for step in steps]
    built_in = [step.id for step in BUILT_IN_STEPS]
    last_block = max(i for i, s in enumerate(BUILT_IN_STEPS) if s.stage is Stage.BLOCK)
    last_inline = max(i for i, s in enumerate(BUILT_IN_STEPS) if s.stage is Stage.INLINE)
    assert order == [
        *built_in[: last_block + 1],
        "a-block-plugin",
        *built_in[last_block + 1 : last_inline + 1],
        "alpha",
        "zeta",
        *built_in[last_inline + 1 :],
    ]
    assert [info.step for info in steps.plugins] == ["a-block-plugin", "alpha", "zeta"]


def test_without_plugins_the_installed_steps_are_the_built_in_steps() -> None:
    steps = installed_steps(entry_points=[])
    assert tuple(steps) == BUILT_IN_STEPS
    assert steps.plugins == steps.problems == ()


def test_a_real_distribution_on_the_path_is_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = tmp_path / "fake_plugin-1.2.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: fake-plugin\nVersion: 1.2\n", encoding="utf-8"
    )
    (info / "entry_points.txt").write_text(
        f"[{PLUGIN_GROUP}]\nampersand-and = example_text_plugin:AmpersandStep\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    loaded = load_plugin_steps()
    assert loaded.plugins == (
        PluginInfo(
            "ampersand-and",
            Category.CHARACTERS,
            "fake-plugin",
            "1.2",
            "example_text_plugin:AmpersandStep",
        ),
    )


@pytest.mark.parametrize(
    ("entry", "says"),
    [
        (point("gone", "no_such_plugin_module:Step"), "could not be loaded: ModuleNotFoundError"),
        (broken_point("not-a-step", "NotAStep"), "did not give a TextStep"),
        (broken_point("failing", "failing_factory"), "RuntimeError: the model file is missing"),
        (broken_point("exiting", "exiting_factory"), "SystemExit"),
        (broken_point("no-version", "NoVersionStep"), "does not declare api_version"),
        (broken_point("future", "FutureStep"), "api_version must be 1, got 2"),
        (broken_point("Bad_Id", "BadIdStep"), "id must be kebab-case"),
        (broken_point("other-name", "AlphaStep"), "entry point name 'other-name' is not"),
        (broken_point("page-furniture", "FurnitureClash"), "a built-in step has the id"),
        (point("instance", "example_text_plugin:_AMPERSAND"), "not a TextStep class"),
    ],
)
def test_a_broken_plugin_is_a_problem_and_the_others_still_load(
    entry: EntryPoint, says: str
) -> None:
    loaded = load_plugin_steps([entry, AMPERSAND])
    assert ids(loaded) == ["ampersand-and"]
    assert says in problem_for(loaded, entry.name)


def test_two_plugins_with_one_id_are_both_left_out() -> None:
    other = point("ampersand-and", "example_text_plugin:make_step")
    loaded = load_plugin_steps([AMPERSAND, other, broken_point("alpha", "AlphaStep")])
    assert ids(loaded) == ["alpha"]
    assert [p.name for p in loaded.problems] == ["ampersand-and", "ampersand-and"]
    assert all("more than one plugin" in p.message for p in loaded.problems)


def test_an_entry_point_listed_twice_loads_once() -> None:
    loaded = load_plugin_steps([AMPERSAND, AMPERSAND])
    assert ids(loaded) == ["ampersand-and"]
    assert loaded.problems == ()


def test_a_problem_names_its_distribution() -> None:
    problem = load_plugin_steps([broken_point("future", "FutureStep")]).problems[0]
    assert problem == PluginProblem("future", "", problem.message)


def test_importing_the_public_module_loads_no_plugin_and_no_test_tool() -> None:
    code = (
        "import sys, importlib.metadata as m\n"
        "m.entry_points = None\n"  # any call would fail
        "import sci2audio.textprep.api\n"
        "assert 'pytest' not in sys.modules and 'hypothesis' not in sys.modules\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


# ---- the guard at run time --------------------------------------------------------------


def paper():
    return make_document(
        [(BlockKind.PARAGRAPH, "Smith & Jones agree."), (BlockKind.PARAGRAPH, "A second one.")]
    )


def run_with(*attributes: str, strict: bool = False, timeout: float = 5.0):
    entries = [broken_point(getattr(broken, a).id, a) for a in attributes]
    steps = installed_steps(entry_points=entries, timeout=timeout)
    assert steps.problems == ()
    return run_steps(paper(), EN, steps, strict=strict)


@pytest.mark.parametrize("attribute", ["RaisingStep", "ExitingStep"])
def test_a_plugin_that_fails_is_left_out_and_the_run_goes_on(attribute: str) -> None:
    run = run_with(attribute, "RemovingStep")
    clean = run_with("RemovingStep")
    assert [p.step for p in run.problems] == [getattr(broken, attribute).id]
    assert run.script() == clean.script()


def test_a_failing_plugin_keeps_its_own_error_in_the_problem() -> None:
    [problem] = run_with("RaisingStep").problems
    assert problem.message == "ValueError: boom"


@pytest.mark.parametrize("attribute", ["RaisingStep", "ExitingStep", "MutatingStep"])
def test_a_strict_run_raises_for_a_broken_plugin(attribute: str) -> None:
    with pytest.raises(StepError):
        run_with(attribute, strict=True)


def test_ctrl_c_in_a_plugin_is_not_swallowed() -> None:
    with pytest.raises(KeyboardInterrupt):
        run_with("InterruptedStep")


def test_a_slow_plugin_is_given_up_and_the_run_goes_on() -> None:
    broken.SlowStep.release.clear()
    try:
        started = time.monotonic()
        run = run_with("SlowStep", "RemovingStep", timeout=0.2)
        assert time.monotonic() - started < 3
    finally:
        broken.SlowStep.release.set()
    [problem] = run.problems
    assert problem.step == "slow"
    assert "took longer than 0.2 s" in problem.message
    assert run.script() == run_with("RemovingStep").script()


def test_a_plugin_that_changes_the_document_is_left_out_and_the_others_see_it_clean() -> None:
    broken.WatchingStep.seen.clear()
    document = paper()
    steps = installed_steps(
        entry_points=[
            broken_point("mutating", "MutatingStep"),
            broken_point("watching", "WatchingStep"),
        ]
    )
    run = run_steps(document, EN, steps)
    assert [p.step for p in run.problems] == ["mutating"]
    assert "changed the document" in run.problems[0].message
    assert document == paper()
    assert broken.WatchingStep.seen == ["Smith & Jones agree."]


def test_the_runner_lists_the_plugins_and_the_load_problems() -> None:
    steps = installed_steps(entry_points=[AMPERSAND, broken_point("future", "FutureStep")])
    run = run_steps(paper(), EN, steps)
    assert [info.step for info in run.plugins] == ["ampersand-and"]
    assert [p.step for p in run.problems] == ["future"]
    assert "not loaded" in run.problems[0].message


def test_a_plugin_edit_is_switched_off_with_its_category() -> None:
    steps = installed_steps(entry_points=[AMPERSAND])
    on = run_steps(paper(), EN, steps, switched_off=())
    off = run_steps(paper(), EN, steps, switched_off={Category.CHARACTERS})
    assert any(edit.step == "ampersand-and" for edit in on.accepted)
    assert not any(edit.step == "ampersand-and" for edit in off.accepted)


# ---- conformance (#216 criterion 4) -----------------------------------------------------


def test_the_example_plugin_passes_the_conformance_suite() -> None:
    check_text_step(AmpersandStep())


def test_the_loaded_example_plugin_passes_the_conformance_suite() -> None:
    [step] = load_plugin_steps([AMPERSAND]).steps
    check_text_step(step)


@pytest.mark.parametrize("step", BUILT_IN_STEPS, ids=lambda step: step.id)
def test_a_guarded_built_in_step_keeps_the_contract(step) -> None:
    check_text_step(guarded(step), allow_ask=False)


@given(st.sampled_from(BUILT_IN_STEPS), documents())
def test_the_guard_changes_no_edit(step, document) -> None:
    try:
        plain = step.find(document, EN)
    except Exception as error:
        with pytest.raises(type(error)):
            guarded(step).find(document, EN)
        return
    assert guarded(step).find(document, EN) == plain


# ---- speed (docs/baseline.md) -----------------------------------------------------------

PAPERS = sorted((Path(__file__).resolve().parents[1] / "corpus" / "papers").glob("*.pdf"))


@pytest.mark.benchmark
def test_benchmark_the_guard_on_the_largest_paper(benchmark) -> None:
    from sci2audio.extraction import extract_pdf
    from sci2audio.layout import build_document

    largest = max(PAPERS, key=lambda paper: paper.stat().st_size)
    document = build_document(extract_pdf(largest))
    step = guarded(AmpersandStep())
    benchmark.extra_info["paper"] = largest.name
    benchmark(step.find, document, EN)
