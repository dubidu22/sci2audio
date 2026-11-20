# Review PR #359, round 1 (textprep follow-ups PR 2, units #320 #321 #335)

Heads reviewed: 0ea532e (base 79d0cdb) and 9fc815f (main 6c91465 merged in; `git diff 6c91465 9fc815f` equals `git diff 79d0cdb 0ea532e`). Plan: plans/textprep-v12-followups-plan.md PR 2 (D-605), author choices accepted as D-610. Critical.

**Verdict: not approvable yet. No blocker, one should-fix (S1), one nit (N1).**

## What I checked

- Change against the plan and D-610. #320: "equals", "less than or equal to" and "greater than or equal to" count as signs around "2x", but a bare "less than"/"greater than" does not (D-610, #358). #321: "beziehungsweise", "resp." and "respektive" join labels. #335: the English option "the second run leaves it too" (D-610). One gap against the plan, see S1.
- Fast suite: 5209 passed, 4 xfailed on 0ea532e, and 5239 passed, 1 skipped, 4 xfailed on 9fc815f. The four xfails are the #324 cases that PR 1 removes.
- Regression cases in English and German, run twice: 569 passed, 4 xfailed both times. The corpus second-run test passes. ruff, ruff format, lint-imports (3 kept) and deptry are clean.
- The 13 corpus documents, run with `run_script_job` on main 79d0cdb (PYTHONPATH to a main worktree) and on 0ea532e: all 39 output files are **byte-identical**.
- Commit messages: no closing keywords in 65f8c2c, 0ea532e or 9fc815f. `Closes #320/#321/#335` is only in the PR body.
- Mutation-style breaks (units, numbers, both regression files): 9 of 11 fail the tests. These failed: "equals" removed; ≤/≥ readings removed; bare "less than" added; the fraction-chain check removed; its unit chain emptied; the "out of" check removed; each of "beziehungsweise", "resp." and "respektive" removed from `label_joins`. Two survived: the look-behinds in `_UNIT_CHAIN_AFTER_FRACTION` and `_OUT_OF` (N1).
- Neighbour probes, whole chain twice, main vs PR (about 100 shapes):
  - Every changed first-run reading falls in a class the PR's table lists: "equals 2x", "less than or equal to 2x faster", "2x equals …", "N out of M <unit>" ("3 out of 10 mg doses" now keeps "10 mg"), and "N <fraction word> <letter power>" in prose ("2 halves m²", "the first 2 thirds s²", "3 quarters x²" now keep the power as printed).
  - German labels: "Kapitel/Tabelle/Bedingungen 1 resp. 2 m/V/kg" now keep the unit as printed, as "bzw." already does. "Es liegen 1 resp. 2 V an" and "Die Werte 3 respektive 4 mm" are unchanged, because they have no label word.
  - Edge shapes ("1017/20 kg", "17/2000 kg", "2.5/4 s⁻¹", "a3/4 s⁻¹", "3/4/5 s⁻¹") are unchanged. Whole-chain second runs now agree for every English fraction-and-power shape I tried, including "12/16 s⁻¹", "17/200 kg", "3/4 kg·m²", "~3/4 s⁻¹" and "−1/2 s⁻¹".
- Nightly seeds (`HYPOTHESIS_PROFILE=nightly`; runner, conformance, numbers, units, German numbers and statistics): seeds 2024 and 123456 are clean. Seed 7 fails `test_the_step_keeps_the_contract_on_any_document` on `t(3)=310^250 000 000`, the same on main 79d0cdb: that is #340/#210, PR 3 (D-614), not this PR.
- Timing: the new patterns are anchored at the end of a 64-character look-back (`_before`) or a 16-character window, so they are constant per match.
- Coordinator note, no fix asked: D-610 covers the listed prose changes. "The cost equals 2x the baseline" now reads "2x" (it read "2 times"). German has done the same with "gleich 2x" since #130, so I accept it as the cost of #320.

## Fix list

### Blockers

None.

### Should-fix

**S1. The German sibling of #335 is left out.** For PR 2 the plan says "the German fraction words likewise". The PR handles only the English fraction words. German still reads a power after a fraction and a unit only on the second run (the same on main):

| printed (de) | first run | second run |
|---|---|---|
| `Es ist 2/3 m s⁻² hier.` | `2 Drittel m s⁻²` | `2 Drittel m s hoch minus 2` |
| `Es ist 3/4 m s⁻¹ hier.` | `3 Viertel m s⁻¹` | `3 Viertel m s hoch minus 1` |
| `Es ist 3/4 kg m² hier.` | `3 Viertel kg m²` | `3 Viertel kg m Quadrat` |

These are fine on both runs: `1/2 m²` and `3/4 m²` stay as printed, and `1/4 cm²`, `3/4 kg` and `1/2 kg` read the same twice.

Fix: make both runs agree in German, either way:
- **(a), recommended.** `numbers_de._fractions` already leaves a fraction as printed when a letter power follows it ("1/5 m⁶", `_LETTER_POWER_AFTER`). Extend that check to a unit chain that ends in a letter power ("2/3 m s⁻²", "3/4 kg m²"). This matches German's existing choice and keeps the English rule's shape.
- **(b)** Have the German power rule leave a letter power after a German fraction reading ("ein halb", "N Drittel/Viertel/…", "N von M") and a unit chain, as the English rule now does.

List any first-run change in the PR body either way. Add a German regression case with the three rows above, plus "1/4 cm²" as a control. It must fail on 9fc815f's second-run check.

### Nits

**N1. Two look-behinds no test pins.** Removing `(?<![\w^.])` from `_UNIT_CHAIN_AFTER_FRACTION` or `(?<![\w.,])` from `_OUT_OF` changes no test and no reading I could find. The numbers step reads no fraction with a 4-digit or decimal numerator ("1017/20", "2.5/4" stay as printed), so a second run never meets such a shape. Either pin each one with a unit test of the prose it protects ("It was 1,017 out of 20 kg." keeps "20 kilograms"), or say in a comment that they are defensive.

### Deferred

None from me. #358 (y < 2x) is already filed.

## CI

`ci:full` was added on 9fc815f, and the macOS/Windows runs were in progress at the time of writing. Note: main 6c91465 itself fails `tests (macos-latest)` at `tests/unit/test_extraction_pdf_process.py::test_each_reported_step_starts_the_childs_own_clock_anew` (from PR #345), so this PR's macOS run can fail there without any cause in this PR.
