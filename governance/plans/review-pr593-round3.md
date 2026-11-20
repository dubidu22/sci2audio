# Review of PR #593, round 3 (textprep batch B5): APPROVED and merged

Reviewed head: **11e325c** (tests-only commit on 5b6c114). Main since review: #582, #513 to #515 and #600, which share only CHANGELOG.md with this PR. GitHub reports the PR mergeable and clean, so there is no branch update (MRG-03).

- **T1 and T2:** the three cases are added word for word. Run against `test_a_second_run_reads_nothing_new` at 11e325c, all four mutants fail one case each (mask with the first glyph, `pieces =` for `+=`, and `continue`→`break` on the Uhr guard and on the hundred guard). The head passes 135 of 135.
- **Three systems on 11e325c:** CI run 44450998893 (workflow_dispatch) has `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)` green, and `CI passed` green.
- **Merged result checked locally:** I merged main a9dad14 with 11e325c and ran the fast unit suite: 7,703 passed, 4 failed. The same 4 fail on plain main in this session's Python 3.13: three `test_cli_golden` help texts and the EPUB `punycode` codec case (#587). None is caused by this PR.
- **Round-2 evidence still holds:** no source file changed since 5b6c114. That covers the three systems, nightly seeds 2024 and 8080, the arrow grid (0 unstable), the corpus (identical) and the mutation runs.

Merge: squash, pinned to 11e325c.
