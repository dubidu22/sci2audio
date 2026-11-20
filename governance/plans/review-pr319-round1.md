# Review: PR #319, round 1 (forward of release/1.0 b787309 into main)

14 Nov 2026 ~16:45 UTC on head 6c12d42, base main e9167e3.

**Verdict: approved, no fixes.** Merge by squash when CI is green on 6c12d42.

- Diff against main: CHANGELOG.md (the 1.0.0 heading dated 2026-11-14; main's [Unreleased] entries such as #237 kept), docs/baseline.md (#251's M4 rows), docs/listening-tests/1.0.0.md (new), pyproject.toml (Homepage dropped). Nothing else.
- docs/listening-tests/1.0.0.md, mutation.yml and release.yml are byte-identical to release/1.0's b787309. docs/baseline.md equals release/1.0's plus main's own German-voice rows from #211, so the merge kept both sides.
- `__version__` stays "1.1.0.dev0" (D-492). The #234 and #261 changes were already on main (#244, #262), so they show no diff.

**Merged** into main by squash pinned to 34bd9be (main cc7cae2 merged in first with update-branch; all CI green): aec6e6a (~16:55 UTC). Nothing deferred.
