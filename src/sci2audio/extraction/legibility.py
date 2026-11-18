"""How readable each page's text is, measured, for the app to decide on (#442, #187).

A PDF can hold text that reads as nonsense: a font with no Unicode source gives its glyph
numbers as characters (`Page.unmapped`), and other broken fonts give wrong letters that no
font check sees. `legibility` measures each page three ways and says which pages are
unreadable; extraction still decides nothing (D-63): stopping a job or warning about pages
is the app's call (#442 part B). The measures and their limits are in
docs/unreadable-pdf-text.md, with the corpus margins they were set from (D-762).

- Glyph numbers: the share of the page's characters that come from fonts with no Unicode
  source.
- Letter pairs: the share of letter pairs inside words that English and German words never
  hold (`RARE_PAIRS`). A TrueType font in the usual glyph order without a Unicode source
  reads "Das Buch" as "'DV %XFK": plain ASCII, so no script check sees it, but "n" becomes
  "q", and "q" before anything but "u" is rare in both languages.
- Foreign letters: the share of letters outside the scripts English and German text and
  its formulas use (Basic Latin, Latin-1, Latin Extended-A, Greek), with U+FFFD and
  private-use characters, as a font's glyph numbers far from Unicode give ("ĞŵĞŝŶ" for
  "Gemein").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sci2audio.core import Content, Page

UNMAPPED_SHARE = 0.5  # more than this share of a page's characters from such fonts
# Letter pairs: at least MIN_PAIRS on the page, and at least RARE_SHARE of them rare. The
# corpus's pages hold at most 0.93 % rare pairs, the same pages read through a font's glyph
# numbers at least 12.7 % (leave-one-out over the corpus, 18 Nov 2026).
MIN_PAIRS = 100
RARE_SHARE = 0.05
# Foreign letters: at least MIN_LETTERS on the page, and at least FOREIGN_SHARE of them
# foreign. The corpus's pages hold at most 1.5 % (Greek in formulas counts as at home).
MIN_LETTERS = 50
FOREIGN_SHARE = 0.2

# Letter pairs (case-folded) that no page of the corpus holds, in English or German, and
# that cannot form where two words of a German compound meet: the first letter is j, q, v,
# w or x, or the second is q or x. Found by counting every pair in the corpus (8 papers, the
# EPUB, the Markdown and text samples) and one German paper used only to measure; "xy" is
# left out ("oxygen", "Hexyl"). A list of pairs, not text.
_PAIRS = (
    "bq bx cx dq dx fx gq gx hq hx jb jd jg jq jr jv jx kq kx lq lx mx pq px qb qc qd qe qg"
    " qh qj qk ql qm qo qp qq qr qt qv qw qz sx uq vb vc vd vh vj vn vq vv vw vx vz wj wq"
    " wx wz xb xd xg xk xl xn xr xv xw xx xz zq zx"
)
RARE_PAIRS = frozenset(_PAIRS.split())
_WORD = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class PageLegibility:
    """One page's measures; `unreadable` says whether any of them is past its limit."""

    number: int  # the `Page.number`
    characters: int  # in the page's lines, white space not counted
    unmapped: int  # of those, from fonts with no Unicode source (`Page.unmapped`)
    pairs: int  # letter pairs inside words, case-folded, a to z
    rare: int  # of those, in RARE_PAIRS
    letters: int  # letters, U+FFFD and private-use characters
    foreign: int  # of those, outside the scripts named above, or U+FFFD, or private use

    @property
    def unreadable(self) -> bool:
        """True if the page's text is mostly glyph numbers, or reads like them."""
        if self.characters and self.unmapped / self.characters > UNMAPPED_SHARE:
            return True
        if self.pairs >= MIN_PAIRS and self.rare / self.pairs >= RARE_SHARE:
            return True
        return self.letters >= MIN_LETTERS and self.foreign / self.letters >= FOREIGN_SHARE


def legibility(content: Content) -> tuple[PageLegibility, ...]:
    """Each page's measures, in page order. Never fails: any content can be measured."""
    return tuple(_page(page) for page in content.pages)


def _page(page: Page) -> PageLegibility:
    pairs = rare = letters = foreign = 0
    for line in page.lines:
        text = line.text
        for word in _WORD.findall(text.casefold()):
            pairs += len(word) - 1
            rare += sum(word[i : i + 2] in RARE_PAIRS for i in range(len(word) - 1))
        for char in text:
            if char.isalpha() or _broken(char):
                letters += 1
                foreign += not _at_home(char)
    return PageLegibility(
        page.number, page.characters, page.unmapped, pairs, rare, letters, foreign
    )


def _broken(char: str) -> bool:
    """U+FFFD (a glyph PDFium could not map) or a private-use character."""
    return char == "�" or unicodedata.category(char) == "Co"


def _at_home(char: str) -> bool:
    """A letter of Basic Latin, Latin-1, Latin Extended-A or Greek."""
    code = ord(char)
    return char.isalpha() and (code < 0x180 or 0x370 <= code < 0x400)
