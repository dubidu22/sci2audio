"""The document's language: the job's setting, the file's own, or a guess from the text
(#219, D-494 to D-496).

The guess counts common function words (articles, pronouns, conjunctions, prepositions,
auxiliaries) of German and of English over the whole text. Whole documents fall far apart:
the English corpus has at most 1.1 % German ones among the two, twelve German papers at least
89.8 %. The first few hundred words alone would mislead, since German papers often open with
an English abstract, so every word counts. Offline, deterministic, no dependency (D-495).
"""

from __future__ import annotations

import re

from sci2audio.core import Content, LanguageGuess, LanguageSource
from sci2audio.layout.settings import LayoutSettings


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


# Function words of each language. Words common in both are in neither list ("in", "an",
# "so", "was", "will", "also", "man", "hat", "war", "um", "am", "as", "es"), so the lists
# never count one word for both languages.
COMMON_WORDS: dict[str, frozenset[str]] = {
    "de": _words(
        """
        der die das den dem des und ist sind nicht ein eine einer eines einem einen zu von
        mit sich auf für im als auch werden wird wurde wurden aus dass daß nach bei noch wie
        wir über zum zur oder nur durch sowie kann können sein ihre ihr diese dieser dieses
        diesem diesen zwischen unter ob wenn weil aber jedoch hier dabei daher somit sowohl
        beim vom bzw
        """
    ),
    "en": _words(
        """
        the of and to is are that for with this be by from which on it not or we can have
        has were been their these its at between such than into our they how what when
        where while however there would should may both each
        """
    ),
}
_WORD = re.compile(r"[^\W\d_]+")  # a run of letters


def guess_language(content: Content, settings: LayoutSettings | None = None) -> LanguageGuess:
    """What the content's text says about its language (D-495).

    German or English when there are at least `settings.language_words` common words of the
    two and one language's outnumber the other's `settings.language_ratio` to 1; otherwise
    "" (too little text, or mixed).
    """
    settings = settings or LayoutSettings()
    words = german = english = 0
    for page in content.pages:
        for line in page.lines:
            for word in _WORD.findall(line.text):
                lower = word.lower()
                words += 1
                german += lower in COMMON_WORDS["de"]
                english += lower in COMMON_WORDS["en"]
    language = ""
    if german + english >= settings.language_words:
        if german >= settings.language_ratio * english:
            language = "de"
        elif english >= settings.language_ratio * german:
            language = "en"
    return LanguageGuess(language, words, german, english)


def choose_language(
    content: Content, settings: LayoutSettings
) -> tuple[str, LanguageSource, LanguageGuess | None]:
    """The document's language, where it came from, and the guess if the text was looked at.

    The job's setting always wins and the text is not looked at. A language the file states
    wins too, unless it names English or German and the text clearly is the other one: then
    the text's language is read (D-496). With nothing stated, the guess decides, and English
    is read when the text does not tell.
    """
    if settings.language:
        return settings.language, LanguageSource.SETTING, None
    guess = guess_language(content, settings)
    stated = content.metadata.language
    if stated:
        primary = stated.split("-")[0].lower()
        if primary in COMMON_WORDS and guess.language and guess.language != primary:
            return guess.language, LanguageSource.TEXT, guess
        return stated, LanguageSource.FILE, guess
    if guess.language:
        return guess.language, LanguageSource.TEXT, guess
    return "en", LanguageSource.FALLBACK, guess
