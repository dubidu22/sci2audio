# Review PR #450, round 3 (final), and merge

Head reviewed: aba42a2, which is one fix commit on a779d66. It changes only `tests/unit/test_textprep_conformance.py` (+61). Critical. Rules: D-707 and D-710 (behaviour reading).

**Verdict: approvable at aba42a2. Merged as 7cd84bd.**

## Round 2 items

- **S1, fixed.** `test_every_placeholder_is_checked_on_its_own_output` uses my shape: "ﬁ" in a formula, and an "e" doubled in a table. It checks that block 1 is refused and block 0 is not.
- **S2, fixed.** `test_a_text_block_read_by_a_placeholder_is_not_checked_on_its_own_output` uses the dirty/clean figure with the X/Z paragraph. `check_text_step` passes it.
- **Mutants** (`mut6.py` on a clean worktree of aba42a2, baseline passed):
  - the author's 26 is killed by the S2 test;
  - the author's 34 (`inside[:1]`) and my identical mutant are both killed by the S1 test.
  - The body's tally of 30 of 35, with 5, 8, 17, 19 and 28 as equivalent, matches my runs from rounds 1 to 3.
- **Fast suite** (`HYPOTHESIS_PROFILE=ci`): 6652 passed, 2 skipped.
- **CI.** `ci:full` was on, and the run on aba42a2 is green on Linux, macOS and Windows.
- **What carries over from round 2.** The source is unchanged since a779d66, so the round 2 results stand:
  - corpus byte-identical;
  - caption fuzz: main 16,080, PR 0;
  - nightly seeds 2024 and 123456 green;
  - the three D-710 checks.

## Merge (16 Nov 2026)

On the coordinator's go:
1. I merged main 1bace26 into the branch with update-branch. The new head is b26e993.
2. `git diff 1bace26 b26e993` is byte-identical to the reviewed diff of aba42a2.
3. CI on b26e993 is green, including `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, browser and `CI passed`.
4. I squash-merged pinned to b26e993 as **7cd84bd**.

It closes #374, #370, #362 and #410. Textprep batch 2 (D-646) is now complete, so the batch audit of PRs 5 and 6 can start.
