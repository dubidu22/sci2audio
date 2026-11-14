"""The timing helper of the textprep tests (#276): it passes a linear run and fails a
quadratic one. A fake clock makes the check exact, whatever the machine's load."""

import pytest
from linear_time import assert_linear


class _Clock:
    """A clock that moves only when a run says how long it took."""

    now = 0.0

    def perf_counter(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    monkeypatch.setattr("linear_time.time.perf_counter", fake.perf_counter)
    return fake


def test_a_linear_run_passes(clock: _Clock) -> None:
    def run(text: str) -> int:
        clock.now += len(text) * 1e-6
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

    assert_linear(run, lambda n: "a" * n, 8_000)  # 0.03 s < 32 * 0.002 s
