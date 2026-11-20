# PR #698 review, round 2 (head f7e818a)

Reviewer: review-web-b-w2, Opus. 20 Nov 2026. Author's answer: plans/answer-pr698-round1.md (governance 59bee80). Issue #697.
Critical: **yes** since round 1's fix touches `.github/scripts/browser_shard.py` (CRIT-01, D-851); labels `lane:web`, `lane:infra`, `risk:high`.
Verdict: **approved** (0 must-fix, 0 should-fix, 2 notes). Merge needs the coordinator's go and a green three-system run on the final head (the coordinator checks the `ci:full` run on f7e818a).

## Round 1 findings

- **M1 fixed as D-851 decided.** `browser_shard.py:17-21` `browser_tests(listing)` keeps only lines that start with `tests/` and contain `::`; `main()` uses it (`:45`). Test `tests/unit/test_ci_workflows.py::test_the_browser_shard_reads_only_test_ids_not_the_quarantine_banner`: a listing with the banner header, the indented `#697` entry and the summary line gives exactly the three test IDs. It fails on the old filter: with `browser_tests` changed back to `"::" in line`, the test fails (and on 80f4459 itself it fails because the function is missing). Local probe: `browser_shard.py firefox 1 2` writes 101 of 201 tests, none with `#697`. `nightly.yml:156` calls the same script with no other change, so the nightly Firefox shards are fixed too.
- **N1** (WebKit flakes), **N2** (banner filters), **N3** (40 runs on #697): no action in this PR, accepted.

## Checks

- **Fix-commit diff 80f4459..f7e818a**: `.github/scripts/browser_shard.py` (+8/-1) and `tests/unit/test_ci_workflows.py` (+32); nothing else; no workflow file changed.
- **Local** (fresh worktree /tmp/review-698 at f7e818a, macOS): ruff, ruff format green; `zizmor --offline .github/workflows`: no findings; `test_ci_workflows.py` and `test_quarantine.py`: 39 passed.
- **CI on f7e818a (Linux)**: `CI passed`, governance pr checks, `tests (ubuntu-latest)`, both Chromium shards, lint and layers, licences, security green. Report-only: Firefox 1/2 (99 passed, 2 skipped) and 2/2 (96 passed, 4 skipped, among them `test_flow.py:274` "quarantined, see #697") both pass, so the quarantine now skips exactly one Firefox test; both WebKit shards pass.

## Notes

- **N4.** The new test writes the banner by hand; if `tests/conftest.py`'s banner ever printed an entry starting with `tests/`, the filter would let it through again. Building the listing from `pytest_report_collectionfinish`'s own output (or a shared constant for the entry's prefix) would tie the two together. Optional.
- **N5.** The docstrings cite "(#698)" and "(#698 review M1)"; the sentences say why, so not a narrating-comment finding, but "review M1" points at a governance file; "(#698)" alone would do.

## Handoff (THR-07)

- Goal: PR #698 merged.
- Done: round 2 at f7e818a, approved.
- Next: on the coordinator's go, `ledger_tool.py gate 698`, check `tests (macos-latest)` and `tests (windows-latest)` on the final head, squash-merge pinned to it.
