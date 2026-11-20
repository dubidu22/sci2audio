# Review of PR #572, round 1 (textprep batch B2, PR 1: #445 + #449)

Reviewer: B2 review thread (critical, Opus high). Reviewed head **38e56e0** (base 1797ceb).
Result: **CHANGES REQUESTED, 2 must-fix.** Push one fix commit for exactly F1 and F2, then tell
this thread the new head. Nothing else changes.

## Checked

- Linux CI green on 38e56e0 (run 44408703956); author ci:full three-system run green
  (44408729112: ubuntu, macos, windows tests all success). `ci:full` label removed.
- Main moved 6 commits since 1797ceb (B1, B3, #552); none touches `src/sci2audio/textprep/`,
  `tests/regression/` or the textprep unit tests. MRG-03: no branch update needed (CHANGELOG
  may conflict once F2 is added if another lane adds a line first; then merge main, never rebase).
- Plan D-764 followed: PR split, P1.2 to P1.6, P2.1 to P2.3. Rows added, none changed; the 7
  changed unit pins are the ones P1.6 names, spoken text unchanged. C2: no snapshot changes.
- Mutant survivor (`skip_end <= candidate.end` → `<`) **is equivalent**: counterexample search,
  200,000 random texts with soft hyphens, zero-width spaces and up to three unread ranges, random
  candidates, `through_unread` with the original vs the mutant `_around`: 0 differences
  (`/home/user/probe/eq.py`, seed 1). The author's argument (a candidate's last character is kept,
  so no range can end at its end) holds.
- AC-445.2, own seeds (`fuzz445.py`, 3,000 per seed, PR vs main 0bbb991-equivalent textprep):

  | seed | (a) hidden-only second-run diffs, main / PR | (b) `cls4.py` four-step replacements differ, main / PR |
  |---|---|---|
  | 7 | 16 / **0** | 17 / **2** |
  | 2024 | 17 / **0** | n/a / **0** |
  | 41 (author's) | – / **0** | – / **0** (matches the PR body) |

  Seed 7's two are the accepted #567 class (D-764): one is the link shape, the other the same
  mechanism with a removed **citation** ("10\n<" + hidden run + " (Smith, 2019)"). Added to #567
  as a comment; not a finding.
- Deviation (guard after "." or "," stays space-only): **accepted.** No #445 or #449 criterion
  needs "e.g.\nm²" or ".\nm²"; reading them as on main keeps #564 where it is.
- Hand probes, PR vs main, both runs: hidden run or page-break marker inside "1 000", "Fig. 3",
  "u. a.", "i.e.", "p < .05", "37 °C" (en, de), "5 mg/kg", two runs side by side, glued on either
  side, after a citation, after a line-end hyphen. Every one reads as the run-free text on run 1
  and run 2; main's three second-run diffs among them ("u. a.", "i.e.", "p < .05") are gone.
- Mass numbers: "¹¹B", "(⁴⁰K)", "“⁴⁰K”", "[⁴⁰K]", "⁴⁰K⁺", "⁴⁰K-atoms", "⁴⁰K." read as
  superscript and stable; "40K/39K", "³⁹Ar-⁴⁰K" read as printed (no magnitude edit on main either).
- Speed: `UnitStep.find` on 500, 2,000 and 8,000 blocks with a raised run each: 0.085, 0.30,
  1.27 s (main 0.076, 0.30, 1.25 s). Linear, same as main.
- Nightly profile (`HYPOTHESIS_PROFILE=nightly --hypothesis-seed=2024`, textprep unit tests and
  regression cases): 3,985 passed (run with the F1 patch below applied locally).

## Must fix

**F1. A raised run glued after a digit or a letter becomes superscript digits, which a second run
reads as a power (new second-run break, critical).** `UnitStep._mass_numbers`
(`src/sci2audio/textprep/units.py`) takes any raised 1 to 3 digit run that ends where a magnitude
letter starts, including an exponent of a power of ten:

| input (runs) | PR run 1 | PR run 2 | main (both runs) |
|---|---|---|---|
| `At T = 10` + sup `4` + `K the gas is hot.` | "At T equals 10⁴K the gas is hot." | "At T equals 10 to the power of 4K the gas is hot." | "…104 thousand…" |
| `At T = 10` + sup `3` + `K and 10` + sup `6` + `M stars.` | "10³K and 10⁶M stars." | "10 to the power of 3K and 10 to the power of 6M stars." | "103 thousand and 106 million" |

"10⁴ K" for a temperature is common in astrophysics papers, and the same shape comes from a PDF
exponent set small and raised. A mass number begins a word. Exact fix: in `_mass_numbers`, keep
the magnitude edit (no superscript replace) when the character before the raised run is a letter
or a digit (`start > 0 and text[start - 1].isalnum()`). Checked locally with exactly that
condition: both rows above read as on main and are stable; "2⁴⁰K" (glued after "2") reads
"240 thousand" as on main; every mass-number shape in "Checked" is unchanged; the nightly run
above passed. Tests (exact): one unit test in `tests/unit/test_textprep_units_abbreviations.py`
with two cases, `At T = 10`+sup`4`+`K` and `The x`+sup`40`+`K value.`: UnitStep makes no edit
whose reason starts `raised "`, and `read_twice` gives the same script on both runs. Do not add
a regression row pinning "104 thousand" (lesson: rows must not lock in wrong readings); that
reading is pre-existing and filed as **#576**. Add one mutant for the new condition to your set
and state it killed.

**F2. CHANGELOG line missing (D-768).** The PR changes what the listener hears (#445 readings,
"⁴⁰K"). Add one line under `## [Unreleased]` → `### Fixed` in `CHANGELOG.md`, in the file's
style, naming #445 and #449: a hidden run or page-break marker between a number and its unit,
inside a statistic or an abbreviation no longer changes how they are read; a number before its
unit on the next line reads the unit; a raised mass number before "K" (potassium-40) is no
longer read "40 thousand".

## Not findings

- Report spans of hidden-run and affiliation-mark removals gain the white space before the run;
  the shown text in their reasons is stripped, so the report reads the same.
- `through_unread` now also cuts numbers and statistics candidates (not only units and
  abbreviations as plan P1.3 named). The PR body says so; the fuzz and probes cover it.

## Filed / commented

- **#576** (new, lane:textprep, risk:low): a raised exponent before K, M or B reads as a
  magnitude ("10⁴K" → "104 thousand"), pre-existing on main.
- #567: comment with the citation shape of the accepted residual.

## Next round

After the fix commit: Linux CI green on the new head; then this thread runs the final-round
checks (mutation on the changed functions incl. the F1 mutant, own nightly seeds, a three-system
CI run of the final head via workflow_dispatch) and merges pinned to that head.
