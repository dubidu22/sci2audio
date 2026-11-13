"""Smoke tests: the package imports and the command line starts (PE-02).

`test_script_command_end_to_end` runs the installed `sci2audio` command in a process of
its own, as a person would; CI also runs it as a step of its own on all three systems.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import sci2audio
from sci2audio.cli import main

SEABORN = Path(__file__).resolve().parents[1] / "corpus" / "papers" / "joss2021-waskom-seaborn.pdf"


def command() -> Path:
    """The `sci2audio` console script of this environment."""
    name = "sci2audio.exe" if sys.platform == "win32" else "sci2audio"
    path = Path(sys.executable).parent / name
    if not path.exists():
        pytest.skip(f"the console script {path} is not installed")
    return path


def test_version_is_set() -> None:
    assert sci2audio.__version__


def test_cli_without_a_command_prints_the_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert capsys.readouterr().err.startswith("usage: sci2audio")


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


def test_the_command_line_loads_nothing_heavy() -> None:
    """`sci2audio --version` and the commands start fast: no web server, torch or kokoro
    at import time (the web interface is imported by `ui` only, #76)."""
    code = (
        "import sys, sci2audio.cli; "
        "print(sorted(m for m in ('sci2audio.web', 'fastapi', 'torch', 'kokoro', 'misaki', "
        "'sci2audio.testing', 'pytest', 'hypothesis') if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"


def test_script_command_end_to_end(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            str(command()),
            "script",
            str(SEABORN),
            "-o",
            str(tmp_path / "out"),
            "--work-folder",
            str(tmp_path / "work"),
            "--ignore-settings",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    stem = tmp_path / "out" / "joss2021-waskom-seaborn"
    for suffix in (".script.txt", ".report.json", ".report.md"):
        assert Path(f"{stem}{suffix}").stat().st_size > 0
    report = json.loads(Path(f"{stem}.report.json").read_text(encoding="utf-8"))
    assert report["format"] == "sci2audio-report"
    assert "Chapters (choose with --chapters):" in result.stdout
