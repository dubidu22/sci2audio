# Answer to review round 1 of PR #692

Thread: infra-b-i1 (implementation, Opus 5.5 high). Head reviewed: 7817c14. Fix commit: 52faf88 (one commit, Linux CI only).

## Fixed

- **S1, part 1** `.github/governance/promised_tests.py`: the new `section()` skips lines inside fenced code blocks (``` or ~~~, closed by a fence of the same character and at least the same length). A `#` line inside a fence no longer ends the section, and lines inside a fence are not read as promises. Why: in Markdown that line is not a heading, and this keeps the plan's "the section runs to the next heading of level 1 or 2". Test: `tests/unit/test_promised_tests.py::test_a_hash_line_inside_a_code_block_does_not_end_the_section`.
- **S1, part 2** `promised_tests.py`: `NODE_RE` now accepts spaces inside the `[...]` parameters (`tests/a.py::t[a b]` is read). Any backticked token in the section that contains `.py::` but is not a node ID fails with `FAIL promised tests: not read as a node ID: <tokens>`. This runs before the empty-section and missing checks. Why: a listed promise is never dropped silently, so "N of N" counts the list a reviewer reads. Test: `tests/unit/test_promised_tests.py::test_a_promise_that_cannot_be_read_fails`.
- **N3** `.github/workflows/governance-pr-checks.yml`: the step runs with `if: ${{ !cancelled() }}`, so its result shows next to a failing title or ownership step. It is asserted in `tests/unit/test_ci_workflows.py::test_the_pr_body_reaches_the_promised_tests_check_only_through_the_environment`.
- **N4** `promised_tests.py`: when the collection gives no test ID at all, the FAIL line is followed by "the collection gave no test" and the last five lines of the pytest output. Why: a failed sync or a collection error no longer looks like wrong IDs, and pytest's own output goes to `collected.txt` rather than the log. Test: `tests/unit/test_promised_tests.py::test_a_collection_that_gives_no_test_says_so`.
- **N6** `tests/unit/test_ci_workflows.py::test_the_governance_check_runs_pr_code_only_without_write_access` now asserts `persist-credentials: false` inside the checkout step's `with:` block.
- The PR body's promised-tests section lists the three new node IDs. A local dry run on the updated body gives `ok   promised tests: 16 of 16 collect`.

## Not changed

- **N1**: near-miss headings pass as opt-in, as the plan specifies. A near-miss should fail once the plan template makes the heading mandatory, and that is on Colin's list with the template wording (META-01, D-846: no Issue).
- **N2**: `./tests/...` and absolute paths fail closed with the ID named. That is acceptable, as the review says.
- **N5**: the cache is scoped to the PR ref and costs about 1 s, so there is no change.

Checks at 52faf88:
- `tests/unit/test_promised_tests.py tests/unit/test_ci_workflows.py`: 40 passed.
- ruff check and format: clean.
- `uv run zizmor --offline .github/workflows`: no findings.
