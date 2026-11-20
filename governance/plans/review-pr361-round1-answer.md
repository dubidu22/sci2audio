# PR #361, answer to review round 1

New head: 56508a4. It holds the fix commit on a merge of main 0af10d0 into 44998bb, with no force-push. ci:full is set. Every item is fixed and nothing is deferred.

- **S1, fixed:** `numbers._CARET` gives the grouped exponent the optional sign `[+−-]?` that the bare one takes. `_grouped_digits` now skips a number right after a caret and a sign, not only right after a caret. A mutation check showed this is needed: with the old skip, 7 tests fail.
  - "10^-250 000 000", "10^+250 000 000" and "10^−250 000 000" read "10 to the power of (minus) 250,000,000" on both runs.
  - They are three new rows in `numbers-powers-with-grouped-or-glued-exponents`, in `test_minus_signs_and_powers_that_read_the_same_on_a_second_run` and in `test_the_whole_chain_reads_these_the_same_on_a_second_run`. They fail on 44998bb.
  - The PR table lists the first-run changes.
- **N1, fixed:** a unit-test row now pins that "It is 10^250 000 000 5 here." stays as printed. That row fails when the grouped look-ahead is removed.
- **N2, done:** the PR table now lists "~+↵5" → "about + 5", and the German "~+↵5" → "etwa + 5" and "~−↵5" → "etwa − 5". I probed main and the branch: main reads "~+ 5" / "~− 5", and all three read the same on both runs.

Checks on 56508a4:
- Fast suite: 5305 passed, 1 skipped, 2 xfailed (#320 and #321, which #359 removes).
- ruff, ruff format, lint-imports and deptry are clean.
- All 13 corpus documents are byte-identical to main.
- Nightly seeds 7, 555 and 8080 on numbers, units and runner are clean.
