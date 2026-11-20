# Review PR #481, round 2 (sentence-boundary batch PR 4, #460 + #455)

Head reviewed: 260d5f3, one fix commit on e591e93. Main is 7d866bf, the merge base, so the branch is up to date. Round 1: plans/review-pr481-round1.md.

**Verdict: not approvable yet, one should-fix (tests only).**

Everything from round 1 is fixed, as tried, and every heavy check is green. But one guard of the new bracket rule, the depth floor in `_inside`, has no test that fails without it. It has a concrete counterexample from a common shape: an inline list "a) … b) …" before a bracket. The fix is one test with no source change, and round 3 is then expected to be approvable.

## Round 1 findings
- **S1, fixed.** `_PAIRS_EN`, `_PAIRS_DE` and `_inside` are in, and a place inside a bracket or quote ranks after every place outside one (+5).
  - The code is byte-for-byte the diff I tried, plus a comment on straight quotes.
  - The five cases of `test_a_long_sentence_is_cut_outside_brackets_and_quotes` fail on e591e93: an en bracket with a comma, a space right after "(", en “…”, de „…“ and de »…«. I put the round 2 tests on e591e93's source to check this.
  - `test_a_sentence_all_inside_a_bracket_is_still_cut` passes on both heads, which is right: it is a guard against over-correction.
  - The seaborn golden is updated.
- **S2, fixed.** `_no_period` is in `_is_citation` and before the narrative `years_only`. The four counter-tests fail on e591e93.
- **N1, fixed.** "S. Dix", "p. Dix" and "(1/2 2019)" are added as stays. They kill the `_PAGE` d/m mutant.
- **N2, fixed.** The body and module docstring use the wording and name #482.
- **N3, fixed.** Both tests are in and kill mutants 8 and 11.
- **Issues.**
  - #482: second-run cut beside a multi-word reading.
  - #483: "(Sommer 2019)" read as a citation.
  - Both are lane:textprep, milestone v1.2.x, and named in the body.

## Heavy checks on 260d5f3
- **Corpus utterances** (`/home/user/probe/p478/utt.py`, all 13 files):
  - only seaborn 43 and arsiwalla 136 move against e591e93;
  - the dump is byte-identical to the variant I tried in round 1 (`fix.jsonl`).

  Against main 7d866bf, it is the round 1 table with those two cuts now outside the bracket.
- **Second-run fuzz** (`fuzz2.py 481 300`): 10 of 600 differ, as measured for the tried fix in round 1. This is #482, and the script text is identical (D-577).
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`, `--hypothesis-seed` 2024 and 123456, `-n 4`, on all 20 `tests/unit/test_textprep_*.py` files with `@given`): 2745 passed each.
- **Three systems.** The author's `ci:full` run on 260d5f3 is green: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser, lint and layers, licences, security, CodeQL and `CI passed`. The Windows flate-bomb test passed, so (7) is a one-off so far; I recheck it on the merged head.
- **The author's fast suite:** 6835 passed, 2 skipped.

### Mutation
`/home/user/probe/m481/run.py` on a copy of 260d5f3. These test files ran with `-n 4 -m "not slow and not benchmark and not browser"` and `HYPOTHESIS_PROFILE=ci`:
- `test_textprep_utterances.py`;
- `test_sentence_boundaries.py`;
- `test_textprep_regression.py`;
- `test_textprep_regression_german.py`;
- `test_textprep_citations.py`;
- `test_textprep_links_citations_de.py`;
- `test_app_corpus.py`.

The baseline passes: 1550 passed. Of 32 mutants, 28 are killed and 4 survive:

| # | mutant | verdict |
|---|---|---|
| 10 | a tie goes to the earlier place | note: an exact-tie choice ("x x x …", 152 words: 153/150 vs 151/152), and neither reading is more right |
| 12 | `max(2, …)` → `max(1, …)` | **equivalent**: `_cut_point` runs only when the window is over `max_chars`, and `left >= counts[-1] > max_chars`, so the ceiling is at least 2 |
| 19 | `_PAGE` without the letter look-ahead | note: decides only a glued "S. Xff.", which the head keeps as printed (the safe side) |
| 27 | `_inside` without the depth floor (`depth -= 1`) | **counterexample (S1 below)** |

The new S1 and S2 mutants are all killed except 27:
- inside rank off, +1 only, German using the English pairs, closing marks ignored;
- `_no_period` off, gap > 0, the narrative check off, the `_is_citation` check off.

## Fix list

### Should-fix

**S1. Pin the depth floor in `_inside`, with no source change.**
- **The counterexample.** "We test a) the speed and b) the care with which … (as we saw in the first study, which … of the long run) … it ended." and its German twin "Wir prüfen a) das Tempo und b) die Sorgfalt, mit der … (wie die erste Studie, die … zeigte) …".
  - Without the floor, the ")" of "a)" takes the depth to -1. The "(" then brings it to 0, so the bracket counts as outside.
  - The mutant cuts at "(as we saw in the first study, | which …" and "(wie die erste Studie, | die …".
  - The head cuts before "(as …" and after "zeigte)".
- **The test.** Take the parametrized test in `plans/review-pr481-round2-tests.py` into `test_textprep_utterances.py`, renamed to match the file's style. Its assertion: no part ends inside the bracket, that is, its last "(" is closed within the part. It passes on 260d5f3 and fails on the mutant (I checked).

## Round 3
- **The fix commit:** one fix commit that changes only `tests/unit/test_textprep_utterances.py`.
- **My checks:**
  - the test kills mutant 27, and the source diff is unchanged;
  - I rerun the utterance tests;
  - I read the three-system run on the new head: ci:full re-added, or the author's run, with `tests (macos-latest)` and `tests (windows-latest)` on that exact head.
- **The merge:** if main has not moved, I squash-merge pinned to that head on the coordinator's standing go. The merge commit closes #460 (textprep part) and #455.
