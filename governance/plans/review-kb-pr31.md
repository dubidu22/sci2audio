# Review of KB PR #31 (D-167 to D-175, sci2audio #66), round 1

Reviewed head 9b13104 (main 4bfe53d merged in), 13 Nov 2026, thread "Review KB PR 31 citations decisions".
Checked against plan `issue66-citations-urls-plan.md` §1 and §3 (L1–L4, C1–C5), the chat post of
2026-11-13T01:53:29Z (created_at confirmed), `review-pr103-round1.md` (N2 and the S/M items), and the code
of PR #103 at 5994d46 (`textprep/links.py`, `textprep/citations.py`, probed with the step itself).

## What holds

- Nine rows, D-175 down to D-167, newest first between D-192 and D-166; no duplicate ID in the file; no
  break in numeric order; every row has exactly six columns (no unescaped pipe); backticks balanced.
- Each row maps to its plan item: D-167 L1, D-168 L2, D-169 L3, D-170 L4, D-171 C1, D-172 C2, D-173 C3,
  D-174 C4, D-175 C5. Alternatives and reasons match §3.
- Status "Decided (Claude)", coordinator 01:53 UTC under D-80, Colin informed 2026-11-13T01:53:29Z: matches
  the chat post.
- Refinements of the PR #103 review are recorded: D-168 bracket-after-preposition, pointer sentences,
  comma before a closing bracket, merged runs, sentence-start marks, label rule; D-171 label words; D-172
  no capital after an abbreviation ("cf. reference 4" confirmed by probe); D-173 outermost first and no
  doubled marks ("presented by Zimmeck et al. (2019).\nMAPS" reads "presented by Zimmeck et al. MAPS",
  confirmed by probe).
- PR body: no closing keyword before any PR or issue link.

## Fixes asked (round 1)

- **K1. D-168 pointer words.** The code's pointers are "see also", "see", "visit", "cf."; the row names only
  "See" or "Visit". Name all four.
- **K2. D-168 purposes.** The code allows "for", "to", "about", "regarding"; the row lists three. Add
  "regarding".
- **K3. D-168 comma rule.** The code takes a comma *or semicolon* in both places (`_with_space`, `_tidied`),
  and the tidy rule works before ".", "!" or "?". The row says only "comma" and "full stop" twice.
- **K4. D-168 join words.** The code also joins links with "&". Add it to the list.
- **K5. D-172 "Reference"/"References".** Plan §1.3 rule 2 (approved) says "Ref.", "Refs.", "Reference",
  "References" are replaced along. The code has only "ref."/"refs.", so "As discussed in Reference [12], it
  holds." reads "As discussed in Reference, it holds." and "See References [3, 5] for more." reads "See
  References for more." The row records the narrowed code rule without saying so. Keep the decided rule
  in the row (all four words), and fix the code in PR #103 with a regression case (or, if not in #103, a
  GitHub issue linked from the row).
- **K6. D-171 maths signs.** The row's list `= ∈ → < > ≤ ≥ ×` reads as complete; the code also has
  `∉ ← ↦ ± ∼ ≈ ⊂ ⊆ ∪ ∩`. Write "such as" before the list, or list them all.
- **K7. D-172 asides.** The code also treats a citation after "and so forth" as an aside; the row names only
  "and so on".

## Verdict

Changes requested: K1 to K7. Text only; after the fixes, re-check and squash-merge.

# Round 2

Re-checked head 7832f6d (fix commit on top of 9b13104; main 4bfe53d still included). Word diff of the fix
commit, against the code of PR #103 at 4d8013c:

- K1 fixed: D-168 names "See", "See also", "Visit", "cf.".
- K2 fixed: "regarding" added to the purposes.
- K3 fixed: both rules say "comma or semicolon"; the tidy rule works before ".", "!" or "?".
- K4 fixed: "&" added to the join words.
- K5 fixed in code (PR #103 4d8013c, round 2 R2-3) and in the row: probe "As discussed in Reference [12], it
  holds." reads "As discussed in reference 12, it holds."; "See References [3, 5] for more." reads "See
  references 3 and 5 for more.".
- K6 fixed: "signs such as".
- K7 fixed: "and so on" or "and so forth".
- Also recorded: D-171 only a capitalised label word makes a bracket a number (PR #103 R2-2); probe "See Eq.
  [3]." keeps the bracket, "the EM algorithm [5] holds." treats it as an aside citation.

Six columns still hold in the three changed rows. Verdict: approved; squash-merged with a commit message
that has no closing keyword.
