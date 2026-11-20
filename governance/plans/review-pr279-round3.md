# Review of PR #279, round 3 (#271 nested citations)

Reviewed head b2e5fcc against main 4cfff38 (which includes #277), 14 Nov 2026. Earlier rounds: review-pr279-round1.md and review-pr279-round2.md.

## Verdict

Approved, and merged by squash.

## Round-2 items, verified

- **M1 (subject nest whose inner citation keeps its names):** fixed. `_with_inner` brings in the inner edits that lie inside the kept names, and declines when edits would cross. `_covered` stops the inner bracket from being visited a second time. All nine shapes in the round-2 table now read correctly on both runs, in en and de, with balanced brackets. For example, `(see (Smith, 2019) 2020) found it.` reads "Smith found it.", and de `(vgl. (Müller, 2019) 2020) zeigt das.` reads "Müller zeigt das.". They are pinned in `test_a_nest_that_keeps_inner_names_reads_the_same_on_a_second_run`, and the new Hypothesis property `test_a_nest_reads_balanced_and_the_same_on_a_second_run` guards them.
- **M2 (page glued inside a nest):** fixed. `It holds ((Smith, 2019)[p. 4] Jones, 2020) here.` reads "It holds here." on both runs, and the German `[S. 4]` shape does too. Both are pinned.
- **N1:** added to #291 (checked on the issue). #291 is open, in milestone v1.2, and linked in the PR body.

## Checks on b2e5fcc

- **Hand shapes:** every hand shape from rounds 1 to 3 (about 160), main against PR, whole chain, two runs. No reading that is balanced as printed comes out unbalanced. Five shapes are still unstable on the second run, all known: two D1 shapes (#291), two N1 shapes (#291) and the link shape (#102).
- **Random nest fuzz:** 12,000 texts (seeds 7, 11, 13 and 99), main against PR. Unstable texts fixed: 61, 53, 46 and 36. Newly unstable: 0, 2, 0 and 4, all the N1 shape (an emptied nest before a bare year, #291). Newly unbalanced: 0.
- **Corpus:** the 13 scripts and 26 reports are byte-identical to main 4cfff38.
- **Timing:** going from 1,000 to 8,000 nests multiplies the time by 7.6 to 8.5 on every shape. 8,000 flat nests take 0.80 s. The `[nests]` case runs on `assert_linear`, and the `shift = 0` mutant fails it (verified in round 2).
- **Suites:** fast suite (ci profile) 4,345 passed, 1 skipped. ruff, lint-imports and deptry are clean. Nightly profile with my own seeds 4242 and 2718: 635 passed each.
- **CI:** all 12 checks are green on b2e5fcc, and GitHub reports the PR as mergeable.

## Deferred

- #291 (v1.2): a nest whose residual is a mixed list or a bare year, including one reached through an emptied nest (N1).
- #278 (v1.2): an empty bracket left in place (`((Smith, 2019); Jones, 2020)`, `((Smith, 2019)) is cited.`).
- #102 (v1.0.1): a citation bracket holding a link. Through the whole chain it needs two runs, both here and on main.

## Merge

Main moved twice after approval, first with #297 (test-only, CPU-time timing) and then with #289 (layout code listings). I merged main into the branch both times (039edf2, then 1186262). After the second merge, the fast suite passed (4,415) and the corpus was byte-identical to main 12944c8. CI was green on 1186262.

Squash-merged at 2026-11-14T14:50:17Z as 34303e1a97b82861e50a0a58d120febc13cb22bf. #271 is closed.
