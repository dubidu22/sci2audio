# Review PR #712, round 1 (batch B-I4, #695, #706)

Thread: review-infra-b-i2 (Opus 5.5), the infra lane's review thread. Head reviewed: c0d934e. Date: 2026-11-20.
**Critical: no**. The PR changes comments and docstrings, one new test file, one test in `test_lanes.py` and the scaffold copy `governance/github-setup/pr-checks.json`. None of these is a critical path: nothing under `src/sci2audio/core/`, `.github/`, `tests/regression/`, `tests/corpus/` or `__snapshots__`. Labels: `lane:infra` (the lock), `lane:cli`, `lane:extraction`, `lane:layout`, `lane:textprep` and `lane:web`; `risk:low`. Plan `plans/infra-b-i4-plan.md`, section "PR 2", approved as D-860.

**Verdict: changes requested** (0 must-fix, 1 should-fix, 3 notes).

## Verified

- (1) Comments and docstrings only:
  - 132 files: 125 `.py`, 4 `.toml`, 2 `.js` and 1 `.json`. The first commit, 908c9bf, adds only the tests.
  - For all 123 `.py` files the sweep commit 908c9bf..c0d934e modifies, the Python AST with docstrings blanked is identical before and after (`ast.dump`, CPython 3.12).
  - The four TOML files (`textprep/data/de/abbreviations.toml`, `de/units.toml`, `en/sentence_openers.toml`, `web/strings/en.toml`) load to equal data with `tomllib`.
  - Every changed line in `static/app.js` and `static/player.js` is a `//` comment.
  - No golden or regression file changed.
  - No changed docstring is read at run time. The one `__doc__` use, `web/window.py:312`, is in a file whose docstring is unchanged. The fast suite's CLI help and OpenAPI snapshots pass.
- (2) Rewrites:
  - Issue numbers stay where the tag pointed at the reason: `(#264 review round 1)` becomes `(#264)`, `(review of PR #228)` becomes `(#228)`, and `(#254, review B1 of PR #377)` becomes `(#254, #377)`.
  - Tag-led docstrings keep their why, behind the issue number: `"""Review M1 of #128: the next printed line …"""` becomes `"""#128: the next printed line …"""`. See N1.
- (3) `tests/unit/test_review_tags.py`:
  - `REVIEW_TAG` catches all eleven forms of the plan's finding 2 and both forms named in #695 (16 parametrized cases).
  - It leaves the plan's five plain phrases alone, plus `(#394)` and the corpus's split "Software Review Repository".
  - Only `#` comments (tokenize) and module, class and function docstrings (ast) are read. Python string literals, TOML values and JS and HTML strings are not, which `test_only_comments_and_docstrings_are_read` pins with line numbers.
  - `tests/regression`, `tests/corpus` and `__snapshots__` are skipped by exact path part, so `test_extraction_corpus.py` and similar files are still read.
  - With the tests of 908c9bf on `main`'s code, `test_no_comment_or_docstring_carries_a_review_tag` and the #706 test fail; on c0d934e, 62 passed.
- (4) #706: `governance/github-setup/pr-checks.json` is byte-equal to `.github/governance/pr-checks.json` (`cmp`). `test_the_scaffold_copy_of_pr_checks_json_equals_the_live_one` compares the bytes.
- (5) The follow-up Issues exist and match the plan:
  - #709: goal strings in `tests/regression/*.toml`, `lane:textprep`, `risk:high`, v1.4. It reuses `REVIEW_TAG` and allows goal-only diffs.
  - #710: the other three stale `github-setup` copies, `lane:infra`, v1.4, byte-equal or removed, with a test.
  - #711: audit N4 plus the base-commit listing of promises that already collect, `lane:infra`, v1.4, keeping the read-only workflow.
- (6) Local run in a fresh `/tmp/review-712` at c0d934e:
  - ruff check: clean. ruff format --check: 389 files formatted.
  - lint-imports: 3 kept. deptry src: no issues. zizmor: no findings.
  - Fast suite with `-k "not espeak" -n auto`: 8695 passed, 6 skipped, 6 xfailed.
  - `pytest -m browser --browser chromium -n 4`: 198 passed, 5 skipped.
- (7) The report-only Firefox shard failure (`browser (Linux, firefox, 1/2, reported only)`) is in `tests/browser/test_voice_cards.py::test_a_sample_stopped_while_it_is_made_never_plays`.
  - The PR changes only that test's docstring (`#446 review S1a:` becomes `#446:`) and its neighbour's. The AST is identical, and the JS changes are comments only, so the PR cannot change its behaviour.
  - It is the known Firefox flake #517, which is open.
  - Chromium passes, and both WebKit shards and Firefox 2/2 pass.
- CI at c0d934e: `CI passed`, `tests (ubuntu-latest)`, `governance pr checks` (run 44828532429), both Chromium shards, `lint and layers`, `licences`, `security`, CodeQL and ZAP are green.
- Licences: none.

## Findings

### S1 (should-fix, narrating-comment): the pattern misses forms still in the tree, so #695's "existing tags are removed" is not met
`tests/unit/test_review_tags.py:25-38`, and the tag reading at `:44-47`. A scan of every comment and docstring the test reads, for "review", "round N" and `R\d-\d`, finds these tags left after the sweep:
- `src/sci2audio/extraction/pdf.py:312`: "as applied after review rounds 1 and 2 of #188" (the plural "rounds" is not matched).
- `src/sci2audio/web/player.py:632`: "(R1-1)"; `tests/unit/test_web_player.py:1079`: "(#601 R1-1)"; `tests/unit/test_extraction_pdf_process.py:388`: "(#345 R2-1)"; `tests/unit/test_textprep_citations.py:554` and `tests/unit/test_textprep_utterances.py:708`: "# R1-3:" and "# R1-4:". These are finding IDs without the word "review".
- `tests/unit/test_web_listen.py:214, 228, 262, 272`: docstrings that open with "Review #489 S1:" or "Review #489 S3 (M1, M2):".
- `tests/unit/test_cli_voices.py:89`: "(round 1 of the review, N3)"; `tests/unit/test_web_figures.py:604, 729`: section comments "round 1 of the review (#582)" and "round 2 of the review (#582)".
- `tests/unit/test_textprep_units_abbreviations.py:440`: "(review)"; `tests/unit/test_textprep_citations.py:339`: "(KB review, K5)"; `tests/unit/test_web_design.py:362`: "the review found passing (PR #409 B1)"; `tests/unit/test_web_player.py:1181`: "The reviewer's probe (#696 M1)"; `tests/unit/test_web_window.py:670`: "what the review's mutants showed untested (#631 T1)".
- `tests/unit/test_textprep_utterances.py:767-768`: "(M2 of the #66" / "# review)". The tag is split across two comment lines, and `python_texts` matches each `#` comment token on its own, so this form can never be caught.

Failure scenario: a new comment in any of these shapes passes CI, so the kind returns although #695 is closed as fixed (REV-05, META-03).

Fix:
- Widen `REVIEW_TAG` with alternatives for:
  - `review rounds? \d+( and \d+)? of #\d+`;
  - `round \d+ of the review`;
  - `review #\d+ [A-Z]{1,2}\d+`;
  - `\(review\)`;
  - a bare finding ID after an issue number or alone (`#\d+ [A-Z]{1,2}\d+(-\d+)?`, `\bR\d+-\d+\b`);
  - `(KB )?review, [A-Z]\d+`;
  - "the review('s)? … (PR #N X1)", or simply `PR #\d+ [A-Z]{1,2}\d+`;
  - "reviewer's probe".
- Join consecutive `#` comment lines into one text before matching, keeping the first line's number.
- Add a parametrized case for each form, and clean the lines above. Keep the plain uses: "a reviewer can check", "for a review", "review the changed file" and "outside review (D-703c)".

### Notes
- N1: most tag-led docstrings now open with the bare issue number (`"""#128: the next printed line …"""`, `"""#582: a lazy image …"""`). The why text is kept, so this meets the plan. A sentence that starts with the why and ends with "(#128)" would read better; no change is asked.
- N2: `JS_COMMENT` also matches a `//` inside a JS string (for example a URL), and `toml_texts` assumes no multi-line strings. Both can only over-read and fail loudly, never pass a tag, so this is fine as it stands.
- N3: the Firefox failure is #517. If it fails again on `main` or a nightly, it follows D-374 (quarantine for Firefox with #517) and is not this PR's concern.

Verdict: changes requested. S1 needs one fix commit, a wider pattern plus the joined comment lines and about 20 lines cleaned. Round 2 is this non-critical PR's last; a leftover would go to an Issue.
