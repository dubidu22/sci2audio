"""Exit codes and messages (#72, D-212): one test per code, each checking the code, the one
line on stderr and that no traceback reaches the person; `clean` (D-210); consoles that
can't show every character (D-225)."""

from __future__ import annotations

import argparse
import io
from pathlib import Path
from typing import Any

import pytest
from cli_helpers import BROKEN, SEABORN, Cli, small_pdf
from pdf_maker import glyph_number_pdf

from sci2audio.cli import (
    COMMANDS,
    EXIT_CODES_HELP,
    CliEnv,
    Exit,
    _never_fail_on_characters,
    _Parser,
)


@pytest.fixture
def cli(tmp_path: Path) -> Cli:
    return Cli(tmp_path)


def one_line(text: str) -> str:
    assert "Traceback" not in text
    lines = [line for line in text.splitlines() if not line.endswith(" ...")]  # progress
    assert len(lines) == 1, text
    return lines[0]


def test_the_codes_are_the_documented_ones() -> None:
    assert {code.name: int(code) for code in Exit} == {
        "OK": 0,
        "FAILED": 1,
        "USAGE": 2,
        "NOT_FOUND": 3,
        "UNSUPPORTED": 4,
        "UNREADABLE": 5,
        "NO_VOICE": 6,
        "EXISTS": 7,
        "BUSY": 8,
        "INTERRUPTED": 130,
    }
    documented = [line.split()[0] for line in EXIT_CODES_HELP.splitlines()[1:] if line[2] != " "]
    assert documented == [str(int(code)) for code in Exit]


def exit_meaning(code: int) -> str:
    """The help's line for `code`, with any further lines of it, in one line."""
    entries: dict[str, list[str]] = {}
    last = ""
    for line in EXIT_CODES_HELP.splitlines()[1:]:
        if line[2] == " ":  # a further line of the entry above
            entries[last].append(line.strip())
        else:
            last, meaning = line.split(maxsplit=1)
            entries[last] = [meaning]
    return " ".join(entries[str(code)])


def test_exit_7_names_both_reasons_alike_in_the_help_and_the_readme() -> None:
    """Exit 7 also means the chapters were made with other settings (#726); a script that
    reads --help learnt only the first reason (#1097)."""
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
    [row] = [line for line in readme.splitlines() if line.startswith("| 7 |")]
    assert exit_meaning(7) == row.split("|")[2].strip().replace("`", "")
    assert "--keep-settings" in exit_meaning(7)


@pytest.mark.parametrize("command", ["script", "convert", "clean"])
def test_a_missing_file(cli: Cli, tmp_path: Path, command: str) -> None:
    result = cli(command, tmp_path / "gone.pdf")
    assert result.code == 3
    assert one_line(result.err) == f"sci2audio: {tmp_path / 'gone.pdf'}: no such file"


def test_a_folder_is_not_a_file(cli: Cli, tmp_path: Path) -> None:
    result = cli("script", tmp_path)
    assert result.code == 3
    assert one_line(result.err) == f"sci2audio: {tmp_path}: not a file"


@pytest.mark.parametrize("command", ["script", "convert"])
def test_an_unsupported_file_type(cli: Cli, tmp_path: Path, command: str) -> None:
    source = tmp_path / "paper.docx"
    source.write_bytes(b"PK\x03\x04")
    result = cli(command, source, "-o", tmp_path / "out")
    assert result.code == 4
    assert one_line(result.err) == (
        "sci2audio: paper.docx: sci2audio can read .epub, .markdown, .md, .pdf, .txt files only"
    )
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("command", ["script", "convert"])
def test_a_password_protected_pdf(cli: Cli, tmp_path: Path, command: str) -> None:
    result = cli(command, BROKEN / "password-protected.pdf", "-o", tmp_path / "out", "-q")
    assert result.code == 5
    assert "password" in one_line(result.err)
    assert not (tmp_path / "out").exists()


def test_a_damaged_pdf(cli: Cli, tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\nthis is not a PDF at all")
    result = cli("script", source, "-q")
    assert result.code == 5
    assert one_line(result.err).startswith("sci2audio: paper.pdf")


def test_a_pdf_of_glyph_numbers_is_not_voiced(cli: Cli, tmp_path: Path) -> None:
    """#442 part B: exit 5, the pages named, no audiobook and no voice made."""
    source = tmp_path / "glyphs.pdf"
    lines = [
        "Das Buch wurde in einer Zeit geschrieben, in der die Arbeit in den Quartieren",
        "neu gedacht werden musste. Die Menschen, die dort leben, kennen ihre Nachbarn,",
    ]
    source.write_bytes(glyph_number_pdf(lines))
    result = cli("convert", source, "-q", "-o", tmp_path / "out")
    assert result.code == 5
    assert one_line(result.err).startswith(
        "sci2audio: glyphs.pdf: the text of page 1 cannot be read: "
    )
    assert cli.voice.made == 0
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").iterdir())


def test_the_output_folder_is_a_file(cli: Cli, tmp_path: Path) -> None:
    (tmp_path / "taken").write_text("x", encoding="utf-8")
    result = cli("script", SEABORN, "-q", "-o", tmp_path / "taken")
    assert result.code == 1
    assert one_line(result.err) == "sci2audio: taken is not a folder; choose another output folder"


def test_an_unexpected_error_is_one_line(
    cli: Cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("something odd")

    monkeypatch.setattr("sci2audio.app.JobRunner.run_script", broken)
    result = cli("script", SEABORN, "-q", "-o", tmp_path)
    assert result.code == 1
    assert one_line(result.err) == (
        "sci2audio: unexpected error, this is a bug in sci2audio (RuntimeError: something odd)"
    )


def test_ctrl_c_during_the_script_job(
    cli: Cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("sci2audio.app.JobRunner.run_script", interrupted)
    result = cli("script", SEABORN, "-q", "-o", tmp_path)
    assert result.code == 130
    assert one_line(result.err) == "sci2audio: stopped; run the same command again to continue"


def test_no_command_prints_the_help(cli: Cli) -> None:
    result = cli()
    assert result.code == 2
    assert result.err.startswith("usage: sci2audio")
    assert result.out == ""


def test_clean_removes_the_speech_cache(cli: Cli, tmp_path: Path) -> None:
    source = small_pdf(tmp_path / "in")
    assert cli("convert", source, "-q").code == 0
    chunks = cli.work(source) / "chunks"
    assert any(chunks.rglob("*.wav"))
    result = cli("clean", source)
    assert result.code == 0
    assert result.out.startswith("Removed the speech cache of note.pdf (")
    assert not chunks.exists()
    assert (cli.work(source) / "audio.json").is_file()  # the records stay
    assert (source.parent / "note.m4b").is_file()  # and so does the book
    again = cli("clean", source)
    assert again.out == "note.pdf has no speech cache; nothing to remove.\n"


def test_clean_with_the_work_folder_option(cli: Cli, tmp_path: Path) -> None:
    source = small_pdf(tmp_path / "in")
    work = tmp_path / "w"
    assert cli("convert", source, "-q", "--work-folder", work).code == 0
    assert cli("clean", source, "--work-folder", work).code == 0
    assert not (work / "chunks").exists()


def test_a_console_without_every_character_never_fails() -> None:
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="cp1252", newline="\n")
    _never_fail_on_characters(stream)
    stream.write("Garc\u0131a and \U0001d45d < .05\n")
    stream.flush()
    assert raw.getvalue() == b"Garc?a and ? < .05\n"
    assert stream.encoding == "cp1252"


def test_the_real_env_reads_the_terminal() -> None:
    env = CliEnv.real()
    assert env.out is not None
    assert env.err is not None
    assert env.fetch is None


def test_clean_while_a_job_works_on_the_file_is_busy(cli: Cli, tmp_path: Path) -> None:
    from sci2audio.app.lock import work_folder_lock

    source = small_pdf(tmp_path / "in")
    assert cli("convert", source, "-q").code == 0
    with work_folder_lock(cli.work(source)):
        result = cli("clean", source)
    assert result.code == 8  # D-226: clean_work_folder takes the job's lock
    assert "another sci2audio job is working on this file" in one_line(result.err)
    assert any((cli.work(source) / "chunks").rglob("*.wav"))


def test_the_command_hands_a_packaged_reader_start_to_the_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A packaged build (v1.3) starts itself again for each PDF reader process; without
    `freeze_support` first, such a start would run the command instead (D-581, #345)."""
    import multiprocessing

    from sci2audio import cli as cli_module

    calls: list[str] = []
    monkeypatch.setattr(multiprocessing, "freeze_support", lambda: calls.append("freeze"))
    monkeypatch.setattr(cli_module, "run", lambda argv, env: calls.append("run") or 0)
    assert cli_module.main([]) == 0
    assert calls == ["freeze", "run"]


def test_an_unknown_command_lists_the_choices_quoted(cli: Cli) -> None:
    result = cli("nosuch")
    assert result.code == 2
    assert result.err.splitlines()[-1] == (
        "sci2audio: error: argument COMMAND: invalid choice: 'nosuch' (choose from "
        + ", ".join(f"'{name}'" for name in (command.name for command in COMMANDS))
        + ")"
    )


def test_an_unknown_action_lists_the_choices_quoted(cli: Cli) -> None:
    result = cli("voices", "nope")
    assert result.code == 2
    assert result.err.splitlines()[-1] == (
        "sci2audio voices: error: argument ACTION: invalid choice: 'nope' (choose from 'download')"
    )


def test_an_unknown_choice_of_an_option_lists_the_choices_quoted(cli: Cli, tmp_path: Path) -> None:
    result = cli("convert", small_pdf(tmp_path / "in"), "--format", "wav")
    assert result.code == 2
    assert result.err.splitlines()[-1] == (
        "sci2audio convert: error: argument --format: invalid choice: 'wav' "
        "(choose from 'both', 'm4b', 'mp3')"
    )


@pytest.mark.parametrize(
    ("choices", "kind", "given", "expected"),
    [
        ({"fast": 1, "slow": 2}, str, "mid", "'mid' (choose from 'fast', 'slow')"),
        (range(1, 4), int, "7", "'7' (choose from '1', '2', '3')"),
        ([10, 20, 30], int, "25", "'25' (choose from '10', '20', '30')"),
    ],
    ids=["dict", "range", "int-list"],
)
def test_an_invalid_choice_lists_any_kind_of_choices_quoted(
    choices: Any, kind: type, given: str, expected: str
) -> None:
    env = CliEnv.real()
    env.err = io.StringIO()
    parser = _Parser(prog="tool", env=env)
    parser.add_argument("--pick", type=kind, choices=choices)
    with pytest.raises(SystemExit) as stopped:
        parser.parse_args(["--pick", given])
    assert stopped.value.code == 2
    assert env.err.getvalue().splitlines()[-1] == (
        f"tool: error: argument --pick: invalid choice: {expected}"
    )


def test_a_valid_choice_of_any_kind_is_accepted() -> None:
    parser = _Parser(prog="tool", env=CliEnv.real())
    parser.add_argument("--a", type=int, choices=range(1, 4))
    parser.add_argument("--b", choices={"fast": 1})
    assert parser.parse_args(["--a", "3", "--b", "fast"]) == argparse.Namespace(a=3, b="fast")
