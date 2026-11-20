# Review PR #368, round 1 (textprep follow-ups PR 4, German numbers #334 #349 #249 captions)

Head reviewed: 0919637 (main 739f69c merged in). Plan: plans/textprep-v12-followups-plan.md PR 4 (D-605), D-615 (#249 captions only, formula part is #362). Critical.

**Verdict: not approvable yet. No blocker, three should-fix (S1–S3), one nit.**

## What I checked

- Change against the plan: #334 (date ranges with spaced or em dashes read "bis" and both dates as ordinals), #349 (no ordinal after the "Punkt" of a dotted section number), #249 captions (`Wording.label_point`). Closing list: #334 #349; #249 stays open for #362. Commit messages carry no closing keywords.
- Fast suite on 0919637: 5344 passed, 1 skipped (includes the regression cases and the corpus second-run test). Linux CI green.
- About 50 shapes probed, whole chain twice, main vs PR. Every new reading is the same on both runs, and the three #349 rows that differed on main now agree. The heavy checks (13 samples, mutants, nightly seeds, three systems) wait for the approving round.

## Fix list

### Should-fix

**S1. `_AFTER_PUNKT` blocks the ordinal after any word "Punkt", not only after the dotted reading.** `\bPunkt \Z` matches prose, so these change on the first run and are not listed:

| printed (de) | main | PR |
|---|---|---|
| `Der Punkt 3. Mai war gut.` | `Der Punkt dritter Mai war gut.` | `Der Punkt 3. Mai war gut.` |
| `Im Punkt 2. Teil steht es.` | `Im Punkt zweiter Teil steht es.` | `Im Punkt 2. Teil steht es.` |
| `Die Note war 2. Punkt 3. Platz.` | `… 2. Punkt dritter Platz.` | `… 2. Punkt 3. Platz.` |

The second run only ever meets "Punkt" as the numbers step's own reading of a dotted number, which always has a digit before it ("1 Punkt 2 Punkt 3. Tag"). Fix: require that digit (`\d Punkt \Z`), so the rule asks the same question the dotted reading answers. Add the three rows above as controls (they must read as on main), next to the existing #349 rows.

**S2. `label_point` turns points the caption itself keeps.** The notice now reads "Punkt" where the caption leaves the label as printed, so notice and caption disagree, which is what the case's goal rules out ("as the caption itself does"). Each reads the same on both runs:

| caption label | caption reads | notice (PR) |
|---|---|---|
| `Tabelle 2.1a` | `Tabelle 2.1a` | `Tabelle 2 Punkt 1a wird übersprungen.` |
| `Abb. 3.1a` | `Abbildung 3.1a` | `Abbildung 3 Punkt 1a wird übersprungen.` |
| `Abb. S3.1` | `Abbildung S3.1` | `Abbildung S3 Punkt 1 wird übersprungen.` |
| `FIG. 3.1` | `FIG. 3.1` | `FIG. 3 Punkt 1 wird übersprungen.` |

On main all four notices matched their caption. Fix: turn the point only where the numbers step reads it, i.e. digits on both sides with no letter glued before or after (`(?<![\w.])\d+(?:\.\d+)+(?![\w])`-style, matched against what `numbers_de` actually takes), and add these four rows to `de-notice-dotted-caption-labels` reading as their captions do. (For `FIG. 3.1` the caption keeps "FIG." while the notice expands it; that is pre-existing and fine.)

**S3. Two label siblings of #249 still differ on a second run (the same on main).** The notice keeps what the caption reads in words:

| caption label | first run notice | second run notice |
|---|---|---|
| `Abbildung 1.2-1.4` | `Abbildung 1 Punkt 2-1 Punkt 4 wird übersprungen.` | `Abbildung 1 Punkt 2 bis 1 Punkt 4 wird übersprungen.` |
| `Abb. 3,1` | `Abbildung 3,1 wird übersprungen.` | `Abbildung 3 Komma 1 wird übersprungen.` |

Fix either in this PR (read "-" between two label numbers as "bis" and "," between digits as "Komma", as the caption does) or file one v1.2 issue for both and name it in the PR body as out of scope. I'd take the issue route if the fix needs more than the two substitutions, since the general answer (notice reads the label through the numbers step) belongs with #362.

### Nits

**N1. Unlisted first-run changes of #334, all the same on both runs; list them in the PR table:**
- `Vom 3.4.2019 – 5.4. lief es.` → `… 2019 bis fünften April …` (was `bis 5.4.`)
- `Vom 3.4. – 5.4. – 7.4. lief es.` → `… bis fünften April bis siebten April …` (three-date chain)
- `Vom 1.3. – 11.3.2020 lief es.` → `… bis elften März 2020 …`
- `Am 3.4.2019 - 5.4.2019 lief es.` → `… bis fünften April 2019 …` (was `- fünfter April 2019`)
- `Am 3.4.2019 —5.4. lief es.` → `… bis fünften April …` (one-sided em dash)
- `Zwischen dem 3.4. – 5.4. lief es.` → `Zwischen dem dritten April bis fünften April` (reads oddly after "zwischen", but no worse than main's `– 5.4.`; no fix asked)

### Deferred

None yet (S3 may become one issue).

## Next

Round 2 is the approving round: S1/S2 rows must fail on 0919637, then 13 samples, mutants, nightly seeds and three-system CI on the fix head.
