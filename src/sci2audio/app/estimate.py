"""The audio job's time estimate: what one voice call costs, fitted on this run (#136).

A voice call takes a fixed time on top of its characters, and long utterances take more
per character than short ones, so the seconds of one call are modelled as

    seconds = constant + per_character * c + per_square * c * c     (c = characters)

with every coefficient zero or more, fitted by least squares on the chunks measured so far
in this run (D-380). The time left is that cost summed over every chunk still to speak.

What keeps a curve from running wild:
- fewer than MIN_CHUNKS measured chunks (twice the coefficients), or fewer different
  lengths than coefficients: the plain rate (measured seconds / measured characters,
  D-159) instead of the fit;
- the curve is never used beyond the longest measured chunk L: a longer chunk costs
  model(L) / L per character, the cost per character at the edge of what was measured
  (D-384). A first chapter of names, headings or a list measures only short chunks,
  and the curve fitted on them can say almost twice the real time for long paragraphs.
The fit also keeps the plain rate when it explains the measured chunks no better than the
rate does; since the per-character-only fit is one of its candidates, that happens only
when the cost is exactly per character.

The measured chunks are kept as running sums, so adding one is constant time; the chunks
still to speak are counted by length, so the time left costs one step per different
length (at most the voice's longest utterance, 300 characters by default).
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass, field

TERMS = 3  # constant, per character, per character squared
MIN_CHUNKS = 2 * TERMS  # measured chunks before the fit is trusted over the plain rate
SCALE = 100.0  # characters are fitted in hundreds, so the sums stay well conditioned
_PIVOT = 1e-9  # a smaller pivot (relative to the diagonal) means the terms cannot be told apart


@dataclass(frozen=True)
class CostModel:
    """Seconds one voice call takes for `characters` characters."""

    constant: float = 0.0
    per_character: float = 0.0
    per_square: float = 0.0

    def seconds(self, characters: int) -> float:
        c = float(characters)
        return self.constant + self.per_character * c + self.per_square * c * c

    @classmethod
    def rate(cls, seconds: float, characters: int) -> CostModel:
        """The plain rate: every character costs the same, nothing per call."""
        return cls(per_character=seconds / characters)


@dataclass
class _Sums:
    """Running sums of x**k (k = 0..2*TERMS-2) and y*x**k (k = 0..TERMS-1) and y*y."""

    powers: list[float] = field(default_factory=lambda: [0.0] * (2 * TERMS - 1))
    weighted: list[float] = field(default_factory=lambda: [0.0] * TERMS)
    squares: float = 0.0

    def add(self, x: float, y: float) -> None:
        for k in range(len(self.powers)):
            self.powers[k] += x**k
        for k in range(TERMS):
            self.weighted[k] += y * x**k
        self.squares += y * y


@dataclass
class Estimate:
    """The measured chunks of one run and the chunks still to speak."""

    measured_characters: int = 0
    measured_seconds: float = 0.0
    measured_chunks: int = 0
    _measured: _Sums = field(default_factory=_Sums)
    _lengths: set[int] = field(default_factory=set)
    _left: Counter[int] = field(default_factory=Counter)  # length -> chunks still to speak

    def measure(self, characters: int, seconds: float) -> None:
        """One voice call of `characters` characters took `seconds`."""
        self.measured_characters += characters
        self.measured_seconds += seconds
        self.measured_chunks += 1
        self._measured.add(characters / SCALE, seconds)
        self._lengths.add(characters)

    def expect(self, characters: int) -> None:
        """A chunk of `characters` characters is still to be spoken."""
        self._left[characters] += 1

    def done(self, characters: int) -> None:
        """A chunk `expect`ed earlier is spoken (or failed): it is no longer left."""
        self._left[characters] -= 1
        if self._left[characters] <= 0:
            del self._left[characters]

    def speed(self) -> float | None:
        """Measured characters per second, the plain rate; None before any measurement."""
        if self.measured_characters == 0 or self.measured_seconds <= 0:
            return None
        return self.measured_characters / self.measured_seconds

    def model(self) -> CostModel | None:
        """The cost of one call, fitted on the measured chunks; None before any."""
        if self.speed() is None:
            return None
        rate = CostModel.rate(self.measured_seconds, self.measured_characters)
        if self.measured_chunks < MIN_CHUNKS or len(self._lengths) < TERMS:
            return rate
        fitted = _fit(self._measured)
        if fitted is None:
            return rate
        coefficients, error = fitted
        if error >= self._error(rate):
            return rate
        constant, per_character, per_square = coefficients
        return CostModel(constant, per_character / SCALE, per_square / SCALE**2)

    def seconds_left(self) -> float | None:
        """The model summed over every chunk still to speak, never beyond the longest
        measured chunk; None before any measurement."""
        model = self.model()
        if model is None:
            return None
        longest = max(self._lengths)
        per_character_beyond = model.seconds(longest) / longest
        seconds = sum(
            count * (model.seconds(length) if length <= longest else per_character_beyond * length)
            for length, count in self._left.items()
        )
        return max(0.0, seconds)

    def _error(self, model: CostModel) -> float:
        """Sum of squared errors of `model` over the measured chunks."""
        p = (model.constant, model.per_character * SCALE, model.per_square * SCALE**2)
        return _sse(self._measured, p)


def _sse(sums: _Sums, p: tuple[float, ...]) -> float:
    """Sum over the measured chunks of (y - sum p_k x**k)**2, from the running sums."""
    cross = sum(p[k] * sums.weighted[k] for k in range(TERMS))
    quad = sum(p[i] * p[j] * sums.powers[i + j] for i in range(TERMS) for j in range(TERMS))
    return max(0.0, sums.squares - 2 * cross + quad)


def _fit(sums: _Sums) -> tuple[tuple[float, ...], float] | None:
    """Non-negative least squares over the terms, exactly: the best unconstrained fit of
    every subset of terms whose coefficients all come out zero or more. None if no subset
    can be solved."""
    best: tuple[tuple[float, ...], float] | None = None
    for size in range(1, TERMS + 1):
        for subset in itertools.combinations(range(TERMS), size):
            solved = _solve(
                [[sums.powers[i + j] for j in subset] for i in subset],
                [sums.weighted[i] for i in subset],
            )
            if solved is None or any(value < 0 for value in solved):
                continue
            p = [0.0] * TERMS
            for index, value in zip(subset, solved, strict=True):
                p[index] = value
            error = _sse(sums, tuple(p))
            if best is None or error < best[1]:
                best = (tuple(p), error)
    return best


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting; None if the matrix is (nearly) singular."""
    n = len(vector)
    rows = [[*matrix[i], vector[i]] for i in range(n)]
    scale = max(abs(rows[i][i]) for i in range(n)) or 1.0
    for column in range(n):
        pivot = max(range(column, n), key=lambda r: abs(rows[r][column]))
        if abs(rows[pivot][column]) <= _PIVOT * scale:
            return None
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for r in range(column + 1, n):
            factor = rows[r][column] / rows[column][column]
            for k in range(column, n + 1):
                rows[r][k] -= factor * rows[column][k]
    solution = [0.0] * n
    for r in reversed(range(n)):
        total = rows[r][n] - sum(rows[r][k] * solution[k] for k in range(r + 1, n))
        solution[r] = total / rows[r][r]
    return solution
