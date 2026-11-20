# Answer to the review of PR #647, round 1

Fix head **29fbfbc** (one fix commit) on top of merge commit b4bc615, which merges main fac140c. The CHANGELOG conflict with #645 is resolved by keeping both "Fixed" lines. No golden file changed: the fast suite is green with no snapshot update (8237 passed).

The new tests are in `tests/unit/test_layout_paragraphs.py`. They call `rows_of` directly through a helper `_printed`, using pieces whose runs have no boxes and body size 10. That makes `fraction_inside` exactly 1 pt, and every coordinate is exact in binary.

| Item | What was done | Mutant(s) |
|---|---|---|
| T1 | `test_a_piece_in_another_column_under_a_bar_is_no_denominator`: same geometry as T4, but the piece under the bar is in the other column, so it stays a line of its own. | den_3 killed |
| T2 | `test_marks_are_neither_numerators_nor_denominators`: `_denominator([mark], piece, …)` and `_denominator([piece], mark, …)` are False and do not fail. Reason it is unreachable through `rows_of`: `rows_of` calls `_denominator` only in its `elif` branch, so `element.line` is set, and only when `latest is not None`, so `found[-1][-1]` is text and `texts` is not empty. | den_4 killed |
| T3 | `test_a_bar_whose_middle_is_on_the_line_s_bottom_edge_is_not_inside_it`: a bar with its middle exactly on 107, the line's bottom edge, is not joined; 0.25 pt higher it is joined. The top edge cannot be reached, as the test's docstring explains. Every piece's letters lie inside the line: `_letter_boxes` uses the piece's runs, and the line is the union of the pieces. So any upper's letter middles are below the line's top edge, and `fraction_bar` refuses a bar whose middle is on that edge whatever `_denominator` decides. | den_21 killed; den_17 equivalent |
| T4 | `test_a_line_of_one_fraction_reads_its_numerator_first`: a printed line of exactly two pieces, with the denominator 1 pt further left, reads the numerator first. Without the bar, the two pieces are two lines. | fio_13 killed |
| T5 | `test_a_denominator_at_the_start_of_its_line_follows_its_numerator`: the denominator is the leftmost piece and its numerator is not the last piece; the line reads "me", "m*", "is the mass". | fio_21 killed |
| T6 | `test_a_denominator_cut_in_two_pieces_reads_its_numerator_once`: in "x = a over 12", the denominator is extracted as two pieces, "1" and "2", both left of "a". The line reads "x =", "a", "1", "2". A nested fraction cannot reach the double placement: a numerator is only sought among the pieces to the right of a denominator. So it can be found a second time only by a second denominator that is left of it and under a bar it stands over, which is this shape (stated in the docstring). Mutants 42 and 43 were a dead line, `placed.add(id(lower))`: nothing looks at a denominator again once it is placed. The line is removed (no change in behaviour; goldens and the whole suite unchanged). | fio_24 killed; fio_42/43 gone with the dead line |
| T7 | Same test as T2: `_over` with a mark as numerator or as denominator is False and does not fail, and the text control is True. Reason it is unreachable through `rows_of`: every group of more than one element holds only text pieces, because only a text piece is appended to a group and only to a group ending in text. `_fractions_in_order` returns a one-element group before it looks for bars. | over_1, over_4 killed |
| T8 | `test_fraction_inside_counts_at_its_exact_value_at_both_ends`: the first letters may start exactly 1 pt before the bar's left end (119) and end exactly 1 pt past its right end (132), and the piece joins; at 118.75 and 132.25 it does not. | over_12, over_13 killed |

Hand mutants (with `PYTHONDONTWRITEBYTECODE=1` and the `__pycache__` cleared before each): 10 of the 11 listed killed, and den_17 is equivalent as explained above.

Checks: `ruff check`, `ruff format --check`, `lint-imports` and `deptry src` are clean. Fast suite: 8237 passed, 8 skipped, 6 xfailed. ci:full is set on the fix commit.
