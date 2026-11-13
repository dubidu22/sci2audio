"""Property-based tests (Hypothesis): rules that must hold for any input.

The command line must never crash with a traceback: whatever arguments it gets,
it either runs (exit 0) or rejects them cleanly (argparse exit 2).
"""

from collections.abc import Iterator

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.cli import main

arguments = st.lists(st.text(min_size=0, max_size=20), max_size=5)


@pytest.fixture(autouse=True, scope="module")
def no_server() -> Iterator[None]:
    """`sci2audio ui` would start the server and open a browser: never from these tests."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("sci2audio.web.run", lambda **kwargs: 0)
        yield


def exit_code(argv: list[str]) -> int | str | None:
    """Run the CLI and return its exit code, whether it returns or exits."""
    try:
        return main(argv)
    except SystemExit as exc:
        return exc.code


@given(argv=arguments | st.lists(st.sampled_from(["ui", "--no-browser", "-h"]), max_size=3))
def test_cli_never_crashes(argv: list[str]) -> None:
    assert exit_code(argv) in (0, 2)


@pytest.mark.parametrize("flag", ["--version", "-h", "--help"])
def test_known_flags_exit_cleanly(flag: str) -> None:
    with pytest.raises(SystemExit) as exc:
        main([flag])
    assert exc.value.code == 0
