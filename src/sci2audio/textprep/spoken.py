"""What the voice says for a stretch of the listening script.

Line breaks inside a block are where the printed lines ended, not something to hear: they
are read as spaces here, not changed by an edit (Q4). Every run of white space becomes one
space and the ends are trimmed. The text in the script itself stays as it is, so read-along
still points at the original characters.

`unspoken` tells a stretch with nothing in it for a voice to say: no letter, digit or symbol
with a reading, only white space, dashes, brackets, quote marks, sentence punctuation and list
bullets (#652). The utterance cutter never makes such a stretch an utterance of its own.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from sci2audio.core import ScriptPiece

PAUSE_MARK = "[pause]"  # how a pause shows in a rendered script; never spoken

_WHITE_SPACE = re.compile(r"\s+")


def spoken_text(pieces: Iterable[ScriptPiece], *, show_pauses: bool = False) -> str:
    """The text the voice reads for these pieces, white space as single spaces.

    With `show_pauses`, each pause shows as PAUSE_MARK (for reports and regression cases).
    """
    parts = []
    for piece in pieces:
        if piece.pause:
            if show_pauses:
                parts.append(f" {PAUSE_MARK} ")
        else:
            parts.append(piece.text)
    return _WHITE_SPACE.sub(" ", "".join(parts)).strip()


# dashes (Pd), brackets (Ps, Pe), quote marks (Pi, Pf) and invisible format characters (Cf):
# printed, never said
_UNSPOKEN_CATEGORIES = frozenset({"Pd", "Ps", "Pe", "Pi", "Pf", "Cf"})
# other punctuation that says nothing on its own: sentence marks, straight quotes, the ellipsis
# and the list bullets; "*", "/", "%", "&", "§" and the like have a reading and are not here
_UNSPOKEN_MARKS = frozenset(
    ".,:;!?\u00a1\u00bf\"'\u2026"
    "\u00b7\u2022\u2023\u2043\u2027\u2219"  # middle dot, bullet, triangular and hyphen bullet
    "\u25aa\u25ab\u25a0\u25a1\u25cf\u25cb\u25e6\u25c6\u25c7\u25b8\u25ba\u25b6"  # shapes
)


def unspoken(text: str) -> bool:
    """True if `text` holds nothing a voice says: only white space, dashes, brackets, quote
    marks, sentence punctuation and list bullets (#652). Empty text is unspoken."""
    return all(
        char.isspace()
        or char in _UNSPOKEN_MARKS
        or unicodedata.category(char) in _UNSPOKEN_CATEGORIES
        for char in text
    )
