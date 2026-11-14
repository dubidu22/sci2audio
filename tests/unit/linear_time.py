"""Timing tests that a busy runner does not decide (#274, #276, D-539, D-540).

A limit in seconds fails on a slow or shared machine (the macOS CI runner went 20% over
one). Instead, a test times a step on a base text and on eight times that text, each the
best of three runs with garbage collection off, and holds the ratio below 32: a linear
step gives about 8, a quadratic one about 64.
"""

from __future__ import annotations

import gc
import time
from collections.abc import Callable

FACTOR = 8  # the large text is this many times the base text
LIMIT = 32  # four times linear, half of quadratic
FLOOR = 0.002  # seconds: a base run faster than this counts as this long (timer noise)


def best_seconds[T](run: Callable[[str], T], text: str, runs: int = 3) -> tuple[float, T]:
    """The fastest of `runs` runs of `run(text)`, gc off while timing, and its result."""
    best = float("inf")
    result: T
    for _ in range(runs):
        gc.collect()
        gc.disable()
        try:
            started = time.perf_counter()
            result = run(text)
            best = min(best, time.perf_counter() - started)
        finally:
            gc.enable()
    return best, result


def assert_linear[T](run: Callable[[str], T], sized: Callable[[int], str], size: int) -> T:
    """Time `run` on `sized(size // FACTOR)` and on `sized(size)`; fail if the large text
    takes more than LIMIT times as long. Returns the result of the large run."""
    small, _ = best_seconds(run, sized(size // FACTOR))
    large, result = best_seconds(run, sized(size))
    assert large < LIMIT * max(small, FLOOR), (
        f"{FACTOR} times the text took {large / max(small, FLOOR):.1f} times as long "
        f"({small:.3f} s, {large:.3f} s); linear is about {FACTOR}, the limit {LIMIT}"
    )
    return result
