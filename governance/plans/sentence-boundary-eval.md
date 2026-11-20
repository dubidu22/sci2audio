# Sentence-boundary evaluation: our cutter, pySBD, syntok (plan D-719, section 3)

Run on 16 Nov 2026, main 2e2ae77 (after PR 1 #467 and PR 2 #476), by the sentence-boundary thread.
Script: `plans/sentence-boundary-eval/eval.py` (imports the repo's metric and swaps
`utterances._sentences`; the same run text after the text steps, the same replacement guard, the
same length limit and metric for every candidate). pySBD 0.3.4 and syntok 1.4.4 (both MIT) in a
scratch folder, never a repo dependency. Line breaks inside a block are given to both libraries as
spaces (the cutter reads them as white space; pySBD otherwise cuts at every one: 778 extra starts).

## Result (errors = extra starts + missed starts)

| set | ours | pySBD 0.3.4 | syntok 1.4.4 |
|---|---|---|---|
| EN natural (hardt, chi, own) | **4** (1 FP, 3 FN), P .9967 R .9900 | 13 (5 FP, 8 FN) | 3 (0 FP, 3 FN) |
| EN stress | **7** (1 FP, 6 FN) | 3 (0 FP, 3 FN) | 7 (2 FP, 5 FN) |
| DE natural (maass, own) | **5** (3 FP, 2 FN), P .9874 R .9916 | 6 (3 FP, 3 FN) | 11 (7 FP, 4 FN) |
| DE stress | **9** (6 FP, 3 FN) | 15 (10 FP, 5 FN) | 17 (7 FP, 10 FN) |
| splitter time, median per run | (part of the cutter) | 0.40 ms | 0.08 ms |

What the libraries get right that we miss (all already in `known-errors.toml`, all #465):
"Zimmeck et al. (2019). MAPS" and "Smith et al. (2019). We" (the citation step leaves "et al."
before the cut), "1. Introduction" cut after "1.", "U.S. Census", "e. V.", the citation in
brackets after a quote (#455 shape, PR 4), "Az. 13" (syntok), "Appendix C. It" (syntok), and
lower-case starts "seaborn", "iOS" (pySBD).

What they get wrong that we get right: pySBD misses six of hardt's plain sentence starts and cuts
appendix headings ("A.2 | Substitutions"), "Abb. 1. | PrivacyScore", "Fahl et al. | haben", and the
whole German ordinal/date family ("Am 3. | 4. 2019", "Er wurde 3. Sieger", "1. und 3. Quartil",
"Es waren 3. Die Studie"), as the smoke test showed. syntok cuts "Keywords: a; b; c" at every
semicolon, misses "Section 2.2. We", "Abs. 1 UrhG. Dies", every sentence after a closing quote
(„…“, »…«), every sentence starting with a digit ("2018 folgte"), and cuts "R. A. Fisher",
"pp. 12–14" and the German ordinal family.

## Decision: keep our rules for both languages (no dependency)

By the plan's test (a library wins for a language only with fewer natural-set errors than ours
after PR 3's rule fixes, and no more stress-set errors):
- **German:** ours has the fewest errors on both sets; neither library comes close on the stress set.
- **English:** syntok has one error fewer on the natural set today (3 vs 4), but two of our four
  ("et al. (2019).", "1. Introduction") are rule fixes of PR 3; after them ours has 2. pySBD has
  more natural-set errors (13). Neither wins.

PR 3 therefore fixes the rule errors in our cutter, taking the libraries' good shapes as cases.
Not measured, because no library won: second-run idempotency and the regression cases under a
library.
