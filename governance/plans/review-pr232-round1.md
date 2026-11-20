# Review: PR #232, round 1 (D-492, main moves to 1.1.0.dev0)

14 Nov 2026 ~01:31 UTC on head 1c1d039, base main b25f192 (up to date).

- One line: `__version__ = "1.1.0.dev0"` (valid PEP 440 pre-release, sorts after 1.0.0 and before 1.1.0). Nothing else changes.
- No test, golden file or snapshot holds "1.0.0" as the app's version (`git grep` over src and tests: only an unrelated `q=1.0.0` header case). The README test does not read the version. CHANGELOG keeps its empty "Unreleased" section, so nothing to add.
- release.yml is unaffected: tags go on release/1.0 (D-490), whose `__init__.py` says 1.0.0.
- **Verdict: approved.** Squash-merge pinned to 1c1d039 when "CI passed" is green.

**Merged** 14 Nov 2026 ~01:34 UTC by squash, pinned to 1c1d039 (all CI green). Nothing deferred.
