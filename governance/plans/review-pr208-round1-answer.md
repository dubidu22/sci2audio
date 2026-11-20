# PR #208, answer to review round 1

New head cce228d. Main 71b30c2 (#206) is merged in at 5f5c85b.

## Must fix

**F1. Fixed.** `citations._not_citations` no longer follows "and", "or" or a comma back by itself. A bracket joined on after an interval is no citation only if the statistics step reads it as an interval: `position in statistics.interval_openings(text)`. That function and `_confidence_intervals` now share one generator, `statistics._ci_runs`, which holds the CI word, the first pair and every joined pair (at most `MAX_JOINED_INTERVALS`). The result is cached per block in `_Rules`. All three of your inputs now read as main does on the first run, and the second run is the same:
- `The 95% CI [1, 3] and [12] agree.` reads `… 1 to 3 and reference 12 agree.`
- `The effect (95% CI [1, 3], [12]) holds.` reads `(… 1 to 3,) holds.`
- `Noise CI [1, 3] and [2-6, 16] here.` reads `… and references 2 to 6 and 16 here.`

The test is `test_textprep_statistics.py::test_after_the_intervals_a_citation_reads_the_same_on_both_runs`, which runs the whole chain twice. It also has a row for `CI [a, b] and [12]` (your F3.1 example).

**F2. Fixed.** There is one limit now. `statistics.MAX_JOINED_INTERVALS = 8` (renamed from the private `_MAX_JOINED`) bounds `_ci_runs`, and the citations step reads it through `interval_openings`. Its own `_MAX_INTERVALS` and the recursion are gone. Boundary test: 9 pairs after "CIs" read the first 8 as intervals, and the 9th is a citation on both runs (`… 8 to 9, hold.`). There is also `test_the_citations_step_leaves_alone_exactly_the_intervals_read_here`.

## Should fix (F3)

1. **`_NUMERIC` check on the previous bracket in the chain.** That code is gone with F1 and F2, because the chain is now the statistics step's own. The `CI [a, b] and [12]` row pins the behaviour you described.
2. **`edits_through_unread` guard: killed.** `test_only_replace_edits_are_mapped_back_through_unread_characters` passes a fake remove edit and a fake pause edit, and both raise `ValueError`.
3. **`characters._read_on`: all four mutants killed** by `test_reading_on_composes_accents_as_the_step_does`, which calls `_read_on` directly:
   - only `len(composed) == 1`: `´ü` must read `ü`, not `ǘ`
   - only `letter.isascii() and letter.isalpha()`: `´q` must read `q`, not `q́`
   - no `_DOTLESS`: `ˇı` must read `ǐ`
   - `j = k + 1`: `ˇl­s` must read `ľs`

   Through the step's only caller (the contraction check) these mutants are equivalent: a composed or uncomposed letter is a letter either way. So the test pins the helper itself.

I ran each mutant above against the textprep tests, and all 7 are killed. Also added: the import of `interval_openings` into citations (no cycle: statistics imports neither citations nor links).

## Checks on cce228d

- ruff, format, lint-imports and deptry are clean.
- Fast suite (`ci` profile): 3240 passed, 1 skipped.
- `HYPOTHESIS_PROFILE=nightly` on the 8 textprep files: 706 passed. Your two pre-existing failures (`5x×`, `10^250 000 000`) did not come up in this run. The coordinator is filing them for v1.0.1.
- Snapshots: no diff against main, and the corpus scripts are byte-identical.

## Notes accepted without change

`_PATH_LIKE` and the `_JOIN` lookahead are equivalent mutants, as you said. They are kept to document intent. The KB text of D-450 should name "and", "or" or a comma; I'm passing that to the coordinator for the daily KB batch.
