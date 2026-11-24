"""Benchmark tests under xdist, checked in a separate pytest process: pytest-benchmark turns
its fixture off there (`benchmark.stats` is None), so a test that reads the stats is skipped
with the reason instead of failing, and runs and measures as before in a plain run (#960)."""

from __future__ import annotations

from pathlib import Path

import pytest

CONFTEST = Path(__file__).parents[1] / "conftest.py"
MARKERS = """
[pytest]
markers =
    benchmark: speed measurement
    every_pdf_read: reads every PDF
"""
BODY = """
import pytest

@pytest.mark.benchmark
def test_measured(benchmark):
    benchmark.pedantic(lambda: sum(range(100)), rounds=1, iterations=1)
    assert benchmark.stats.stats.max < 15

@pytest.mark.benchmark
def test_timed_by_hand():
    assert sum(range(100)) == 4950

def test_fine():
    pass
"""


def made_up(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)  # this run may be a worker itself
    pytester.makeini(MARKERS)
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    pytester.makepyfile(test_made_up=BODY)


def test_a_benchmark_that_reads_the_stats_is_skipped_under_xdist(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    made_up(pytester, monkeypatch)
    result = pytester.runpytest_subprocess("-n", "2", "-rs")
    result.assert_outcomes(passed=2, skipped=1)
    result.stdout.fnmatch_lines(["SKIPPED*no benchmark stats under xdist*"])


def test_a_benchmark_is_skipped_if_benchmarking_is_switched_off(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    made_up(pytester, monkeypatch)
    result = pytester.runpytest_subprocess("--benchmark-disable", "-rs")
    result.assert_outcomes(passed=2, skipped=1)


def test_a_benchmark_runs_and_measures_in_a_plain_run(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    made_up(pytester, monkeypatch)
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    result.assert_outcomes(passed=3)
