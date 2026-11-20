# Answer to review of PR #577, round 1

Fix commit **a1ddddd** (one commit on fc97dac). Next: Linux CI, then ci:full again (final round, three systems).

- **R1 fixed.** `README.md` line 92 and `src/sci2audio/cli.py` `EXIT_CODES_HELP` line 108 now read "the file is damaged, protected or can't be opened, or its text can't be read". `tests/unit/__snapshots__/test_cli_golden.ambr`: exactly that one `--help` line changed (`--snapshot-update`), and the PR body names it.
- **R2 fixed.** `tests/unit/test_app_readability.py` has the new strategy `mixed_pdfs()`, made of 1 to 8 pages: readable (1 to 400 "a"), glyph numbers (1 to 400, `unmapped` = all), or foreign letters (`MIN_LETTERS` to 400 of U+FFFD or U+E000). If no page is unreadable, one glyph page is inserted at a random place. The new property `test_the_verdict_on_pdfs_with_unreadable_pages` asserts that `bad` is non-empty in every example, that `found.pages` equals the unreadable pages and is a subset of the page numbers and sorted, and that `stops is (2 * held > total)`, with `event("stops"/"warns")`. Reach: in the ci profile, 100 of 100 passing examples (11 invalid), about 65 stop and 35 warn. In the nightly profile, all 2000 passing examples reach the branch, at 62 % stops and 21 % warns of all cases including invalid ones. The old `contents()` property stays.
- **R3 fixed.** The new test `tests/unit/test_app_job.py::test_the_unreadable_warning_comes_before_every_other_warning` uses a glyph PDF with no language set: two warnings, the unreadable one first and the language fallback (D-495) second, in the report and in the JSON. Mutant m8 (`(*warnings, warning(found))`) now fails it.
- Notes N1 to N3: no action, as noted.

Checks: ruff and format are clean. The changed test files (app readability, job, report, all cli tests) pass: 200 passed.
