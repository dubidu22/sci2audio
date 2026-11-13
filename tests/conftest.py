"""Shared test configuration.

Hypothesis profiles (select with the HYPOTHESIS_PROFILE environment variable):
- dev (default): quick, for local runs
- ci: every pull request; deterministic, so a red run can be reproduced
- nightly: many more examples to find rare edge cases
"""

import os
import sys

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
# its fix. `platform="win32"` (a `sys.platform` value) limits the skip to one system.
# Every quarantined test must be fixed before the v1.0 release (#80). List them with
# `uv run pytest -m quarantined --collect-only -q`; run them with `--run-quarantined`.


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-quarantined",
        action="store_true",
        help="run the quarantined tests too (to fix them, D-374)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_them = config.getoption("--run-quarantined")
    for item in items:
        marker = item.get_closest_marker("quarantined")
        if marker is None:
            continue
        issue = marker.kwargs.get("issue")
        reason = marker.kwargs.get("reason")
        if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0 or not reason:
            raise pytest.UsageError(
                f"{item.nodeid}: quarantined needs issue=<GitHub issue number> and reason=..."
            )
        if marker.args or set(marker.kwargs) - {"issue", "reason", "platform"}:
            raise pytest.UsageError(
                f"{item.nodeid}: quarantined takes only issue=, reason= and platform="
            )
        platform = marker.kwargs.get("platform")
        if run_them or (platform is not None and sys.platform != platform):
            continue
        item.add_marker(pytest.mark.skip(reason=f"quarantined, see #{issue}: {reason}"))


def pytest_report_collectionfinish(config: pytest.Config, items: list[pytest.Item]) -> list[str]:
    """Name every quarantined test at the top of each run, so the list is never forgotten."""
    lines = []
    for item in items:
        marker = item.get_closest_marker("quarantined")
        if marker is not None:
            where = marker.kwargs.get("platform")
            lines.append(
                f"  #{marker.kwargs.get('issue')} {item.nodeid}" + (f" (on {where})" if where else "")
            )
    if not lines:
        return []
    return [f"{len(lines)} quarantined test(s), all to be fixed before v1.0 (D-374, #80):", *lines]
