# Review of PR #105, round 1 (issue #91, glued abbreviations in the cutter)

Reviewed head: d724b15 (main with #66 / d30e6e7 merged in). Reviewer thread: "Review cutter follow-up PR 105".

## What I ran

- `uv run ruff check`, `ruff format --check`, `lint-imports` (2 kept, 0 broken), `deptry src`: clean.
- Fast suite: 1487 passed, 46 snapshots passed. CI on d724b15: all jobs green (Linux, macOS, Windows, lint and layers, licences, security, CodeQL).
- `HYPOTHESIS_PROFILE=nightly` on `tests/unit -k "textprep or core or utterance"`: 723 passed, 23 snapshots.
- Corpus diff, main vs PR, all 7 papers, utterances with the default steps and with no edits at all (Citations off): with steps, no change in any paper; with no edits, only hardt changes, exactly the two intended "[p." sentences (328 to 326 utterances). No other paper changes.
- Edge probe of 24 hand-made sentences against main and the PR (below).
- D-174 is only cited; no D-numbered decision changes in substance. Q4 (textprep owns the cutter, 300 characters) is untouched.

## Must-fix

**M1. The initials rule now fires on a capital after a closing bracket or an apostrophe, so real sentence ends are lost.** `_GLUED_BEFORE` splits on `_OPENING + _CLOSING + "}"`, and `_INITIAL` is now checked on the split word too. `_OPENING` holds the ASCII apostrophe and `_CLOSING` holds `)`, `]` and `’`, so any word ending in an apostrophe, a closing bracket and one capital letter becomes an "initial". Main cut all of these; the PR keeps them in one utterance:

| text | main | PR |
|---|---|---|
| `I SAID I DON'T. Then we left.` | 2 utterances | 1 |
| `It is in Table 1(a)B. Next.` | 2 | 1 |
| `The value was x)A. Next.` | 2 | 1 |
| `It was 5'A. Next.` | 2 | 1 |
| `We cite [1]A. Next.` | 2 | 1 |
| `We call it Plan(B. Next one.` | 2 | 1 |

All-caps words with an apostrophe ("DON'T.", "ISN'T.", "WON'T.") occur in EPUB fiction and in all-caps titles. The PR body says the initials rule works "as before", which it does not.

Fix (checked locally: all 71 tests in `test_textprep_utterances.py` and `tests/regression` still pass, and every row above is cut again): keep the split word for the abbreviation check only, and check initials on the old word, with leading openers stripped:

```python
whole = _LAST_WORD.search(text, 0, match.end()).group().rstrip(_CLOSING)
word = _GLUED_BEFORE.split(whole)[-1]
...
if _INITIAL.match(whole.lstrip(_OPENING)):
```

Add at least `I SAID I DON'T. Then we left.` and `We cite [1]A. Next.` to the "must still end a sentence" rows of the table test, so the initials side is pinned. Correct the PR body sentence.

## Should-fix

**S1. An abbreviation glued to an en dash, em dash or slash is still cut.** `In the results—e.g. Table 2 shows it.` gives `In the results—e.g.` / `Table 2 shows it.`; `results/e.g. Table 2` likewise. Glued dashes are common in PDF text. Either add `–—/` to `_GLUED_BEFORE` (with M1's fix the initials rule is not affected) plus a table row, or file a GitHub issue and link it in the reply.

## Nits

- **N1.** The test imports the private `_BEFORE_NUMBERS`. Acceptable for a unit test of the module; no change needed unless you prefer a local copy with a comment.

## Verdict

Not ready: one must-fix (M1), one should-fix (S1). After the fix, answer item by item (fixed / deferred with issue / declined with reason), merge main if it moved, and I re-run the suite, the nightly profile and the corpus diff.
