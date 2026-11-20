# Review PR #484, round 2 (sentence-boundary batch PR 5, #463 + #464)

Head reviewed: 99b3f48, one fix commit on 8db9cc2. Main is cfeb084, the merge base, so the branch is up to date. Round 1: plans/review-pr484-round1.md, with the coordinator's rulings in its addendum.

**Verdict: not approvable yet. There is one should-fix, and it was found by the nightly seeds.**

The fix commit does everything round 1 and the rulings asked. But the new `_run_tags`, which is the fix I proposed in round 1, crashes `rebuilt_from_script` on a tagged run that holds a line break. The textprep runner's property test finds this with both nightly seeds, and on main it passes. My round 1 trial ran the fast and regression suites but not the nightly seeds, so I missed it there.

## Round 1 findings
- **S1, fixed as tried.** `rebuilt_from_script` keeps a printed placeholder's run tags (`_run_tags`, with the "never point at other text" guard), and the exclusion in `_run_problems` is gone.
  - `hole.py` gives 8 problems again.
  - The two new tests fail with 8db9cc2's source: `test_an_edit_inside_a_placeholder_that_hangs_on_another_block_is_caught` and `test_a_placeholder_back_as_printed_keeps_its_tagged_runs_and_one_read_does_not`. I put the round 2 tests on 8db9cc2's source to check.
  - The docstrings and the body's point 3 are updated.
- **N1, fixed.** "[3], [4]" (en) and "https://x.org – (WBGU 2011, S. 1)" (de) are added. They kill the "blank only" mutant.
- **Ruling 2, done.** The tests now hold a bare "https://x.org" (en), "(Smith, 2019)" (en), "vgl. https://x.org" (de) and "(Müller 2019, S. 4)" (de), so there is a URL-only and a citation-only case in each notice language. The departure from #464 is recorded as approved in the body.
- **Ruling 3 (D-718), done.** Every placeholder kind is covered with the notice on and off in all three languages:

| kind | en on / off | de on / off | fr on / off |
|---|---|---|---|
| table | notice / "a b c" | notice / "a b c" | "a b c" / "a b c" |
| formula | notice / "a b c" | notice / "a b c" | "a b c" / "a b c" |
| figure | notice / "a b c" | notice / "a b c" | "a b c" / "a b c" |
| code | notice / "a b c" | notice / "a b c" | "a b c" / "a b c" |

  The en and de cases are in `test_a_placeholder_whose_notice_is_off_loses_its_hidden_runs`, where "on" means the other categories are off. The fr cases are in `test_a_placeholder_in_a_language_without_notices_loses_its_hidden_runs`, which is parametrized over kind × on/off.
- **The body's D-718 line** names #436 and #450 (PR 6) as the PRs that built on the old notice model.

## Checks on 99b3f48
- **Corpus utterances:** byte-identical to 8db9cc2 and to main.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, `-n 4`): 6879 passed, 2 skipped.
- **Three systems:** the author's `ci:full` run on 99b3f48 is green: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser, lint and layers, licences, security, CodeQL and `CI passed`.
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`, `--hypothesis-seed` 2024 and 123456, `-n 4`, on the 20 textprep property files plus `test_textprep_conformance.py` and `test_testing_rebuilt_from_script.py`): **1 failed and 2862 passed for each seed.**
  - The failing test is `test_textprep_runner.py::test_the_built_in_steps_never_fail_and_are_idempotent`.
  - The error is `ValueError: tagged range 5-7 must lie inside one line, in order` (seed 2024) and `4-6` (seed 123456), raised by `make_document` from `rebuilt_from_script`.
  - The falsifying example is a TABLE block "0\n00\n" whose second line's run "0\n" carries a tag ("h1"), and whose parts overlap (two parts at start 0).
  - On main the rebuild passes no tags, so it cannot fail this way.

### Mutation
`/home/user/probe/m484/run.py` on a copy of 99b3f48, with the same test files as round 1. The baseline passes: 1322 passed. Of 15 mutants, 10 are killed and 5 survive:

| # | mutant | verdict |
|---|---|---|
| 1 to 4, 7, 8, 10, 11 | as round 1 | killed (8 is now killed by N1) |
| 5, 6 | alt for a captioned figure / without `named` | **equivalent**, as in round 1 |
| 9 | `read_twice` rebuilds notice-off placeholders as printed | **now equivalent in effect.** With the tags kept, a printed placeholder reads the same on the second run as its own output. `own_output=read` stays harmless, and dropping it is optional |
| 12 | no run tags kept | killed |
| 13 | `_run_tags` without the other-text guard | **survives (S1 test c)** |
| 14 | empty tagged runs kept (`if run.tags:`) | **survives (S1 test b)**: an empty tagged run gives an empty range, and `make_document` raises on it |
| 15 | the exclusion put back | killed (the Neighbour test) |

## Fix list

### Should-fix

**S1. `_run_tags` must give only ranges that `make_document` accepts.** A range may not cross a line break, may not go back over the one before it, and may not be empty.
- **Fix.** Split each tagged run at "\n", skip empty pieces, and skip a piece that starts before the previous range's end (overlapping parts).
- **Tried** (`plans/review-pr484-round1-probes/fix484-r2.diff`):
  - with both seeds, `test_textprep_runner.py`, `test_testing_rebuilt_from_script.py`, `test_textprep_conformance.py` and `test_textprep_hidden_runs.py` pass under the nightly profile (175 passed each);
  - `hole.py` still gives 8 problems.
- **Tests** (in `test_testing_rebuilt_from_script.py`; each fails on 99b3f48):
  - **(a)** the falsifying shape: a placeholder whose tagged run holds a line break, and whose parts overlap, rebuilds without error and keeps the tag on the text before the break. Build it with `Content`/`TextLine`/`TextRun` directly, or add it as an `@example` to the runner property test;
  - **(b)** an empty tagged run in a placeholder rebuilds without error (kills mutant 14);
  - **(c)** a part whose line is not the block's text at that place gives no tag (kills mutant 13), mirroring HiddenRunStep's guard test.

## Round 3
- **The fix commit:** one fix commit (`testing/documents.py` and its tests).
- **My checks:**
  - nightly seeds 2024 and 123456 on the same file set, the three tests and their mutants;
  - `hole.py`, the corpus utterances and the fast suite;
  - a three-system run on the new head.
- **The merge:** if main has not moved, I squash-merge pinned to that head on the coordinator's standing go, then add the batch summary line.
