# PR #698 review, round 1 (head 80f4459)

Reviewer: review-web-b-w2, Opus. 20 Nov 2026. PR: "web: quarantine the Firefox resume test (#697)", from main 44c59c2, `lane:web`, `risk:low`. Issue #697.
Critical: **no** (one test decorator; no golden, contract, workflow or critical path touched). The fix M1 asks for touches `.github/**`; done in this PR it makes the PR critical (CRIT-01, `risk:high`).
Verdict: **changes requested** (1 must-fix, 0 should-fix, 3 notes).

## Checked and fine

- **Diff.** One file, `tests/browser/test_flow.py:274-278`: `@pytest.mark.quarantined(issue=697, reason="...", browser="firefox")` on `test_resume_of_a_paused_replace_never_asks_to_replace_again`. Nothing else; CHANGELOG untouched (right for a test-only change).
- **Marker.** Registered in `pyproject.toml:155`; `tests/conftest.py:54-81` checks `issue` (positive int) and `reason`, refuses unknown keys and unknown browsers, and adds a skip "quarantined, see #697: ..." only when the item's `browser_name` is `firefox`. `tests/unit/test_quarantine.py`: 11 passed.
- **Other browsers.** Local `pytest tests/browser/test_flow.py -m browser --browser chromium`: 29 passed, the resume test among them, not skipped. Firefox collection shows the test with the quarantine banner; WebKit and Chromium collections carry no banner and keep the test.
- **Issue #697** (v1.4, `lane:web`, `risk:low`, open): names both failures (#689 at 13ec9c2 and #696 at 51daacd, same job, `test_flow.py:305`, `hold.reached.wait(30)`), and its acceptance criteria hold the fix-and-lift and the 40 runs per browser of D-682 after the quarantine.
- **Local run** (worktree /tmp/review-698 at 80f4459, macOS): ruff and ruff format green.
- **CI on 80f4459**: required checks green (`CI passed`, governance pr checks, `tests (ubuntu-latest)`, both Chromium shards, lint and layers, licences, security). Report-only: Firefox 2/2 pass; Firefox 1/2, WebKit 1/2, WebKit 2/2 fail (M1, N1).

## Must fix

**M1. The quarantine stops the whole Firefox shard 1/2 from starting, in CI and nightly.** `.github/scripts/browser_shard.py:37` keeps every line of `pytest --collect-only -q` that contains `::`. `tests/conftest.py:89-102` (`pytest_report_collectionfinish`) prints the quarantine banner into that listing, and its entry line `  #697 tests/browser/test_flow.py::test_resume_...[firefox]` contains `::`, so it becomes the first "test" of shard 1. `pytest @shard.txt` then gets `  #697 tests/...` as a path and exits with code 4 ("ERROR: file or directory not found"), before a single test runs (job 136528308952). Reproduced locally: `browser_shard.py firefox 1 2` writes 101 lines of 202 "tests", line 1 the banner entry; for chromium and webkit the file is clean (the banner filters by browser). Nightly uses the same script (`nightly.yml:156`), so the nightly Firefox shard 1 would run nothing too. The failure scenario is wider than this PR: any quarantine of a browser test without `browser=` or with `platform=` (the banner does not filter by platform) breaks the required Chromium shards on every PR. This is the first quarantine of a browser test since the shards came in (D-759), which is why the script never saw the banner.

What the entry must look like: the marker is right as written; no list file is involved. The banner is a report line, not a test ID, and the shard script must take only test IDs. Fix: `browser_shard.py` keeps only lines that start with `tests/` and contain `::` (probe: Firefox shard 1 then has 101 of 201 tests, no banner, and `pytest --collect-only "@shard.txt"` collects 101; the quarantined test stays in the list and is skipped by the marker). Add a unit test that feeds the script's filter a listing with a banner line and asserts only test IDs come out (META-03), e.g. beside `tests/unit/test_ci_workflows.py:138`. The script is under `.github/**` (lane:infra, critical path): either this PR takes the fix with `lane:infra` and becomes critical (`risk:high`, ci:full before merge), or an infra PR lands the fix first and #698 merges unchanged after it. Merging #698 alone is not acceptable: it would trade one skipped test for half of the Firefox suite.

## Notes

- **N1. The WebKit failures are neither #699 nor the resume test.** WebKit 1/2: `test_markers.py::test_m_in_focus_listening_marks_the_stage_sentence[webkit]` ("Marker set." not shown); WebKit 2/2: `test_updates.py::test_the_update_check_is_off_until_turned_on[webkit]` ("Clicking the checkbox did not change its state"). #699 names `test_joined.py::...stay_on_the_sentence...` and `test_player_figures.py::...figure_passes_axe...`. In the last 25 CI runs each WebKit failure was a different test (597a7b1: `test_focus.py::test_every_key_on_the_listen_page`, `test_markers.py::test_two_quick_presses_set_and_remove_in_order`; 51daacd: the two of #699). The PR cannot cause them (one decorator on a Firefox-only skip). It looks like general WebKit-in-CI flakiness, first occurrence for each of these tests; worth recording on #699 or a new Issue so a second failure triggers D-374.
- **N2.** The conftest banner (`tests/conftest.py:100`) lists a platform-limited quarantine on every system ("(on win32)"), but a browser-limited one only on its browser; harmless once M1 is fixed, mentioned for whoever touches the banner.
- **N3.** After the quarantine merges, the 40 solo runs per browser (D-682) are recorded on #697; not this PR's job.

## Handoff (THR-07)

- Goal: PR #698 merged with the quarantine skipping one Firefox test and nothing else.
- Done: round 1 at 80f4459, changes requested (M1).
- Next: round 2 after the shard-script fix (in this PR as critical, or in an infra PR first); check the Firefox 1/2 shard starts and runs its tests, and the new unit test.
