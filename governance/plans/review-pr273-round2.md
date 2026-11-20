# Review of PR #273 (#269), round 2

Head reviewed: 32d2b0d (main 89a80d3 merged in), then c6077b5 after I merged main aa71172 (#275, test-only) into the branch.

## Round 1 fixes, checked

- F1 fixed: the sign branch gets `(?!(?<=°)[NSOWE]{1,3}(?![^\W\d_]))`. "52,5°N und 13,4°O", "52,5 °N", "52,5°NNE" and the four-point row read as on main; three rows pinned for both runs.
- F2 fixed: `_ends_in_letter` classifies by the last character before a final dot, so Std./Mio./Min. and the rest keep main's rule; PR body corrected; "1,5 Min.Pause" and "2,5 Mio.Einwohner" pinned.
- Author's correction accepted: "2,5 Mio.Einwohner" was already as printed on main (the dotless "Mio" form is listed too). My round-1 table row for it was wrong; "1,5 Min.Pause" was the real case.

## Re-run

- 76 probe shapes, two runs each: output identical to my scratch fix from round 1; no second-run break (main 89a80d3 has 6 among them).
- Fast suite 4221 passed, 1 skipped; ruff, format, lint-imports clean.
- Nightly seeds 13001 and 90217 (new): 858 passed each.
- Corpus 26 script jobs byte-identical to main 89a80d3.
- After merging aa71172 (#275 changes only test_textprep_numbers_statistics_de.py timing tests): that file plus the German regression cases, 339 passed.

## Result

Approved. Merge by squash once CI is green on c6077b5.

## Merge

Main moved again to fea9874 (#267, German sentence ends) while CI ran; I merged it in too (head 6a8f606). Checked on 6a8f606 against main fea9874: probes give no second-run break, and their only change from round 2 is #267's own ("2 Komma 5 Stunden. Danach"). The corpus is byte-identical (26 jobs), the fast suite passed (4287), and seed 13001 passed (881). CI was green on 6a8f606.

On c6077b5, macOS failed once on the wall-clock test `test_long_german_blocks_take_linear_time[dashes]` (3.6 s against a 3 s limit). That is not this PR's doing: the dashes text takes the same time on main and on the PR locally (0.97 s and 0.98 s, best of 3, whole chain). It passed on 6a8f606. It is the first failure, so it is not quarantined; if it fails again it needs an issue (best-of-3 with gc off, as #274 did for the link timing test).

Squash-merged at 12:39:17Z as d91a074. Nothing deferred.
