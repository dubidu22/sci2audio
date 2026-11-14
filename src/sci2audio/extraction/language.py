"""The language a file states, as one BCP 47 tag or "" (#237, D-513 to D-515).

A PDF's /Lang, an EPUB's dc:language and Markdown's `lang` are written by many tools, not
all of them careful: "en_US" with an underscore, "und" for "undetermined", "x-default",
"ger". Layout compares the primary subtag with the text's guess (D-496), and the voice and
the text steps go by it, so every extractor hands on the stated language through this one
rule: white space removed, "_" read as "-"; a value that is not tag shaped, or whose primary
subtag states no language ("und", "zxx", "mul", "mis"), states nothing, so layout guesses;
the three-letter codes of the two languages sci2audio reads ("eng", "deu", "ger") become
"en" and "de". Letter case is kept as written; other codes are left as they are.
"""

from __future__ import annotations

import re

_TAG = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{1,8})*")
_NO_LANGUAGE = frozenset({"und", "zxx", "mul", "mis"})  # undetermined, none, many, uncoded
_TWO_LETTERS = {"eng": "en", "deu": "de", "ger": "de"}


def stated_language(raw: str) -> str:
    """The tag `raw` states, normalised, or "" when it states no language."""
    tag = raw.strip().replace("_", "-")
    if not _TAG.fullmatch(tag):
        return ""
    primary, dash, rest = tag.partition("-")
    lower = primary.lower()
    if lower in _NO_LANGUAGE:
        return ""
    return _TWO_LETTERS.get(lower, primary) + dash + rest
