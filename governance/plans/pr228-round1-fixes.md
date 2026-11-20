# PR #228, round 1: what is fixed (author's list)

The branch has three new commits after b0e1fb4, with no rewrite:
- 57b28b2 merges main (b25f192, release 1.0.0).
- 411c128 adds the golden cases first.
- 04bb809 makes the fixes.

## Golden cases (tests/regression/german.toml)

All eight failed before the fix commit:
- de-units-percent-euro-and-per-mille (replaces de-units-percent-and-euro-left-to-the-voice)
- de-units-one-after-ueber-auf-ab
- de-units-german-label-joins
- de-units-one-in-a-compound
- de-units-min-with-a-full-stop (with utterances)
- de-abbreviations-u-a-before-a-year-after-a-lower-case-word
- de-abbreviations-capitals-with-umlauts (with utterances)
- de-abbreviations-lower-case-ae-and-ff

## Fixes

1. **Case after "über", "auf" and "ab".** In units.toml, "über" and "auf" moved from dative to accusative, and "ab" was added to dative.
   - Golden case: "über 1 Mio. Euro" reads "über eine Million Euro", "auf 1 m" reads "auf einen Meter", "ab 1 kg" reads "ab einem Kilogramm".
   - Unit parameters cover all three.
2. **Capitals with umlauts.** In abbreviations.py, for any language other than "en", a capital is any upper-case letter in the label, word and next-sentence patterns. The class is built with str.isupper over U+0000 to U+024F. English keeps [A-Z] exactly.
   - Golden case: "Prof. Dr. Özdemir" reads "Professor Doktor Özdemir", and "usw. Über" keeps the cut (utterances pinned).
   - Unit cases: "Dr. Özdemir" and "usw. Ältere".
3. **Lower-case "o. ä." and "u. ä."** Both are exact_case entries now. They list "o. Ä.", "o.Ä.", "o. ä." and "o.ä.", and the same four forms with "u.". A golden case uses every lower-case spelling, and unit cases cover them too.
4. **"%", "€" and "‰".** units.toml adds "%" as Prozent (n), "‰" as Promille (n) and "€" as Euro (m).
   - "1 %" reads "ein Prozent", and "für 1 €" reads "für einen Euro".
   - "10 %" now reads "10 Prozent".
   - Glued "10%" stays as printed: the guard for a glued one-character symbol keeps it, and the voice reads it right.
   - The old golden case is replaced, and the unit cases are updated.
5. **German label joins.** A new optional unit-list key, `label_joins`, holds them; German lists "und", "oder", "bzw.", "sowie" and "bis".
   - units.py compiles a label pattern per language and keeps English's `_LABEL_LIST` exactly when the key is empty.
   - The loader test parses the key.
   - Golden case: "Bedingungen 1 bzw. 2 V" and "Gruppen 1 und 2 K". Unit cases add "sowie".
6. **"1" at the start of a compound.** "1-kg-Packung" reads "Ein-Kilogramm-Packung": an uninflected "Ein", with a capital because it starts the compound. "1,5-l-Behälter" reads "1,5-Liter-Behälter". The existing unit case "1-s-Takt" now expects "Ein-Sekunde-Takt", because the unit's singular form is unchanged.
7. **before_year only after a name.** It applies only when the word right before the abbreviation starts with a capital (`_after_name`). "Das gilt u. a. 2019" reads "unter anderem 2019", in a golden case and a unit case. The data-file header documents the rule.
8. **"ff."** It reads "folgende" (exact_case, can_end_sentence). Unit cases:
   - "S. 12 ff." at the end of a block reads "Seite 12 folgende." with its full stop.
   - In the middle of a sentence it reads "folgende und mehr".
9. **"min." as a unit.** "min." is a printed form of Minute now. "nach 12 min. Pause" reads "nach 12 Minuten Pause" and is not cut (golden case with utterances). "max. 5, min. 3" still reads "maximal 5, minimal 3", in both the golden case and a unit case.
10. **Pointers in the data files.** Both data files point to #113 and #211 instead of the plans file.

## Checks

- ruff check and ruff format --check are clean.
- lint-imports keeps 3 contracts, and deptry is clean.
- The fast suite: 3538 passed, 1 skipped (HYPOTHESIS_PROFILE=ci).
- English byte-identity: `sci2audio script --ignore-settings` on all 10 corpus documents, main worktree (b25f192) against the branch. All 30 output files are identical under `diff -r`.

## Deferred

#229, #230 and #231, as the reviewer filed them.
