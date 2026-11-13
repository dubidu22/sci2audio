"""`sci2audio script` (#72, WI-03): the files, the chapter list, the options, and the
settings file read as defaults but never written (D-213, D-214, D-215, D-216)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from cli_helpers import SEABORN, Cli, files_in, small_pdf
from syrupy.assertion import SnapshotAssertion

from sci2audio.app import JobSettings, run_script_job
from sci2audio.cli import chapter_numbers
from sci2audio.textprep import Category

SCRIPT_FILES = [
    "joss2021-waskom-seaborn.report.json",
    "joss2021-waskom-seaborn.report.md",
    "joss2021-waskom-seaborn.script.txt",
]


@pytest.fixture
def cli(tmp_path: Path) -> Cli:
    return Cli(tmp_path)


def report(folder: Path, name: str = "joss2021-waskom-seaborn") -> dict:
    return json.loads((folder / f"{name}.report.json").read_text(encoding="utf-8"))


def test_writes_the_same_files_as_the_script_job(cli: Cli, tmp_path: Path) -> None:
    result = cli("script", SEABORN, "-o", tmp_path / "out", "--ignore-settings")
    assert result.code == 0, result.err
    assert files_in(tmp_path / "out") == SCRIPT_FILES
    run_script_job(SEABORN, JobSettings(output_folder=tmp_path / "job"), tmp_path / "job-work")
    for name in SCRIPT_FILES:
        assert (tmp_path / "out" / name).read_text(encoding="utf-8") == (
            tmp_path / "job" / name
        ).read_text(encoding="utf-8")
    assert (cli.work(SEABORN) / "job.json").is_file()  # the work folder of D-216


def test_prints_the_chapters_to_choose_from(
    cli: Cli, tmp_path: Path, snapshot: SnapshotAssertion
) -> None:
    result = cli("script", SEABORN, "-o", tmp_path, "-q")
    assert result.code == 0
    assert result.err == ""  # -q: no progress
    # only the chapter list is pinned: the edit counts change with every new text step
    chapters, edits = result.out.split("Wrote:")[0].split("Edits that change what is heard:\n")
    assert chapters == snapshot
    assert edits.splitlines()[0].startswith("  Page furniture: ")
    for name in SCRIPT_FILES:
        assert str(tmp_path / name) in result.out


def test_progress_lines_without_a_terminal(cli: Cli, tmp_path: Path) -> None:
    result = cli("script", SEABORN, "-o", tmp_path)
    assert result.err.splitlines() == [
        "Reading the file ...",
        "Finding the reading order ...",
        "Preparing the text ...",
        "Writing the script and the report ...",
    ]


def test_progress_on_a_terminal_is_one_line(tmp_path: Path) -> None:
    result = Cli(tmp_path, live=True)("script", SEABORN, "-o", tmp_path)
    assert result.code == 0
    assert result.err.count("\n") == 1
    assert result.err.endswith("\n")
    assert result.err.count("\r") == 4


def test_files_go_next_to_the_file_by_default(cli: Cli, tmp_path: Path) -> None:
    source = tmp_path / "in" / SEABORN.name
    source.parent.mkdir()
    shutil.copy(SEABORN, source)
    assert cli("script", source, "-q").code == 0
    assert files_in(source.parent) == sorted([SEABORN.name, *SCRIPT_FILES])


@pytest.mark.parametrize(
    ("chosen", "indices"),
    [("2", [1]), ("1,3-4", [0, 2, 3]), ("all", [0, 1, 2, 3, 4, 5, 6])],
)
def test_chapters_are_counted_from_one(
    cli: Cli, tmp_path: Path, chosen: str, indices: list[int]
) -> None:
    assert cli("script", SEABORN, "-o", tmp_path, "-q", "--chapters", chosen).code == 0
    data = report(tmp_path)
    assert data["settings"]["chapters"] == indices
    assert [c["index"] for c in data["chapters"] if c["selected"]] == indices


def test_a_chapter_the_document_lacks_is_a_warning_in_its_own_numbers(
    cli: Cli, tmp_path: Path
) -> None:
    result = cli("script", SEABORN, "-o", tmp_path, "-q", "--chapters", "1,9")
    assert result.code == 0
    assert result.err == (
        "sci2audio: warning: there is no chapter 9 (the document has chapters 1 to 7); ignored\n"
    )
    # the report itself has no other kind of warning, so the cli's own line replaces it
    assert len(report(tmp_path)["warnings"]) == 1


@pytest.mark.parametrize(
    ("text", "indices"),
    [("1", {0}), (" 2 , 4-5 ", {1, 3, 4}), ("3-3", {2}), ("ALL", None)],
)
def test_chapter_numbers(text: str, indices: set[int] | None) -> None:
    assert chapter_numbers(text) == (None if indices is None else frozenset(indices))


@pytest.mark.parametrize("text", ["0", "3-1", "x", "1,,2", "-2", "1-", "1-99999"])
def test_bad_chapter_numbers_are_a_usage_error(cli: Cli, tmp_path: Path, text: str) -> None:
    result = cli("script", SEABORN, "-o", tmp_path, "--chapters", text)
    assert result.code == 2
    assert "argument --chapters" in result.err
    assert files_in(tmp_path) == []


def test_categories_switch_on_and_off(cli: Cli, tmp_path: Path) -> None:
    result = cli(
        "script",
        SEABORN,
        "-o",
        tmp_path,
        "-q",
        "--off",
        "citations,links",
        "--on",
        "footnote-texts",
    )
    assert result.code == 0
    assert report(tmp_path)["settings"]["switched_off"] == ["citations", "links"]


def test_an_unknown_category_lists_the_known_ones(cli: Cli, tmp_path: Path) -> None:
    result = cli("script", SEABORN, "--off", "maths")
    assert result.code == 2
    assert "unknown category 'maths'" in result.err
    assert all(category.value in result.err for category in Category)


def test_the_same_category_on_and_off_is_a_usage_error(cli: Cli, tmp_path: Path) -> None:
    result = cli("script", SEABORN, "-o", tmp_path, "--on", "citations", "--off", "citations")
    assert (result.code, result.err) == (
        2,
        "sci2audio: citations: switched both on and off; choose one\n",
    )
    assert files_in(tmp_path) == []


def test_a_bad_language_tag_is_a_usage_error(cli: Cli, tmp_path: Path) -> None:
    result = cli("script", SEABORN, "-o", tmp_path, "--language", "English")
    assert result.code == 2
    assert "language must be a tag" in result.err


def test_existing_files_are_kept_without_overwrite(cli: Cli, tmp_path: Path) -> None:
    assert cli("script", SEABORN, "-o", tmp_path, "-q").code == 0
    (tmp_path / SCRIPT_FILES[2]).write_text("mine", encoding="utf-8")
    result = cli("script", SEABORN, "-o", tmp_path, "-q")
    assert result.code == 7
    assert "add --overwrite" in result.err
    assert (tmp_path / SCRIPT_FILES[2]).read_text(encoding="utf-8") == "mine"
    assert cli("script", SEABORN, "-o", tmp_path, "-q", "--overwrite").code == 0
    assert (tmp_path / SCRIPT_FILES[2]).read_text(encoding="utf-8") != "mine"


def write_settings(cli: Cli, data: dict) -> str:
    cli.config.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data)
    cli.config.write_text(text, encoding="utf-8")
    return text


def test_the_settings_file_gives_the_defaults(cli: Cli, tmp_path: Path) -> None:
    saved = tmp_path / "saved"
    text = write_settings(
        cli, {"version": 1, "switched_off": ["citations"], "output_folder": str(saved)}
    )
    assert cli("script", SEABORN, "-q").code == 0
    assert report(saved)["settings"]["switched_off"] == ["citations"]
    assert cli.config.read_text(encoding="utf-8") == text  # never written (D-213)


def test_options_override_the_settings_file(cli: Cli, tmp_path: Path) -> None:
    write_settings(cli, {"version": 1, "switched_off": ["citations"], "output_folder": "x"})
    assert cli("script", SEABORN, "-q", "-o", tmp_path, "--on", "citations").code == 0
    assert report(tmp_path)["settings"]["switched_off"] == []


def test_ignore_settings_uses_the_built_in_defaults(cli: Cli, tmp_path: Path) -> None:
    write_settings(cli, {"version": 1, "switched_off": ["citations"]})
    assert cli("script", SEABORN, "-q", "-o", tmp_path, "--ignore-settings").code == 0
    assert report(tmp_path)["settings"]["switched_off"] == ["footnote-texts"]


def test_a_broken_settings_file_only_warns(cli: Cli, tmp_path: Path) -> None:
    cli.config.parent.mkdir(parents=True)
    cli.config.write_text("{not json", encoding="utf-8")
    result = cli("script", SEABORN, "-q", "-o", tmp_path)
    assert result.code == 0
    assert result.err.startswith("sci2audio: warning: the settings file is damaged")
    assert cli.config.read_text(encoding="utf-8") == "{not json"


def test_no_settings_file_is_made(cli: Cli, tmp_path: Path) -> None:
    assert cli("script", SEABORN, "-q", "-o", tmp_path).code == 0
    assert not cli.config.exists()


def test_the_work_folder_option(cli: Cli, tmp_path: Path) -> None:
    work = tmp_path / "mine"
    assert cli("script", SEABORN, "-q", "-o", tmp_path, "--work-folder", work).code == 0
    assert (work / "job.json").is_file()
    assert not cli.work(SEABORN).exists()


def test_a_small_pdf(cli: Cli, tmp_path: Path) -> None:
    source = small_pdf(tmp_path / "in")
    result = cli("script", source, "-q")
    assert result.code == 0, result.err
    script = (source.parent / "note.script.txt").read_text(encoding="utf-8")
    assert "A short note." in script
