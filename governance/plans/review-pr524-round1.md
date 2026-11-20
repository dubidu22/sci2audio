# Review of PR #524 (#494, cut limit 300 → 400), round 1

Reviewed head: **da4d10d** (base 96de4a3; main has moved to 2979dce, merge main happens before the pinned squash-merge).
Plan: `plans/textprep-batch-3-plan.md` PR 1, D-743 (A1 to A3), D-753. Critical (regression rows, corpus snapshot, risk:high): up to 4 rounds.

**Verdict: CHANGES REQUESTED. 5 findings: 1 blocking (B1), 3 should-fix (S1 to S3), 1 nit (N1).**
One fix commit for B1, S1, N1; S2 and S3 are PR-body and issue changes. Merge also waits for the slow-suite comment (green).

## Checked and fine
- P1.1 the constant and its comment (measured margin named).
- P1.2 the 5 rows changed, goals reworded to what they prove; no row pins a wrong reading. P1.3 twins over the limit: `long-sentence-comma-before-a-conjunction-over-the-limit` (411 characters, cut 269 + 141 before "but"), `de-…-over-the-limit` (416, cut 244 + 171 before "und"), `long-sentence-without-a-clause-mark-over-the-limit` (405, cut 203 + 201). Each keeps its rule covered at 400.
- P1.4 `SIZED_FOR = 300` on the 4 cut-ranking tests (8 cases); 301/399/400 one utterance, 401 two; `continues` on the second piece.
- P1.5 / A3: the progress test stays on the default limit and now expects the D-384 rule; the cost-curve test pins 300; the `app/estimate.py` docstring edit is named.
- P1.6: the snapshot diff touches only maass (−9) and seaborn (−3). I joined every removed and added script line: the text is identical, 12 joins in 11 sentences, no cut moved elsewhere, nothing else in the file changed.
- A1 gate evidence in the body (47 utterances of 300 to 400 characters, none over 510 tokens; dense sentences split by the voice and heard whole). The slow tests assert the split (`segments > 1`) and that every digit is heard in order, so "the voice splits it itself" is proven, not assumed.
- A2: `test_a_marker_in_a_sentence_whose_cut_moves_or_goes_lands_on_that_sentence` covers markers on every old piece and on the whole sentence; position.json drop by design, named with its test (#153).
- P1.9 cache note present. D-753: only `LONG` changed in `tests/browser/test_joined.py`; I measured it: 456 characters, cut 136 + 319 at 400 and 136 + 174 + 144 at 300, as the body says.
- Three-system run on da4d10d (run 44318801891): Linux, macOS, Windows, browser (Chromium), lint, licences, security all green.
- Nightly seeds (HYPOTHESIS_PROFILE=nightly) on `test_textprep_utterances.py`, `test_sentence_boundaries.py` and both regression files: seeds 555, 8080, 31337, 20261118, 1092 passed each.

## Findings

### B1 (blocking): a #481 regression test went silent in English at 400
`tests/unit/test_textprep_utterances.py::test_a_closing_mark_of_an_inline_list_opens_no_bracket_for_cutting[text0-en]`: its sentence is now one utterance (2 at 300), so the loop over parts asserts nothing. The mutant that brings back the #481 round-2 bug (`_inside`: `depth = max(0, depth - 1)` → `depth = depth - 1`) is killed by both cases on main, and only by the German case on da4d10d.
How I found it: I ran the whole fast unit suite with `cut_utterances` wrapped to cut every call at the default limit both at 300 and at 400 and to report tests whose piece count changed. This test is the only cut-rule test among them that was not pinned to 300.
**Fix:** pass `max_chars=SIZED_FOR` in that test (both cases; they were sized for 300), and assert `len(parts) > 1` in it, so it cannot go silent again.

### S1 (should-fix): no row keeps a colon past the first window
The two colon rows keep their ids (`long-sentence-colon-beyond-the-limit`, `de-long-sentence-colon-beyond-the-limit`), but their colons now sit at 312 and 321 characters, inside the 400 window, so they are cut at the colon at once (313 + 130, 322 + 170). The D-719 PR 4 behaviour they pinned, a colon past the first window (the window's own clause comma is cut first, then the colon), and with it the only three-utterance sentence among the regression rows, has no row left. The plan says "the colon rule stays covered", which is true for a colon inside the window only.
**Fix:** add an over-the-limit twin of each colon row (en and de), own wording, with the colon past character 400 and a ", which" / ", dass" clause comma before it, so the reading is three utterances as the old rows were at 300. Goal states the rule, not the number. The two existing rows stay as they are.

### S2 (should-fix): PR body must list the corpus joins pair by pair
P1.6 (approved) says the PR lists every joined pair; the body gives two examples. List all 12 joins (maass 9, seaborn 3): for each, the section and the cut that went (the word pair at the old cut, e.g. "Wissenschaftlerinnen, | die große Mengen"). Two of the 11 sentences lost one of two cuts ("Während manche deutsche Gerichte …" and "Hierfür ist im Rahmen des Artikel 32 …"): say so.

### S3 (should-fix): one web value is sized by the cutter's limit
The body says "Nothing in `web/` is sized by utterance length". `src/sci2audio/web/models.py:12` has `PREVIEW_LIMIT = 300  # characters of a preview sentence: the cutter's utterance limit (Q4)`. After this PR the comment is wrong. Per P1.8 PR 1 does not touch `web/`.
**Fix:** file a `lane:web` issue (keep 300 and reword the comment, or follow `DEFAULT_MAX_CHARS`; the web lane decides), link it in the body under "Out of scope", and correct the sentence in the body.

### N1 (nit): blank lines around the new rows
`tests/regression/english.toml` and `german.toml`: each new `[[case]]` has two blank lines before it and none after it (the next `[[case]]` follows the closing `]` directly). Use one blank line on each side, as elsewhere in the files.

## Mutation probe (cut logic and limit)
27 hand mutants of `utterances.py` (limit 399/401/300/450, window, `left` bookkeeping, `_cut_point` ranking, bracket depth, fair filter, tie-break, `_rank`, `_outside_replacement`, `MIN_PIECE`), run against `test_textprep_utterances.py` and both regression files from a clean worktree, baseline green first. da4d10d: 20 killed, 7 survived. The same 7 survive on main 96de4a3, so they are older than this PR: filed as **#533** (lane:textprep, v1.2.x). The 4 limit mutants are killed by `test_a_sentence_up_to_the_default_limit_is_one_utterance`. The only coverage this PR lost is B1.
The repository's `mutation.yml` is a whole-repo mutmut dispatch (dies after about 5 hours, #246), so I ran the targeted probe instead.

## Round 2 will check
The fix commit (B1, S1, N1 only), the body (S2, S3 with the issue link), Linux CI on the fix head, the three-system run on the final head, the slow-suite comment, then merge main, check the diff is unchanged and squash-merge pinned.
