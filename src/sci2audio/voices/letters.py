"""Spelled abbreviations at the listener's pace (#295, D-554).

Both voices spell an all-capitals word they don't know ("NLP", "LSTM") as one quick word:
the English voice at 6 to 7 letters a second, faster than its ordinary syllables (4.9 a
second). The synthesis parameter `letter_speed` (1.0 = as today) slows only the sounds of
those spelled letters: Kokoro predicts a length for every sound and divides it by the speed,
so the speed is given per sound, and the rest of the sentence keeps its pace and melody.

This module finds which sounds those are; it imports neither torch nor kokoro at import
time.

- English (misaki): a token of two or more capital letters, maybe with a plural or
  possessive "s" ("GPUs", "BERT's"), whose sounds are misaki's own spelling of its letters
  (`lexicon.get_NNP`), stress marks aside. Words misaki says as words ("NASA") are left
  alone.
- German (espeak-ng): a word of two or more capital letters whose sounds, said alone, are
  those of its letters said one by one ("BERT" is said "Bert" and left alone). Its sounds
  are then found in the sentence's sounds, between word boundaries; where espeak-ng said
  them otherwise in the sentence, the word keeps the voice's pace.

Mixed case ("RoBERTa"), single letters, dotted forms ("i.i.d.") and letters with digits
("GPT-4") are not slowed.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from sci2audio.voices.errors import InvalidInputError

LETTER_SPEED_MIN = 0.25
LETTER_SPEED_MAX = 1.0

# two or more letters, all capitals, maybe a plural or possessive "s"
_CAPITALS = re.compile(r"\A([^\W\d_]{2,}?)(s|['\u2019]s)?\Z")
# what does not count when sounds are compared: stress, length, white space, punctuation
_MARKS = re.compile(r"[\u02c8\u02cc\u02d0\s.,;:!?\u2026\u2014\u2013\-'\"()\u201c\u201d]")
# a word boundary in espeak-ng's sounds: start, end, white space or punctuation
_EDGE_CHARS = " \t\n.,;:!?\u2026\u2014\u2013-'\"()\u201c\u201d"
_EDGE = "".join(re.escape(char) for char in _EDGE_CHARS)
# a plural or possessive ending adds at most two sounds (a "z" or "s", maybe a vowel)
_ENDING = 2


def letter_speed(value: Any) -> float:
    """The `letter_speed` parameter as a number, or InvalidInputError."""
    if isinstance(value, bool):
        raise InvalidInputError(f"letter_speed must be a number, got {value!r}")
    try:
        speed = float(value)
    except (TypeError, ValueError):
        raise InvalidInputError(f"letter_speed must be a number, got {value!r}") from None
    if not math.isfinite(speed) or not LETTER_SPEED_MIN <= speed <= LETTER_SPEED_MAX:
        raise InvalidInputError(
            f"letter_speed must be between {LETTER_SPEED_MIN} and {LETTER_SPEED_MAX}, got {value}"
        )
    return speed


def capitals(word: str) -> str | None:
    """The letters of an all-capitals word ("GPUs" → "GPU"), else None."""
    match = _CAPITALS.match(word)
    if match is None or not match.group(1).isupper():
        return None
    return match.group(1)


def _plain(sounds: str) -> str:
    return _MARKS.sub("", sounds)


def is_spelled(said: str, letters: str | None) -> bool:
    """True if `said` is `letters` (the word's letters said one by one), stress and
    punctuation aside, maybe with a plural or possessive ending."""
    if not letters:
        return False
    plain, spelled = _plain(said), _plain(letters)
    return bool(spelled) and plain.startswith(spelled) and len(plain) - len(spelled) <= _ENDING


def english_spans(
    tokens: Sequence[Any], spell: Callable[[str], str | None]
) -> list[tuple[int, int]]:
    """Where in kokoro's sounds of `tokens` (`KPipeline.tokens_to_ps`) the voice spells
    letters; `spell(letters)` is misaki's spelling of a word's letters. Each token needs
    `text`, `phonemes` and `whitespace`, as misaki's tokens have them."""
    raw = ""
    found: list[tuple[int, int]] = []
    for token in tokens:
        sounds = token.phonemes or ""
        letters = capitals(token.text)
        if letters is not None and sounds and is_spelled(sounds, spell(letters)):
            found.append((len(raw), len(raw) + len(sounds)))
        raw += sounds + (" " if token.whitespace else "")
    shift = len(raw) - len(raw.lstrip())  # tokens_to_ps strips the joined sounds
    return [(start - shift, stop - shift) for start, stop in found]


def german_spans(text: str, sounds: str, phonemize: Callable[[str], str]) -> list[tuple[int, int]]:
    """Where in `sounds` (part of the sounds of `text`) the voice spells letters;
    `phonemize` gives the voice's sounds of any text."""
    forms: set[str] = set()
    for word in set(re.findall(r"[^\W\d_]+(?:['\u2019]s)?", text)):
        letters = capitals(word)
        if letters is None:
            continue
        alone = phonemize(word).strip(_EDGE_CHARS)
        if alone and is_spelled(alone, phonemize(" ".join(letters))):
            forms.add(alone)
    found: list[tuple[int, int]] = []
    for form in sorted(forms, key=len, reverse=True):
        pattern = re.compile(rf"(?<![^{_EDGE}]){re.escape(form)}(?![^{_EDGE}])")
        for match in pattern.finditer(sounds):
            span = match.span()
            if not any(start < span[1] and span[0] < stop for start, stop in found):
                found.append(span)
    return sorted(found)


def per_sound(
    sounds: str,
    vocab: Mapping[str, int],
    spans: Iterable[tuple[int, int]],
    speed: float,
    factor: float,
) -> list[float]:
    """The speed of every sound kokoro speaks for `sounds`: the sounds it knows (as
    `KModel.forward` filters them), between its two padding tokens; `speed * factor` inside
    `spans`, `speed` elsewhere."""
    inside = [False] * len(sounds)
    for start, stop in spans:
        for index in range(max(start, 0), min(stop, len(sounds))):
            inside[index] = True
    known = [
        speed * factor if slow else speed
        for sound, slow in zip(sounds, inside, strict=True)
        if vocab.get(sound) is not None
    ]
    return [speed, *known, speed]


def speed_tensor(values: Sequence[float], device: Any) -> Any:
    """`per_sound` as the tensor kokoro's `KModel` divides its sound lengths by."""
    import torch

    return torch.tensor([list(values)], dtype=torch.float32, device=device)
