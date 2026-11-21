# Review PR #721, round 1 (v1.4.1 patch into release/1.4, #716)

Thread: review-infra-b-i2 (Opus 5.5). Head reviewed: 050fb99. Base: `release/1.4` at 5c18f8c (tag v1.4.0). Date: 2026-11-21.
**Critical: yes** (a release into `release/1.4`, plus packaging and the installers workflow; `bug`, `lane:infra`, `risk:high`, `ci:full`, `ci:installers`). Plan `plans/release-fix-716-plan.md` §4, approved as D-865.

**Verdict: approved, on one condition** (0 must-fix, 0 should-fix, 2 notes): the installers run 44910026784 on 050fb99 must finish green before the merge. It is still in progress.

## Verified

- Commits: a26c162, the cherry-pick (`-x`, "cherry picked from commit 9fe4bda…"), and 050fb99, the version.
- The cherry-pick against 9fe4bda (`git show` of both, `index` lines ignored): every hunk is identical except `CHANGELOG.md`.
  - There, the Fixed line goes into a new `## [1.4.1] - 2026-11-21` section instead of `main`'s Unreleased list.
  - `main`'s other Unreleased lines (#684, #693, #694) are **not** carried over, so nothing from `main` beyond the fix comes in.
  - The other 7 files match #718 hunk for hunk: the spec, `build_installer.py`, `installer_smoke.py`, `installers.yml`, the two docs and `test_installers.py`.
- The version commit 050fb99 changes only two files:
  - `src/sci2audio/__init__.py`: `__version__` 1.4.0 → 1.4.1, the only source of the version (`pyproject.toml` has `dynamic = ["version"]`);
  - `docs/installing.md`: the intro and the 8 file names → 1.4.1, and the 1.4.0 workaround line kept and reworded.
- No other version string is left that should change. The remaining `1.4.0` hits are history (the CHANGELOG, the checklist's "as 1.4.0", the workaround line and the #716 comments), fixed test inputs in `test_installers.py`, the `.iss` usage comment and the tester-report placeholder.
- The CHANGELOG `[1.4.1] - 2026-11-21` section:
  - It has the one-paragraph summary ("Nothing else changed; if 1.4.0 works for you on Windows or Linux, you need not update").
  - Its Download table holds the three 1.4.1 file names, and its First start lines say how to replace 1.4.0.
  - Its Fixed section holds the one #716 line.
  - The empty `## [Unreleased]` heading above it stays.
- CI on 050fb99:
  - Linux `CI passed`, `tests (ubuntu-latest)`, both browser shards, lint, licences and security are green.
  - Dispatch run 44910930275 is green on all three systems, `tests (macos-latest)` and `tests (windows-latest)` included.
  - Installers run 44910026784: ffmpeg ×3 and build ×3 are green. `installed` on macos-latest, windows-latest, ubuntu-22.04 and ubuntu-24.04 is **pending**.

## Findings

### Notes
- N1: `release/1.4` predates `.github/workflows/governance-pr-checks.yml`, so no `governance pr checks` or promised-tests step runs on this PR. That is expected: the release-branches ruleset requires `CI passed` only, and the promised tests are #718's, which passed there.
- N2: the CHANGELOG date is 2026-11-21. If the tag v1.4.1 is pushed on a later day, the release page still shows that date. release.yml checks only that the section is dated, so this is not blocking.

Verdict: approved. Merge on the coordinator's go, pinned to 050fb99, once installers run 44910026784 is green on all four `installed` jobs. In particular, `installed (macos-latest)` runs the Launch Services step on the 1.4.1 bundle.
