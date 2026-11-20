# PR #333 round 1: answer

Head bfa2184: fix commit 28a34bd plus a merge of main 8f530a4 (with #332). Route for R1-1 as decided in D-595.

## Fixed

**R1-1 (blocker).** `StepContext` gets a defaulted field `switched_off: frozenset[Category] = frozenset()`, documented in the `StepContext` docstring next to the other fields (the repo has no separate text-step docs file). `run_steps` fills it from its own `switched_off` argument with `dataclasses.replace`, so the caller's context stays as it was. `found_marks` returns no marks while `Category.FOOTNOTES` is in it, so the steps read the marks that stay. TEXT_STEP_API stays 1.
- Your four shapes run twice with Footnotes off and read exactly as on main: "Siehe Abschnitt 2 Punkt 1 Dann weiter.", "Siehe Tabelle 2 Punkt 1 Dann mehr.", "Er sagte „ja“0 Komma 1 Dann ging er.", "Das ist z.1 B. so." (`test_with_footnotes_switched_off_the_marks_stay_and_are_read_on_both_runs`).
- Runner test: the field arrives, replaces what the caller put there, defaults to `DEFAULT_SWITCHED_OFF` (`test_every_step_learns_which_categories_this_run_switched_off`).
- Conformance: `text_step_problems` runs every step twice, with nothing and with every category switched off; a test step that breaks the contract only when something is off is caught (`test_the_suite_also_runs_each_step_with_every_category_switched_off`).

**R1-2.** Your four shapes were added to `test_a_mark_hides_no_abbreviation_or_number_from_the_first_run`, which now also reads a rebuilt second run. Both mutants (`units.py` and `statistics.py`) fail it.

**R1-3.** `Er nannte „Dr.“ Müller dann.` and `Er sagte „A.“ Dann ging er.` were added as single utterances. The `closing = _CLOSING` mutant fails.

**R1-4.** German: `_CLOSING_DE` gains › and ‹, a new `_OPENING_DE` (› ‹ open the next sentence) and `_GLUED_BEFORE_DE` (so `›z. B.‹` and `›Dr.‹` stay one sentence, as with „…“). `footnotes._CLOSING` gains › and ‹. Tests: cuts after `›ja.‹`, `‹ja.›`, `»ja.« ›Nein.‹`, `«ja.» ‹Nein.›`; English rows with › and ‹ are not cut; a mark after `›ja.‹¹`, `‹ja.›¹` (and `»ja.«¹`) is found and moved. Mutants removing each of the new sets fail.

**R1-5.** PR body and CHANGELOG say "glued after", name the #341 exception, and list #340, #341 and #342 under Out of scope.

**N1.** Done: `FootnoteStep().handles(context.language)`.

## Checks on bfa2184

- Fast suite, ci profile: 4865 passed, 1 skipped, 76 snapshots unchanged.
- Corpus, 13 documents through `run_script_job`: byte-identical to main 8f530a4.
- Second run of every regression case (153 en, 108 de): only the six known exceptions (#320/#321 and the notice labels of #324).
- Eight one-line mutants, all killed (list in the PR body).
- Nightly profile, seeds 555 and 31337, on the utterances, footnotes, footnote-places, units/abbreviations, statistics, conformance and runner tests: 716 passed each.
