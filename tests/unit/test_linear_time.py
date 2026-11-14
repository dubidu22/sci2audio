"""The timing helpers of the textprep tests (#276): they pass a linear run and fail a
slow one. A fake clock makes the check exact, whatever the machine's load."""

import sys

import pytest
from linear_time import FLOOR, assert_linear, assert_near


class _Clock:
    """A clock that moves only when a run says how long it took."""

    now = 0.0

    def process_time(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr("linear_time.time.process_time", fake.process_time)
    return fake


def test_a_linear_run_passes(clock: _Clock) -> None:
    def run(text: str) -> int:
        clock.now += len(text) * 1e-5  # 0.5 s and 4 s: above the Windows floor too
        return len(text)

    assert assert_linear(run, lambda n: "a" * n, 400_000) == 400_000


def test_a_quadratic_run_fails(clock: _Clock) -> None:
    def run(text: str) -> int:
        clock.now += len(text) ** 2 * 1e-9
        return len(text)

    with pytest.raises(AssertionError, match=r"64\.0 times as long"):
        assert_linear(run, lambda n: "a" * n, 400_000)


def test_a_base_run_below_the_timer_floor_counts_as_the_floor(clock: _Clock) -> None:
    def run(text: str) -> int:
        clock.now += 0.03 if len(text) > 1000 else 0.0
        return len(text)

    assert_linear(run, lambda n: "a" * n, 8_000)  # 0.03 s < 32 * 0.002 s (or the Windows floor)


def test_a_text_near_its_reference_passes(clock: _Clock) -> None:
    def run(text: str) -> int:
        clock.now += 0.5 if text.startswith("(") else 0.1  # above the Windows floor too
        return len(text)

    assert assert_near(run, "(" * 1000, "a" * 1000, 16) == 1000  # 5 times as long


def test_a_text_far_slower_than_its_reference_fails(clock: _Clock) -> None:
    def run(text: str) -> int:
        clock.now += 2.0 if text.startswith("(") else 0.1  # above the Windows floor too
        return len(text)

    with pytest.raises(AssertionError, match=r"20\.0 times as long"):
        assert_near(run, "(" * 1000, "a" * 1000, 16)


def test_the_floor_is_two_ms_or_four_windows_ticks() -> None:
    """Windows counts CPU time in 15.6 ms ticks, whatever resolution it reports (#294)."""
    assert (4 / 64 if sys.platform == "win32" else 0.002) == FLOOR
