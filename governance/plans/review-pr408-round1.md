# Review PR #408, round 1 (textprep batch 2 PR 3: #257 #258 #372 #375, pins #383 #384)

Head reviewed: 7056689. It is 2ebc2fe with main e517873 merged in. Plan: plans/textprep-v12-pr3-plan.md (D-668), with #258 implemented without the pause (D-676). Critical.

**Verdict: approvable at 7056689.** It closes #257, #258, #372, #375, #383 and #384. The heavy checks ran in this round. There are no fix items. Two leftovers are filed as #414 and #415, and both are as on main or better. Nothing is merged. The plan holds the merge until the v1.1 tag is cut.

## What I checked

- **Plan.** The change follows the plan, apart from the #258 pause (D-676). The PR body closes all six issues, and the commit messages carry no closing keywords. `mergeable_state` is clean.
- **Probes.** About 90 hand rows (en and de) ran through the whole chain twice, against main e517873. Every reading is the same on both runs.
  - **#257 pairs.** These read "references 1 and 3" or "Quellen 1 und 3": "Between [1] and [3]", "Zwischen [1] und [3]", "It holds [1] and [3] here.", "Compare [1] and [3] with [5]", "[1] and [3]:" and "[1] and [3, 4]". These are unchanged: "or" pairs, "in [1] and [3]" (both needed), "[0, 1] and [2]", "[1] and [3.5]" and unlisted keys "[MH17] and [Fa14]".
  - **#257 pages.** "[12, p. 3]" reads "reference 12, page 3", "[12, S. 3]" reads "Quelle 12, Seite 3", and "[12, pp. 3–5]" reads "pages 3 to 5". An aside "This holds [12, p. 3]." goes whole, and "[12, p. 3; 14]" stays as printed.
  - **#257 join words.** "We thank https://x.org and Smith" and "Wir danken https://x.org und Müller" read "We thank Smith" and "Wir danken Müller". These are kept: "and then run it", "from https://x.org and ran it", "at https://x.org and Smith helps", ", and Smith" and "and the team" (lower case, the same as main). The removed guard gives "We thank and https://x.org and Smith." → "We thank and Smith." (main: "and and Smith"). Accepted.
  - **#258.** "et al.", "Fig." and "Abb." before a link that ends the sentence now read with one full stop, also before ")" and "”". "u. a." and "e.g." keep their reading with its stop. "et al. https://x.org. https://y.org." still reads "et al..", as the PR body says, the same as main. The #258 shapes now read as one utterance, as their printed form without the link does (D-676). Accepted.
  - **#372 and #375.** All plan rows read as wanted in en and de: "Smith, Lee and Jones", "Smith and Lee", "Jones and Smith", "Müller, Lee und Schmidt", and "Data here." / "Daten hier." for the year shells. Separators "," and ";;", and ";" without spaces, also keep every name.
  - **The PR 2 changes the author flagged.** "1 %-Hürde" with a no-break space (U+00A0 or U+202F) now reads "Ein-Prozent-Hürde", as with a plain space (main: "ein Prozent-Hürde"). That is right, and it fixes a main defect. "pro m s²" reads "pro Meter Sekunde hoch 2", the same as main.
  - **The #383 and #384 pins.** "[Mn12] A. Bee", "a. F. CDs" (two utterances), "a. F. S. 2" (one utterance) and "BGS. 1 Hs. 2" all read as on main.
- **Corpus:** 13 documents against main e517873. Every file is byte-identical, including the work folders.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 6059 passed, 1 skipped.
- **Token fuzz:** 9,000 texts (seeds 10–12, en and de) from 52 tokens: pairs, page brackets, links, join words, abbreviations, subject nests, year shells, "1 %-Hürde" and "pro m s²". The whole chain ran twice against main. There were no crashes. Five texts differ on a second run on the PR only. All five are #405 shapes, which the PR now reaches: an abbreviation ("Fig.", "S.") before a removed bracket, then read on run 2.
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`; pairs, pages and nests, citations, links, links in brackets, conformance, runner): seeds 2024 and 123456, 590 passed each.
- **CI with `ci:full`** on 7056689: tests on ubuntu, macOS and Windows, browser, lint and layers, licences, security and CodeQL are all green.

## The author's mutation claims

**The method holds up.** `mut3.py` runs the unmutated code first and stops unless it passes. It copies `ROOT/src` for each mutant and runs ROOT's own `tests/unit/test_textprep_*.py` with `PYTHONPATH` set to the copy. Every KILLED line in `mut_final.txt` and `mut_pr2_final.txt` names a failing test that hits the mutant.

**My rerun.** I ran 16 mutants with the author's script on ROOT = 7056689. Each copy went to a private folder. The baseline passed in both runs.
- From `mutants_final.py`:
  - These are killed, as claimed: 1 (`bare`), 5 (the stop), 9 (glued number), 14 (REPLACE in a nest) and 21 (the year-shell rest). Each failing test hits its rule.
  - These survive, as claimed: 6, 11, 18, 19, 22, 23 and 24, the seven defensive guards. On a private copy of the source I applied each one to 15 more shapes (one-citation shells, ";;", "," and no separator, a lead word in a nest, triple pairs, a glued "and"). None changes a reading.
- From `mutants_pr2.py`:
  - These are killed: 24 (the year range from 1100), 32 (the first unit after "pro") and 41 (the variable's look-behind).
  - **1 (`"law": _WORD` in `_FOLLOWS`) survives, and it is equivalent.** Only the German list has a `before = "law"` entry (`de/abbreviations.toml:394`). `_place_fits` takes `_FOLLOWS_ANY_CAPITAL` for every language but English, and that holds the live `"law"` rule, whose mutant the author's PR 3 list kills (#0). As a nit, `"law"` could be dropped from `_FOLLOWS`, but nothing is asked.

## Leftovers, filed

- **#414:** a list of three or more brackets ("It holds [1], [2] and [3] here.") reads only its last pair. The PR reads "It holds, references 2 and 3 here."; main read "It holds, and reference 3 here.". The PR body names the shape but filed no issue. The PR's reading is no worse than main's, and it is better where the list is needed ("reference 1, references 2 and 3" against main's "reference 1, and reference 3").
- **#415:** older subject nests still lose names, the same on main and the PR: a year shell around one citation as the subject ("((Smith, 2019) 2021) is cited."), a lead word ("(see (Smith, 2019); (Lee, 2018))" reads "(see Smith)"), no separator, "; and", and ";;" after a flat item.
- Already filed by the author: #402 (a join word before a link) and #405 (the second-run shapes the fuzz finds).

## Fix list

None.

## Merged

Squash-merged pinned to 7056689 as **ffdd2f9** (D-683). All six issues are closed.
