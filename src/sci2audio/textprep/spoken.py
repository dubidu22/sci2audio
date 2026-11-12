"""What the voice says for a stretch of the listening script.

Line breaks inside a block are where the printed lines ended, not something to hear: they
are read as spaces here, not changed by an edit (Q4). Every run of white space becomes one
space and the ends are trimmed. The text in the script itself stays as it is, so read-along
still points at the original characters.
"""

from __future__ import annotations

import re
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
