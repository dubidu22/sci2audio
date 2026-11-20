# Review of PR #524 (#494, cut limit 300 → 400), round 2 (final)

Reviewed: fix commit **1b27a7f** (on 8ccb353, which merges main f2aea0e per D-756). Merge head after my merge of main 158f1ae (#530): **6bfe161**.

**Verdict: APPROVED, 0 new findings.** The merge waits for the three-system run and the nightly run on 6bfe161 (below).

## Round 1 findings
- **B1 fixed.** `test_a_closing_mark_of_an_inline_list_opens_no_bracket_for_cutting` passes `max_chars=SIZED_FOR` and asserts `len(parts) > 1`. The #481 round-2 mutant (`depth = depth - 1`) is now killed by both cases again (en and de), as on main.
- **S1 fixed.** New rows `long-sentence-colon-past-the-first-window` (607 characters, colon at 462, cut 124 + 338 + 143) and `de-long-sentence-colon-past-the-first-window` (610, colon at 484, cut 111 + 373 + 124): the first window is cut at its ", which" / ", dass" comma, not at a later list comma, and the colon comes next. Own wording; goals state the rule.
- **S2 fixed.** The body lists all 12 joins with the word pair at each cut that went. Correction to my round 1: they are 12 sentences with one join each, not 11 sentences. Two of them ("Während manche deutsche Gerichte …", "Hierfür ist im Rahmen des Artikel 32 …") still have their other cut, as the body says.
- **S3 fixed.** The body names `PREVIEW_LIMIT` in `web/models.py`, and #534 (lane:web) is filed and listed under Out of scope.
- **N1 fixed.** One blank line on each side of every new row.

## Other changes in the round
- `tests/unit/test_web_joined.py`: only `LONG` changes, to the sentence of `tests/browser/test_joined.py` (456 characters, cut 136 + 319 at 400). #523's new test needs the later piece to be the longest. The change is listed in the body as a test-harness change. It follows from D-753 and D-756.
- The merge 8ccb353 brings in only main: `git diff f2aea0e 8ccb353` lists exactly the PR's 11 files.

## Final-round checks
- **Merge of main.** I merged main 158f1ae (#530, layout) into the branch as 6bfe161. The merge was clean, and the corpus snapshot did not conflict. `git diff origin/main 6bfe161` is byte-identical to `git diff f2aea0e 1b27a7f`, so the PR diff is unchanged. Fast suite on 6bfe161 locally: 7036 passed, 3 skipped.
- **Mutation.** The round 1 probe of the cut logic: 20 of 27 mutants killed, and the 7 survivors also survive on main (#533). The fix commit changes tests only, and B1's mutant is killed again.
- **Nightly seeds.** Round 1 seeds 555, 8080, 31337 and 20261118 were green on the cutter, sentence and regression tests. The fix changes no Hypothesis test. I dispatched the whole nightly workflow on the branch to cover the rest (run 44332652709).
- **Slow tests.** The author's comment shows the 4 A1 tests green with the real voices and whisper. The whole slow suite did not finish locally, so the nightly run above covers it on Linux, macOS and Windows. A failure that main's last nightly also has does not block (D-731).
- **Three-system run.** I added `ci:full` on 6bfe161 (run 44332659795).

## Merge
Squash-merge pinned to 6bfe161 once the three-system run and the nightly run are green, with no failure of this PR's own. Before the squash, I grep the commit messages for closing keywords, and the squash message closes #494 only.
