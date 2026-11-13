"""The interface's languages (#79, D-288 to D-290): one string table per language.

Every string a person reads comes from `strings/<language>.toml` (D-256); German mirrors
the English keys exactly and nothing falls back to English at run time (D-289). A page's
language is the switch's cookie, else the browser's `Accept-Language`, else English
(D-288). There is no "current language" anywhere: each request gets its own `Strings`.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any

from starlette.requests import Request

LANGUAGES = ("en", "de")
DEFAULT_LANGUAGE = "en"

# The language the person chose with the switch. Deliberately not named after the port,
# unlike the start-up cookie (D-193): cookies ignore ports, so the choice survives the next
# server run. It holds "en" or "de" and nothing else (D-288).
COOKIE = "sci2audio-language"
COOKIE_AGE = 365 * 24 * 60 * 60  # one year, in seconds

PLURAL_FORMS = ("one", "other")  # the CLDR forms English and German share (D-290)

# what the script reads from the page's data block
SCRIPT_KEYS = (
    "js.",
    "phase.",
    "error.",
    "make.needs_",
    "job.state_",
    "voice.speed_value",
    "common.decimal",
    "common.details",
    "player.",
    "remove.removing",
    "remove.done",
    "remove.stays",  # and remove.stays_folder
)


def _flatten(table: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in table.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(_flatten(value, f"{name}."))
        else:
            flat[name] = str(value)
    return flat


@cache
def load_table(language: str) -> Mapping[str, str]:
    """One language's table as `section.key` → text (a plural as `key.one`, `key.other`)."""
    if language not in LANGUAGES:
        raise ValueError(f"no interface language {language!r}")
    text = (files("sci2audio.web") / "strings" / f"{language}.toml").read_text(encoding="utf-8")
    return _flatten(tomllib.loads(text))


def plural_form(n: int | float) -> str:
    """`one` for exactly 1, else `other`: the rule of both English and German."""
    return "one" if n == 1 else "other"


@dataclass(frozen=True)
class Strings:
    """The interface texts of one language."""

    language: str
    table: Mapping[str, str]

    def t(self, key: str, /, **values: Any) -> str:
        """The text `key` with its placeholders filled in (escaped later by Jinja).

        A key with plural forms picks `one` or `other` by the value `n`.
        """
        text = self.table.get(key)
        if text is None and "n" in values:
            text = self.table.get(f"{key}.{plural_form(values['n'])}")
        if text is None:
            raise KeyError(key)
        return text.format(**values) if values else text

    def __call__(self, key: str, /, **values: Any) -> str:
        return self.t(key, **values)

    def number(self, value: float, places: int = 2) -> str:
        """A decimal number with the language's decimal sign, without trailing zeros and
        without digit grouping (D-290)."""
        text = f"{value:.{places}f}".rstrip("0").rstrip(".") if places else f"{value:.0f}"
        return text.replace(".", self.table["common.decimal"])

    def size(self, n: int) -> str:
        """A file size in bytes, KB or MB (decimal units, as the voice page lists them)."""
        if n >= 1_000_000:
            return self.t("common.megabytes", n=self.number(n / 1_000_000, 1))
        if n >= 1000:
            return self.t("common.kilobytes", n=round(n / 1000))
        return self.t("common.bytes", n=n)

    def script_json(self) -> str:
        """The strings the script uses, as JSON for the page's data block."""
        return data_block({k: v for k, v in self.table.items() if k.startswith(SCRIPT_KEYS)})


def data_block(data: Any) -> str:
    """`data` as JSON for a `<script type="application/json">` block. `<`, `>` and `&`
    are written as JSON escapes, so no text in it (`</script>`, `<!--<script>`) can
    change how the browser parses the page; JSON.parse reads the same data back."""
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


_KNOWN = {code: code for code in LANGUAGES}


def known_language(text: str | None) -> str | None:
    """The interface language `text` names, taken from `LANGUAGES` itself, or None: what
    goes into the cookie is never the request's own text."""
    return _KNOWN.get(text) if text else None


def strings(language: str) -> Strings:
    return Strings(language, load_table(language))


_RANGE = re.compile(r"^\s*([A-Za-z]{1,8})(?:-[A-Za-z0-9]{1,8})*\s*(?:;\s*q\s*=\s*([0-9.]+))?\s*$")


def from_accept_language(header: str | None) -> str | None:
    """The first interface language among the browser's languages, by their weights."""
    if not header:
        return None
    ranked: list[tuple[float, int, str]] = []
    for position, part in enumerate(header.split(",")[:32]):
        match = _RANGE.match(part)
        if match is None:
            continue
        try:
            weight = float(match[2]) if match[2] is not None else 1.0
        except ValueError:
            continue
        primary = match[1].lower()
        if weight > 0 and primary in LANGUAGES:
            ranked.append((-weight, position, primary))
    return min(ranked)[2] if ranked else None


def language_from(cookies: Iterable[str | None], accept_language: str | None) -> str:
    """The page language from the switch cookie's values, else from the browser's
    `Accept-Language`, else English (D-288)."""
    for value in cookies:
        chosen = known_language(value)
        if chosen is not None:
            return chosen
    return from_accept_language(accept_language) or DEFAULT_LANGUAGE


def language_of(request: Request) -> str:
    """The page language of a request (D-288)."""
    return language_from([request.cookies.get(COOKIE)], request.headers.get("accept-language"))


def strings_of(request: Request) -> Strings:
    return strings(language_of(request))


def local_path(back: str | None) -> str:
    """Where the switch sends the browser back: a path on this server, never elsewhere."""
    if (
        not back
        or not back.startswith("/")
        or back.startswith("//")
        or "\\" in back
        or any(ord(c) < 0x20 or ord(c) == 0x7F for c in back)
    ):
        return "/"
    return back
