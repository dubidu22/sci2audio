"""`sci2audio listen` (#154): open an audiobook the command line made in the player. The
folders are named as for `convert`; nothing is taken from a path written in a file. The
server start is replaced here; `test_web_outside.py` serves such a job for real."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from cli_helpers import Cli, small_pdf

import sci2audio.web
from sci2audio.web import OutsideJob

LINES = ("The first sentence is here.", "A second sentence follows it.")


@pytest.fixture
def cli(tmp_path: Path) -> Cli:
    return Cli(tmp_path)


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Each server start `listen` asks for, instead of a real one."""
    calls: list[dict[str, Any]] = []

    def run(**kwargs: Any) -> int:
        calls.append(kwargs)
        return 0

    monkeypatch.setattr(sci2audio.web, "run", run)
    return calls


@pytest.fixture
def made(cli: Cli, tmp_path: Path) -> tuple[Path, Path]:
    """A PDF and the folder `convert` wrote its audiobook into."""
    source = small_pdf(tmp_path / "in", LINES)
    out = tmp_path / "book"
    result = cli("convert", source, "-o", out, "-q")
    assert result.code == 0, result.err
    return source, out


def test_listen_opens_the_job_convert_made(
    cli: Cli, made: tuple[Path, Path], started: list[dict[str, Any]]
) -> None:
    source, out = made
    result = cli("listen", source, "-o", out, "--no-browser")
    assert result.code == 0, result.err
    (call,) = started
    assert call["open_browser"] is False
    (job,) = call["outside"]
    assert isinstance(job, OutsideJob)
    assert job.document == hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    assert job.name == "note.pdf"
    assert job.work == cli.work(source).absolute()
    assert job.folder == out.absolute()
    assert "note.pdf: its audiobook is on the start page" in result.out


def test_the_folders_default_as_for_convert(
    cli: Cli, tmp_path: Path, started: list[dict[str, Any]]
) -> None:
    source = small_pdf(tmp_path / "in", LINES)
    assert cli("convert", source, "-q").code == 0  # next to the file
    assert cli("listen", source).code == 0
    (job,) = started[0]["outside"]
    assert job.folder == source.parent.absolute()
    assert started[0]["open_browser"] is True
    other = tmp_path / "w2"
    assert cli("convert", source, "--work-folder", other, "-o", tmp_path / "b2", "-q").code == 0
    assert cli("listen", source, "--work-folder", other, "-o", tmp_path / "b2").code == 0
    (job,) = started[1]["outside"]
    assert (job.work, job.folder) == (other.absolute(), (tmp_path / "b2").absolute())


def test_the_settings_files_output_folder_counts_as_for_convert(
    cli: Cli, tmp_path: Path, started: list[dict[str, Any]]
) -> None:
    source = small_pdf(tmp_path / "in", LINES)
    saved = tmp_path / "saved-out"
    cli.config.parent.mkdir(parents=True)
    cli.config.write_text(json.dumps({"output_folder": str(saved)}), encoding="utf-8")
    assert cli("convert", source, "-q").code == 0
    assert cli("listen", source).code == 0
    assert started[0]["outside"][0].folder == saved.absolute()
    result = cli("listen", source, "--ignore-settings")  # next to the file: nothing there
    assert result.code != 0
    assert "the audiobook files are not in" in result.err


def test_no_audiobook_yet(cli: Cli, tmp_path: Path, started: list[dict[str, Any]]) -> None:
    source = small_pdf(tmp_path / "in", LINES)
    result = cli("listen", source)
    assert result.code == 3, result.err  # Exit.NOT_FOUND
    assert f"no audiobook of note.pdf in {cli.work(source)}" in result.err
    assert "sci2audio convert" in result.err
    assert started == []


def test_a_changed_file_is_refused(
    cli: Cli, made: tuple[Path, Path], started: list[dict[str, Any]]
) -> None:
    source, out = made
    source.write_bytes(source.read_bytes() + b"\n% changed\n")
    result = cli("listen", source, "-o", out)
    assert result.code != 0
    assert result.code == 1
    assert "was made from another version of note.pdf" in result.err
    assert started == []


@pytest.mark.parametrize("damage", ["readalong", "mp3", "folder"])
def test_missing_or_changed_files_are_refused(
    cli: Cli, made: tuple[Path, Path], started: list[dict[str, Any]], tmp_path: Path, damage: str
) -> None:
    source, out = made
    if damage == "readalong":
        (out / "note.readalong.json").unlink()
        folder = out
    elif damage == "mp3":
        next(out.glob("*.mp3")).rename(out / "renamed.mp3")
        folder = out
    else:
        folder = tmp_path / "elsewhere"
        folder.mkdir()
    result = cli("listen", source, "-o", folder)
    assert result.code == 3
    assert f"the audiobook files are not in {folder.absolute()}" in result.err
    assert started == []


def test_a_broken_record_is_refused(
    cli: Cli, made: tuple[Path, Path], started: list[dict[str, Any]]
) -> None:
    source, out = made
    (cli.work(source) / "audio.json").write_text("{", encoding="utf-8")
    result = cli("listen", source, "-o", out)
    assert result.code != 0
    assert "can't be read" in result.err
    assert started == []


def test_no_such_file(cli: Cli, tmp_path: Path, started: list[dict[str, Any]]) -> None:
    assert cli("listen", tmp_path / "nothing.pdf").code == 3
    assert started == []
