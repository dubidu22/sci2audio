# Review of PR #647, round 1 (#322; layout B13 PR 2, critical)

Reviewer: B13 review thread, 19 Nov 2026. Pinned head **05d76f9** (base main 9f2cbaa). Verdict: **changes requested, tests only** (no code defect found). One fix commit; it may also merge main (CHANGELOG conflict with #645, keep both lines).

## What was checked

| Check | Result |
|---|---|
| CI on 05d76f9 | `CI passed` green, `tests (ubuntu/macos/windows-latest)` success (ci:full) |
| Corpus blocks, main 9f2cbaa vs PR (`plans/b13-review/dump.py`) | 7 papers identical (blocks, furniture, columns). liu: 133 → 129 blocks, two replaced runs only: p2 "… energy gap σintOH = −egsgν 12π me m∗ . Physically,\nthe dominance …" (one paragraph; AC-322.1 as corrected), p4 "U3 1 2πniU4 0 mev2F∆2 (q2Fv2F+∆2), which dominates as the\nballistic limit …" (one paragraph). Nothing else moves |
| Spoken scripts (`sci2audio script --chapters all --ignore-settings`, 8 papers, main vs PR) | only liu differs, at exactly those two sentences |
| `test_textprep_citations_links_corpus.ambr` | 112 lines changed, all liu; with the leading block number removed the old and new lines are the same multiset (pure renumbering, edits unchanged) |
| `test_textprep_rules_corpus.py` liu list test | now finds the list by its "[1] " entry; still pins 81 entries ending at the last block, the "[81] " entry, and "Acknowledgments." before it: same strength, no longer tied to block numbers |
| Nightly property tests (nightly.yml run 44503189392) | success |
| mutmut (mutation.yml run 44503185505, globs `x__denominator*`, `x__fractions_in_order*`, `x__over*`, `x__first_letters*`, `x_rows_of*`; tests test_layout_paragraphs.py, test_layout.py, test_layout_corpus.py) | 185 killed, 16 survived; analysed below |

## Fix list (one commit, tests)

**T1. The column check of `_denominator` is untested.** `x__denominator__mutmut_3` (`not texts and edges…`, which drops the check whenever the line has text) survives. Add: a piece in the other column that starts under a bar of a line in this column, read right after that line, is not joined to it.

**T2. A printed line without text before the piece.** `x__denominator__mutmut_4` (`element.line is None and not texts or edges[id(texts[-1])]…`, which raises IndexError when the group holds no text) survives. Add a test where the group before a text piece holds only a mark (a group made of graphics), or state with code references why `rows_of` never calls `_denominator` with such a group.

**T3. "Inside the line" at its edges.** `x__denominator__mutmut_17` (`<=` at `line.y0`) and `_21` (`<=` at `line.y1`) survive. Add: a rule whose middle lies exactly on the line's bottom edge, and one exactly on its top edge, is not a bar inside the line, so the piece under it stays a line of its own. Use coordinates that are exact in binary.

**T4. A printed line of exactly two pieces.** `x__fractions_in_order__mutmut_13` (`len(pieces) > 2`) survives. Add: a line of exactly two pieces, a numerator and its denominator, with the denominator starting further left, reads the numerator first.

**T5. A fraction at the start of the line.** `x__fractions_in_order__mutmut_21` (`pieces[k - 1 :]`, which looks only at the last piece for the leftmost one) survives. Add: the leftmost piece of a line is a denominator whose numerator starts further right and is not the line's last piece; the numerator is read first, and the rest keeps its order.

**T6. Each piece is read once.** `x__fractions_in_order__mutmut_24` (`id(None) not in placed`) and `_42` / `_43` (lowers never marked placed) survive. Add: a nested fraction, where one piece is the denominator of one bar and the numerator of a second bar below it. Every piece appears exactly once, in reading order. If that geometry cannot reach the double placement, give the shape that can, or state why none can.

**T7. A non-text piece in a line with a bar.** `x__over__mutmut_1` (`upper.line is None and lower.line is None`) and `_4` (`return True` for a non-text piece) survive. Add: a printed line that holds an inline graphic (an icon or mark that `rows_of` keeps in the line) beside a fraction keeps its order and does not fail. Or state, with code references, that a printed line passed to `_fractions_in_order` never holds a non-text element.

**T8. `fraction_inside` at its exact value.** `x__over__mutmut_12` (`<` at `bar.x0 - reach`) and `_13` (`<` at `bar.x1 + reach`) survive. Add: first letters starting exactly `fraction_inside` em before the bar's left end, and ending exactly that far past its right end, still count (inclusive). Use coordinates that are exact in binary.

## Survivors not on the list

- `x__fractions_in_order__mutmut_9`, `_12` (also look for bars when the line has one piece): with one piece the loop finds no upper. Equivalent.
- `x_rows_of__mutmut_24` (`holds(…) and inline_mark(…)` → `or`): a line this PR does not change (#163). Pre-existing.

## Noted

- #648 (paragraph break between "conductance ∝" and the p4 fraction, on v2) is the plan's 322.3 remainder, filed as planned.
- The CHANGELOG line will conflict with #645's on main fac140c. Merge main in with the fix commit and keep both lines.

Round 2 is the final round: re-run the 14 listed mutants (mutmut on the same globs), ci:full on the fix commit, and the nightly property run, then squash-merge pinned on the reviewed head.
