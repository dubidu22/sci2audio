"""Shared test configuration.

Hypothesis profiles (select with the HYPOTHESIS_PROFILE environment variable):
- dev (default): quick, for local runs
- ci: every pull request; deterministic, so a red run can be reproduced
- nightly: many more examples to find rare edge cases
"""

import copy
import hashlib
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

pytest_plugins = ["pytester"]  # tests/unit/test_quarantine.py runs pytest on made-up tests

settings.register_profile("dev", max_examples=50)
settings.register_profile(
    "ci",
    max_examples=100,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile("nightly", max_examples=2000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


# --- quarantine (D-374) ------------------------------------------------------------------
# A test that failed twice without a code cause is skipped the same day with
# `@pytest.mark.quarantined(issue=N, reason="...")`, linked to the GitHub issue that tracks
# its fix. `platform="win32"` (a `sys.platform` value) limits the skip to one system, and
# `browser="webkit"` (a pytest-playwright browser name) to one browser of the browser tests.
# Every quarantined test is fixed before the next release (D-374, D-739). List them with
# `uv run pytest -m quarantined --collect-only -q`; run them with `--run-quarantined`.


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-quarantined",
        action="store_true",
        help="run the quarantined tests too (to fix them, D-374)",
    )


BROWSERS = ("chromium", "firefox", "webkit")  # pytest-playwright's names


def _benchmarks_off(config: pytest.Config) -> str | None:
    """Why pytest-benchmark gives its fixture no stats in this run, else None: it switches
    itself off under xdist (parallel runs time nothing reliably) and with --benchmark-disable."""
    if config.getoption("dist", "no") != "no" or os.environ.get("PYTEST_XDIST_WORKER"):
        return "no benchmark stats under xdist (run it without -n; the nightly run does)"
    if config.getoption("benchmark_disable", False) and not config.getoption(
        "benchmark_enable", False
    ):
        return "no benchmark stats with --benchmark-disable"
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_them = config.getoption("--run-quarantined")
    off = _benchmarks_off(config) if config.pluginmanager.hasplugin("benchmark") else None
    for item in items:
        if off and "benchmark" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.skip(reason=off))
        marker = item.get_closest_marker("quarantined")
        if marker is None:
            continue
        issue = marker.kwargs.get("issue")
        reason = marker.kwargs.get("reason")
        if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0 or not reason:
            raise pytest.UsageError(
                f"{item.nodeid}: quarantined needs issue=<GitHub issue number> and reason=..."
            )
        if marker.args or set(marker.kwargs) - {"issue", "reason", "platform", "browser"}:
            raise pytest.UsageError(
                f"{item.nodeid}: quarantined takes only issue=, reason=, platform= and browser="
            )
        platform = marker.kwargs.get("platform")
        browser = marker.kwargs.get("browser")
        if browser is not None and browser not in BROWSERS:  # a typo would quarantine nothing
            raise pytest.UsageError(
                f"{item.nodeid}: quarantined browser= is one of {', '.join(BROWSERS)}"
            )
        if run_them or (platform is not None and sys.platform != platform):
            continue
        if browser is not None and _browser_of(item) != browser:
            continue
        item.add_marker(pytest.mark.skip(reason=f"quarantined, see #{issue}: {reason}"))


def _browser_of(item: pytest.Item) -> str | None:
    """The browser a browser test runs in (pytest-playwright's `browser_name`), else None."""
    callspec = getattr(item, "callspec", None)
    return callspec.params.get("browser_name") if callspec is not None else None


def pytest_report_collectionfinish(config: pytest.Config, items: list[pytest.Item]) -> list[str]:
    """Name every quarantined test at the top of each run, so the list is never forgotten."""
    lines = []
    for item in items:
        marker = item.get_closest_marker("quarantined")
        if marker is not None:
            issue, where = marker.kwargs.get("issue"), marker.kwargs.get("platform")
            browser = marker.kwargs.get("browser")
            if browser is not None and _browser_of(item) != browser:
                continue
            lines.append(f"  #{issue} {item.nodeid}" + (f" (on {where})" if where else ""))
    if not lines:
        return []
    banner = f"{len(lines)} quarantined test(s), each to be fixed before the next release"
    return [f"{banner} (D-374, D-739):", *lines]


# --- PDF reader processes (D-581) ----------------------------------------------------------
# Every PDF is read in a child process, about 0.2 s each; the job, web and command-line tests
# read the same few files hundreds of times. Each distinct file (its bytes, name and the
# limits in force) is read in a real child once per test worker, and later reads of it get
# a fresh copy of that result, as from the child. Tests marked `every_pdf_read`
# (the reader's own tests) or `benchmark` (speed measurements) always start a child.

_PDF_READS: dict[tuple[object, ...], object] = {}


@pytest.fixture(autouse=True)
def _each_pdf_read_once(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("every_pdf_read") or request.node.get_closest_marker(
        "benchmark"
    ):
        return
    from sci2audio.extraction import isolate, pdf

    real = pdf._isolated

    def once(
        target: Callable[..., object],
        path: str,
        *,
        on_step: Callable[[str], None] | None = None,
        cancel: threading.Event | None = None,
        extra: tuple[object, ...] = (),
    ) -> object:
        if extra:  # regions of a page (#293): what is asked differs from call to call
            return real(target, path, on_step=on_step, cancel=cancel, extra=extra)
        try:
            data = Path(path).read_bytes()
        except OSError:
            return real(target, path, on_step=on_step, cancel=cancel)
        if cancel is not None and cancel.is_set():  # the real reader's answer to a cancel
            return real(target, path, on_step=on_step, cancel=cancel)
        limits = tuple(getattr(pdf, name) for name in pdf._LIMITS)
        key = (target, hashlib.sha256(data).digest(), Path(path).name, limits)
        key += (pdf.MAX_MEMORY, pdf.STEP_SECONDS)
        if key not in _PDF_READS:
            steps: list[str] = []
            # an error is raised, and not kept
            result = real(target, path, on_step=steps.append, cancel=cancel)
            if isinstance(result, isolate.Stopped):
                return result
            _PDF_READS[key] = (result, tuple(steps))
        result, steps = _PDF_READS[key]  # type: ignore[misc]
        for step in steps:  # the child's steps, as it reported them (#343)
            isolate._tell(on_step, step)
        return copy.deepcopy(result)

    monkeypatch.setattr(pdf, "_isolated", once)
