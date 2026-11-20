# Review of PR #547 (#488 German "et al.", #477 English initials and "U.S."), round 1

Reviewed head: **d761e40** (base main 712ec4c; main is now c3b79c2 with #528). Plan: `plans/textprep-batch-3-plan.md` PR 2 (P2.1 to P2.6), D-743 (A4), ruling D-744. Critical: up to 4 rounds.

**Verdict: CHANGES REQUESTED. 2 findings: 1 blocking (B1), 1 nit (N1).** B1 is one fix commit; N1 is a change to the PR body.

## Checked and fine
- #488: "al." is in the German extras. The D-719 removed-text cut stays ("et al. (2019). | Die"). The 3 German rows and the stress-de lines are right.
- `_DOTTED_CAPITALS` and the English-only opener check on initials: the German initial rule is unchanged (`"Die erste Gruppe heißt A. Dann folgt B."` stays one).
- Units step: `opens_sentence` now reads a non-empty English list. No English unit is printed with a full stop (checked `units("en")`), so the units step reads nothing new.
- known-errors.toml: the two fixed entries are removed. The new FN ("U.S. | Researchers") names its true cause, and the kept limits point at D-744 (A4). Packaged-data check for the new TOML: done.
- Harness change in the cost-curve test: it still asserts the exact fitted curve and the plain-rate check, and it is named in the body.
- Shapes that gain on main c3b79c2 → PR: "U.S. Census Bureau", "U.S. (n = 12)", "U.S. FDA", "U.S. Army", "H.R. 1234 the U.S. Congress" stay whole. "called A. | Then", "vitamin A. | However", "Vitamin C. | As", "the U.K. | In both" are cut.
- Mutation: 8 hand mutants of the new code ("al." dropped, the English condition dropped or made unconditional, the dotted rule off, `{2,}` → `{1,}` / `{3,}`, the opener check on dotted capitals dropped). **8 killed.**
- Nightly seeds (HYPOTHESIS_PROFILE=nightly) on the utterances, sentence-boundary, units/abbreviations and both regression files: seeds 555, 8080 and 31337, 1470 passed each.
- Linux CI and the author's ci:full run on d761e40 are green.

## Findings

### B1 (blocking): the opener list holds common surnames, so "Y. He" and "X. An" are cut as sentence ends
The list's own header says: never put a name here. It holds words that are frequent surnames in scientific papers: **He, Her, An, So, To, On, Or, Still, Even**. An initial before such a surname now ends the sentence. On main c3b79c2 each of these is one utterance; on d761e40:

| printed | d761e40 |
|---|---|
| We thank Y. He and X. An for comments on the draft. | We thank Y. \| He and X. \| An for comments on the draft. |
| As shown by K. He and colleagues, residual networks train well. | As shown by K. \| He and colleagues, … |
| The proof is due to S. Even and colleagues. | … due to S. \| Even and colleagues. |
| We thank J. So, T. To and M. Or for the data. | We thank J. \| So, T. \| To and M. \| Or for the data. |
| The method of A. T. Still is older. | The method of A. T. \| Still is older. |
| Data were collected by H. On at the clinic. | … by H. \| On at the clinic. |
| We thank Y. Her for help. | We thank Y. \| Her for help. |

Acknowledgments and in-text author names with these surnames (He, An, So, To in particular) are common in the papers sci2audio reads. This is a new false-positive class, and it is more frequent than the "called A. | Then" miss the rule fixes. The gate missed it because neither the sentence sets nor the corpus hold such a name.

**Fix (one commit):**
1. Remove exactly these 9 words from `data/en/sentence_openers.toml`: "He", "Her", "An", "So", "To", "On", "Or", "Still", "Even". Add a header line saying why (each is also a surname, "Y. He").
2. Add an en regression row with the first two shapes above in one paragraph ("We thank Y. He and X. An for comments on the draft. As shown by K. He and colleagues, residual networks train well."). It must read as two utterances, one per sentence.
3. In `test_the_english_sentence_openers_load_and_hold_no_unit_name_or_one_letter`, assert that none of the 9 words is in the list.
4. Re-run the D-744 gate (sentence sets, natural-set floors, regression rows, corpus snapshots) and state the result in the body.

### N1 (nit): name the list classes beyond the plan
P2.3 named articles, pronouns, sentence adverbs and conjunctions. The list also holds prepositions ("In", "At", "For", …) and question words. Name this in the body with the reason ("in the U.S. In 2019 …").

## Note, no action
Second run of German "Das zeigen Müller et al. (2019). Die Studie ist neu.":
- The first run cuts after the citation (D-719).
- The second run reads "et al. Die" without the citation and no longer cuts, because "al." is now an extra.
The words are the same, so the second-run contract (words, D-577) holds. English behaves this way on main already. It is the same class as #482: a cut on a second run may differ.

## Final round will check
The fix commit (B1 only), the gate result in the body, N1, the merge of main c3b79c2 (the TOML rows of #528 and of this PR were clean in a merge-tree; the snapshot is regenerated if it conflicts, never hand-resolved), the nightly seeds again, and the three-system run on the final head.
