# Answer to the review of PR #712, round 1

Thread: implementation infra-b-i4. Review: `plans/review-pr712-round1.md` (711baf8), head reviewed c0d934e. Fix commit: d562db0 (one commit, round 1).

## S1 (should-fix): fixed

**The pattern** (`tests/unit/test_review_tags.py`, `REVIEW_TAG`). New alternatives, each with a comment naming its form:
- `#N X1` / `#N, X1` / `#N R1-1`: a finding after an issue number. The letters are limited to the ones reviews use (`B F M N R S T`). That leaves an issue's own questions and decisions alone ("(#64, Q2)", "(#315, D5)", "(#6, Q11)"), which the first draft of this pattern flagged.
- `R\d+-\d+` bare (`(R1-1)`, `# R1-3:`).
- `review rounds? N` (catches "review rounds 1 and 2 of #188").
- `review #N` ("Review #489 S1:").
- `round N of the review`.
- `(review)`, `review, X1` ("(KB review, K5)"), and "reviewer's probe".

**Joined comment lines.** `joined()` merges comments on consecutive lines into one text at the first line's number, with their markers dropped. It is used for Python `#` comments, TOML `#` comments and JS `//` comments; JS block comments are already one text. So "(M2 of the #66" / "# review)" is now caught.

**Tests:**
- `test_the_pattern_catches_every_known_form` gains the 15 forms of the review.
- `test_the_pattern_leaves_plain_words_alone` gains "a reviewer can check it", "review the changed file", "outside review (D-703c)" and "a ruling of #185, D-581".
- `test_only_comments_and_docstrings_are_read` gains a tag split over two Python comment lines and over two JS `//` lines.

**Fails before, passes after.** With only the test file changed on c0d934e, `test_no_comment_or_docstring_carries_a_review_tag` failed with 77 hits. These are the review's lines plus about 60 more of the `(#631 F3)` kind, which the review's list did not name. After the clean-up all 43 tests in the file pass.

**The clean-up.** The finding IDs after issue numbers went by script: `(#631 F3)` becomes `(#631)`, `(#345 S2, plan Q9)` becomes `(#345, plan Q9)`. The review's lines were edited by hand:
- `extraction/pdf.py:312`: "as applied after review rounds 1 and 2 of #188" becomes "as applied in #188".
- `web/player.py:632`: "(R1-1)" dropped. `test_web_player.py:1079`: "(#601 R1-1)" becomes "(#601)". `test_extraction_pdf_process.py:388`: "(#345 R2-1)" becomes "(#345)".
- `test_textprep_citations.py:554` and `test_textprep_utterances.py:708`: the "R1-3:" and "R1-4:" prefixes are dropped.
- `test_web_listen.py:214, 228, 262, 272`: "Review #489 S1:" and "Review #489 S3 (M1, M2):" become "#489:".
- `test_cli_voices.py:89`: "(round 1 of the review, N3)" dropped.
- `test_web_figures.py:604, 729`: the section rules now say what each section holds: "#582: lazy images, the EPUB reader, the crops" and "#582: links, the batch of crops, EPUB tables".
- `test_textprep_units_abbreviations.py:440`: "(review)" dropped. `test_textprep_citations.py:339`: "(KB review, K5)" dropped.
- `test_web_design.py:362`: "the four the review found passing (PR #409 B1)" becomes "four that passed the check before (#409)".
- `test_web_player.py:1181`: "The reviewer's probe (#696 M1):" becomes "#696:".
- `test_web_window.py:670`: "what the review's mutants showed untested (#631 T1)" becomes "what mutation testing showed untested (#631)".
- `test_textprep_utterances.py:767-768`: "(M2 of the #66 / review)" becomes "(#66)".
- The two tags that the earlier pass had split over docstring lines are fixed the same way: `layout/furniture.py:424` "(#530, F2)" and `test_extraction_pdf_progress.py:124` "(PR #366 S1)".

**Scope held.** Comments, docstrings and one Jinja comment changed (`templates/privacy.html:30`, `lane:web`). No code line, string literal, golden file or core file changed. The ownership check passes with the PR's existing labels (`pr_checks.py` run locally on the full diff), so no label was added.

## Notes

- **N1:** left as is, as the review allows.
- **N2:** agreed. `JS_COMMENT` and `toml_texts` can only over-read. `joined()` keeps JS block comments apart, so the line numbers stay exact.
- **N3, and the coordinator's note:** the report-only Firefox 1/2 failure in `tests/browser/test_voice_cards.py::test_a_sample_stopped_while_it_is_made_never_plays` is #517. This PR changes only that test's docstring, so it is not this PR's concern; the coordinator tracks it.

## Local run on d562db0

Fast suite (`-k "not espeak" -n auto`): the first run had 2 failures that were not captured by name, and a full rerun on the same tree had none. The browser suite (Chromium) gave 198 passed, 5 skipped. ruff, ruff format, lint-imports (3 kept) and deptry are clean.
