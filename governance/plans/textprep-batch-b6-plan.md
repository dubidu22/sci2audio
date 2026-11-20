# Textprep batch B6: sentence cutter (#479, #482, #533)

Status: **waiting for approval** (critical: a German regression row, the sentence gate's stress set, and a regression-harness
check for second-run cuts, see 5 and 6).
Author: textprep lane thread "Fix the sentence cutter for German labels", 19 Nov 2026 ~04:05Z. Base: main b32612d (B5 #593 merged).
Read: `next-batches-2026-11-18.md` (rows 479/482/533, B6), `next-batches-2026-11-19.md` §4 (B6 → B13 → B11 PR 2 share
`tests/sentences/`), D-779, issues #479 #482 #533 (all three have acceptance criteria, PLAN-04 met), CLAUDE.md,
`.claude/rules/tests.md`, `textprep-batch-b5-plan.md` (template), REVIEW LESSONS in `memory/MEMORY-archive-2026-11-18.md`,
`review-pr481-round1.md` (#482's probe), `review-pr524-round1.md` (#533's mutants).

All three reproduce on b32612d (probe: `run_steps`, then `rebuilt_from_script` and `run_steps` again, then `cut_utterances`):

| issue | input | run 1 utterances | run 2 utterances |
|---|---|---|---|
| #479 | `Es gilt Abs. 2. Abs. 3 gilt hier auch.` | one: `Es gilt Absatz 2. Absatz 3 gilt hier auch.` | same |
| #479 (same cause) | `Es gilt Art. 3. Art. 4 gilt auch.`, `Rn. 3. Rn. 4`, `Ziff. 3. Ziff. 4` | one utterance each | same |
| #479 (already right) | `Es gilt Satz 2. Satz 3 …`, `Nr. 2. Nr. 3` | two (label words of the unit list) | two |
| #482 | `fuzz2.py` (the #481 reviewer's probe), seeds 1, 2, 3 × 400 per language and 481 × 150 | | **6 of 2,700** sentences cut differently on run 2 ("3 \| Komma 5", "for \| example", "zum \| Beispiel") |
| #482 | `fuzz3.py` (mine: more readings, units, operators, powers, fewer commas), seeds 1, 2 × 300 per language | | **649 of 1,200** (54 %) without punctuation, 258 of 1,200 (22 %) with |
| #533 | the seven mutants of the issue | survive the three test files | |

Mutant counterexample search (`plans/b6-mutants/search.py`, whole `cut_utterances`, mutant vs original, seeded random
sentences of 5 to 160 words with commas, dashes, quotes, readings and long words, max_chars from 20 to 400, 20,000 tries):
mutants 1, 3, 4, 6 and 7 change output (so none is equivalent, mutant 1 included); 2 and 5 survive the random search, and I
found by reading why: each needs an input the generator does not make (see 3). So all seven get a test; none is called equivalent.

## PR split

**One PR**, `textprep/sentence-cutter-b6`, labels `lane:textprep`, `risk:high`. Closes #479 #482 #533. Milestone v1.2.x.
Why one: all three change or pin `textprep/utterances.py`, its unit tests and the cutter's rows; two PRs would conflict
in `test_textprep_utterances.py` and need two review set-ups. Files: `textprep/utterances.py`,
`tests/unit/test_textprep_utterances.py`, `tests/regression/german.toml`, `tests/unit/test_textprep_regression.py`,
`tests/unit/test_textprep_regression_german.py`, `tests/sentences/stress-de.txt`, `CHANGELOG.md` (D-768). Not touched:
`numbers_de.py`, the word lists, `known-errors.toml` (no entry comes or goes, see 4), `pyproject.toml`, CI, anything outside textprep.

Earlier rules this PR revisits: the German short-number rule (#227, D-530; `_after_label`, D-719) and the ranked cut
(#460, D-719; `_rank`, the bracket rank of the #481 review). Both kept; each gets one more case, below.

## 1. #479 "Abs. 2. Abs. 3" stays one utterance

**Cause.** A German number of one to three digits with a full stop ends a sentence only after a label word of the unit list
(`_after_label`: "Abbildung", "Satz", "Nr.", …) or before a sentence opener. "Absatz" (and "Artikel", "Randnummer",
"Ziffer") is no label word there. The numbers step already treats the shape right: `numbers_de` leaves `2.` as printed when
the word before the number comes again after it ("Es gilt Satz 2. Satz 3": a label's number, then the same label again, D-719).
The cutter has no such rule, so it keeps the sentence whole.

**Change.** One structural rule beside `_after_label`: `_label_again(text, start, end)`: the word right before the number
is the same word as the one right after the full stop ("Absatz 2. Absatz 3", "Artikel 3. Artikel 4"), compared exactly, as
`numbers_de` compares them. Then the full stop ends the sentence. It holds on both runs (the cutter sees "Absatz" either way).
Why not add "absatz", "abs.", "artikel", … to the unit list's labels: that list also drives the units step and the links step
(a label's number gets no unit), so it would change readings beyond the cut; and it would fix only the words added, while the
same-word rule covers the whole class the numbers step already knows (#477's lesson: a structural cue, not a longer list).

**Not changed (AC 2).** `Im Abs. 2. Teil steht es.` stays one utterance: `2. Teil` is read as an ordinal, so its full stop
is inside a replacement and cuts nothing (the reading, "Im Absatz zweiter Teil", is the numbers step's and not this PR's; the
unit test pins only the cut). `Es gilt Abs. 2 Satz 3 hier.` (no full stop) stays one. `Es gilt Satz 2. Satz 3` and
`Nr. 2. Nr. 3` keep their cut. `(Absatz 2. Absatz 3)` glued to a bracket stays one utterance as today (the word before is
"(Absatz"); a test pins it, so the rule's reach is explicit.

**English.** No change: English has no short-number rule (a number and a full stop before a capital ends a sentence already).

## 2. #482 a second-run cut inside a multi-word reading

**Cause.** On run 1 a reading such as "u. a." → "unter anderem" is one replacement: when the best cut falls inside it,
`_outside_replacement` moves it to the reading's start or end. On run 2 the reading is plain words, nothing moves it, and the
cut nearest an even share (#481) can stay inside: "die unter | anderem", "3 | Komma 5". The script text is the same (D-577);
only the cut moves.

**Change.** A new rank between "white space" (4) and "inside a bracket": **5, a space inside a reading**. `_rank` stays as it
is; `_cut_point` ranks a white-space place 5 instead of 4 when it joins the words of one reading, and the bracket penalty
becomes `+ 6` (was `+ 5`), so every place outside a bracket still beats every place inside one. "Inside a reading" is found
from the text alone, so run 1 and run 2 rank the same places:
- **number readings:** a space with a digit right before or after it ("3 | Komma 5", "Komma | 5", "Seite | 12",
  "19 | hundert 98", "13 | Uhr 30", "2 | bis 3", "Mai | 2019", "approximately 20 | minutes"); a space inside a month
  date ("dritten | Mai", "3 | May"); "to the power of (minus)" and German "hoch minus";
- **abbreviation readings:** every reading with a space in `data/<language>/abbreviations.toml` (`reads`, `before_year`,
  `after_paragraph`: "unter anderem", "zum Beispiel", "das heißt", "in Verbindung mit", "for example", "that is"), case
  insensitive, built from the list at first use (a new entry is covered at once, as `_german_abbreviations` does);
- **unit readings:** unit names with a space in `units.toml` ("Grad Celsius", "pound per square inch"), the spaces on both
  sides of the per word ("Kilometer pro Stunde", "kilometres per hour"), after "square"/"cubic" and before
  "squared"/"cubed" (English; German writes them into the word);
- **operator readings** of the statistics step that the same cut can split ("less than or equal to", "kleiner oder
  gleich", "plus or minus", "R squared"), from `statistics.OPERATORS`, `statistics_de.OPERATORS_DE` and the squared names
  (imported, not copied).
The search runs over the window only (as `_inside` does), so a long text still costs linear time (#268); the slow linear-time
test covers it.

**Measured with a prototype** (on this branch, not pushed):
- `fuzz2.py`, the issue's probe: **0 of 2,700** differ (main 6 of 2,700; the AC asks at most main's).
- `fuzz3.py`, the harder probe: 103 of 1,200 (9 %) without punctuation (main 649, 54 %), 96 of 1,200 (8 %) with (main
  258, 22 %). The rest is cuts where every place near the even share is rank 5, so run 1 moves its pick out of a
  replacement and run 2 does not. That is a smaller limit of the same kind: follow-up F1, and the module docstring says it.
- Corpus utterances: identical to main on both runs (all 13 sources, script job defaults; first and second run; 7,729 lines).
  All 15 cut sentences of the corpus are cut at ";", ":" or a comma, so a space rank cannot move them.
- The fast tests of the cutter, both regression files and the sentence gate pass unchanged (1,176).

**Why not something else.** The issue's second option ("the second run otherwise cuts where the first run did") would need
the second run to know the first run's replacements, which `rebuilt_from_script` drops on purpose (D-577: the script is
plain text). A list of every reading in one place would copy the steps' tables; reading them from where they live keeps one source.

## 3. #533 seven surviving mutants of the cutter

Each new test names the rule it pins, not the mutant (AC 3). Tests use the literal 40, not the `MIN_PIECE` import, so
changing the constant fails them (today's tests import it, which is why 6 and 7 survive).

| # | mutant | why it survives today | test (the rule it pins) |
|---|---|---|---|
| 1 | `width = max_chars + 1` | no test puts a clause opener right past the limit | "a comma at the limit before a clause opener ranks as a clause cut even when the opener lies past the limit": the window must hold the word after the last place that fits |
| 2 | `counts[-1] >= max_chars` | needs a window of 2·max+2 characters whose spoken text is exactly max_chars, so long white-space runs (the random search had at most double spaces) | "no utterance is over the limit when the text holds long white-space runs": the mutant then reads the whole rest as one utterance |
| 3 | `left` without `- 1` | the even share moves by one character; no test sits on the edge | "the cut nearest an even share counts the space at the cut once": a sentence whose two candidate commas are one character either side of the share |
| 4 | tie-break `i` for `-i` | no test has two candidates at the same distance | "on a tie the later cut wins, so the first part is the longer one" |
| 5 | `return after` never taken | needs a cut inside a replacement that opens the part | "a cut inside a replacement that opens the part moves to the replacement's end when that fits" (a document whose first piece is a replacement) |
| 6 | `MIN_PIECE = 30` | tests import the constant | "no part under 40 characters when another cut leaves none": a cut that would leave 35 is passed over |
| 7 | `MIN_PIECE = 50` | same | "a part of 45 characters is allowed": the cut that leaves 45 is taken |
Proof: the search script and a hand-mutant run (each mutant applied alone to a clean worktree, the three test files plus the
new ones run, baseline green first) go into `plans/b6-mutants/` and the PR body: every mutant killed. The PR's own new code
(`_label_again`, the reading rank) gets the same treatment: hand mutants of each condition, all killed, listed in the PR.

## 4. Sentence gate and corpus goldens

- **Floors** (en 1.000/1.000, de 1.000/1.000) hold: the natural sets read the same (the corpus utterances are identical, 2).
- **known-errors.toml:** no entry comes or goes. The four stress entries are #477 limits this PR does not touch.
- **stress-de.txt** gains the #479 shapes, our own sentences (CC0, as the file says), in the legal paragraph after
  "Satz 3 gilt hier nicht.": `Es gilt Abs. 2.` / `Abs. 3 gilt hier auch.` / `Es gilt Art. 3.` / `Art. 4 gilt auch.` /
  `Im Abs. 2. Teil steht mehr.` (one sentence). Checked: on main they fail the gate with two new FN (`Es gilt Abs. 2. | Abs. 3`, `Es gilt Art. 3. | Art. 4`); with the
  prototype the gate passes, so it holds the fix.
  Stress sets have no floor; no new error.
- **Goldens and snapshots:** none moves. The script text does not change anywhere (this PR changes only where utterances
  are cut); `test_app_corpus.ambr` holds scripts and reports, which do not hold cuts. No other lane's file is touched, so
  B13 and B11 PR 2 (which wait for B6 on `tests/sentences/`) merge main after this and regenerate nothing of mine.

## 5. Regression rows (written first, failing on main, then the rule)

`german.toml`:
- `de-label-again-ends-the-sentence` (#479): blocks `Es gilt Abs. 2. Abs. 3 gilt hier auch.` and
  `Es gilt Art. 3. Art. 4 gilt auch. Es gilt Abs. 2 Satz 3 hier.`; expected script as today (`Absatz`, `Artikel`);
  utterances `["Es gilt Absatz 2.", "Absatz 3 gilt hier auch.", "Es gilt Artikel 3.", "Artikel 4 gilt auch.",
  "Es gilt Absatz 2 Satz 3 hier."]`. Goal: the number between the same label word twice is the label's; its full stop ends
  the sentence. No "Im Abs. 2. Teil" in the row: its reading "zweiter Teil" is not one a row should lock in (lesson); the
  unit test pins its cut only.
- `de-long-sentence-not-cut-inside-a-reading` (#482): a sentence over 400 characters without a comma near the even
  share, with "u. a." and "3,5 %" right at the share; utterances pinned; goal: the cut falls before or after the reading,
  on a first and on a second run. (Wording: our own; the exact text is fixed when I write the row, so the share falls on the reading on main.)
`english.toml`:
- `long-sentence-not-cut-inside-a-reading` (#482): the same for "e.g." and "≤" ("for example", "less than or equal to").

## 6. Test-harness changes (all of them)

- **Second-run cuts** (new, both regression files): `test_the_utterances_cut_the_same_on_a_second_run` for every case with
  `utterances`: run 2 over run 1's script (`read_twice`'s rebuild, same switches) cuts into the same utterances. A
  `SECOND_RUN_CUT_EXCEPTIONS` dict, strict xfail as `SECOND_RUN_EXCEPTIONS` does, names the six rows that differ on main
  today, each with its reason: four where a removed citation or link ended the sentence after "et al." or "Fig." (the
  documented D-719 limit: "On a second run the removed text is gone, so the cut stays only where the rules make it"),
  `linked-endnote-on-another-page` (a moved note, #213: run 2 reads the note where it is printed) and
  `de-links-no-two-full-stops-after-an-abbreviation` (the German twin of the first kind). A helper `rebuilt(case)` is
  factored out of `read_twice` so both use one rebuild; `read_twice` keeps its behaviour and its callers. Nothing weakens
  the D-577 script check (lesson #484).
- `test_textprep_utterances.py`: the #533 tests of 3; the #479 cases (parametrized: cut / not cut, as in 1); the #482 cases
  (`unter anderem`, `3 Komma 5`, `zum Beispiel`, `for example`, `less than or equal to`, `dritten Mai`: a sentence cut on
  run 1 and on its rebuilt run 2 gives the same utterances), and a `_cut_point` case: a space inside a reading loses to any
  other space, and a reading space outside a bracket still beats any place inside one.
- No change to `make_document`, `rebuilt_from_script`, `said`, the regression loader or `SECOND_RUN_EXCEPTIONS`.
- The probes stay outside the repo (`plans/b6-mutants/`, `plans/b6-probes/fuzz2.py`, `fuzz3.py`, `corpus_utts.py`).

## 7. Checks before hand-off

Fast suite, ruff, format, lint-imports, deptry; the slow linear-time test of the cutter; Hypothesis `dev` profile on the
cutter and regression property tests with fresh `.hypothesis` plus 3 extra seeds; `fuzz2.py` (all 2,700) and `fuzz3.py`;
the corpus utterance diff main vs branch (both runs; expected: none); the #533 hand-mutant run; then `ci:full` (critical) and
Linux CI green before hand-off; `ci:full` removed after. Ledger line per PR. One CHANGELOG line under Fixed:
"Long sentences are no longer cut between the words of a reading such as "unter anderem" or "3 Komma 5", and German
"Abs. 2. Abs. 3" ends its sentence after the first number (#479, #482)." (#533 is tests only, no line.)

## 8. Follow-up issues to file (proposed milestone v1.2.x)

- F1: on a second run a cut can still move when every place near the even share is inside a reading (rank 5): run 1 moves
  its pick out of the replacement, run 2 cannot (`fuzz3.py`: 9 % of long sentences without punctuation, against 54 % on main).
- F2: German "10⁻³ d. h." keeps the power as printed on run 1 and reads "10 hoch minus 3" on run 2 (a second-run script
  break, D-577; found by `fuzz3.py`, reproduces on b32612d). Not a cutter bug; numbers/abbreviations rule order.
- F3 (if the review agrees): the same-label rule stops at a glued bracket, "(Absatz 2. Absatz 3)"; pinned as today.

Size: ~70 lines of rule code (reading rank ~55, same-label rule ~15), ~250 lines of tests and rows, 5 sentence lines.
Review: Opus high (critical), up to four rounds; final round ci:full, mutation, nightly seeds.
