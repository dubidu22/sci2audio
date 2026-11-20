"""Counterexample for the depth-floor mutant that survives on 260d5f3 (review #481 round 2).

Passes on 260d5f3; fails when `_inside` lets the depth go below zero (`depth -= 1`), because a
")" of an inline "a) … b)" list then cancels the next "(" and the cut falls inside the bracket.
Put it in tests/unit/test_textprep_utterances.py in that file's style (`cut` is the helper there).
"""
import pytest
from test_textprep_utterances import cut

EN = "the listeners heard every part of the recording in the quiet room and "
DE = "die Hörer hörten jeden Teil der Aufnahme im stillen Raum und "


@pytest.mark.parametrize(
    ("text", "language"),
    [
        (
            "We test a) the speed and b) the care with which " + EN * 2
            + "(as we saw in the first study, which " + EN + "of the long run) " + EN + "it ended.",
            "en",
        ),
        (
            "Wir prüfen a) das Tempo und b) die Sorgfalt, mit der " + DE * 2
            + "(wie die erste Studie, die " + DE + "zeigte) " + DE * 2 + "und es endete.",
            "de",
        ),
    ],
)
def test_a_closing_mark_of_an_inline_list_does_not_open_a_bracket_for_cutting(
    text: str, language: str
) -> None:
    for part in cut(text, language=language):
        # no part ends inside the bracket: its last "(" is closed within the part
        assert part.rfind("(") < part.rfind(")") or "(" not in part
