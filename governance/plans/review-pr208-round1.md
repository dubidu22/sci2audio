# Review of PR #208, round 1 (textprep batch: #109 #110 #145 #151 #159 #160)

Reviewed head 967a930 (main 2ea317e merged in), 13 Nov 2026, about 22:15 UTC. Verdict: **changes requested** (2 must-fix, 1 should-fix).

## What I checked and found right

- **Each issue has a test that fails without the fix.** I copied the PR's tests and regression file onto main's `src`: 32 failed, 687 passed. Every issue is covered: #109 (links, 4 failing tests), #110 (3 article rows), #145 (2 rows), #151 (5 citation rows, 3 statistics rows and the second-run test), #159 (6 first/second-run rows and the span mapping test), #160 (the ligature/accent test and the `5 x86K` rows). All 5 new regression cases fail on main.
- **The reading rules match the decisions.** D-447 (#145): a bracket of lead words and a narrative citation goes whole, and a full stop inside it only when the bracket starts a sentence. D-448 (#110): an article before the name, unless "et al." or a second author. D-449 (#109): after `/ - _ ~ = & ? # %`, a plain English word does not join. D-450 (#151): "CI:", "CIs", "CI =" and joined pairs. The PR also joins on "or" and a comma, besides "and". I accept this as within D-450's intent ("CIs [1, 3], [2, 4] and [5, 6]" needs the comma). The KB text of D-450 should name "and", "or" or a comma.
- **Golden data.** `tests/regression/english.toml` only appends 5 cases, and no existing case or `expected` line changes. There are no snapshot or corpus changes in the diff, and the corpus snapshot tests pass, so the spoken scripts of the corpus papers are byte-identical. Nothing outside the six issues is in the diff.
- **Tests.** The fast suite (ci profile) gave 3223 passed and 1 skipped, the same as the author. All 12 CI checks on 967a930 are green.
- **Speed.** A 20k-bracket "CI [1, 3] and [0] and [1] ..." block takes 0.63 s in the citations step, and a 60k-character "CIs [1, 3], [1, 3], ..." takes 0.74 s for the whole chain. That is linear.
- **Hand mutants.** I ran 25 mutants: 17 killed and 8 survived (see F3 and the notes).

## Must fix

**F1. A citation joined on after an interval is no longer read as a citation (new idempotence break).** `citations._not_citations` follows "and" / "or" / "," back to a CI bracket for *any* numeric bracket. `statistics._confidence_intervals`, however, only reads a *pair of two numbers* as an interval. So a citation that is not a pair now stays printed on the first run and becomes a reference on the second:

| Printed | main | PR first run | PR second run |
|---|---|---|---|
| `The 95% CI [1, 3] and [12] agree.` | `… 1 to 3 and reference 12 agree.` | `… 1 to 3 and [12] agree.` | `… and reference 12 agree.` |
| `The effect (95% CI [1, 3], [12]) holds.` | `(… 1 to 3,) holds.` | `(… 1 to 3, [12]) holds.` | `(… 1 to 3,) holds.` |
| `Noise CI [1, 3] and [2-6, 16] here.` | `… and references 2 to 6 and 16 here.` | `… and [2 to 6, 16] here.` | (same) |

Fix: apply the joined-on rule only when the bracket at `position` is itself a pair that the statistics step reads as an interval (two numbers separated by `,` or `;`, the shape of `statistics._INTERVAL`). Add tests for these three inputs that check both runs of the whole chain.

**F2. The two steps' limits disagree at the 9th joined pair.** The statistics step reads at most 8 intervals after "CIs" (`count < _MAX_JOINED`). The citations chain accepts the 9th bracket, because the recursion reaches the CI bracket at depth 8. Probe: `The CIs [1, 2], [2, 3], … [11, 12] hold.` reads `… 8 to 9, [9, 10], hold.`, which leaves the 9th printed and removes the 10th and 11th as citations, and a second run differs. Fix: use one limit for both steps, so that the bracket after the last interval the statistics step reads is a citation again. Add a test at the boundary. This also kills the surviving mutant `depth >= _MAX_INTERVALS` → no limit.

## Should fix (tests only)

**F3. Surviving mutants that are not equivalent.** Add a test that kills each one, or say in the reply why it is equivalent:

1. `citations._not_citations`: dropping `_NUMERIC.match(text[opened + 1 : end]) is not None` survives. Example: `CI [a, b] and [12]`. The previous bracket is not numeric, so `[12]` should stay a citation.
2. `notation.edits_through_unread`: dropping the `ValueError` guard for a non-replace or empty edit survives. Add a unit test with a fake remove edit.
3. `characters._read_on` (#160): four mutants survive, so only the one ligature example pins the new branch:
   - `len(composed) == 1 and letter.isascii() and letter.isalpha()` → `len(composed) == 1`
   - the same condition → `letter.isascii() and letter.isalpha()`
   - dropping `_DOTLESS.get(...)`
   - `j = _skip_forward(text, k + 1)` → `j = k + 1`, which would show with an unread character after the composed letter

## Notes (no change needed)

- `links._continues`: the `_PATH_LIKE` check is an equivalent mutant, because no word in `_SENTENCE_WORDS` holds an address character. Keeping it is harmless and documents intent. `https://x.org/⏎about` no longer joins ("about" is in the list). That is the faithful side to err on (the word is still read) and matches D-449.
- `statistics._JOIN`: the lookahead `(?=[\s\[(])` survives as an equivalent mutant, because `_INTERVAL` needs a bracket after optional space or `=`/`:`.
- D-448 consequence: `the Smith (2019) study` now reads its year (one author after an article). That is as decided.

## Worth deferring (pre-existing on main, not caused by this PR)

`HYPOTHESIS_PROFILE=nightly` on the 8 textprep files gave **691 passed, 2 failed**. Both failures reproduce on main 2ea317e with `check_text_step`:

- **units:** `5x×` gives `5x times` on the first run and `5 times times` on the second (the units step alone is not idempotent).
- **numbers:** `10^250 000 000` gives `10^250,000,000` on the first run and `10 to the power of 250,000,000` on the second.

The nightly run will turn red on these whenever Hypothesis finds them. The coordinator decides on the issues.
