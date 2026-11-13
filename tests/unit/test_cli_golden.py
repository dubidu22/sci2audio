"""Golden-file tests (syrupy): the help texts are pinned.

When a help text changes on purpose, accept the new version with
`uv run pytest --snapshot-update` and review the changed file in the PR.
"""

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.cli import main


@pytest.fixture(autouse=True)
def fixed_width(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "80")  # argparse wraps to the terminal's width


def test_help_text(capsys: pytest.CaptureFixture[str], snapshot: SnapshotAssertion) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert capsys.readouterr().out == snapshot


@pytest.mark.parametrize(
    "command", [["script"], ["convert"], ["voices"], ["voices", "download"], ["clean"], ["ui"]]
)
def test_command_help_text(
    command: list[str], capsys: pytest.CaptureFixture[str], snapshot: SnapshotAssertion
) -> None:
    with pytest.raises(SystemExit) as exit_:
        main([*command, "--help"])
    assert exit_.value.code == 0
    assert capsys.readouterr().out == snapshot
