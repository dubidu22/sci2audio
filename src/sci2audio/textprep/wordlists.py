"""The word lists the abbreviation and unit steps read, kept as data (TP-08, D-229).

One folder per language under `textprep/data/` (`en/abbreviations.toml`, `en/units.toml`),
written for sci2audio. A list is read once and checked as it is read: a missing field, a
wrong type or a form listed twice raises `ValueError` naming the file and the entry, so a
broken list fails the first test that loads it, never a job. A language without a folder
has no list (`None`).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any

BEFORE = ("anything", "number", "label", "word")  # where an abbreviation is read in full


@dataclass(frozen=True)
class Abbreviation:
    """One abbreviation: its printed forms and what is read instead."""

    printed: tuple[str, ...]
    reads: str
    before: str  # one of BEFORE
    can_end_sentence: bool = False


@dataclass(frozen=True)
class Unit:
    """One unit: its printed forms and its singular and plural readings."""

    printed: tuple[str, ...]
    singular: str
    plural: str
    length: bool = False  # a power 2 or 3 reads "square" / "cubic" before it
    per_only: bool = False  # a word read as a unit only after "per": "day" in "kg⁻¹ day⁻¹"
    not_before_word: bool = False  # also an English word: "1 A note" is not "1 ampere note"


@dataclass(frozen=True)
class UnitList:
    """Everything the unit step reads: units, magnitude letters and its own words."""

    units: tuple[Unit, ...]
    magnitudes: dict[str, str]  # printed letter -> word ("K" -> "thousand")
    words: dict[str, str]  # per, square, cubic, squared, cubed, approximately, about, times
    labels: frozenset[str]  # words before a number that make it a label, lower case
    articles: frozenset[str]  # "a", "an"


_WORDS = ("per", "square", "cubic", "squared", "cubed", "approximately", "about", "times")


def _language(language: str) -> str:
    return language.split("-", 1)[0].lower()


def _source(language: str, name: str) -> tuple[str, str] | None:
    """The file's name for messages and its text, or None if the language has none."""
    folder = _language(language)
    path = files("sci2audio.textprep").joinpath("data", folder, name)
    if not path.is_file():
        return None
    return f"textprep/data/{folder}/{name}", path.read_text(encoding="utf-8")


def _load(where: str, text: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{where}: {error}") from None


def _strings(where: str, entry: dict[str, Any], key: str) -> tuple[str, ...]:
    value = entry.get(key)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() == item and item for item in value)
    ):
        raise ValueError(f"{where}: {key} must be a list of printed forms, got {value!r}")
    return tuple(value)


def _text(where: str, entry: dict[str, Any], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: {key} must be words, got {value!r}")
    return value


def _flag(where: str, entry: dict[str, Any], key: str) -> bool:
    value = entry.get(key, False)
    if not isinstance(value, bool):
        raise ValueError(f"{where}: {key} must be true or false, got {value!r}")
    return value


def _no_extra(where: str, entry: dict[str, Any], keys: set[str]) -> None:
    if extra := set(entry) - keys:
        raise ValueError(f"{where}: unknown keys {sorted(extra)}")


def _once(where: str, forms: list[str]) -> None:
    seen: set[str] = set()
    for form in forms:
        if form in seen:
            raise ValueError(f"{where}: {form!r} is listed twice")
        seen.add(form)


@cache
def abbreviations(language: str) -> tuple[Abbreviation, ...] | None:
    """The abbreviations read in full for a language ("en-GB" uses "en"), or None."""
    source = _source(language, "abbreviations.toml")
    return None if source is None else parse_abbreviations(*source)


@cache
def units(language: str) -> UnitList | None:
    """The units, magnitude letters and words of the unit step for a language, or None."""
    source = _source(language, "units.toml")
    return None if source is None else parse_units(*source)


def parse_abbreviations(where: str, text: str) -> tuple[Abbreviation, ...]:
    """Read and check an abbreviation list; `where` names it in error messages."""
    data = _load(where, text)
    _no_extra(where, data, {"abbreviation"})
    result = []
    for number, entry in enumerate(data.get("abbreviation", []), 1):
        at = f"{where}, abbreviation {number}"
        _no_extra(at, entry, {"printed", "reads", "before", "can_end_sentence"})
        printed = _strings(at, entry, "printed")
        if not all(form.endswith(".") for form in printed):
            raise ValueError(f"{at}: every printed form ends in a full stop, got {printed!r}")
        before = entry.get("before")
        if before not in BEFORE:
            raise ValueError(f"{at}: before must be one of {BEFORE}, got {before!r}")
        result.append(
            Abbreviation(
                printed, _text(at, entry, "reads"), before, _flag(at, entry, "can_end_sentence")
            )
        )
    _once(where, [form.casefold() for entry in result for form in entry.printed])
    return tuple(result)


def parse_units(where: str, text: str) -> UnitList:
    """Read and check a unit list; `where` names it in error messages."""
    data = _load(where, text)
    _no_extra(where, data, {"words", "magnitude", "unit"})
    words_entry = data.get("words")
    if not isinstance(words_entry, dict):
        raise ValueError(f"{where}: a [words] table is needed")
    _no_extra(f"{where}, words", words_entry, {*_WORDS, "labels", "articles"})
    words = {key: _text(f"{where}, words", words_entry, key) for key in _WORDS}
    labels = frozenset(w.lower() for w in _strings(f"{where}, words", words_entry, "labels"))
    articles = frozenset(w.lower() for w in _strings(f"{where}, words", words_entry, "articles"))
    magnitudes: dict[str, str] = {}
    for number, entry in enumerate(data.get("magnitude", []), 1):
        at = f"{where}, magnitude {number}"
        _no_extra(at, entry, {"printed", "reads"})
        reads = _text(at, entry, "reads")
        for form in _strings(at, entry, "printed"):
            if form in magnitudes:
                raise ValueError(f"{at}: {form!r} is listed twice")
            magnitudes[form] = reads
    result = []
    for number, entry in enumerate(data.get("unit", []), 1):
        at = f"{where}, unit {number}"
        _no_extra(
            at, entry, {"printed", "singular", "plural", "length", "per_only", "not_before_word"}
        )
        result.append(
            Unit(
                _strings(at, entry, "printed"),
                _text(at, entry, "singular"),
                _text(at, entry, "plural"),
                _flag(at, entry, "length"),
                _flag(at, entry, "per_only"),
                _flag(at, entry, "not_before_word"),
            )
        )
    _once(where, [form for unit in result for form in unit.printed])
    return UnitList(tuple(result), magnitudes, words, labels, articles)
