"""Property-based tests (Hypothesis): rules that must hold for any input.

The command line must never crash with a traceback: whatever arguments it gets, it ends
with one of its documented exit codes (D-212), and never with "this is a bug". It runs
with every folder in a temporary place and the network blocked.
"""

from pathlib import Path

import pytest
from cli_helpers import Cli
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sci2audio.cli import Exit, main
from sci2audio.testing import no_network

WORDS = st.sampled_from(
    [
        "script",
        "convert",
        "voices",
        "download",
        "clean",
        "--chapters",
        "--on",
        "--off",
        "--speed",
        "--voice",
        "--format",
        "-o",
        "all",
        "1,2",
        "citations",
        "--yes",
        "-q",
    ]
)
arguments = st.lists(st.one_of(WORDS, st.text(min_size=0, max_size=20)), max_size=6)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(argv=arguments)
def test_cli_never_crashes(argv: list[str], tmp_path_factory: pytest.TempPathFactory) -> None:
    root = tmp_path_factory.mktemp("cli")
    cli = Cli(root, voice_installed=False)
    with no_network():
        result = cli(*argv)
    assert result.code in {int(code) for code in Exit}
    assert "Traceback" not in result.err
    assert "this is a bug" not in result.err
    assert not (root / "models").exists()  # nothing was downloaded


@pytest.mark.parametrize("flag", ["--version", "-h", "--help"])
def test_known_flags_exit_cleanly(flag: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main([flag])
    assert exc.value.code == 0


def test_files_named_like_options_are_read(tmp_path: Path) -> None:
    result = Cli(tmp_path)("script", "--", "-q")
    assert result.code == 3
    assert result.err == "sci2audio: -q: no such file\n"
