"""The command line and the project folders (#469, D-747, D-748): by default a command
moves its file's old working folder over first; a folder named with `--work-folder` is
used exactly as given, never moved (D-752)."""

from __future__ import annotations

from pathlib import Path

import pytest
from cli_helpers import Cli, small_pdf
from project_helpers import tree_digest

from sci2audio.app import config as config_module
from sci2audio.app.chunks import CHUNKS
from sci2audio.app.projects import project_work_folder
from sci2audio.cli import CliEnv


def test_by_default_a_command_uses_the_project_folder_and_moves_an_old_one() -> None:
    assert CliEnv.__dataclass_fields__["work_folder"].default is project_work_folder


def test_a_named_work_folder_is_used_as_given_and_never_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        config_module.platformdirs, "user_data_path", lambda *a, **k: tmp_path / "d"
    )
    monkeypatch.setattr(
        config_module.platformdirs, "user_cache_path", lambda *a, **k: tmp_path / "c"
    )
    source = small_pdf(tmp_path / "in")
    # a folder in the old root, named on the command line as before #469
    work = tmp_path / "c" / "jobs" / config_module.file_id(source)
    work.mkdir(parents=True)
    (work / "notes.txt").write_text("kept")
    before = tree_digest(work)
    cli = Cli(tmp_path)
    assert cli("convert", source, "-q", "--work-folder", work, "-o", tmp_path / "out").code == 0
    assert (work / "notes.txt").read_text() == "kept"
    assert {k: v for k, v in tree_digest(work).items() if k in before} == before
    assert any((work / CHUNKS).rglob("*.wav"))  # the speech cache inside it, as before
    assert (work / "audio.json").is_file()
    assert not (tmp_path / "d" / "projects").exists()
