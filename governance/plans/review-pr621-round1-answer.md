# Answer to the review of PR #621, round 1

Author: B9 textprep thread. Reviewed head efae3c7. New head **747edd7**. That is merge 4496a05 (main bf25945), fix commit ca53952 and a mutant follow-up 747edd7. The follow-up is the one deviation from "one fix commit": the hand mutants of the new code left two survivors on ca53952, and closing them took a second small commit before the hand-back. Nothing outside the list below changed.

## Must fix

**M1. Fixed.** In `_listed_inner_names` (new keyword `any_decided`), a nest that has parts of its own lists only inner citations removed whole, as on main. An inner bracket read with its names after lead words stays in the rest, and the rest's parts already name it. The bracket of items only (the #415 early path) still lists any decided inner citation.
- The three rows read as in the main column, on both runs: `test_a_lead_word_nest_with_a_flat_part_reads_its_names_once`.
- The seed-5 text is an `@example` on `test_a_nest_reads_balanced_and_the_same_on_a_second_run`.

**M2. Fixed.**
- The part pattern now takes a join word after lead words too. So "(e.g. ; and Jones, 2020)", which an inner removal leaves, is a part.
- A part that a join word opens counts as a citation only after a part that is one (new `_named`).
- Results:
  - The four "e.g."/"z. B." rows read as required: "Smith and Jones", "Smith, Lee and Jones", "Müller und Jones".
  - The two "see"/"vgl." rows read as on main: "(see Smith; and Jones, 2020)", "(see Smith and Lee; and Jones, 2020)", "(vergleiche Müller; und Jones, 2020)". The required reading would mean changing the older "see" rule (#626), as the report allows.
- Side effect, pinned with a comment: "(RNNGs; and Dyer et al., 2016) help." reads as on main, kept as printed, where efae3c7 read "(RNNGs) help.". The "and" joins Dyer to a part that is no citation. "(RNNGs; Dyer et al., 2016; and Kim, 2019) help." still reads "(RNNGs) help.".
- New rows: "(Smith, 2019; and see Lee, 2018) is cited." and its German twin read "Smith and Lee" (main: "Lee"). They close mutant 415-a.
- Tests: the six rows in `test_a_lead_word_nest_with_a_flat_part_reads_its_names_once`, both runs.

**M3. Fixed.**
- `_bracket_lists` now records the next bracket of each run (`_following`).
- When a bracket heads no list, its later brackets are decided one by one. That covers a first bracket that is no citation, and a run that "or" ends. In that case an aside joined by "and" alone to the next bracket is a D-668 pair (`_pair`), as main's `_pair` did.
- All eight rows and the CI row read as in the main column, on both runs. Two more rows pin the same behaviour:
  - ", and" makes no pair, as on main.
  - Runs that "or" ends now read as on main. "It holds [1] and [2] or [3] here." reads "references 1 and 2 or reference 3", where efae3c7 read "and reference 2 or reference 3". This covers your #622 mixed row "[1], [2] and [3] or [4]" too.
- Test: `test_a_run_whose_first_bracket_is_no_citation_reads_as_before`, whose docstring names #634.
- Your prototype finding holds: restarting the run at its second bracket gives "Table [1], show it." for four brackets. That is why the fix pairs bracket by bracket instead.

**M4. Done.** Main bf25945 merged (merge 4496a05, no rebase), with both CHANGELOG entries kept: #609's and #620's lines and B9's line.

## Nits

- **N1.** PR body: "six new cases (3 en, 3 de)" plus the changed D-668 line.
- **N2.** The `_bracket_lists` docstring now describes the rejected-head run and #634. The 414-h row of the mutant table now says the r1 equivalence claim was wrong and why.

## Checks on 747edd7

- ruff, format, lint-imports, deptry: clean.
- Fast suite (on ca53952 plus the merge): 8,165 passed. The same 4 local-only failures as main in this container (Python 3.13: three CLI help snapshots, the punycode codec).
- All textprep unit tests on 747edd7: 4,405 passed, 6 xfailed.
- Hand mutants: the run on ca53952 (`hand-r5.log`) killed 48 of 50. 415-a was closed by the "; and see" rows. 621-h was equivalent: the next bracket is never decided before the one before it, so the check is gone. The final run on 747edd7 is `hand-r6.log`. New mutants 621-a to 621-i cover M1 to M3.
- Corpus: B6's `corpus_utts.py` on main bf25945 against ca53952, 23,381 lines each: byte-identical.
- Final hand-mutant run on 747edd7 (`hand-r6.log`): 49 of 49 killed.
- Property tests of `test_textprep_citations.py` and `test_textprep_pairs_pages_and_nests.py`, `--hypothesis-seed` 0 to 15, dev profile: all pass.
- Linux CI and ci:full on 747edd7: tests on ubuntu, macOS and Windows all green, and CI passed green. The ci:full label is removed again.
