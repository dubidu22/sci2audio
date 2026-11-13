"""The quarantine marker (D-374), checked in a separate pytest process: a flaky test is
skipped with a link to its issue, only on the system it names, runs again with
--run-quarantined, and a marker without an issue number is refused."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

CONFTEST = Path(__file__).parents[1] / "conftest.py"
MARKERS = """
[pytest]
markers =
    quarantined(issue, reason, platform=None): see D-374
"""


def made_up(pytester: pytest.Pytester, body: str) -> None:
    pytester.makeini(MARKERS)
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    pytester.makepyfile(test_made_up="import pytest\n\n" + body)


BODY = f"""
@pytest.mark.quarantined(issue=138, reason="flaky first stop")
def test_flaky():
    assert False

@pytest.mark.quarantined(issue=157, reason="mtime", platform="{sys.platform}")
def test_flaky_here():
    assert False

@pytest.mark.quarantined(issue=1, reason="elsewhere", platform="no-such-system")
def test_flaky_elsewhere():
    pass

def test_fine():
    pass
"""


def test_a_quarantined_test_is_skipped_with_its_issue(pytester: pytest.Pytester) -> None:
    made_up(pytester, BODY)
    result = pytester.runpytest_subprocess("-rs")
    result.assert_outcomes(passed=2, skipped=2)
    result.stdout.fnmatch_lines(
        [
            "*quarantined, see #138: flaky first stop*",
            "*quarantined, see #157: mtime*",
        ]
    )


def test_the_marker_selects_the_quarantined_tests(pytester: pytest.Pytester) -> None:
    made_up(pytester, BODY)
    result = pytester.runpytest_subprocess("-m", "quarantined", "--collect-only", "-q")
    result.stdout.fnmatch_lines(
        [
            "3 quarantined test(s), all to be fixed before v1.0*",
            "  #138 test_made_up.py::test_flaky",
            f"  #157 test_made_up.py::test_flaky_here (on {sys.platform})",
            "  #1 test_made_up.py::test_flaky_elsewhere (on no-such-system)",
            "*test_flaky",
            "*test_flaky_here",
            "*test_flaky_elsewhere",
        ]
    )
    assert "test_fine" not in result.stdout.str()


def test_run_quarantined_runs_them(pytester: pytest.Pytester) -> None:
    made_up(pytester, BODY)
    result = pytester.runpytest_subprocess("--run-quarantined")
    result.assert_outcomes(passed=2, failed=2)


@pytest.mark.parametrize(
    "marker",
    [
        'quarantined(reason="no issue")',
        'quarantined(issue="138", reason="issue as text")',
        "quarantined(issue=138)",
        'quarantined(138, reason="positional")',
        'quarantined(issue=138, reason="x", until="v1.1")',
    ],
)
def test_a_marker_without_an_issue_number_is_refused(
    pytester: pytest.Pytester, marker: str
) -> None:
    made_up(pytester, f"@pytest.mark.{marker}\ndef test_flaky():\n    pass\n")
    result = pytester.runpytest_subprocess()
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*quarantined*"])
