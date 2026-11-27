"""What the built-in text steps read for a block's printed text, in one language (#1107).

Each step proposes its edits on the printed text, never on another step's output (D-57), so a
step that must read the same on a second run has to know the words other steps write. It asks
here: `readings_of("units", text, language)` gives the units step's readings of the whole
text, each a span, the words spoken and the step's category (GLOSSARY: reading).

Every built-in step that answers keeps its rules and offers them through one module-level
finder, from which its own edits come too, so what other steps expect of it and what it does
cannot drift apart. Answers are cached by step, text and language. Readings assume the
default category switches, and plugins are never asked: the second-run guarantee covers the
built-in steps only.

This module is internal to text preparation; it is no part of the public text-step interface
(`sci2audio.textprep.api`).
"""

from __future__ import annotations

import bisect
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache, lru_cache

from sci2audio.textprep.steps import Category


@dataclass(frozen=True, slots=True)
class Reading:
    """What one built-in step says for the printed text from `start` to `end`: `words`
    replace that span, as the step's edit does."""

    start: int
    end: int
    words: str
    category: Category


@dataclass(frozen=True)
class Finder:
    """A step's finder ("my readings in this block text, in this language") and the steps
    whose readings it asks for."""

    read: Callable[[str, str], Sequence[Reading]]
    asks: tuple[str, ...] = ()


class ReadingsError(RuntimeError):
    """A step's finder asked for readings its entry in the table does not name."""


class ReadingsLoopError(ReadingsError):
    """A step's readings were asked for while they were being found."""

    def __init__(self, steps: Sequence[str]) -> None:
        self.steps = tuple(steps)
        super().__init__(
            f'the readings of "{self.steps[0]}" ask for themselves: {" → ".join(self.steps)}'
        )


def readings_of(step: str, text: str, language: str) -> tuple[Reading, ...]:
    """The readings of the built-in step `step` in the whole of `text`, in text order."""
    finders = _finders()
    if step not in finders:
        raise ReadingsError(f'no built-in step "{step}" offers readings')
    asking = _asking()
    if step in asking:
        raise ReadingsLoopError([*asking[asking.index(step) :], step])
    if asking and step not in finders[asking[-1]].asks:
        raise ReadingsError(
            f'the readings of "{asking[-1]}" ask for those of "{step}", which their entry in '
            "the readings table does not name"
        )
    asking.append(step)
    try:
        return _read(step, text, language)
    finally:
        asking.pop()


def holding(found: Sequence[Reading], position: int) -> Reading | None:
    """The reading whose span holds `position`, of one step's readings (in text order, apart),
    or None. Looked up by halves, so a long block's many questions stay fast."""
    index = bisect.bisect_right(found, position, key=_start) - 1
    if index >= 0 and found[index].end > position:
        return found[index]
    return None


def first_from(found: Sequence[Reading], position: int) -> Reading | None:
    """The first of one step's readings that starts at `position` or after it, or None."""
    index = bisect.bisect_left(found, position, key=_start)
    return found[index] if index < len(found) else None


def _start(reading: Reading) -> int:
    return reading.start


def dependencies() -> dict[str, tuple[str, ...]]:
    """Each step in the table, with the steps whose readings its finder asks for."""
    return {step: finder.asks for step, finder in _finders().items()}


# a book's blocks, each in the few forms the steps read it in: the runner runs one step over
# every block before the next, and the later step's questions should still find the answers
@lru_cache(maxsize=8192)
def _read(step: str, text: str, language: str) -> tuple[Reading, ...]:
    return tuple(_finders()[step].read(text, language))


@cache
def _finders() -> dict[str, Finder]:
    # the steps import this module to ask for readings, so their finders can only be
    # reached once every step module is loaded: the one local import of step modules here
    from sci2audio.textprep import units

    return {"units": Finder(units.find_readings)}


_local = threading.local()  # each job's thread asks along its own chain


def _asking() -> list[str]:
    """The steps whose readings are being found in this thread, the first asker first."""
    if not hasattr(_local, "asking"):
        _local.asking = []
    return _local.asking
