# Review PR #371, round 3 (textprep follow-ups PRs 5–7)

Head reviewed: 81ba6a3 (751bd48 and 81ba6a3 on 0f43871). Answer: plans/review-pr371-round2-answer.md. Critical. The heavy checks ran on 0f43871 in round 2; this round re-checks the fix.

**Verdict: approvable at 81ba6a3**, provided the three-system CI below is green. It closes #326, #337, #338, #339, #278 and #342. #372 is deferred.

## Round 2 items

- **S1, fixed.** The check now tests `in ("(", "[")`. For a link bracket at the end of a block, the script piece is `Text` with span 0–4, the same as on main 82d9e0d. This holds for both `Text (see https://example.org)` and `Text [see https://example.org]`. "Text (more)", "Text (more) here." and the other round 1 rows are unchanged. Restoring `in "(["` makes the new script-piece test fail.
- **N1, done.** All three of my breaks now fail the tests.
- **N2, done.** A new first-run change, probed on both runs against main:
  - **Now removed with the link:** a "/" with white space on both sides. "(see https://example.org / Lee, 2019)" and its German, square-bracket, line-broken and "/ the code" variants now read "It holds here.", "It holds [Lee, 2019] here." and "It holds (the code) here."; main left "( / …)".
  - **Unchanged:** a slash glued to the address ("example.org/ Lee") or to the next word ("/Lee"), and a slash outside brackets.
  - **Partly removed:** "(see … / and Lee, 2019)" now reads "(and Lee, 2019)". Only one join goes. That is stable, and better than main's "( / and Lee, 2019)".
  - All of these read the same on both runs.
- **N3, done.** The PR table and the CHANGELOG are updated.

## Checks on 81ba6a3

- Fast suite (`HYPOTHESIS_PROFILE=ci`): 5507 passed, 1 skipped.
- Targeted breaks: 5 of 6 fail the tests. These fail: the empty-string check restored, the spaced-slash alternative removed, and the three N1 checks. One survives: allowing the slash without a space after it. That would also take "/" in "(see https://example.org /Lee, 2019)", which now stays as "( /Lee, 2019)", the same on main. Either reading is defensible and both are stable, so no fix is asked.
- Commit messages carry no closing keywords.
- CI with `ci:full` on 81ba6a3: all green on three systems. Main 3d66b93 (#364, CI only) landed meanwhile; merged in as 0285e3b (diff unchanged but CHANGELOG offsets), three-green, squash-merged as 342a8f5.

## Fix list

None. Deferred: #372.
