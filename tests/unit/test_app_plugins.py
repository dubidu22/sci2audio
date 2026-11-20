"""Text-step plugins in a job: the runner loads them, the report and the command line list
them (#216, PE-10)."""

import json
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest
from cli_helpers import Cli

from sci2audio.app import JobRunner, JobSettings
from sci2audio.textprep import BUILT_IN_STEPS, Category
from sci2audio.textprep.api import PLUGIN_GROUP
from sci2audio.textprep.plugins import installed_steps

AMPERSAND = EntryPoint("ampersand-and", "example_text_plugin:AmpersandStep", PLUGIN_GROUP)
FUTURE = EntryPoint("future", "broken_text_plugins:FutureStep", PLUGIN_GROUP)


def source(folder: Path) -> Path:
    path = folder / "note.txt"
    path.write_text("Smith & Jones agree.\n", encoding="utf-8")
    return path


def runner(*entries: EntryPoint) -> JobRunner:
    return JobRunner(installed_steps(entry_points=entries))


def test_a_runner_without_plugins_runs_the_built_in_steps() -> None:
    assert tuple(JobRunner().steps) == BUILT_IN_STEPS


def test_a_plugin_edit_is_in_the_script_and_the_report_lists_the_plugin(tmp_path: Path) -> None:
    job = runner(AMPERSAND).run_script(source(tmp_path), JobSettings(), tmp_path / "w")
    assert "Smith and Jones agree." in job.files.script.read_text(encoding="utf-8")
    data = json.loads(job.files.report_json.read_text(encoding="utf-8"))
    assert data["plugins"] == [
        {
            "step": "ampersand-and",
            "category": "characters",
            "distribution": "",
            "version": "",
            "entry_point": "example_text_plugin:AmpersandStep",
        }
    ]
    assert "Text-step plugins: ampersand-and" in job.files.report_markdown.read_text(
        encoding="utf-8"
    )


def test_a_report_without_plugins_has_no_plugins_key(tmp_path: Path) -> None:
    job = runner().run_script(source(tmp_path), JobSettings(), tmp_path / "w")
    assert "plugins" not in json.loads(job.files.report_json.read_text(encoding="utf-8"))
    assert "plugins" not in job.files.report_markdown.read_text(encoding="utf-8")


def test_switching_its_category_off_reads_the_text_as_printed(tmp_path: Path) -> None:
    settings = JobSettings(switched_off=frozenset({Category.CHARACTERS}))
    job = runner(AMPERSAND).run_script(source(tmp_path), settings, tmp_path / "w")
    assert "Smith & Jones agree." in job.files.script.read_text(encoding="utf-8")


def test_a_plugin_that_did_not_load_is_a_report_problem(tmp_path: Path) -> None:
    job = runner(AMPERSAND, FUTURE).run_script(source(tmp_path), JobSettings(), tmp_path / "w")
    data = json.loads(job.files.report_json.read_text(encoding="utf-8"))
    [problem] = data["problems"]
    assert problem["step"] == "future"
    assert "not loaded" in problem["message"]
    assert "Smith and Jones agree." in job.files.script.read_text(encoding="utf-8")


def test_the_command_line_names_the_installed_plugins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    info = site / "amp-plugin-0.1.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: amp-plugin\nVersion: 0.1\n", encoding="utf-8"
    )
    (info / "entry_points.txt").write_text(
        f"[{PLUGIN_GROUP}]\nampersand-and = example_text_plugin:AmpersandStep\n"
        "future = broken_text_plugins:FutureStep\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(site))
    result = Cli(tmp_path)("script", source(tmp_path), "-o", tmp_path / "out", "-q")
    assert result.code == 0, result.err
    assert "Text-step plugins: ampersand-and (amp-plugin 0.1)\n" in result.out
    assert "the text step future failed and was left out: plugin not loaded" in result.err


def test_broken_installed_plugins_do_not_stop_the_command_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner the command line makes at start-up loads every installed plugin; plugin
    code that fails while it loads is a warning, never a crash."""
    site = tmp_path / "site"
    info = site / "bad-plugins-0.1.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: bad-plugins\nVersion: 0.1\n", encoding="utf-8"
    )
    (info / "entry_points.txt").write_text(
        f"[{PLUGIN_GROUP}]\nbad-property = broken_text_plugins:BadPropertyStep\n"
        "boom-import = boom_on_import:Step\n"
        "boom-factory = broken_text_plugins:boom_factory\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(site))
    result = Cli(tmp_path)("script", source(tmp_path), "-o", tmp_path / "out", "-q")
    assert result.code == 0, result.err
    for name in ("bad-property", "boom-import", "boom-factory"):
        assert f"the text step {name} failed and was left out: plugin not loaded" in result.err
