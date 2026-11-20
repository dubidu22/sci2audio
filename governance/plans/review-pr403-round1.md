# Review of PR #403 (v1.1.0 R1), round 1

Reviewed head **6fb9b6e**, base `release/1.1` (a9e0e2d). Critical (packaging/release), Opus high. Review thread "Review the v1.1 release PRs", 15 Nov 2026 ~22:55 UTC.

**Verdict: changes needed.** One blocker: Windows is red in 3 of 5 runs on this head because of a real fault in v1.1 code (from #378), not in R1. Three CHANGELOG corrections. The #365 fix is right and proven.

## What was checked

| Check | Result |
|---|---|
| Diff | 5 files: CHANGELOG, README line 5, `__version__`, two browser test files. No `src/` change besides the version. No behaviour change hidden in R1. |
| Version strings | Single source `src/sci2audio/__init__.py` (hatch dynamic version); `pyproject.toml` has no literal; uv.lock holds no version for the project; CLI `--version` prints `sci2audio 1.1.0`; no doc or golden holds `1.1.0.dev0`. `uv build` gives `sci2audio-1.1.0.tar.gz` and the wheel, METADATA `Version: 1.1.0`. |
| Release workflow checks (local) | The date grep refuses `## [1.1.0] - unreleased` and passes on a copy dated 2026-11-16; the release-notes awk extracts 57 lines (summary to last Development line). |
| CHANGELOG completeness | All issue numbers in the 51 commit subjects since v1.0.0 appear in the 1.1.0 section (script). 83 issues were closed since the 1.0 branch point; those not cited: #247 #331 (duplicates), #351 #380 (not planned), and **#291** and **#298** (completed, see C2, C3). |
| CHANGELOG accuracy | German examples run through `sci2audio script` on 6fb9b6e: "z. B.", "S. 12", "5 km", "1 kg", "u. a. 2019", "2,45", "2 Mio. Euro", "2 Std. Danach", "17 von 20", "3 zu 1", "13:30 Uhr", URL removal, "pro Std.", "i. S. v.", "i. V. m.", "S. 12 f.", "p. a.", "Az. 13 W" (no "Watt") all read as written. English: grant number "(0801700)" removed, "PM10" kept. **"[MH17]", "[Knu84]", "[GKL+19]" are NOT read as citations without a reference list that prints them as entry labels** (C1). |
| #365 race | `settled()` waits for `#document[data-events]` count 0 (the state), then load and app.css: no timeout widened. Proof by a probe (in-process server, the analysis job held after its report is written, so the page shows the summary while it still follows the job): **without `settled` 3 of 3 runs fail with "Page.evaluate: Execution context was destroyed"; with it 3 of 3 pass.** Probe deleted afterwards. |
| Other axe calls | Swept all 72 `check_axe` calls. The German twin `test_errors_in_german_with_the_apps_words` (damaged file, test_german.py:221) has no `settled`, but it cannot race: the page shows `#analysis-error` only when no analysis is followed (`pages.py:390-394`), so a page with the error never has `data-events` (N1). |
| Quarantine | `pytest -m quarantined --collect-only` collects none. |
| Local fast suite | 5877 passed, 1 skipped (Linux). |
| CI on 6fb9b6e | Linux 6/6, browser 6/6, macOS 5/5 green. **Windows 2 of 5 green**: runs 43768865178, 43768867644, 43768874878 fail, all in `tests/unit/test_app_chunks.py::test_the_default_folders_come_from_platformdirs`. |

## Fix list (exact)

**B1. Windows: `file_id` returns a stale id for a file rewritten in place within one clock tick.** `src/sci2audio/app/config.py:62-76` (from #378) caches the hash under `(st_ino, st_mtime_ns, st_size)`. Rewriting the same file with content of the same size keeps the inode and size, and on Windows often the mtime, so `default_work_folder(copy) != work` fails (test_app_chunks.py:188). Reproduced deterministically on Linux: rewrite with the same size, `os.utime(ns=...)` back to the first stat, and `file_id` gives the old id. Fix:
  1. In `file_id`, hash the file directly (no cache) when `time.time_ns() - stat.st_mtime_ns < 2_000_000_000` (a racy-file guard, as git does); keep the cache for older files.
  2. A unit test: write a file, take `file_id`, rewrite it with other bytes of the same size, set its times back with `os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))`, assert a different id. It must fail on 6fb9b6e.
  3. A unit test that a file whose mtime is older than 2 s (set with `os.utime`) is opened once over two `file_id` calls (keeps #154's "read a big file once").
  4. Keep the existing test unchanged. Then run CI three times on the new head with Windows (workflow_dispatch) and put the run ids in the PR body.
  No CHANGELOG line (it fixes unreleased #154 code).

**C1. CHANGELOG line "Alphanumeric citation keys are read as citations (#254)":** say that this happens when the document's reference list prints those keys as its entry labels (the #377 B1 guard); without such a list "[MH17]" is read as printed. Verified on 6fb9b6e: without a list the script keeps "[MH17] and [Knu84]" and "[GKL+19]"; with one it reads "reference MH17" and leaves "[GKL+19]" out.

**C2. CHANGELOG line "Citations read the same on a second pass (#305, #306, #308, #309, D-577)":** add #291 (a citation nest whose rest is a mixed list or a bare year; closed by 99b8166, PR #330).

**C3. CHANGELOG Development line "Text-step timing tests compare against a baseline run on CPU time …":** cover extraction timing tests too and add #298 (done in PR #327).

## Not changed (noted)

- **N1.** test_german.py:221 needs no `settled` (reason above); adding it for symmetry is allowed but not asked.
- **N2.** The plan (section 3) promised a table of all 51 commits in the PR body; the body has a grep-loop statement instead. This review's own check covers it; no change needed.

## Deferred (issues filed)

- **#406** (v1.2, lane:textprep): German "Az." before a file number ends the sentence ("Das Gericht hat im Az." / "13 W 17/12 entschieden."). Present on main; not a regression of R1.
- **#407** (v1.2, lane:web): `load_readalong` caches under `(st_mtime_ns, st_size)` without `st_ino`, so on Windows a replaced read-along file of the same size can be served stale. From #78 (v1.0).

## Round 2 will check

B1 test fails on 6fb9b6e and passes on the new head; Windows green in three dispatch runs plus the PR run on one head; C1 to C3 wording; diff touches nothing else.
