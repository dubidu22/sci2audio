# Review of PR #585, round 1 (textprep batch B2, PR 2: #448)

Reviewer: B2 review thread (critical, Opus high). Reviewed head **8ef9ae4** (b1c244f tests,
3821311 code, 8ef9ae4 merge of main 0a72357). Result: **CHANGES REQUESTED, 1 must-fix.** Push
one fix commit for exactly F1, then message this thread with the new head once Linux CI is green.

## Checked

- Linux CI 44428092806 green; author ci:full 44428148135 green on three systems; label removed.
  PR mergeable (clean) against main 0a72357.
- Plan D-764 §3 followed: `_after_name` / `_before_affiliation` split (same regexes; `match(text,
  end)` equals `match(text[end:])` here, since `_AFTER_NAME`'s `\Z` and `_AFFILIATION` have no
  start anchor), structural author-line cue, no word list. The change only narrows removals
  (after-name marks unchanged; before-affiliation marks now also need `authors`), apart from F1.
- Changed rows: the three named rows gain only an author block and its line in `expected`; the
  readings they protect are unchanged. AC-448.2's row pins "1Ca' Foscari" etc. as the criterion
  asks (today's reading, the safe failure, D-57).
- AC-448.1 (both title shapes, en and de), AC-448.3 (structural), AC-448.4 (chi, arsiwalla, liu,
  biggs unchanged: corpus snapshots unchanged, `test_app_corpus.py` 15 passed): met.
- D-768 CHANGELOG line present.

## Must fix

**F1. An author line whose marks follow a comma (REVTeX, Physical Review style) no longer opens
the affiliations, so every affiliation mark is read (regression against main).** `_after_name`
looks for the name right before the mark; in "Jane Roe,¹ Ann Lee,² and Bo Kim,¹" a comma stands
between them, so no mark counts as "after a name", `authors` stays False, and the affiliation
lines keep their marks. Main removed them through the before-affiliation shape alone. REVTeX's
`superscriptaddress` sets exactly "Roe,¹˒² Ann Lee,¹ and Bo Kim²", the template of the physics
papers whose titles have isotopes. No corpus paper has this shape, which is why the snapshots did
not move.

| title block (runs) | main | PR 8ef9ae4 |
|---|---|---|
| "Cold atoms in orbit" / `Jane Roe,`+sup`1,2`+` Ann Lee,`+sup`1`+` and Bo Kim`+sup`2` / sup`1`+`Department of Physics, Example University` / sup`2`+`AI Lab, Example City` | "Jane Roe, Ann Lee,1 and Bo Kim", affiliations without marks | "Jane Roe,1,2 Ann Lee,1 and Bo Kim", affiliations without marks |
| same, every author mark after a comma (`Roe,`¹ `Lee,`² `Kim,`¹) | "Jane Roe, Ann Lee,2 and Bo Kim,1", affiliations without marks | "Jane Roe,1 Ann Lee,2 and Bo Kim,1", **"1Department of Physics…", "2AI Lab…"** |
| de: `Jana Rot,`¹ `Anna Lee,`² ` und Bo Kim`¹ / ¹`Institut für Physik` / ²`KI Labor` | "Jana Rot, Anna Lee,2 und Bo Kim" | "Jana Rot,1 Anna Lee,2 und Bo Kim" |

Exact fix (prototype `plans/b2-review/pr585-f1-prototype.diff`): in `_after_name`, one comma
glued directly before the mark is part of the name's end: `before = text[:start]`; if it ends with
",", drop that one character; then `_NAME_END.search(before.rstrip())` as now. With it all three
rows above remove every author and affiliation mark ("Jane Roe, Ann Lee, and Bo Kim", "Jana Rot,
Anna Lee, und Bo Kim"); "Mapping ¹²CO,¹³CO and ¹⁵NH₃" (mark glued after a comma in a title) and
"Mapping ¹²CO, ¹³CO" keep their mass numbers; the textprep unit tests (4,011 passed) and
`test_app_corpus.py` (15 passed, snapshots unchanged) pass with it.

Tests (exact):
1. en regression row `affiliation-marks-after-a-comma-in-the-author-line`: the first table row's
   blocks; expected `["Cold atoms in orbit", "Jane Roe, Ann Lee, and Bo Kim", "Department of
   Physics, Example University", "AI Lab, Example City"]`.
2. de regression row `de-affiliation-marks-after-a-comma-in-the-author-line`: the de table row's
   blocks with a title block "Kalte Atome" first; expected `["Kalte Atome", "Jana Rot, Anna Lee,
   und Bo Kim", "Institut für Physik", "KI Labor"]`.
3. A unit test in `tests/unit/test_textprep_affiliation_marks.py` for `_after_name`: True for
   "Jane Roe,¹ Ann" (mark at the comma), False for "Mapping ¹²CO,¹³CO and" (the "13") and for
   "Mapping ¹²CO, ¹³CO" (the "13").
4. A mutant dropping the comma strip, stated killed with the failing test's name.

## Not findings

- Title notes: a raised note mark after the title's last word ("A Study of Taurus¹") opens the
  author line, so a subtitle's mass number at a block start is removed. Same on main and with F1;
  filed **#586** (lane:textprep, risk:low).
- Unaffected shapes probed (PR = main): all-capitals names "JANE ROE¹, ANN LEE²", initials
  "J. Roe¹ and A. B. Lee²", one author line with plain marks.

## Final round after F1

Mutation on the changed functions (author's 13 plus the F1 mutant, I re-run a sample), own
nightly seeds, three-system run of the final head (I dispatch it), then merge pinned.
