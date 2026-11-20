## Review round 1 (head 92155f9)

Good, small, well-tested module. Three span/sentence bugs to fix before merge, one speed issue to fix or defer with an issue, and two optional nits. Everything below was reproduced on this head.

### What I checked and found fine
- `ruff check`, `ruff format --check`, `lint-imports` (2 kept), `deptry src`: clean.
- Fast suite: **689 passed** (same as the PR body). `HYPOTHESIS_PROFILE=nightly` on `test_textprep_utterances.py` + `test_textprep_regression.py`: **70 passed**.
- Benchmark: 14.7 ms mean / 13.3 ms median here, in line with the 15.9 ms row in `docs/baseline.md`.
- **Corpus, own script** (all 7 papers, built-in steps, then `cut_utterances`): 2,836 utterances, longest exactly 300; every utterance trimmed; spans inside one block, in order, non-overlapping, non-empty for text. Stronger than the PR's "no character lost": for **every block** the utterance texts joined with single spaces equal `spoken_text` of that block **exactly** (0 mismatches in 7 papers).
- Abbreviations: "Fig.", "Dr.", "Approx.", "approx. 30 mg", "et al.", "e.g.", "i.e." do not end a sentence; "(see Table 2). Approx. half" does cut before "Approx.". Decimals and "p < .05" fine.
- Regression file: `utterances` added to exactly 4 cases (`links`, `statistics`, `abbreviations`, `homographs`); **no `expected` line changed** (checked the diff).
- Mutations, each caught by at least one test: dropping `_outside_replacement`; dropping the initial rule; swapping the clause-mark order (`,` before `;:`); disabling the "move cut to replacement start" branch.

### Must fix
1. **A sentence end inside a replacement splits the replacement** (plan §4: "a cut is never placed inside a replacement unless the replacement alone is over the limit"; D-115 (5)). `_sentences` runs on the joined text without looking at piece boundaries, so ". " + capital inside a replacement cuts it even when it fits. The second part then gets a span that leaves out the replaced original, so read-along loses it. Repro: "See note 1 here. More." with `1` replaced by "one. The note says hi.":
   ```
   'See note one.'            span 0..10  orig 'See note 1'
   'The note says hi. here.'  span 10..16 orig ' here.'
   ```
   Footnote texts read at the column foot (Q2, #66) are the likely real source of multi-sentence replacements. Suggested fix: drop sentence cuts with `run.inside_replacement(cut)` (the fallback still caps the length), plus a unit test and a property: no cut strictly inside a replacement whose spoken text fits `max_chars`.
2. **A replacement that starts with white space loses its span when it starts an utterance.** `_Run.start_of` returns `piece.span.end` for any index other than the replacement's first character, and `_utterance` skips leading white space first. Repro: "First part. X tail." with `X` replaced by " Footnote one":
   ```
   'Footnote one tail.'  span 13..19  orig ' tail.'   (should start at 12, the 'X')
   ```
   Suggested fix: in `start_of`, treat the index as the replacement's start when `piece.text[: index - offset]` is all white space; unit test for it.
3. **Non-ASCII white space defeats the abbreviation list.** `_SENTENCE_END` uses `\s` (so a no-break space counts as the gap after the full stop), but the word start is found with `rfind` over ASCII white space only, so the "word" swallows the word before it:
   ```
   'Smith et al. (2019) showed it.' -> ['Smith et al.', '(2019) showed it.']
   'As in Fig. 2 we see.'           -> ['As in Fig.', '2 we see.']
   ```
   The corpus PDFs have no such spaces (checked: none), but EPUB and Markdown input (#5, v1.0) often have `&nbsp;` in exactly these places. Suggested fix: find the word start with `str.isspace` (e.g. `re.search(r"\S+\Z", text[:match.end()])`) and add both strings as unit cases.

### Fix or defer with an issue
4. **The fallback cut is quadratic in a sentence's length.** `_fitted` recomputes `_counts` over the whole remaining text for every cut, and `_cut_point` builds `fits` over all of it. Measured: a block of 20,000 characters with no sentence end takes 0.05 s, 100,000 takes 1.24 s, so about 1 MB (plain text or Markdown with no full stops: lists, code, lyrics) would take around two minutes. PDFs are unaffected (benchmark above). Fix: compute `counts` once per sentence and work with offsets, or only look at a window of about `max_chars * 2` characters after `start`. If deferred, open an issue (lesson of #60/#62).

### Optional nits (fixing or declining with a reason is both fine)
5. "no." and a single capital initial also sit at real sentence ends: "The answer is no. Then we stop." and "Take set A. Then go." stay one utterance. The cost is only a longer utterance, which the fallback caps; restricting "no."/"nos." to a following digit would remove the first case. If kept as is, one line in the module docstring saying so.
6. The property test checks "characters without white space equal"; the corpus test could assert the exact single-space rejoin per block (it holds on all 7 papers today), which would have pinned fewer degrees of freedom.

Please answer item by item (fixed and how / deferred with issue link / declined with reason) and push; I will re-run the checks above on the new head. Merge happens only after #83 is on `main` and this branch is updated.

---
_Generated by [Claude Code](https://claude.ai/code)_
