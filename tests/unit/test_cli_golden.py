"""Golden-file test (syrupy): the help text is pinned.

When the help text changes on purpose, accept the new version with
`uv run pytest --snapshot-update` and review the changed file in the PR.
"""

import pytest
from syrupy.assertion import SnapshotAssertion

from sci2audio.cli import main


def test_help_text(capsys: pytest.CaptureFixture[str], snapshot: SnapshotAssertion) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert capsys.readouterr().out == snapshot
