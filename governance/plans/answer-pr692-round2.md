# Answer to review round 2 of PR #692

Thread: infra-b-i1 (implementation, Opus 5.5 high). Head reviewed: 52faf88.
- Fix commit: bb4ae8b (one commit).
- Then main (c4c2de8) was merged in with merge commit 359dd9b, the head for round 3. `ci:full` is set.

## Fixed

- **S1** `tests/unit/test_promised_tests.py`: the two docstrings no longer start with "Review round 1 of #692, S1:". They keep the why: "A shell comment in a fence is not a heading." and "A listed promise is never dropped without a word." The repeated kind is #695 (v1.4, `lane:infra`, `risk:low`): a fast test over `src/` and `tests/` for review-round tags, with the existing ones removed. Today 106 lines in 44 files match, so the cleanup is its own PR.
- **S2** `.github/governance/promised_tests.py`: the new `read()` returns promises and unreadable tokens together. After the backticked tokens are taken out of a section line, any `.py::` left in it (no backticks, or a missing closing backtick) joins the unreadable list. The check fails on it under the same `not read as a node ID` message. Why: the claim "a listed promise is never dropped silently" now holds for every `.py::` the section holds. Test: `tests/unit/test_promised_tests.py::test_a_promise_without_both_backticks_fails`, with a bare ID and an unclosed one.
- **S3** `.github/workflows/governance-pr-checks.yml`: `astral-sh/setup-uv` now also runs with `if: ${{ !cancelled() }}`. When an earlier step fails, uv is still there, so the step reports the real collection result instead of every promise as missing. The assertion is in `tests/unit/test_ci_workflows.py::test_the_pr_body_reaches_the_promised_tests_check_only_through_the_environment`. It finds the setup-uv step by its action name, not by the pinned version, so a Dependabot bump does not break it.
- The module docstring now says that any `.py::` in the section that is not a backticked node ID fails.
- PR body: the promised-tests section lists the new node ID, and "Out of scope" names #695. A local dry run on that body gives `ok   promised tests: 17 of 17 collect`.

Checks at 359dd9b:
- `tests/unit/test_promised_tests.py tests/unit/test_ci_workflows.py tests/unit/test_lanes.py`: 76 passed.
- ruff check and format: clean.
- `uv run zizmor --offline .github/workflows`: no findings.
