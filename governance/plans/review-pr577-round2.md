# Review PR #577, round 2 (final round, critical)

Reviewed: fix commit **a1ddddd** (R1 to R3 of round 1). Verdict: **approved, merged** as **ee02e56** (squash, pinned to a1ddddd). #187 closed; #442 stays open for part 3.

## Round-1 items

| Item | Result |
|---|---|
| R1 exit code 5 | README and `EXIT_CODES_HELP` say "…, or its text can't be read". `test_cli_golden.ambr` changes by exactly that one line, and the PR body names it. |
| R2 Hypothesis reach | The new `mixed_pdfs()` strategy always holds at least one unreadable page (glyph numbers, U+FFFD or private use), with varied counts. The property asserts the pages and the rule. I re-ran it with nightly seeds 1, 2 and 3: green, 22 tests. The author measured 100 % reach, with about 62 % of examples stopping and the rest warning. |
| R3 warning first | `test_the_unreadable_warning_comes_before_every_other_warning` (with the language fallback warning second). It kills m8. |

## Final-round checks

- **Mutation:** the clean baseline is 158 passed on the 8 affected test files, and **20 of 20** hand mutants are killed, m8 included.
- **Nightly seeds:** the two Hypothesis properties of `test_app_readability.py` pass with seeds 1, 2 and 3 under the nightly profile.
- **Three-system run:** Linux and ci:full on a1ddddd are green on ubuntu, macOS and Windows, with Chromium shards.
- **MRG-03:** main is at 0a72357 (#572). The only file both changed is `CHANGELOG.md`, and `git merge-tree` merges cleanly, so no branch update was needed (the same ruling as #569).
- **D-768:** the CHANGELOG line is present and accurate.

## Notes

- N1 to N3 of round 1 stand: an empty project folder after an API-started job; the stop is whole-document; #442 stays open for part 3.
- #583 must merge main again after this merge (both add CHANGELOG lines).
