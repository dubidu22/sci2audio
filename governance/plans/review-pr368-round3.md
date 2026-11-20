# Review PR #368, round 3 (textprep follow-ups PR 4, German numbers #334 #349 #249 captions)

Head reviewed: d0fb704 (one commit on 7936a1c, which is 697ca15 + main 3fcba56). Answer: plans/review-pr368-round2-answer.md. Critical.

**Verdict: approvable at d0fb704.** It closes #334 and #349. #249 stays open for #362, and #370 is deferred.

## Round 2 items

- **S1, fixed.** With `NUMBERS_AND_UNITS` switched off, "Abb. 3.1" and "Abbildung 1.2-1.4" read as printed in both notice and caption, as on main, on both runs.
- **S2, fixed.** "Tab. 1/2:", "Abb. 3/4:", "Abb. 1/5:", "Abb. 2/3:" and "Abb. 12/13:" keep the fraction in both notice and caption. The controls "Abb. 3/4 Verlauf" and "Abbildung 3/4. Verlauf" read "3 Viertel" in both. All of them read the same on both runs.

## Checks on d0fb704

- Fast suite (`HYPOTHESIS_PROFILE=ci`): 5423 passed, 1 skipped. This includes the English and German regression cases with their second-run check and the corpus second-run test.
- About 60 caption labels and 40 paragraph shapes were run through the whole chain twice, against main 3fcba56. The only second-run differences left are also on main:
  - `Tab. 3x` (#370).
  - `Abb. 4` in a caption "Abb. 4. Juli: …", where the caption reads the label number as a date. It is pathological and is noted on #370.
  - The #358 rows (`y < 2x`).
- The #361 and #359 probe sets read as before.
- 13 corpus documents with `run_script_job`: all 39 files are byte-identical to main 3fcba56.
- Mutation-style breaks: 11 of 14 fail the tests. These failed:
  - the paired-date ending;
  - each of the three `_PAIR_DASH` alternatives (em dash, spaced dash, optional space around the em dash);
  - the date-adjacency check;
  - `_AFTER_PUNKT` widened to `\bPunkt`, and the guard removed;
  - the label read without its caption context, and `after` emptied;
  - the numbers switch check dropped;
  - German label reading turned off.
- Three breaks survived, and all of them are defensive:
  - `not _DASH_RANGE.match(...)` before the "bis" candidate: the range rule's own candidate wins the overlap, so no probed reading changes.
  - `candidate.end <= len(label)` loosened to `start < len(label)`: this changes only the pathological "Abb. 4. Juli" shape, which already differs on main.
  - The whitespace join in `label_numbers_read`: no reading changes.

  No fix is asked for.
- Nightly seeds (`HYPOTHESIS_PROFILE=nightly`; conformance, numbers, German numbers and statistics, placeholders, runner, units): seeds 7, 2024 and 123456 are clean, in addition to the author's 7, 555 and 8080.
- Commit messages carry no closing keywords. The PR body closes #334 and #349.
- CI on d0fb704 with `ci:full`: tests (ubuntu-latest), (macos-latest) and (windows-latest), browser, lint and layers, licences, security and CodeQL are all green. `mergeable_state` is clean against main 3fcba56.

## Fix list

None. No blockers, should-fix items or nits. Deferred: #370.
