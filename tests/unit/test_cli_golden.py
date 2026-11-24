"""Golden-file tests (syrupy): the help texts are pinned.

When a help text changes on purpose, accept the new version with
`uv run pytest --snapshot-update` and review the changed file in the PR.
"""

import argparse

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.cli import _Formatter, main


@pytest.fixture(autouse=True)
def fixed_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "80")  # argparse wraps to the terminal's width


def test_help_text(capsys: pytest.CaptureFixture[str], snapshot: SnapshotAssertion) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert capsys.readouterr().out == snapshot


@pytest.mark.parametrize(
    "command",
    [["script"], ["convert"], ["voices"], ["voices", "download"], ["clean"], ["ui"], ["listen"]],
)
def test_command_help_text(
    command: list[str], capsys: pytest.CaptureFixture[str], snapshot: SnapshotAssertion
) -> None:
    with pytest.raises(SystemExit) as exit_:
        main([*command, "--help"])
    assert exit_.value.code == 0
    assert capsys.readouterr().out == snapshot


def _invocation(*args: str, **kwargs: object) -> str:
    parser = argparse.ArgumentParser(formatter_class=_Formatter)
    action = parser.add_argument(*args, **kwargs)  # type: ignore[arg-type]
    return _Formatter("prog")._format_action_invocation(action)


def test_option_with_both_forms_names_its_value_twice() -> None:
    # Python 3.13 names it once (`-o, --output FOLDER`); the stored help texts hold the 3.12 form.
    assert _invocation("-o", "--output", metavar="FOLDER") == "-o FOLDER, --output FOLDER"


def test_other_options_and_positionals_read_as_before() -> None:
    assert _invocation("--output", metavar="FOLDER") == "--output FOLDER"
    assert _invocation("-v", "--verbose", action="store_true") == "-v, --verbose"
    assert _invocation("-n", "--count", type=int) == "-n COUNT, --count COUNT"
    assert _invocation("source", metavar="FILE") == "FILE"
