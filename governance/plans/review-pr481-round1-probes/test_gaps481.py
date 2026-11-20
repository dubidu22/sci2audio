"""Counterexamples for the cut mutants that survive on e591e93 (review #481 round 1).

Each passes on e591e93 and fails on its mutant. Put them in tests/unit/test_textprep_utterances.py
in that file's style; `cut` and `MIN_PIECE` are the helpers already imported there.
"""
from test_textprep_utterances import cut
from sci2audio.textprep.utterances import MIN_PIECE


def test_a_semicolon_that_leaves_a_clipped_last_part_is_not_taken() -> None:
    # mutant 8: the fair filter checks only the first part
    text = "w " * 80 + "b, " + "c " * 62 + "d; " + "e " * 8 + "f."  # 308 characters
    parts = cut(text)
    assert parts[0].endswith("b,")
    assert all(len(part) >= MIN_PIECE for part in parts)


def test_three_parts_share_the_whole_sentence_evenly() -> None:
    # mutant 11: the even share is taken over the window, not over what is left of the sentence
    parts = cut(" ".join(["word"] * 140) + ".")  # 700 characters, no clause mark
    assert len(parts) == 3
    assert max(map(len, parts)) - min(map(len, parts)) <= 10
