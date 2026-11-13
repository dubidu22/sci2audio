"""Exit codes and messages (#72, D-212): one test per code, each checking the code, the one
line on stderr and that no traceback reaches the person; `clean` (D-210); consoles that
can't show every character (D-225)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from cli_helpers import BROKEN, SEABORN, Cli, small_pdf

from sci2audio.cli import EXIT_CODES_HELP, CliEnv, Exit, _never_fail_on_characters


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
    documented = [line.split()[0] for line in EXIT_CODES_HELP.splitlines()[1:]]
    assert documented == [str(int(code)) for code in Exit]


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
    assert one_line(result.err) == "sci2audio: paper.docx: sci2audio can read .pdf files only"
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
    stream = io.TextIOWrapper(raw, encoding="cp1252")
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
