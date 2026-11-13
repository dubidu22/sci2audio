"""The audio job's cost model for the time estimate (#136, D-380): the fit, its fallback to
the plain rate, and the chunks still to speak."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sci2audio.app.estimate import MIN_CHUNKS, CostModel, Estimate


def measured(*calls: tuple[int, float]) -> Estimate:
    estimate = Estimate()
    for characters, seconds in calls:
        estimate.measure(characters, seconds)
    return estimate


def plain_rate(estimate: Estimate) -> CostModel:
    return CostModel.rate(estimate.measured_seconds, estimate.measured_characters)


def test_nothing_measured_gives_no_estimate() -> None:
    estimate = Estimate()
    estimate.expect(100)
    assert estimate.speed() is None
    assert estimate.model() is None
    assert estimate.seconds_left() is None


def test_the_fit_finds_a_cost_per_call_per_character_and_per_square() -> None:
    def cost(characters: int) -> float:
        return 0.5 + 0.01 * characters + 0.00005 * characters**2

    estimate = measured(*((n, cost(n)) for n in (10, 40, 80, 120, 200, 250, 300)))
    model = estimate.model()
    assert model is not None
    assert model.constant == pytest.approx(0.5)
    assert model.per_character == pytest.approx(0.01)
    assert model.per_square == pytest.approx(0.00005)
    for characters in (7, 150, 290):
        estimate.expect(characters)
    assert estimate.seconds_left() == pytest.approx(cost(7) + cost(150) + cost(290))


def test_a_fixed_cost_per_call_is_found() -> None:
    """Every call costs a second whatever its length: the time left is one second a chunk."""
    estimate = measured(*((n, 1.0) for n in (10, 50, 90, 130, 170, 210)))
    for characters in (20, 280, 5):
        estimate.expect(characters)
    assert estimate.seconds_left() == pytest.approx(3.0)


def test_a_cost_that_falls_with_length_never_gets_a_negative_coefficient() -> None:
    estimate = measured(*((n, 3.0 - n / 100) for n in (10, 50, 90, 130, 170, 210)))
    model = estimate.model()
    assert model is not None
    assert min(model.constant, model.per_character, model.per_square) >= 0


@pytest.mark.parametrize("count", range(1, MIN_CHUNKS))
def test_too_few_chunks_keep_the_plain_rate(count: int) -> None:
    """A short run never gets a curve through a handful of points (D-380)."""
    lengths = (10, 300, 60, 200, 30)[:count]
    estimate = measured(*((n, 0.2 + n * n / 10_000) for n in lengths))
    assert estimate.model() == plain_rate(estimate)


def test_too_few_different_lengths_keep_the_plain_rate() -> None:
    estimate = measured(*((n, 0.1 + n / 50) for n in (100, 100, 200, 200, 100, 200, 100)))
    assert estimate.model() == plain_rate(estimate)


def test_a_cost_exactly_per_character_keeps_the_plain_rate() -> None:
    """The fit is used only when it explains the measured chunks better than the rate."""
    estimate = measured(*((n, n / 40) for n in (10, 50, 90, 130, 170, 210)))
    assert estimate.model() == plain_rate(estimate)
    estimate.expect(400)
    assert estimate.seconds_left() == pytest.approx(10.0)


def test_spoken_and_failed_chunks_are_no_longer_left() -> None:
    estimate = measured(*((n, n / 40) for n in (10, 50, 90, 130, 170, 210)))
    for characters in (40, 80, 120):
        estimate.expect(characters)
    estimate.done(80)
    assert estimate.seconds_left() == pytest.approx(4.0)
    estimate.done(40)
    estimate.done(120)
    assert estimate.seconds_left() == pytest.approx(0.0)


def test_the_speed_is_the_measured_characters_per_second() -> None:
    estimate = measured((100, 2.0), (300, 6.0))
    assert estimate.speed() == pytest.approx(50.0)


calls = st.lists(
    st.tuples(st.integers(1, 2000), st.floats(0.001, 120, allow_nan=False)),
    min_size=1,
    max_size=60,
)


@given(calls, st.lists(st.integers(1, 2000), max_size=30))
def test_the_model_is_never_negative_and_never_worse_than_the_rate(
    spoken: list[tuple[int, float]], left: list[int]
) -> None:
    estimate = measured(*spoken)
    model = estimate.model()
    assert model is not None
    assert min(model.constant, model.per_character, model.per_square) >= 0

    def error(m: CostModel) -> float:
        return sum((seconds - m.seconds(n)) ** 2 for n, seconds in spoken)

    rate = plain_rate(estimate)
    assert error(model) <= error(rate) * (1 + 1e-9) + 1e-9
    for characters in left:
        estimate.expect(characters)
    seconds = estimate.seconds_left()
    assert seconds is not None
    assert seconds >= 0
    assert seconds == pytest.approx(sum(model.seconds(n) for n in left), rel=1e-6, abs=1e-6)
