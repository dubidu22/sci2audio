"""Smoke tests: the package imports and the command line starts."""

import subprocess
import sys

import pytest

import sci2audio
from sci2audio.cli import main


def test_version_is_set() -> None:
    assert sci2audio.__version__


def test_cli_runs() -> None:
    assert main([]) == 0


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert sci2audio.__version__ in capsys.readouterr().out


def test_module_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sci2audio.cli", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
