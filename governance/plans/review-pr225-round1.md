# Review: PR #225, round 1 (R2 of #80: version, changelog, README, licences, learning note)

Reviewed 14 Nov 2026 ~01:40 UTC on head bccc055 (base f1a334a). Critical (risk:high, release). Checked against plans/issue80-release-plan.md s.2 and s.7, CLAUDE.md, .claude/rules.

**Verdict: three fixes needed (F1 to F3).**

## Checked and correct

- `__version__ = "1.0.0"` (D-484). No file in the tree still holds `0.0.1`; no golden file, snapshot, regression case or truth file changes.
- README: no third-party text. The before/after paragraph is written for the README (fictional citation, `example.org` is reserved), so `tests/corpus/LICENSES.md` is not involved. Install commands are the ones R1's branch run used; size figures (1.3 GB / 5.6 GB, 355 MB) match `docs/baseline.md` and `cli.py`. Privacy section matches `/privacy` (no update check in 1.0: true, that is #216 in v1.3). Has "Only convert texts you are allowed to use", the AI label, licence and where to report problems.
- `tests/unit/test_readme.py` runs the README paragraph through `sci2audio script` and checks spoken text, the change count and each quoted report line: passes here (1 passed, 0.9 s).
- `THIRD_PARTY_LICENSES.md`: checked against `uv export --no-dev --frozen` (103 packages). Every package not named in a row has MIT, BSD, Apache, ISC or PSF metadata in the installed environment, so the "all other packages" row holds. Not installed here: colorama (BSD) and win32-setctime (MIT), both `win32` only, and httpx2-jsfetch (`emscripten` only, never installed). No change needed.
- `docs/release-checklist.md`: only the "(not yet possible)" marks and their sentence are removed; the PyPI item names R1's from-pypi jobs.
- `docs/learning/v1.0.md` says at the top that it is a draft by Claude for Colin (D-489); "Hours spent" and "What I would tell a client" are left as *(Colin)*.

## F1 (fix needed): the changelog does not cover every merged PR

The PR body says the 1.0.0 section covers every merged PR (#1 to #218). Checked by script: for each merged PR, do its title's issue numbers appear in CHANGELOG.md? These do not:

User-visible, need a line or their numbers in an existing line:
- PR #206: #104 (the report numbers out-of-range chapters from 1) and #118 (a line break shown in an edit's quote in the report).
- PR #208: #109 (URL ending in "/" at a line end), #110 (year bracket after a capitalised word taken for a citation), #145 ("see" bracket with a narrative citation dropped whole), #151 (confidence interval after "CI:"/"CIs" taken for a citation), #159 (soft hyphen or zero-width space hiding a unit), #160 (two second-run changes).

Development and process only (the plan's one "Development" line with their numbers): PRs #19/#20 (#17 core data objects), #81 (#39), #84 (#47), #137 (#129), #170 (quarantine, D-374), #182 (#138, #147, #157, #161, #166), #198 (#195), #201 (#199), #30 and #44 (process, D-68 to D-72, D-80).

Fix: add them as above, then re-run the same check (every merged PR's issue numbers appear in the changelog, or the PR is named in the Development line) and say in the PR body that it passes.

## F2 (fix needed): #222 is on main and will be in 1.0.0

PR #222 (#96 German line-end hyphens, #221 German reference-list titles) merged to main at 9af111e after this branch was cut. The tag goes on R2's merge commit, so 1.0.0 ships it. Merge main into the branch and add a changelog line for it (German texts: line-end hyphens joined by the German rule; German reference-list titles found), with its issue numbers.

## F3 (fix needed): guard against releasing with "unreleased" as the date

Leaving the date to the release-day PR is fine, but nothing stops a tag while the heading still says "unreleased"; the sdist and the repository would then carry `## [1.0.0] - unreleased` for good, and PyPI never takes 1.0.0 again. Fix (after R1 is merged and main is merged in):
- in `release.yml`'s `build` job, next to the tag check, fail unless CHANGELOG.md has `## [<version>] - YYYY-MM-DD` (e.g. `grep -qE "^## \[${version//./\\.}\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$" CHANGELOG.md`), with `TAG`/version still passed through `env:`;
- in `docs/release-checklist.md` "Release", make the first item say the version's changelog heading carries the release date.
Check the grep locally on the current CHANGELOG.md (must fail) and on a copy with a date (must pass), and run zizmor again.

## Not part of this review

- Main now receives v1.1 work before the v1.0.0 tag; anything merged before the tag ships in 1.0.0 and needs its changelog line in the release-day PR. Reported to the coordinator.
