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
    """Its languages are computed, and computing them fails."""

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


HANG = threading.Event()  # set by a test when it ends, so a hanging plugin lets go


def hanging_factory() -> TextStep:
    HANG.wait(5)
    return AlphaStep()


class HangingPropertyStep(_Plugin):
    """Its id takes forever to compute."""

    @property
    def id(self) -> str:  # type: ignore[override]
        HANG.wait(5)
        return "hanging-property"


def interrupting_factory() -> TextStep:
    raise KeyboardInterrupt


class _NoRepr:
    """An id like a lazy translation: not a str, and it cannot even be shown."""

    def __repr__(self) -> str:
        raise RuntimeError("no repr")


class LazyIdStep(_Plugin):
    id = _NoRepr()  # type: ignore[assignment]


class _SlowVersion:
    def __ne__(self, other: object) -> bool:
        HANG.wait(5)
        return False

    __hash__ = object.__hash__


class SlowVersionStep(_Plugin):
    id = "slow-version"
    api_version = _SlowVersion()  # type: ignore[assignment]


class _TouchyId(str):
    """A str whose own methods fail: only a plain copy of it is safe to hash or sort."""

    def __hash__(self) -> int:
        raise RuntimeError("no hash")

    def __lt__(self, other: object) -> bool:
        raise RuntimeError("no order")


class TouchyIdStep(_Plugin):
    id = _TouchyId("touchy-id")
    languages = (_TouchyId("en"),)


# ---- a hostile plugin that records the thread its objects run in (#693, META-03) --------

CALLS: list[tuple[str, str]] = []  # (dunder, thread name), in call order

_TRACED = (
    "__str__",
    "__repr__",
    "__format__",
    "__eq__",
    "__ne__",
    "__hash__",
    "__lt__",
    "__bool__",
    "__len__",
    "__iter__",
    "__index__",
    "__int__",
)


def _record(name: str) -> None:
    CALLS.append((name, threading.current_thread().name))


def traced[T](base: type[T]) -> type[T]:
    """A subclass of `base` whose dunders record their thread, then answer as `base` does."""

    def answering(name: str):
        inner = getattr(base, name)

        def method(self, *args):
            _record(name)
            return inner(self, *args)

        return method

    def __getattr__(self, name: str):
        _record("__getattr__")
        raise AttributeError(name)

    def __del__(self) -> None:
        _record("__del__")

    body = {name: answering(name) for name in _TRACED if hasattr(base, name)}
    body.update(__getattr__=__getattr__, __del__=__del__)
    return type(f"Traced{base.__name__}", (base,), body)


TracedStr = traced(str)
TracedInt = traced(int)


class _Liar(traced(object)):
    """Passes `isinstance(x, Category)` and `isinstance(x, Stage)` without being either."""

    def __init__(self, posing_as: type) -> None:
        self.posing_as = posing_as

    @property  # type: ignore[misc]
    def __class__(self) -> type:  # type: ignore[override]
        return self.posing_as


class HostileStep(_Plugin):
    """Hands over a traced object at the point `case` names; otherwise removes "Smith"."""

    id = "hostile"

    def __init__(self, case: str) -> None:
        self.case = case

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        case = self.case
        if case == "exception":
            raise traced(Exception)("traced")
        if case == "system-exit":
            raise traced(SystemExit)(TracedInt(4))
        if case == "base-exception":
            raise traced(BaseException)("traced")
        if case == "document":
            block = document.blocks[0]
            object.__setattr__(block, "text", traced(object)())
            return []
        if case == "context":
            object.__setattr__(context, "language", TracedStr(context.language))
            return []
        edit = Edit(Span(0, 0, 5), EditKind.REMOVE, reason="test", step="hostile")
        if case == "edit":
            edit = traced(Edit)(Span(0, 0, 5), EditKind.REMOVE, reason="test", step="hostile")
        if case == "offsets":
            span = Span(TracedInt(0), TracedInt(0), TracedInt(5))
            edit = Edit(span, EditKind.REMOVE, reason="test", step="hostile")
        if case == "replacement":
            edit = Edit(
                Span(0, 6, 7),
                EditKind.REPLACE,
                reason=TracedStr("test"),
                step=TracedStr("hostile"),
                replacement=TracedStr("and"),
            )
        return traced(list)([edit]) if case == "list" else [edit]


def hostile(case: str) -> TextStep:
    """The hostile step for `case`, made in the loader's worker like any plugin's step."""
    step = traced(HostileStep)(case) if case == "step" else HostileStep(case)
    if case == "id":
        step.id = TracedStr("hostile")
    if case == "languages":
        step.languages = traced(tuple)((TracedStr("en"),))
    if case == "category":
        step.category = _Liar(Category)  # type: ignore[assignment]
    if case == "stage":
        step.stage = _Liar(Stage)  # type: ignore[assignment]
    return step


class _Hostile:
    """`broken_text_plugins:HOSTILE.<case>` is the factory of that case's hostile step."""

    def __getattr__(self, case: str):
        return lambda: hostile(case.replace("_", "-"))


HOSTILE = _Hostile()


class _BlockingEq:
    def __eq__(self, other: object) -> bool:
        HANG.wait(5)
        return True

    __hash__ = object.__hash__


class BlockingEqStep(_Plugin):
    """Leaves an object in its copy whose comparison takes forever."""

    id = "blocking-eq"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        object.__setattr__(document.blocks[0], "text", _BlockingEq())
        return []


class _SlowMessage(Exception):
    def __str__(self) -> str:
        HANG.wait(5)
        return "slow"


class SlowMessageStep(_Plugin):
    """Raises an error whose text takes forever to build."""

    id = "slow-message"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        raise _SlowMessage


class _NoIndex(int):
    def __index__(self) -> int:
        raise RuntimeError("no index")


class NoIndexStep(_Plugin):
    """Removes "Smith" with offsets whose `__index__` raises."""

    id = "no-index"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        span = Span(_NoIndex(0), _NoIndex(0), _NoIndex(5))
        return [Edit(span, EditKind.REMOVE, reason="test", step=self.id)]


class _LooksLikeEn:
    """A language that is not a str but shows as one."""

    def __str__(self) -> str:
        return "en"


class NotStrLanguageStep(_Plugin):
    id = "not-str-language"
    languages = (_LooksLikeEn(),)  # type: ignore[assignment]


class CyclicPlantStep(_Plugin):
    """Plants in its copy an object that refers to itself: only the collector frees it."""

    id = "cyclic-plant"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        planted = traced(object)()
        planted.me = planted
        object.__setattr__(document.blocks[0], "text", planted)
        return []


class CyclicErrorStep(_Plugin):
    """Raises an error that refers to itself."""

    id = "cyclic-error"

    def find(self, document: Document, context: StepContext) -> list[Edit]:
        error = traced(Exception)("cyclic")
        error.me = error
        raise error
