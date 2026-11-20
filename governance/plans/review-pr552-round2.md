# Review PR #552, round 2 (final round, critical)

Reviewed: fix commit **5c9bec0**. Verdict: **approved, merged** as **8622f85** (squash, pinned to 5c9bec0). #469 closed.
Under MRG-03 (D-760) there was no branch update: no PR file changed on main since the review, and mergeable was clean.

## Round-1 items

| Item | Result |
|---|---|
| R1 record name | Fixed. `_project` refuses a name that `folder_name`'s cleaning would change, and `_make_folder` refuses any folder not directly in the output folder (or named `""`, `.`, `..`) before `mkdir`. My round-1 probe (`../escape`, an absolute name, `a/b`, `""`) now fails with "can't be read" and makes nothing. Tests: 8 record names, 4 folder names. |
| R2 remade folder | Fixed. The entry with the same path is replaced and its files are reset. The probe now lists the folder once. Test `test_r2_a_folder_made_again_is_recorded_once`. |
| R3 A7 | Old-reader test (`audiobook.json` alone) and old-file test (flat layout plays, next audiobook goes into the project folder, flat files keep their bytes) added. |
| R4 texts | player.py and api.py docstrings name the project's own folders; the PR body names the changed cancel assertion and its reason. |

## Final-round checks

- **Mutation:** 23 hand mutants from a clean baseline (171 passed, 1 skipped on the 6 affected test files). 22 were killed, including the three new guards: p21 name check, p22 parent check, p23 remade-entry replacement. p20 (`PurePosixPath` → `Path` for the stem) survives on Linux only; it differs only on Windows, where the drive-letter tests cover it (the first ci:full run caught it).
- **Nightly seeds:** not applicable (no Hypothesis tests in this PR).
- **Three-system run:** ci:full run 44390342594 on 5c9bec0 green on ubuntu, macOS and Windows, plus browser and ZAP; Linux run 44382381731 green.
- **Plan §7:** `web/api.py` changed in the `audiobook` route's docstring only.

## Notes carried to PR 3 (#470)

- Round-1 notes N1 to N4 stand. N1: a stale manifest entry stays until removal checks size and SHA-256. N2: a folder the person remade at the recorded path is used. N3: an empty project folder is left after a failed first run. N4: an output path spelled differently gets a `(2)` folder.
- PR 3's warning counts one line per recorded folder; R2 makes that one line per path.
