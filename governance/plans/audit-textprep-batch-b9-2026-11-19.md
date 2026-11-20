# Light batch audit: textprep B9 (#414, #415, #402), 19 Nov 2026

Scope: the merged diff of the whole batch, one PR: #621, squash 9f2cbaa on main (10 files, +913 −88). This is the last textprep batch before the tester release (D-795). I checked it for contract touches and for inconsistencies inside the batch. I am the batch's review thread, so this audit is not independent of the review (reports: `review-pr621-round1.md`, `review-pr621-round2.md`).

**Result: 0 blocking findings.** Two notes below. Neither needs work before the release.

## Contract touches

- **Text-step interface, core dataclasses, layer imports:** none touched. No golden, snapshot or corpus truth file moved. Corpus utterances were byte-identical to main on both review rounds.
- **`CitationWords` gains `or_word`.** It has a default ("or"), German sets "oder", and no other code builds a `CitationWords`, so nothing else needs it.
- **`link_removals` changed.** For #402, a removal span can now start at the join word before a link. Its three consumers are `citations.py:438`, `abbreviations.py:246` and `statistics_de.py:219`. `link_removals` is built from the same `LinkStep._block_edits` that the step uses, so the consumers see the step's spans. The #428 kind of drift does not apply here. The author added a unit row per consumer, and my probes ("z. B. Müller und https://x.org hier", "Wir danken Müller u. a. und https://x.org hier") read as expected.
- **Regression cases:** six new (3 en, 3 de) and one changed line (D-668 case, line 4, decision A). All seven failed on main before the rules changed.

## Rulings the batch changed (for the decision log; recorded under D-791)

- **D-668:** a needed two-item pair now reads once over both: "It was shown in references 1 and 3." An aside "and" pair is unchanged (ruling question #624).
- **D-605:** "as before" for one-item subject nests is superseded. "((Smith, 2019)) is cited." reads "Smith is cited.", and so does "(see (Smith, 2019)) is cited.".
- **New, review round 1 (M3):** when a run's first bracket is no citation (a label word, a sign or a glued word), its later brackets read as before #414. What such a run should read is #634.

## Notes (not blocking)

1. **Two code paths give the D-668 reading.** `_needed_pair` covers a two-item list, and `_pair` (put back in round 1 for M3) covers a run whose head was rejected. Both read "references X and Y", with the same "and in before" guard. If #634 or #624 changes the pair rule, both paths have to change. Recorded on #634 below.
2. **Subject and aside readings differ for lead-word nests.** "(see (Smith, 2019)) is cited." reads "Smith is cited.", but "It holds (see (Smith, 2019)) here." still reads "It holds (see Smith) here.", and the "see"/"vgl." nests with a flat part keep main's readings (fallback allowed by M2). All of these are on #626 (v2).

## Follow-ups (all milestone v2)

#622 (+ round 1 rows), #623, #624, #625, #626 (+ round 1 rows), #627, #628, #629, #634, #646.

## Ledger input

B9 had 2 review rounds and 0 post-merge defects so far. Round 1 found 3 reading regressions the author's checks had missed. One came from the PR's own property test under another Hypothesis seed. Two came from label, sign and lead-word shapes that the author's random generators never produced. Lesson for later batches: a review runs the PR's property tests on dev profile under several seeds. Any "equivalent mutant" search must include the words that stand before the shape (labels, signs, lead words).
