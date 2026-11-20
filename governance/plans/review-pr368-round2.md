# Review PR #368, round 2 (textprep follow-ups PR 4, German numbers #334 #349 #249 captions)

Heads reviewed: 697ca15 (fix on a merge of main 0e830ee) and 7936a1c (main 3fcba56 merged in by this thread through update-branch; the merge adds only #369's quarantine mark in tests/browser/test_flow.py). Answer: plans/review-pr368-round1-answer.md. Critical.

**Verdict: not approvable yet. No blocker, two should-fix (S1, S2), one deferred (#370).**

## Round 1 items

- **S1, fixed.** `\d Punkt \Z`: "Der Punkt 3. Mai", "Im Punkt 2. Teil" and "Die Note war 2. Punkt 3. Platz" read as on main. "Kapitel 1.2.3. Tag" and the other #349 rows stay the same on both runs.
- **S2 and S3, fixed for the reported rows.** About 45 labels probed, whole chain twice, against main 739f69c. "Tabelle 2.1a", "Abb. S3.1", "FIG. 3.1", "Abbildung 1.2-1.4", "Abb. 3,1", "Abb. 3.1–3.4", "Abb. 3–5", "Abb. 3.1 bis 3.4", "Abb. 4.12.", "Abb. 10.000", "Tabelle 1.1.2019", "Abb. IV" and "Abbildungen 3.1-3.3" now read the same in notice and caption, on both runs. On main, 16 of them differed on run 2. English notices are unchanged.
- **N1, done.**

## Fix list

### Should-fix

**S1. With "Numbers and units" switched off, the notice still reads the label's numbers.** `_NoticeStep.find` calls `label_numbers_read` whatever the switches say, so the user's switch no longer holds for notices, and notice and caption disagree again:

| label, `switched_off={NUMBERS_AND_UNITS}` | caption | notice (PR) | notice (main) |
|---|---|---|---|
| `Abb. 3.1` | `Abbildung 3.1` | `Abbildung 3 Punkt 1 wird übersprungen.` | `Abbildung 3.1 wird übersprungen.` |
| `Abbildung 1.2-1.4` | `Abbildung 1.2-1.4` | `Abbildung 1 Punkt 2 bis 1 Punkt 4 …` | `Abbildung 1.2-1.4 …` |

Fix: read the label's numbers only when `Category.NUMBERS_AND_UNITS not in context.switched_off`, as `footnotes.py` already checks another step's category. Add a unit test with the numbers switched off (both rows above, read as on main) that fails on 7936a1c.

**S2. A fraction-shaped label is read out of its caption's context, so notice and caption disagree.** The label is read on its own, but the caption reads it with what follows. "3/4" before ":" stays as printed in the caption, so the notice turns a number the caption keeps, which is S2 of round 1 again. Each row reads the same on both runs; the first-run change is new and unlisted:

| caption text | caption reads | notice (PR) | notice (main) |
|---|---|---|---|
| `Tab. 1/2: Verlauf der Werte.` | `Tabelle 1/2: …` | `Tabelle ein halb wird übersprungen.` | `Tabelle 1/2 …` |
| `Abb. 3/4: Verlauf der Werte.` | `Abbildung 3/4: …` | `Abbildung 3 Viertel …` | `Abbildung 3/4 …` |
| `Abb. 1/5: Verlauf der Werte.` | `Abbildung 1/5: …` | `Abbildung ein Fünftel …` | `Abbildung 1/5 …` |
| `Abb. 2/3: Verlauf der Werte.` | `Abbildung 2/3: …` | `Abbildung 2 Drittel …` | `Abbildung 2/3 …` |
| `Abb. 12/13: Verlauf der Werte.` | `Abbildung 12/13: …` | `Abbildung 12 von 13 …` | `Abbildung 12/13 …` |

Controls that must stay as they are now: `Abb. 3/4 Verlauf der Werte.` and `Abbildung 3/4. Verlauf der Werte.` read "3 Viertel" in both caption and notice, the same on both runs (on main they differed on run 2).

Fix: ask the caption's own reading. When the caption text starts with its label, take `find_numbers_de(caption text)` and apply only the candidates that lie inside the label's span; otherwise fall back to reading the label alone, as now. Add the five rows and the two controls to `test_a_german_notice_names_the_figure_as_its_caption_reads`; the five must fail on 7936a1c.

### Nits

None.

### Deferred

- **#370** (v1.2, lane:textprep): `Tab. 3x` reads "3 mal" in the caption (another step) but "3x" in the notice, so run 2 differs. The same on main; it needs the whole chain's caption reading, which belongs with #362.

## Checks on 7936a1c

- Fast suite (`HYPOTHESIS_PROFILE=ci`): 5414 passed, 1 skipped. Three-system CI was running at the time of writing.
- Commit messages 697ca15 and 129cd65 carry no closing keywords; the PR body closes #334 and #349, and #249 stays open for #362.
- `ci:full` added. Mutants, nightly seeds and the 13 samples are left for round 3, which should be the approving round. Round 4 is the last before Colin.
