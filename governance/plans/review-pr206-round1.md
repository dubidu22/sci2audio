# Review of PR #206, round 1 (app batch: #104, #118)

Reviewed head b35b4a7 (base 4bc809b), then the branch merged with main 486e18b (#200, #201) by update-branch: head 16373dc, same tree as my local merge. Critical (golden file change, accepted by D-445). Local Python 3.12.3 (3.12.16 has no uv download here); CI runs the pin.

## Result

No must-fix, no should-fix. One nit, deferred to issue #207 (v1.1).

## What I checked

1. **Golden file.** `pytest tests/unit/test_app_corpus.py --snapshot-update` on the merged branch leaves `test_app_corpus.ambr` unchanged. The 95 changed lines are all in the two `[markdown]` report snapshots (hunks at 3811, 5696, 5760): 80 `“-” → “-↵”`, 14 `“” → “↵”`, 1 `“–” → “–↵”` (waskom, numbers range "2030–\n2035" set aside by reference-list). Each line differs from main only in that one quote. Matches the PR body.
2. **All 10 corpus documents, not only the two goldens** (7 PDFs, the EPUB, the Markdown note, the text sample), run with `run_script_job` on main 486e18b and on the merged branch: every `script.txt` and every `report.json` byte-identical; `report.md` differs in 8 of them, every changed line a quote with no letter or digit gaining "↵": 444 "-↵", 52 "↵", 9 "–↵" (numbers ranges), 1 "=↵" (nowak, statistics step). Nothing else.
3. **Tests fail without the fixes.** With `report.py` and `pages.py` restored to main (and a stub `shown_original` that keeps the old one-line behaviour so imports work), 6 tests fail: both new `test_app_report` tests, both `test_app_script` chapter tests, the new `test_web_pages` check-table test and the changed `test_web_languages` cell.
4. **#104 criteria.** Report line now 1-based, same as the chapter table and the CLI; `settings.chapters` keeps 0-based indices in the report JSON and job.json; the document page shows `report.warnings` from the JSON, so it is 1-based too. No corpus snapshot has the line.
5. **#118 criteria.** Markdown report and the web check table (the JSON-derived view) both use `shown_original`; the JSON keeps the raw "\n". Test runs the real `LineEndHyphenStep` on a kept and a joined hyphen.
6. **Edge probes** of `shown_original` with all built-in steps: "\r\n" shows "↵"; " " or NBSP-only collapses as before; a soft hyphen at a line end from unicode-clean-up quotes "­↵" (shows as "↵", reason names the soft hyphen); a removed zero-width space quotes as an empty-looking "​" (nit N1).
7. Ruff check and format, lint-imports (3 kept) on the merged branch. CI on b35b4a7 all green.
8. Fast suite and Chromium browser suite on the merged branch: see the merge note below.

## Nit

- **N1 (deferred, #207, v1.1):** an edit whose original is only an invisible non-line-break character (U+200B from unicode-clean-up) still quotes as an empty-looking text. Outside #118's line-break scope; not in any corpus document today.

## Final check and merge

- Main moved twice during review. Merged into the branch with update-branch (merge commits, no force-push): 16373dc (main 486e18b, #200 #201), then 2a30c15 (main 2ea317e, #204). Each new head has the same tree as my local merge.
- On 2a30c15's tree: golden regenerates unchanged; the 10-document comparison against main 2ea317e again shows scripts and report JSON byte-identical and only no-letter/no-digit quotes gaining "↵" (444 "-↵", 52 "↵", 9 "–↵", 2 "=↵"; #204 added one "=↵" in a non-golden paper); fast suite 3178 passed, 1 skipped (HYPOTHESIS_PROFILE=ci); Chromium browser suite 46 passed.
- CI on 2a30c15: all jobs green, including macOS, Windows, browser and ZAP.
- Squash-merged pinned to 2a30c15 as **71b30c2** at 2026-11-13T21:58:01Z. #104 and #118 closed by the merge. Deferred: #207 (v1.1).
