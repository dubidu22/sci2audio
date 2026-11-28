"""Recognise the letters of a font with no Unicode source from its glyphs' shapes (#618).

Such a font gives only glyph numbers (#442). For the usual Office fonts, open fonts with the
same advance widths exist: Tinos, Arimo, Cousine, Caladea and Carlito, the twins of Times
New Roman, Arial, Courier New, Cambria and Calibri. Their letters are drawn on the em grid
of `extraction.glyphs` once, by `scripts/letter_shapes.py` (`data/letter-shapes.json.gz`),
and a document's glyphs are drawn the same way and compared (D-789):

1. Identity: the PDF's width of each glyph must be the program's own advance of the glyph
   with that number; otherwise the codes are not glyph numbers (a /CIDToGIDMap stream) and
   the shapes drawn would not be the ones printed.
2. Family and style: the reference style in which most glyphs find a letter of their width;
   among styles close to the best by that count, the one whose letters lie nearest.
3. Letters: each glyph's candidates are the style's letters of its width (or, where
   the PDF shows only how wide it is at most, no wider); the nearest
   drawing wins, one letter per glyph (glyphs taken in order of how near their letter is).
   Two drawings are compared as the share of ink that would have to move: each is blurred
   by a cell and scaled to the same total ink, so a twin's slightly other serifs and
   stroke weight cost little, while a mark, a crossbar or a place on the em costs much.
4. Close calls: where another letter, or the swap of two glyphs' letters, lies about as
   near as the best (`_margin`: a twin's drawing differs from the original's by about its
   own distance), the readings that use only letters English and German text uses
   (`COMMON_LETTERS`) are kept; if more than one is left, they are tried on the font's
   words and the one that makes clearly more common English and German words (or numbers)
   wins (`COMMON_WORDS`). A close call left unsettled leaves its glyphs unrecognised.
5. Refusal: a font is recognised only when enough of its glyphs' occurrences are
   recognised, closely enough; otherwise None, and the text stays as today (AC-442.6).

Whether the pages then read as text is the caller's check (`legibility`). The thresholds
were measured on Times New Roman, Arial and Courier New against their twins
(`scripts/letter_shapes.py measure`); the margins are in docs/unreadable-pdf-text.md.
"""

from __future__ import annotations

import functools
import gzip
import itertools
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from importlib import resources
from typing import cast

import numpy as np

from sci2audio.extraction import glyphs

WIDTH_TOLERANCE = 1.0  # 1/1000 em: a PDF's widths are whole thousandths
IDENTITY_SHARE = 0.95  # of the glyphs with an advance of their own, this many must agree
IDENTITY_MIN = 8  # and at least this many (or all the font uses) are compared
IDENTITY_WIDTHS = 3  # different widths among the agreeing glyphs: one width shows nothing
FAMILY_SHARE = 0.9  # of the drawn glyphs, this many must have a letter of their width
# Distances (0 the same drawing, 1 no ink in common), measured with
# `scripts/letter_shapes.py measure` on the 89 letters, digits and marks of English and
# German text (24 Nov 2026): a Times New Roman or Arial letter lies on average 0.07 to 0.17
# from its twin's (italic the most), at most 0.42 (Times italic quotes); the nearest other
# letter of the same width lies within 0.05 of the right one for 5 to 30 of the 89.
GLYPH_DISTANCE = 0.35  # a glyph's letter lies at most this far from its drawing
FONT_SHARE = 0.95  # of the drawn glyphs' occurrences, this many must be recognised
FONT_DISTANCE = 0.2  # mean distance of the recognised occurrences, at most
# A reading is a close call when it lies within CLOSE_SHARE of the best reading's distance
# of it, and within CLOSE_FLOOR at least. Set on whole texts in Times New Roman, Arial and
# Courier New, every style: at 0.5 no letter came out wrong; at 0.35 Arial Bold's "l" read
# as "I"; larger shares only refused more (docs/unreadable-pdf-text.md).
CLOSE_SHARE = 0.5
CLOSE_FLOOR = 0.01
_BLUR = 1.0  # cells: the spread of the blur before drawings are compared
WORD_MARGIN = 2  # the winning reading makes at least this many more common words
MAX_LETTERS = 6  # letters a close call chooses among; more stays unsettled
MAX_WORD_CHECKS = 2000  # words (the most frequent) a close call is tried on, a glyph
STYLE_SAMPLE = 64  # glyphs (the most used) that choose between close styles

# Common words of English and German (case-folded), for close calls between letters of the
# same width: a closed list written for this purpose, not taken from any text.
_WORDS = """
a about after again all also an and any are as at be because been before being both but
by can could did do does each even first for from had has have he her here him his how i
if in into is it its just like made make many may more most much must my new no not now
of on once one only or other our out over own people same see she should since so some
such than that the their them then there these they this those through time to too two
under up use used very was way we well were what when where which while who why will with
would year you your center centre case cases science second effect effects rather place
example evidence experience except excellent face fact force less level line science sense
aber alle allem allen aller alles als also am an auch auf aus bei beim bereits bis da
dabei damit dann das dass dem den denen denn der des deshalb die dies diese diesem diesen
dieser dieses doch dort durch ein eine einem einen einer eines er es etwa für gegen hat
haben hier ich ihr ihre im immer in ist jedoch jetzt kann kein keine man mehr mit muss
nach neben nicht noch nun nur ob oder ohne sehr sein seine seiner selbst sich sie sind so
sowie über um und uns unter vom von vor war waren was weil welche welcher wenn wer werden
wie wieder wird wir wurde wurden zu zum zur zwischen recht leben menschen arbeit gemeinwesen
groß große großen größer daß muß weiß heißt außer außerdem schließlich bloß maß straße
"""
COMMON_WORDS = frozenset(_WORDS.split())
# The letters, digits and marks English and German text uses; in a close call, a reading
# that needs another letter (an "Å" for an "Ä") gives way to one that does not.
COMMON_LETTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    "\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df"
    ".,;:-()[]/!?'\"%&+=*@#\u00a7\u20ac"
    "\u2013\u2014\u2026\u2022\u201e\u201c\u201d\u201a\u2018\u2019"
)


@dataclass(frozen=True)
class Style:
    """One reference style: its letters, their advances (1/1000 em) and drawings, made
    ready to compare (`prepare`)."""

    name: str  # "Tinos Regular"
    letters: str
    widths: np.ndarray  # float, one a letter
    shapes: np.ndarray  # float, letters x cells


@functools.cache
def references() -> tuple[Style, ...]:
    """The reference styles, loaded once, and only when a font needs recognising: nothing
    loads them for a file without fonts with no Unicode source (AC-442.10)."""
    data = resources.files("sci2audio.extraction").joinpath("data/letter-shapes.json.gz")
    document = json.loads(gzip.decompress(data.read_bytes()))
    grid = [glyphs.COLUMNS, glyphs.ROWS, glyphs.LEFT, glyphs.RIGHT, glyphs.TOP, glyphs.BOTTOM]
    if document["grid"] != grid:  # drawn on another grid: comparing would be meaningless
        return ()
    cells = glyphs.COLUMNS * glyphs.ROWS
    found = []
    for style in document["styles"]:
        letters = style["letters"]
        drawn = np.frombuffer(bytes.fromhex("".join("0" + c for c in style["shapes"])), np.uint8)
        widths = 1000 * np.asarray(style["advances"], float) / style["units"]
        shapes = prepare(drawn.reshape(len(letters), cells))
        found.append(Style(style["name"], letters, widths, shapes))
    return tuple(found)


def _kernel() -> np.ndarray:
    steps = np.arange(-3, 4)
    kernel = np.exp(-(steps**2) / (2 * _BLUR**2))
    return kernel / kernel.sum()


_KERNEL = _kernel()


def prepare(pictures: np.ndarray) -> np.ndarray:
    """Drawings (`glyphs.draw`, one a row) blurred by `_BLUR` cells and each scaled to a
    total ink of 1, ready for `distances`; a drawing without ink stays all 0."""
    rows, columns = glyphs.ROWS, glyphs.COLUMNS
    found = pictures.reshape(-1, rows, columns).astype(np.float32)
    reach = len(_KERNEL) // 2
    padded = np.pad(found, ((0, 0), (reach, reach), (reach, reach)))
    # sum() of arrays is an array, which its stub cannot tell from its int start
    across = cast(
        "np.ndarray", sum(w * padded[:, :, k : k + columns] for k, w in enumerate(_KERNEL))
    )
    blurred = cast("np.ndarray", sum(w * across[:, k : k + rows, :] for k, w in enumerate(_KERNEL)))
    flat = blurred.reshape(len(found), rows * columns)
    total = flat.sum(axis=1, keepdims=True)
    return flat / np.where(total > 0, total, 1)


def distances(prepared: np.ndarray, shapes: np.ndarray) -> np.ndarray:
    """How far one prepared drawing lies from each of `shapes`: the share of its ink that
    lies elsewhere, 0 for the same drawing, 1 for drawings that share no ink."""
    return 0.5 * np.abs(shapes - prepared).sum(axis=1)


@dataclass
class Usage:
    """What a document uses of one font: its program, how often each glyph stands, the
    width the PDF gives each (1/1000 em) and its words as glyph numbers."""

    font: glyphs.Font
    counts: Counter[int] = field(default_factory=Counter)
    widths: dict[int, float] = field(default_factory=dict)
    limits: dict[int, float] = field(default_factory=dict)  # widths known only as at most
    words: Counter[tuple[int, ...]] = field(default_factory=Counter)


def recognise(usage: Usage, budget: glyphs.Budget | None = None) -> dict[int, str] | None:
    """Each glyph's letter (" " for a glyph without ink), or None when the font is refused:
    its codes are not shown to be glyph numbers, no reference style fits, the read's
    `budget` ran out on it, or too few of its glyphs' occurrences are recognised, closely
    enough. A glyph left out matched no letter, or its close call was not settled. What
    costs nothing is checked first: the widths come before any glyph is drawn."""
    budget = glyphs.Budget() if budget is None else budget
    font = usage.font
    if not _identity(usage):
        return None
    inked = [g for g in sorted(usage.counts) if font.inked(g)]
    empty = [g for g in sorted(usage.counts) if g not in set(inked)]
    widths = {g: w for g in inked if (w := _width(usage, g)) is not None}
    limits = {g: usage.limits[g] for g in inked if g not in widths and g in usage.limits}
    close = _fitting(widths, len(inked))
    if not close:
        return None
    pictures: dict[int, np.ndarray] = {}
    unreadable = 0
    for glyph in inked:
        outline = font.outline(glyph, budget)
        if budget.spent:
            return None  # the read's budget ran out on this font: today's text
        if outline:
            pictures[glyph] = glyphs.draw(outline, font.units)
        else:
            unreadable += usage.counts[glyph]
    if not pictures:
        return None
    drawn = dict(zip(pictures, prepare(np.stack(list(pictures.values()))), strict=True))
    style = _nearest(close, drawn, widths, usage.counts)
    order = list(drawn)
    table = np.full((len(order), len(style.letters)), np.inf)
    for row, glyph in enumerate(order):
        if glyph in widths:
            fits = np.abs(style.widths - widths[glyph]) <= WIDTH_TOLERANCE
        elif glyph in limits:
            fits = style.widths <= limits[glyph] + WIDTH_TOLERANCE
        else:
            continue
        table[row, fits] = distances(drawn[glyph], style.shapes[fits])
    settled = _close_calls(table, _assign(table), order, style.letters, usage.words, budget)
    total = sum(usage.counts[g] for g in order) + unreadable
    recognised = sum(usage.counts[order[row]] for row in settled)
    if not recognised or recognised / total < FONT_SHARE:
        return None
    mean = sum(usage.counts[order[r]] * table[r, c] for r, c in settled.items()) / recognised
    if mean > FONT_DISTANCE:
        return None
    letters = {order[row]: style.letters[column] for row, column in settled.items()}
    letters.update(dict.fromkeys(empty, " "))
    return letters


def _width(usage: Usage, glyph: int) -> float | None:
    """The glyph's width in 1/1000 em: as the PDF gives it, else the program's own."""
    if glyph in usage.widths:
        return usage.widths[glyph]
    advance = usage.font.advance(glyph)
    return None if advance is None else 1000 * advance / usage.font.units


def _identity(usage: Usage) -> bool:
    """True if the codes are shown to be the program's glyph numbers: the PDF's width of
    each glyph agrees with the program's own advance of the glyph of that number, and the
    agreeing glyphs have at least `IDENTITY_WIDTHS` different widths. Where every glyph is
    as wide (a monospaced font), a /CIDToGIDMap stream that shuffles the codes agrees just
    as well, so nothing is shown and the font is refused."""
    font = usage.font
    compared = agreeing = 0
    kinds: set[int] = set()  # the agreeing glyphs' widths
    for glyph, width in usage.widths.items():
        advance = font.advance(glyph)
        if advance is None:
            continue
        compared += 1
        if abs(1000 * advance / font.units - width) <= WIDTH_TOLERANCE:
            agreeing += 1
            kinds.add(round(width))
    if not compared or compared < min(IDENTITY_MIN, len(usage.counts)):
        return False
    return agreeing / compared >= IDENTITY_SHARE and len(kinds) >= IDENTITY_WIDTHS


def _fitting(widths: dict[int, float], inked: int) -> list[Style]:
    """The reference styles close to the one in which most glyphs find a letter of their
    width, by widths alone; none if that one fits fewer than `FAMILY_SHARE` of the `inked`
    glyphs."""
    styles = references()
    wanted = np.fromiter(widths.values(), float, len(widths))
    fitting = [
        int((np.abs(wanted[:, None] - style.widths[None, :]) <= WIDTH_TOLERANCE).any(axis=1).sum())
        for style in styles
    ]
    best = max(fitting, default=0)
    if best == 0 or best < FAMILY_SHARE * inked:
        return []
    return [s for s, fits in zip(styles, fitting, strict=True) if fits >= FAMILY_SHARE * best]


def _nearest(
    close: list[Style], drawn: dict[int, np.ndarray], widths: dict[int, float], counts: Counter[int]
) -> Style:
    """Of the `close` styles, the one whose letters lie nearest the most used glyphs."""
    sample = [g for g in sorted(widths, key=lambda g: (-counts[g], g)) if g in drawn]
    sample = sample[:STYLE_SAMPLE]

    def nearness(style: Style) -> float:
        found = []
        for glyph in sample:
            fits = np.abs(style.widths - widths[glyph]) <= WIDTH_TOLERANCE
            found.append(distances(drawn[glyph], style.shapes[fits]).min() if fits.any() else 1.0)
        return float(np.mean(found)) if found else 1.0

    return min(close, key=nearness)


def _assign(table: np.ndarray) -> dict[int, int]:
    """One letter per glyph (row to column), nearest pairs first, each within
    `GLYPH_DISTANCE`."""
    rows, columns = np.nonzero(table <= GLYPH_DISTANCE)
    pairs = sorted(zip(table[rows, columns].tolist(), rows.tolist(), columns.tolist(), strict=True))
    chosen: dict[int, int] = {}
    taken: set[int] = set()
    for _, row, column in pairs:
        if row not in chosen and column not in taken:
            chosen[row] = column
            taken.add(column)
    return chosen


def _close_calls(
    table: np.ndarray,
    chosen: dict[int, int],
    order: list[int],
    letters: str,
    words: Counter[tuple[int, ...]],
    budget: glyphs.Budget,
) -> dict[int, int]:
    """The assignment with its close calls settled, glyph by glyph, the most used first:
    for each glyph whose letter has rivals (`_readings`), the readings that use the most
    common letters are kept, and of those the one the words prefer wins (`_by_words`). The
    glyphs of a close call left unsettled are left out, and so are those of every close
    call once the `budget`'s steps are spent: each reading tried and each letter looked up
    in a word costs one."""
    by_glyph: dict[int, list[tuple[int, ...]]] = {}
    for word, _ in words.most_common():
        for glyph in set(word):
            found = by_glyph.setdefault(glyph, [])
            if len(found) < MAX_WORD_CHECKS:
                found.append(word)
    settled = dict(chosen)
    owner = {column: row for row, column in settled.items()}
    common = np.array([c in COMMON_LETTERS for c in letters])
    unsure: set[int] = set()
    used = Counter({row: sum(words[w] for w in by_glyph.get(order[row], ())) for row in chosen})
    for row in sorted(chosen, key=lambda r: (-used[r], r)):
        involved, readings = _readings(table, row, settled, owner, common, budget)
        if readings is not None and len(readings) > 1:
            counts = [int(common[list(r.values())].sum()) for r in readings]
            readings = [r for r, n in zip(readings, counts, strict=True) if n == max(counts)]
        if readings is not None and len(readings) > 1:
            checked = {w for r in involved for w in by_glyph.get(order[r], ())}
            tried = {w: words[w] for w in checked}
            found = _by_words(readings, settled, order, letters, tried, budget)
            readings = None if found is None else [found]
        if readings is None:
            unsure.update(involved)
            continue
        for r, column in readings[0].items():
            settled[r] = column
            owner[column] = r
    return {row: column for row, column in settled.items() if row not in unsure}


def _readings(
    table: np.ndarray,
    row: int,
    settled: dict[int, int],
    owner: dict[int, int],
    common: np.ndarray,
    budget: glyphs.Budget,
) -> tuple[list[int], list[dict[int, int]] | None]:
    """The glyphs of the glyph's close call and their readings. Its rivals are the letters
    about as near it as its own (`_margin`; where its own is a common letter, the common
    ones only: another could not win); the close call holds it and the glyphs that have
    those letters. A reading gives them distinct letters among their own and the rivals,
    each within `GLYPH_DISTANCE`, its sum within `_margin` of the best. Just the present
    reading where there is no rival; None where there are more than `MAX_LETTERS` letters
    to try, or the budget has not the steps to try them."""
    own = table[row, settled[row]]
    near = (table[row] < own + _margin(own)) & (table[row] <= GLYPH_DISTANCE)
    if common[settled[row]]:
        near &= common
    near[settled[row]] = True
    rivals = np.flatnonzero(near).tolist()
    if len(rivals) == 1:
        return [row], [{row: settled[row]}]
    involved = sorted({row} | {owner[c] for c in rivals if c in owner})
    columns = sorted(set(rivals) | {settled[r] for r in involved})
    if len(columns) > MAX_LETTERS or not budget.step(math.perm(len(columns), len(involved))):
        return involved, None
    found = []
    for pick in itertools.permutations(columns, len(involved)):
        costs = [table[r, c] for r, c in zip(involved, pick, strict=True)]
        if max(costs) <= GLYPH_DISTANCE:
            found.append((float(sum(costs)), dict(zip(involved, pick, strict=True))))
    best = min(cost for cost, _ in found)  # the present reading is always among them
    return involved, [reading for cost, reading in found if cost < best + _margin(best)]


def _margin(distance: float) -> float:
    """How much farther than `distance` a reading may lie and still be a close call: a
    twin's drawing lies about its own distance from the original's, so a reading within
    half of it could be the right one."""
    return max(CLOSE_FLOOR, CLOSE_SHARE * distance)


def _by_words(
    readings: list[dict[int, int]],
    settled: dict[int, int],
    order: list[int],
    letters: str,
    words: dict[tuple[int, ...], int],
    budget: glyphs.Budget,
) -> dict[int, int] | None:
    """The reading that makes at least `WORD_MARGIN` more common words (or numbers) than
    any other, or None, also when the budget has not the steps to try them all. A word with
    a glyph not recognised counts for none."""
    if not budget.step(len(readings) * sum(len(word) for word in words)):
        return None
    rows = {glyph: row for row, glyph in enumerate(order)}
    scores = []
    for reading in readings:
        assigned = {**settled, **reading}
        score = 0
        for word, count in words.items():
            found = [assigned.get(rows.get(glyph, -1)) for glyph in word]
            known = [c for c in found if c is not None]
            if len(known) == len(found):
                score += count * _known("".join(letters[c] for c in known))
        scores.append(score)
    ranked = sorted(range(len(readings)), key=lambda k: -scores[k])
    if scores[ranked[0]] - scores[ranked[1]] < WORD_MARGIN:
        return None
    return readings[ranked[0]]


_NUMBER = re.compile(r"\d+(?:[.,:/-]\d+)*")


def _known(text: str) -> bool:
    """True for a common word or a number, with the punctuation around it left out."""
    start, end = 0, len(text)
    while start < end and not text[start].isalnum():
        start += 1
    while end > start and not text[end - 1].isalnum():
        end -= 1
    word = text[start:end]
    return word.casefold() in COMMON_WORDS or bool(_NUMBER.fullmatch(word))
