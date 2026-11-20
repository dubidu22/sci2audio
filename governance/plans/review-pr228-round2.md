# Review of PR #228, round 2 (German abbreviations, symbols and units, #113)

Reviewed 14 Nov 2026 at head 04bb809 (main b25f192 merged in by 57b28b2; golden cases first in 411c128, fixes in 04bb809). Author's list: plans/pr228-round1-fixes.md.

**Verdict: approved.** All ten round 1 fixes are in and right. One new v1.2 issue (#233). Branch updated with main 2693f00 (1.1.0.dev0) by update-branch (merge commit, no force-push); merge by squash when CI is green on the new head.

## Fixes checked

1. "über"/"auf" accusative, "ab" dative: "über ein Kilogramm", "über eine Million Euro", "auf einen Meter", "ab einem Kilogramm". Right.
2. Capitals with umlauts in non-English jobs (str.isupper class over U+0000–U+024F in label, word and next-sentence patterns; English keeps [A-Z]): "Doktor Özdemir", "Professor Ünal", "usw. Über" keeps its cut. Right.
3. "o. ä.", "o.ä.", "u. ä.", "u.ä." read. Right.
4. "%" Prozent, "‰" Promille, "€" Euro: "einem Prozent", "einen Euro", "5 Promille"; glued "10%" stays as printed (the voice reads it right). Right.
5. `label_joins` (und, oder, bzw., sowie, bis): "Bedingungen 1 bzw. 2 V", "Gruppen 1 sowie 2 K" stay. English pattern unchanged when the key is empty. Right.
6. "1-kg-Packung" reads "Ein-Kilogramm-Packung"; "1,5-l-Behälter" stays a number. Right.
7. before_year only after a capitalised word: "gilt u. a. 2019" reads "unter anderem". Right ("Ärzte u. a. 2019" still reads "und andere": a capitalised noun looks like a name; rare, accepted).
8. "ff." reads "folgende". Right.
9. "min." a unit form: "nach 12 Minuten Pause", one utterance; "max. 5, min. 3" still "maximal 5, minimal 3". Right.
10. Data files point to #113 and #211. Right.

Every new golden case read as spoken German: all right.

## Checks

- ruff, format, lint-imports (3 kept) clean.
- Fast suite: 3538 passed, 1 skipped (ci profile, -n 8). Changed test files under the nightly profile: 460 passed.
- English byte-identity: all 10 corpus documents, main b25f192 worktree vs 04bb809: 30 files identical under diff -r.

## Deferred (issue filed)

- #233 (v1.2): "p. a." not listed; "1 %-Hürde" reads "ein Prozent-Hürde" (the compound rule covers only "1-kg-").

## Note for PR 3 (#130)

"95 %-KI" now reads "95 Prozent-KI" through the units step. The statistics step runs before units, so S-de-4 still sees "%-KI"; keep a case that pins it.

## Accepted as is

- "zahlte man 1 €" reads "ein Euro" (an accusative object with no preposition stays nominative; plan Q7 limit).
