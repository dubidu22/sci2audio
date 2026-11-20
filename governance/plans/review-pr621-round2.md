# Review of PR #621, round 2 (final; textprep B9: #414, #415, #402)

Reviewer: B9 review thread (Opus high, critical). Reviewed head **747edd7** (merge 4496a05 of main bf25945, fix ca53952, mutant follow-up 747edd7; the second commit is accepted by the coordinator, D-805). Main is bf25945, so the base is unchanged and the PR merges cleanly. 19 Nov 2026.
Verdict: **approved.** No must-fix item. Test gaps from my mutants are filed as #646 (v2).

## Round 1 items

| item | check on 747edd7 | result |
|---|---|---|
| M1 unbalanced lead-word nest | the three rows, en/de, both runs; seed-5 `@example` on the property test | read as on main ("Smith and Lee, Jones is cited.", "Müller und Lee, Jones wird zitiert."); balanced |
| M2 "; and" drops a name | the six rows | four "e.g."/"z. B." rows read as required ("Smith and Jones", "Smith, Lee and Jones", "Müller und Jones"); the two "see"/"vgl." rows read as on main, the fallback the report allowed (#626) |
| M3 run whose first bracket is no citation | the eight rows + CI row, both runs | all read as on main; "CI [1, 3] and [12]" unchanged |
| M4 merge main | `mergeable_state: clean`, both CHANGELOG entries kept | done, by merge, no rebase |
| N1, N2 | PR body, `_bracket_lists` docstring, 414-h row | corrected |

Side effects checked: "(RNNGs; and Dyer et al., 2016) help." back to main's reading (pinned); runs that "or" ends read as on main again, so #414's "or lists stay as today" now also holds for the mixed rows I had put on #622 (#622 comment updated).

## Final-round checks

- **All round 1 probe files** (115 en, 30 de, the 42-row lead-word grid, flat forms, label/sign runs) on 747edd7 against main bf25945: no unbalanced output, no second-run change; every difference from main is a row of the PR's tables or a round 1 required reading.
- **Property tests**, dev profile, `--hypothesis-seed` 0 to 15, 31337 and 2024, over `test_textprep_citations.py`, `test_textprep_pairs_pages_and_nests.py`, `test_textprep_links.py`, `test_textprep_links_in_brackets.py`, `test_textprep_links_citations_de.py`: 18 × 815 passed.
- **My own hand mutants** of the round 1 fix code (13, not the author's 621-a to 621-i; author's harness, clean worktree of 747edd7, baseline PASS): killed R2, R5, R6, R12, R13. Survivors:
  - R1 `_pair` without the "and in before" check: equivalent for both built-in word sets (each holds its "and"); the same guard as `_needed_pair`.
  - R7 pair's second bracket not marked, R10 removed-whole check reduced to "one edit": 0 of 12,000 random texts differ (my `fz.py`, seeds 1 to 3, lists, nests, labels, links), so equivalent in effect.
  - R3, R4, R9 (lead words, capital "And", "&" in the join-word paths) and R11 (pair reason text): the head reads the rows right but no test pins them → **#646** with each row.
  - R8 `_following` not reset per look: no difference reachable in one-block texts; in #646.
- **Corpus** (B6's `corpus_utts.py`, 13 sources, three settings, both runs): 23,381 lines, byte-identical to main bf25945.
- **Three-system CI** on 747edd7: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` and `CI passed` green.
- **Nightly** (slow on three systems + property-based with the nightly profile) dispatched on the branch at 747edd7, run 44493049898: see the merge note below.

- **Nightly** run 44493049898 on 747edd7: slow tests on ubuntu, macOS and Windows and property-based tests (nightly profile) all green.

## Merge

Main moved to e45d655 (#631) after the review; it changed CHANGELOG.md, which the PR also touches, so per MRG-03 the branch was updated by merge (update-branch, head f5b5ad6). The PR diff against its base is unchanged apart from the CHANGELOG hunk's line offset. Three systems and `CI passed` green on f5b5ad6 (ci:full on, removed after). Squash-merged pinned to f5b5ad6 at 09:37Z: **9f2cbaa**. #414 #415 #402 closed.
