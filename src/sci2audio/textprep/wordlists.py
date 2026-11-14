"""The word lists the abbreviation and unit steps read, kept as data (TP-08, D-229).

One folder per language under `textprep/data/` (`en/abbreviations.toml`, `en/units.toml`),
written for sci2audio. A list is read once and checked as it is read: a missing field, a
wrong type or a form listed twice raises `ValueError` naming the file and the entry, so a
broken list fails the first test that loads it, never a job. A language without a folder
has no list (`None`).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files
from typing import Any

BEFORE = ("anything", "number", "label", "word")  # where an abbreviation is read in full
GENDERS = ("m", "f", "n")  # a unit's grammatical gender, for "ein"/"eine" before it (German)
CASES = ("nominative", "dative", "accusative")  # the forms of "ein" a list may give


@dataclass(frozen=True)
class Abbreviation:
    """One abbreviation: its printed forms and what is read instead."""

    printed: tuple[str, ...]
    reads: str
    before: str  # one of BEFORE
    can_end_sentence: bool = False
    exact_case: bool = False  # found only as printed, read as listed ("S." Seite, "s." siehe)
    before_year: str = ""  # read instead before a year: "u. a. (2019)" is "und andere"


@dataclass(frozen=True)
class Unit:
    """One unit: its printed forms and its singular and plural readings."""

    printed: tuple[str, ...]
    singular: str
    plural: str
    length: bool = False  # a power 2 or 3 reads "square" / "cubic" before it
    per_only: bool = False  # a word read as a unit only after "per": "day" in "kg⁻¹ day⁻¹"
    not_before_word: bool = False  # also an English word: "1 A note" is not "1 ampere note"
    gender: str = ""  # "m", "f" or "n" where the language says "1" by gender ("eine Sekunde")


@dataclass(frozen=True)
class UnitList:
    """Everything the unit step reads: units, magnitude letters and its own words."""

    units: tuple[Unit, ...]
    magnitudes: dict[str, str]  # printed letter -> word ("K" -> "thousand")
    words: dict[str, str]  # per, square, cubic, squared, cubed, approximately, about, times
    labels: frozenset[str]  # words before a number that make it a label, lower case
    articles: frozenset[str]  # "a", "an"; may be empty
    decimal: str = "."  # the decimal sign numbers are printed with ("," in German)
    joined_powers: bool = False  # "square"/"cubic" written into the unit: "Quadratmeter"
    hyphen_singular: bool = True  # "a 5-km race": singular when joined by a hyphen
    # the words read for "1" before a unit, by case and gender ({"nominative": {"f": "eine"}})
    ones: dict[str, dict[str, str]] = field(default_factory=dict)
    dative: frozenset[str] = frozenset()  # words before "1" that ask for the dative
    accusative: frozenset[str] = frozenset()  # words before "1" that ask for the accusative


_WORDS = ("per", "square", "cubic", "squared", "cubed", "approximately", "about", "times")
# optional keys of [words] for languages that print and say numbers otherwise (German)
_LANGUAGE_KEYS = (
    "labels", "articles", "decimal", "joined_powers", "hyphen_singular", "one", "dative",
    "accusative",
)  # fmt: skip


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
        _no_extra(
            at,
            entry,
            {"printed", "reads", "before", "can_end_sentence", "exact_case", "before_year"},
        )
        printed = _strings(at, entry, "printed")
        if not all(form.endswith(".") for form in printed):
            raise ValueError(f"{at}: every printed form ends in a full stop, got {printed!r}")
        before = entry.get("before")
        if before not in BEFORE:
            raise ValueError(f"{at}: before must be one of {BEFORE}, got {before!r}")
        before_year = _text(at, entry, "before_year") if "before_year" in entry else ""
        result.append(
            Abbreviation(
                printed,
                _text(at, entry, "reads"),
                before,
                _flag(at, entry, "can_end_sentence"),
                _flag(at, entry, "exact_case"),
                before_year,
            )
        )
    # a form found in any case may not share its letters with another form; forms found only
    # as printed ("S." and "s.") may, if they differ as printed
    _once(
        where,
        [form.casefold() for entry in result if not entry.exact_case for form in entry.printed],
    )
    _once(where, [form for entry in result if entry.exact_case for form in entry.printed])
    loose = {form.casefold() for entry in result if not entry.exact_case for form in entry.printed}
    for entry in result:
        for form in entry.printed if entry.exact_case else ():
            if form.casefold() in loose:
                raise ValueError(f"{where}: {form!r} is also listed in any case")
    return tuple(result)


def parse_units(where: str, text: str) -> UnitList:
    """Read and check a unit list; `where` names it in error messages."""
    data = _load(where, text)
    _no_extra(where, data, {"words", "magnitude", "unit"})
    words_entry = data.get("words")
    if not isinstance(words_entry, dict):
        raise ValueError(f"{where}: a [words] table is needed")
    at_words = f"{where}, words"
    _no_extra(at_words, words_entry, {*_WORDS, *_LANGUAGE_KEYS})
    words = {key: _text(at_words, words_entry, key) for key in _WORDS}
    labels = frozenset(w.lower() for w in _strings(at_words, words_entry, "labels"))
    articles = frozenset(
        w.lower()
        for w in (_strings(at_words, words_entry, "articles") if "articles" in words_entry else ())
    )
    decimal = words_entry.get("decimal", ".")
    if decimal not in (".", ","):
        raise ValueError(f'{at_words}: decimal must be "." or ",", got {decimal!r}')
    ones = _ones(at_words, words_entry.get("one", {}))
    dative = frozenset(
        w.lower()
        for w in (_strings(at_words, words_entry, "dative") if "dative" in words_entry else ())
    )
    accusative = frozenset(
        w.lower()
        for w in (
            _strings(at_words, words_entry, "accusative") if "accusative" in words_entry else ()
        )
    )
    if (dative or accusative) and not ones:
        raise ValueError(f"{at_words}: dative and accusative words need a [words.one] table")
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
            at,
            entry,
            {"printed", "singular", "plural", "length", "per_only", "not_before_word", "gender"},
        )
        gender = entry.get("gender", "")
        if gender not in ("", *GENDERS):
            raise ValueError(f"{at}: gender must be one of {GENDERS}, got {gender!r}")
        if ones and not gender:
            raise ValueError(f"{at}: the list reads 1 by gender, so every unit needs a gender")
        result.append(
            Unit(
                _strings(at, entry, "printed"),
                _text(at, entry, "singular"),
                _text(at, entry, "plural"),
                _flag(at, entry, "length"),
                _flag(at, entry, "per_only"),
                _flag(at, entry, "not_before_word"),
                gender,
            )
        )
    _once(where, [form for unit in result for form in unit.printed])
    return UnitList(
        tuple(result),
        magnitudes,
        words,
        labels,
        articles,
        decimal,
        _flag(at_words, words_entry, "joined_powers"),
        _flag(at_words, words_entry, "hyphen_singular")
        if "hyphen_singular" in words_entry
        else True,
        ones,
        dative,
        accusative,
    )


def _ones(where: str, table: Any) -> dict[str, dict[str, str]]:
    """The [words.one] table: for each case, the word for "1" before a unit of each gender."""
    if not isinstance(table, dict):
        raise ValueError(f"{where}: one must be a table of cases, got {table!r}")
    _no_extra(f"{where}, one", table, set(CASES))
    if table and "nominative" not in table:
        raise ValueError(f"{where}, one: the nominative is needed")
    ones = {}
    for case, forms in table.items():
        at = f"{where}, one, {case}"
        if not isinstance(forms, dict) or set(forms) != set(GENDERS):
            raise ValueError(f"{at}: give exactly the genders {GENDERS}, got {forms!r}")
        ones[case] = {gender: _text(at, forms, gender) for gender in GENDERS}
    return ones
