"""A stable, readable export of the core objects, for golden files and saved jobs (D-60).

`to_data` turns an object into plain data (dicts with sorted keys, lists, strings, numbers,
booleans); fields left at their default are left out, so snapshots stay short and their diffs
show only what changed. `from_data` builds the object again: `from_data(type(x), to_data(x))`
equals `x`. The data holds nothing that changes between runs: no timestamps, no paths.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from enum import Enum
from typing import Any

Data = dict[str, Any] | list[Any] | str | int | float | bool | None


def to_data(value: object) -> Data:
    """Plain, sorted data for a core object (or a tuple of them)."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        data = {}
        for f in dataclasses.fields(value):
            item = getattr(value, f.name)
            if item != _default(f):
                data[f.name] = to_data(item)
        return dict(sorted(data.items()))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple | list):
        return [to_data(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"cannot export {type(value).__name__}")


def from_data[T](cls: type[T], data: Data) -> T:
    """Build a `cls` from data made by `to_data`; raise ValueError if the data doesn't fit."""
    return _build(cls, data)


def _default(f: dataclasses.Field[Any]) -> object:
    if f.default is not dataclasses.MISSING:
        return f.default
    if f.default_factory is not dataclasses.MISSING:
        return f.default_factory()
    return dataclasses.MISSING


def _build(hint: Any, data: Any) -> Any:
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin is types.UnionType or origin is typing.Union:
        if data is None and type(None) in args:
            return None
        (inner,) = (a for a in args if a is not type(None))
        return _build(inner, data)
    if origin is tuple:
        if not isinstance(data, list):
            raise ValueError(f"expected a list, got {data!r}")
        return tuple(_build(args[0], item) for item in data)
    if isinstance(hint, type) and dataclasses.is_dataclass(hint):
        if not isinstance(data, dict):
            raise ValueError(f"expected a mapping for {hint.__name__}, got {data!r}")
        hints = typing.get_type_hints(hint)
        unknown = set(data) - set(hints)
        if unknown:
            raise ValueError(f"unknown fields for {hint.__name__}: {sorted(unknown)}")
        return hint(**{name: _build(hints[name], item) for name, item in data.items()})
    if isinstance(hint, type) and issubclass(hint, Enum):
        return hint(data)
    if hint is float and isinstance(data, int | float) and not isinstance(data, bool):
        return float(data)
    if hint in (str, int, bool) and type(data) is hint:
        return data
    raise ValueError(f"expected {getattr(hint, '__name__', hint)}, got {data!r}")
