# Review of sci2audio PR #98, round 2

Reviewed head 30e09e9 (main 3f0149d merged in; my own local merge of 5fb9771 with main is
byte-identical to it), 13 Nov 2026.

## Round 1 findings
- M1 fixed: liu "{Lˆ z, vˆy}" gets no edit, "J´erˆome" reads "Jérôme", "Grˆace" reads "Grâce";
  liu characters 106 -> 105.
- S1 fixed: "Kl¨a-\nui" reads "Kläui", "ﬁ-\nnally" reads "finally", "Garc´ı-\na" joined;
  printed_words folds accents and ligatures. Truth file (495 rows, 7 misses) unchanged.
- N1 no change needed: main's links step (#103) wins over the hyphen edit inside an address.
- N2 deferred to issue #118 (milestone v1.0).
- N3 fixed: Letterlike Symbols are named by code point ("U+212A KELVIN SIGN read as "K"").
- N4 fixed: registry docstring line added.

## Checks on the merged tree
- ruff, format, lint-imports, deptry: clean.
- Fast suite (ci profile): 1916 passed, 1 failed (test_web_launch::test_nothing_listens_after_the_server_stopped),
  which passed on re-run alone and on main; the PR does not touch web code. CI green on
  Linux, macOS and Windows at 30e09e9.
- Nightly profile, 3 random seeds: 223 passed each.
- Snapshots against main 3f0149d: the script snapshots differ only in joined/kept hyphens
  (checked with hyphens, spacing accents and white space stripped: identical). Furniture
  snapshot: the characters totals equal round 1's accepted counts; every set-aside edit lost
  to reference-list (136), figure/formula notices (15) or one citation ("Spenader"), 152 in all, checked
  edit by edit.
- Edge probes ("x ´-\nab", "ab-\n´", "´-\n´"): contract holds, no crash.

## Verdict
Pass. D-149 to D-153 unchanged in substance (M1 narrows a detail of plan table 2.1: a
circumflex inside a word is composed only onto a vowel).
