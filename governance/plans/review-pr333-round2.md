# Review PR #333, round 2

Reviewed head: bfa2184 (fix commit 28a34bd, plus main 8f530a4 merged in, which includes #332). Author's answer: plans/review-pr333-round1-answer.md. Verdict: **one more small fix (R2-1, a missing test)**. Everything from round 1 is fixed.

## Round-1 items

- **R1-1 fixed (D-595 design).**
  - The design is followed. `StepContext.switched_off: frozenset[Category] = frozenset()` is documented in the class docstring. `run_steps` replaces the caller's value with its own `switched_off` argument and leaves the caller's context unchanged (runner test `test_every_step_learns_which_categories_this_run_switched_off`). `found_marks` returns {} while Footnotes is off, and TEXT_STEP_API stays 1.
  - My shape probe with Footnotes off (110 shapes, en and de, run 1, the same text without the mark, run 2) is byte-identical to main.
  - The new test pins my four round-1 shapes on both runs.
  - Mutants: removing the runner line, or the `switched_off` condition in `found_marks`, each fail the tests.
- **R1-2 fixed.** The units and statistics shapes were added, and the test now also reads a rebuilt second run. Both mutants are killed.
- **R1-3 fixed.** The „Dr.“ and „A.“ rows were added. Mutant `closing = _CLOSING` is killed.
- **R1-4 fixed.** ‹ and › close and open German sentences, and footnotes `_CLOSING` holds them too.
  - New tests cover cutting at ›…‹ and ‹…›, English staying unchanged, and a mark after ›…‹ or ‹…› being found.
  - Mutants killed: dropping either guillemet from `_SINGLE_GUILLEMETS` or from footnotes `_CLOSING`, `_OPENING_DE = _OPENING`, and `glued = _GLUED_BEFORE`.
- **R1-5 fixed.** The PR body and CHANGELOG now say "glued after" and name #341. #340, #341 and #342 are under Out of scope.
- **N1 done.** `found_marks` uses `step.handles(...)`.

## D-595 checks (coordinator)

- **Field documented:** yes, in the `StepContext` docstring: what it is, who fills it, and who reads it.
- **The conformance check really exercises it:** yes. `text_step_problems` runs every step on every sample document twice, with nothing off and with every category off, and labels the second run's problems ", every category off".
  - `test_the_suite_also_runs_each_step_with_every_category_switched_off` uses a step that breaks the contract only when `switched_off` is set, and asserts the problem is found.
  - The mutant that drops the second run (`for off, said in ((frozenset(), ""),)`) fails that test.
  - Limit, by design: a step runs alone in the conformance suite, so it cannot show a cross-step effect like R1-1. The chain tests in test_textprep_footnote_places cover that.
- **Old steps without the field still conform:** yes. The field has a default, so `StepContext(language)` still works (the player and the app script build it that way). A step that ignores the field gets the same results in both conformance runs. Every built-in step, and the existing test steps (Fixed, Bad, Mover), still pass.

## Other checks on bfa2184

- Fast suite, ci profile: 4865 passed, 1 skipped, 76 snapshots unchanged.
- Corpus, main 8f530a4 vs PR: all 13 documents, with script, report JSON, report Markdown and utterances (52 files), are byte-identical.
- Timing: every `assert_linear`/`assert_near` ratio in the seven textprep timing files is 5.6 to 9.4, against a limit of 32, with no change beyond noise. The whole chain with 800 marks and notes takes 0.55 s on main and 0.65 s on the PR, still linear.
- Shapes with Footnotes on: the only remaining second-run differences are #341's (a mark inside `z. B.`, `d. h.`, `u. a.`, `i. e.`), the same as on main.
- Nightly seeds: see the note at the end.

## Required fix

**R2-1: the initials check's new `whole.lstrip(opening)` is untested.** The mutant `whole.lstrip(opening)` → `whole.lstrip(_OPENING)` passes every textprep test (2390 passed). It changes real output: with the mutant, `Er sagte ›A.‹ Dann ging er.` and `Er sagte ‹A.› Dann ging er.` are cut after the quote; on the PR they stay one utterance, as „A.“ does. Add both rows to `test_german_sentences_end_where_german_ends_them`.

## Nightly seeds

My seeds 4242 and 99 passed on the utterances, footnotes, footnote-places, units/abbreviations, statistics, numbers, regression, conformance and runner tests (1449 and 1451 tests). Seed 8080 failed only on #340 (`3 × 10−410^2`), which main has too; it now also shows in the new "every category off" run.

## R2-1 and the merge check (head bb9cde4)

- **R2-1 fixed** in bb9cde4. The commit only adds tests: the ›A.‹ and ‹A.› rows. With the `whole.lstrip(_OPENING)` mutant, 2 tests fail; on the PR all 54 pass.
- **ci:full** was added. On bb9cde4, tests (ubuntu-latest), tests (macos-latest) and tests (windows-latest) succeeded, along with lint and layers, browser, security, licences, CodeQL and the latest CI passed. GitHub calls the PR mergeable ("clean"), and main is still 8f530a4.
- **Verdict: approve.** I recommend squash-merging bb9cde4.
