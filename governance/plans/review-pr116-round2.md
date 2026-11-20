# Review of PR #116, round 2 (#68 units and abbreviations)

Reviewed head: 62f5e89. Main is merged in up to a0d363a, which includes d30e6e7 (#103),
3f0149d (#105) and a0d363a (#65). Date: 13 Nov 2026.

## Round 1 items, checked

Each item was checked with the round 1 probe texts and new ones:
- M1 is fixed. "y = 2x + 1", "3x^2" and "f(x) = 4x." stay as printed. "10x over", "3.5x
  faster", "2–3x speedup", "(10x)" and "1920x1080" read "times".
- M2 is fixed. "Figures 2B and 3B", "Figs. 2A and 3B", "panels 2A and 4B", "Tables 1A, 1B, and
  2C", "Types 1A or 2B", "Figure 1, panels A and 3B" and "Fig. 3B–D and 4B" are left as
  printed. "7B model", "13B model" and "models 7B and 13B" read "billion".
- M3 is fixed. "trained on 15M", "300K" and "2bn" at the end of a block are read.
- M4 is done (merge commits 9590854, 40bbd67 and 62f5e89). The registry order is links,
  citations, footnotes, units, abbreviations, then #65's steps last (D-150). The angstrom edits
  win over #65's "˚A" composition: two of #65's edits are set aside, with no overlap error.
- S1 is fixed. "Eq. [3]" and "Eq.[4]" read "Equation [3]" and "Equation [4]".
- S2 is fixed: `tests/unit/test_package_data.py`. hatchling joins the dev group. Its licence
  row is right (MIT; pathspec MPL-2.0, tomlkit MIT, trove-classifiers Apache-2.0), and
  uv.lock adds only those four packages. But see M5.
- S3 is fixed: the PR body is corrected.
- N1: the reason for leaving it is accepted.

## Run on 62f5e89

| Check | Result |
|---|---|
| fast suite, locally (Linux) | 2060 passed |
| ruff check, format, lint-imports (3 contracts kept), deptry | all clean |
| nightly Hypothesis profile, every textprep test | 934 passed |
| slow ASR (`test_units_are_heard_as_words` and the round trip), real models | 2 passed |
| GitHub CI | ubuntu and macOS green; **windows-latest red**, so "CI passed" is red |

## Must fix

**M5. `test_package_data.py` fails on Windows (CI job 131755327838).**
`distribution_path` uses the system separator, so on Windows the paths are
`sci2audio\textprep\...`. Both tests then fail: every file looks missing, and the word lists
are not found. Fix: normalise to forward slashes in `shipped()`, for example
`Path(f.distribution_path).as_posix()` or `.replace("\\", "/")`. Then show the Windows job
green.

## Nits (no change needed)

- "with Figure 2 and 7B parameters" now leaves "7B" as printed, because the list rule carries
  "Figure" over "2 and 7B". It is ambiguous, and leaving it as printed is the safe side.
- "5-10x gains" stays as printed (a hyphen right before the number), while "2–3x" reads
  "times". Harmless.

## Outcome

M5 was fixed in 23b8c32 (forward slashes in `shipped()`). CI was green on all three systems,
and the PR was up to date with main (a0d363a). It was squash-merged as **088abee** on
13 Nov 2026 at about 07:44 UTC, and every check on main passed afterwards. Issue #68 is closed.
