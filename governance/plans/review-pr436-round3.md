# Review PR #436, round 3 (textprep batch 2 PR 5: hidden runs, affiliation marks, figure alt text, link language)

Head reviewed: 23a43c0 (one fix commit on e94cf00, on main 7a3b3ec). Round 2: plans/review-pr436-round2.md. Critical, final round.

**Verdict: approvable at 23a43c0.** It closes #193, #93, #191, #428 and #434. There is no fix list. Three leftovers are filed: #445 (round 2), #448 and #449. Nothing is merged.

## Round 2 items

All rows were probed through the whole chain twice, against main 7a3b3ec.

- **B1, fixed.** A mark before a two-letter element symbol (`ELEMENTS`, the 104 two-letter symbols) is no affiliation mark. These keep their numbers on both runs:
  - "⁸⁷Rb Bose-Einstein condensates in orbit" (block start);
  - "condensation of↵⁸⁷Rb in microgravity" (line start);
  - "³He spin filters";
  - de "Kondensate aus↵⁸⁷Rb im Orbit";
  - "⁶Li", "¹⁷¹Yb, ⁸⁷Sr and ¹³³Cs".

  These still lose their marks: "¹UC Berkeley", "²AI Lab", "²Österreichische Akademie", "¹Example University" and the corpus rows. The two new regression cases (`affiliation-marks-not-before-element-symbols`, en and de) and the three new unit rows fail on e94cf00 source.

  **The ⁴⁰K → ⁴⁰Ca swap is accepted.** Main and the PR both read "40K" as "40 thousand", from the English numbers rule ("5K"). A golden case should not pin that reading. It now has its own issue, **#449**.
- **S1, fixed.** "Shown [1, 2 x y] here." (x and y hidden) is a test, `test_links_and_citations_read_the_text_without_hidden_runs[runs7]`, and it reads "Shown here.". Mutant 11 is killed by it. The PR body now says the two removals can touch.

## Checks on 23a43c0

- **Corpus:** 13 documents. Every file is byte-identical to e94cf00 and to acde859, so the 8 planned changes against main stand as reviewed in round 1. The corpus second-run test passes.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`, PR source): 6557 passed, 2 skipped.
- **Token fuzz** (`fuzz5.py` and `cmp5.py`) on new seeds, against main 7a3b3ec. There were no crashes.

  | family | seed | texts | PR-only second-run differences |
  |---|---|---|---|
  | `FAMILY=hidden` | 51 | 1500 | 0 |
  | `FAMILY=sup` | 52 | 1500 | 0 |
  | mixed | 53 | 3000 | 2 |

  Both mixed ones differ on main too once the hidden run is deleted from the text: de "size; 5 mg↵m² +" and en "size, results. [3] m²". They are #405 shapes.
- **Mutants**, with the author's `mut3.py` on a clean worktree of 23a43c0. The baseline passed.
  - These are killed: 0 (`if skip_start > at` → `if True`, by the S1 row) and 1 (the `ELEMENTS` check removed).
  - The author's `mut_pr5_r2.txt` shows 7 of 7 killed, each naming a failing test.
  - Together with rounds 1 and 2, every live guard in the PR has a test that fails without it. The one survivor left, `kept[span.end]`, is equivalent (round 2).
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`; hidden runs, affiliation marks, placeholders, links, citations, the English and German regression cases, conformance, runner, `rebuilt_from_script`):
  - Seed 2024: 1611 passed.
  - Seed 123456: 1610 passed and 1 failed, `test_textprep_runner.py::test_the_built_in_steps_never_fail_and_are_idempotent`. I rebuilt its falsifying example by hand: a TABLE block inside a "REFERENCES" section reads "" on run 1 and "A table is skipped." on run 2. That is the known **#410** (milestone v1.2). The same document fails the same way on main 7a3b3ec. Main passes this seed only because Hypothesis draws other examples there. Not caused by this PR.
- **CI with `ci:full`** on 23a43c0: `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)`, the browser run, lint and layers, licences, security and CodeQL are all green.
- The commit message carries no closing keyword. The PR body closes #193, #93, #191, #428 and #434.

## Leftovers (filed, v1.2, lane:textprep, risk:high)

- **#448:** the mass number of an isotope-labelled molecule in the title block is still removed: "¹³CO and C¹⁸O observations" reads "CO and C18O …", and "¹³CH₄" reads "CH4". The word after the mark ("CO", "CH") is no element symbol.

  The reverse: "¹Ca' Foscari", "²Co-design Lab" and "³In Silico Institute" keep their marks, which is the safe way to fail.

  This is a leftover rather than a round 4 blocker because a longer word list will not fix it. It needs a structural cue, for example counting "before an affiliation" only after the author line, and that deserves its own plan. The shape is narrower than round 2's B1, which is fixed.
- **#449:** a raised mass number before K ("⁴⁰K") reads "40 thousand", on main too.
- **#445:** a hidden run between a number and its unit (round 2).
- #431 and #405 were already filed. #434 is closed by this PR.

## Merge note

Main is now 71ca0aa (#444, web only), and the PR shows `behind`. `git merge-tree` of 23a43c0 with main is clean.

On the merge go, I will:
1. update the branch with a merge (update-branch);
2. confirm that the PR diff against the new main is the reviewed one;
3. dispatch the three-system run on the new head (critical PR, MRG-02);
4. merge pinned to that head, once `CI passed` and `tests (macos-latest)` and `tests (windows-latest)` are green on it.

## Merge (16 Nov 2026)

On the coordinator's go: main 71ca0aa merged into the branch (update-branch), new head 3d0a6e4. `git diff 71ca0aa 3d0a6e4` is byte-identical to the reviewed diff of 23a43c0. The three-system run on 3d0a6e4 is green: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, browser, CI passed. Squash-merged pinned to 3d0a6e4 as **6a2aeb3**. Closes #193 #93 #191 #428 #434. Follow-ups: #445, #448 (own plan), #449.
