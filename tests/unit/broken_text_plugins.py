"""Text-step plugins that break the rules, for the loader and the guard (#216)."""

import sys
import threading
from typing import ClassVar

from sci2audio.textprep.api import (
    Category,
    Document,
    Edit,
    EditKind,
    Span,
    Stage,
    StepContext,
    TextStep,
)


class _Plugin(TextStep):
    languages = ("en",)
    category = Category.CHARACTERS
    stage = Stage.INLINE
    api_version = 1

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return []


class NoVersionStep(TextStep):
    """Inherits `api_version` from TextStep instead of naming its contract."""

    id = "no-version"
    languages = ("en",)
    category = Category.CHARACTERS
    stage = Stage.INLINE

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        return []


class FutureStep(_Plugin):
    id = "future"
    api_version = 2


class BadIdStep(_Plugin):
    id = "Bad_Id"


class BlockPlugin(_Plugin):
    id = "a-block-plugin"
    stage = Stage.BLOCK


class ZetaStep(_Plugin):
    id = "zeta"


class AlphaStep(_Plugin):
    id = "alpha"


class FurnitureClash(_Plugin):
    id = "page-furniture"


class NotAStep:
    id = "not-a-step"


def failing_factory() -> TextStep:
    raise RuntimeError("the model file is missing")


def exiting_factory() -> TextStep:
    sys.exit(3)


class RaisingStep(_Plugin):
    id = "raising"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        raise ValueError("boom")


class ExitingStep(_Plugin):
    id = "exiting"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        sys.exit(4)


class InterruptedStep(_Plugin):
    id = "interrupted"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        raise KeyboardInterrupt


class SlowStep(_Plugin):
    """Waits until `release` is set; the guard gives up first."""

    id = "slow"
    release: ClassVar[threading.Event] = threading.Event()

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        self.release.wait(10)
        return []


class MutatingStep(_Plugin):
    """Changes the first block's text in place, which no step may do."""

    id = "mutating"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        object.__setattr__(document.blocks[0], "text", "changed")
        return []


class WatchingStep(_Plugin):
    """Remembers the first block's text it was given; runs after `mutating` (by id)."""

    id = "watching"
    seen: ClassVar[list[str]] = []

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        self.seen.append(document.blocks[0].text)
        return []


class RemovingStep(_Plugin):
    """Removes the first word of the first block."""

    id = "removing"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        end = document.blocks[0].text.find(" ")
        return [Edit(Span(0, 0, end), EditKind.REMOVE, reason="test", step=self.id)]


class Boom(BaseException):
    """Not an Exception: what a careless plugin might raise."""


class BadPropertyStep(_Plugin):
    """Its languages are computed, and computing them fails (review M1 of #676)."""

    id = "bad-property"

    @property
    def languages(self) -> tuple[str, ...]:
        raise RuntimeError("no language list")


def boom_factory() -> TextStep:
    raise Boom("from the factory")


class BoomStep(_Plugin):
    id = "boom"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        raise Boom("from find")


class _Unequal:
    def __eq__(self, other: object) -> bool:
        raise Boom("from __eq__")

    __hash__ = object.__hash__


class UnequalStep(_Plugin):
    """Leaves an object in its copy that cannot even be compared."""

    id = "unequal"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        object.__setattr__(document, "blocks", (_Unequal(),))
        return []
