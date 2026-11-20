# Review of PR #528 (#487, notice-off tables and figures read as a paragraph), round 1

Reviewed head: **161f854** (base main 96de4a3). Plan: `plans/textprep-batch-3-plan.md` PR 3 (P3.1 to P3.5), D-743, ruling D-726. Critical (regression rows): up to 4 rounds.
The merge order holds: #524 merges first, then this PR merges main.

**Verdict: CHANGES REQUESTED. 3 findings: 2 should-fix (S1, S2), 1 nit (N1). No blocking finding.**
S1 and S2 go in one fix commit. N1 is a change to the PR body.

## Checked and fine
- `read_as_prose` matches P3.2. All six steps use it: links, citations, numbers, statistics, units, abbreviations. The removed `SKIPPED_KINDS` / `_skipped` have no other users.
- Unchanged on purpose and true in the code: `hyphens.SKIPPED_KINDS` (formula, table, code), footnote marks (`MARKED_KINDS`), the hidden-runs and characters steps.
- Cross-step predictors: `link_removals(text, kind, …)` and `unread_marks` / `hidden_removals` work per block. They need no kind check of their own, so the citations and abbreviations steps predict the links step on table text as they do on paragraph text.
- The default is unchanged: no corpus snapshot moves. In a language without a notice step (fr, nl), the six steps do not run, so nothing new is read there.
- Rows: `de-hidden-runs-in-a-table-read-when-its-notice-is-off` is corrected (`4 Komma 2`) and the en twin is reworded. No row pins a wrong reading.
- **Differential fuzz (mine).** 2,700 random texts of 2 to 10 tokens (en and de: citations, links, units, decimals, statistics, abbreviations, row breaks, line-end hyphens), seeds 1, 2, 3, 555 and 8080. Each text went in a notice-off TABLE, a notice-off FIGURE and a PARAGRAPH, through the whole chain (strict).
  - All three read alike in every case without a line-end hyphen.
  - On a second run (`rebuilt_from_script`, own output), no table or figure changed where the same paragraph did not.
  - The paragraph shapes that change on a second run are older than this PR (main 96de4a3). I filed the new ones as **#540**.
- **13-document conformance (P3.4).** I ran `check_text_step` for the six steps on the other 5 corpus documents too (2 Markdown, 2 text, 1 EPUB; 8 table and figure blocks in total). The contract holds, with 0 edits inside their tables and figures.
- Three-system run on 161f854: Linux, macOS, Windows and browser are green.

## Findings

### S1 (should-fix): nothing pins the links step on a notice-off table or figure
Mutation: in `links.py`, `LinkStep.find` put back to the old skip (`kind in FURNITURE, TABLE, FORMULA, FIGURE, CODE`). The mutant **survives** the regression files, `test_textprep_conformance.py` and `test_textprep_placeholders.py`. The other five steps' mutants are killed by `a-table-and-a-figure-read-as-a-paragraph-when-their-notice-is-off`. Neither "read as a paragraph" row has a link in it, and the corpus edit count (at least 50) does not need one.
**Fix:** add a link that the links step removes to the text of both rows, `a-table-and-a-figure-read-as-a-paragraph-when-their-notice-is-off` (en) and `de-a-table-and-a-figure-read-as-a-paragraph-when-their-notice-is-off`. Put the same text in all three blocks, for example "… (Smith, 2019), data at https://example.org/data." or its German twin, with `expected` updated. The mutant must then fail on both rows.

### S2 (should-fix): the furniture branch of `read_as_prose` is not pinned
Mutation: `if block.kind is BlockKind.FURNITURE: return False` disabled. The mutant **survives** the same test files. Its effect: with "Page furniture" switched off, a furniture block is read as printed today. Under the mutant its words are read as prose. For example, `Journal of Tests 12 m² e.g. (Smith, 2019) https://x.org` would read `Journal of Tests 12 square metres for example`, with the citation and link removed.
**Fix:** add an en regression row with `switched_off = ["page-furniture"]`, a paragraph and a furniture block holding a unit, an abbreviation, a citation and a link. `expected` is the furniture text exactly as printed, and the goal says that furniture read with its switch off stays as printed (D-128, #487). The mutant must then fail.

### N1 (nit): name the two plan changes in the body
1. P3.4 named all 13 corpus documents. The new conformance test reads the 8 PDFs. Say why, and quote my run above: the other 5 hold 8 table and figure blocks, with 0 edits inside them and the contract kept.
2. P3.1 asked for rows showing the same blocks with the notice on as unchanged. That check is the `inside[frozenset()] == []` assertion on the corpus instead. Say so.
A dropped or replaced plan step is named with its reason (#489 N1 lesson).

## Mutation probe
Twelve hand mutants (each step's old skip put back; `read_as_prose` kinds, the notice term and the furniture branch), run on a clean worktree with a green baseline. 10 killed, 2 survived: S1 and S2. The notice term (`not notice_read`) is killed by the corpus conformance test. Adding FORMULA or CODE to the read kinds is killed by `formula-and-code-stay-as-printed-when-their-notices-are-off`.

## Final round will check
The fix commit (S1 and S2 only), the S1 and S2 mutants failing, N1 in the body, nightly seeds on the regression and conformance files, the merge of main once #524 is in (corpus snapshot regenerated if it conflicts, never hand-resolved), and the three-system run on the final head.
