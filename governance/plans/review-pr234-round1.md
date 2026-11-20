# Review: PR #234, round 1 (mutation run on release/1.0, #80)

14 Nov 2026 ~01:52 UTC on head 71e3ff2, base release/1.0 b25f192 (up to date).

- Diff: `pyproject.toml` [tool.mutmut] gains `also_copy = ["scripts/", "README.md"]` (+comment); `mutation.yml` drops `|| true` (+comment). Nothing else.
- mutmut 3.8.1 (the locked version) reads `also_copy` (configuration.py: added to its own defaults tests/, pyproject.toml, uv.lock, ...) and copies files or trees into mutants/ (file_utils.copy_also_copy_files; a missing path is skipped silently).
- The PR body's exit-code claim checked in mutmut 3.8.1 `__main__.py`: `exit(1)` only on failed stats collection, no tests found, no mutated code covered, failed test listing, bad import setup, or a failed clean test run. Survivors do not fail the run. So the job now turns red exactly when the run breaks, and stays green with survivors.
- Root files tests read (grep of `parents[2]`): README.md (test_readme), scripts/speed.py, scripts/zap_scan.py, and the root for test_package_data (pyproject.toml, copied by default; README). All covered.
- Pending: the full branch run 43542564683 must end green with mutants actually checked, plus CI on 71e3ff2.

**Merged** (D-525, on the local evidence; the full branch run 43542564683 was not waited for): #234 into release/1.0 by squash pinned to 71e3ff2 → 87ba1f5 (14 Nov ~03:48 UTC). Forward cherry-pick PR #244 into main (same diff) merged by squash pinned to d5e3126, all CI green → 98eb92a (~05:42 UTC). Nothing deferred; the survivors report stays with the author thread.
