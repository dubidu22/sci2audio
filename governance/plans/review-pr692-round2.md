# Review PR #692, round 2 (batch B-I2, #687)

Thread: review-infra-b-i2 (Opus 5.5). Head reviewed: 52faf88 (one fix commit on 7817c14). Date: 2026-11-20.
**Critical: yes** (unchanged from round 1). Plan `plans/infra-b-i2-plan.md`, section "#687", approved as D-846. Answer: `plans/answer-pr692-round1.md` (governance f348742).

**Verdict: changes requested** (0 must-fix, 3 should-fix, 2 notes).

## Verified

- Scope: `git diff 7817c14..52faf88` touches the same four files and nothing else (+102/−8). The changes are only the round-1 answers: S1, N3, N4 and N6.
- S1 is fixed as the answer describes:
  - `section()` skips fenced blocks (``` and ~~~, closed by the same character at the same or greater length), so a `#` line inside a fence ends nothing.
  - Lines inside a fence are not read. A node ID in a code block is neither a promise nor a failure.
  - `NODE_RE` reads parameters that contain spaces (`tests/a.py::TestX::test_y[a-b c]` is read).
  - Any other backticked `.py::` token fails with `not read as a node ID`, before the empty and missing checks. My probes: `:: t`, `t[open` and `t[a[0]]` all fail.
  - Tests `test_a_hash_line_inside_a_code_block_does_not_end_the_section` and `test_a_promise_that_cannot_be_read_fails` exist.
- N3: `if: ${{ !cancelled() }}` is on the step (`governance-pr-checks.yml:37`), and a test asserts it. See S3.
- N4: when no `::` line was collected, the FAIL line is followed by the last five lines of pytest's output, and `test_a_collection_that_gives_no_test_says_so` pins that. Printing PR output to the log adds no capability: the PR's code already runs in this job and can write to stderr.
- N6: `persist-credentials: false` is now asserted inside the checkout step's `with:` block.
- N1, N2 and N5 were left as they are, and the reasons hold. N1 waits for the mandatory heading (META-01, Colin's list). N2 fails closed and names the ID. N5's cache is ref-scoped and cheap.
- PR body: the promised-tests section lists 16 node IDs, including the three new ones. Governance pr checks runs 44794944147 and 44794944462 (pull_request, headSha 52faf88) both print `ok   promised tests: 16 of 16 collect`.
- Security is unchanged: `pull_request` only, the two read permissions, the body only through `env:`, and no `${{ }}` in `run:`.
- Local run in a fresh `/tmp/review-692` at 52faf88:
  - ruff check: clean. ruff format --check: 385 files formatted.
  - lint-imports: 3 kept, 0 broken. deptry src: no issues.
  - `uv run zizmor --offline .github/workflows`: no findings.
  - Fast suite with `-k "not espeak" -n auto`: 8601 passed, 6 skipped, 6 xfailed.

## Findings

### S1 (should-fix, narrating-comment): review tags in two new docstrings
`tests/unit/test_promised_tests.py:167` and `:177` begin with "Review round 1 of #692, S1:". That names who asked, which PR-05 rules out. The same kind was found in #676 round 2.
- Fix: delete the prefix and keep the why ("a shell comment in a fence is not a heading", "a listed promise is never dropped without a word").
- The kind repeats (REV-05, META-03), and `src/` already holds about a dozen such tags, for example `textprep/abbreviations.py:51`, `textprep/runner.py:238` and `textprep/hyphens.py:113`. The check that stops it belongs in an Issue for the coordinator, not in this PR: extend the PR-05 comment check to docstrings, or add a test over `src/` and `tests/` for `review (round \d|[BMSN]\d+ of #)`, with the existing tags removed.

### S2 (should-fix, correctness): an ID without both backticks is still dropped silently
`.github/governance/promised_tests.py:28,63`. Only paired backtick tokens are examined, so a promise is still skipped without a word in two cases:
- an ID with no backticks: `- tests/a.py::t1` next to `` - `tests/a.py::t2` `` gives `['tests/a.py::t2']`;
- an ID missing its closing backtick: `` `tests/a.py::t1` ``, `` `tests/a.py::t2 `` (no closing backtick), `` `tests/a.py::t3` `` gives `[t1, t3]`.

In both cases the step prints "N of N" with N smaller than the list a reviewer reads, which is the S1 scenario of round 1. The answer says "a listed promise is never dropped silently", and that is not yet true.

Fix: after removing the backticked tokens from a section line, fail on any `.py::` left in it, under the same `not read as a node ID` message. Add a test with both cases.

### S3 (should-fix, correctness): with N3, the step can run without uv
`.github/workflows/governance-pr-checks.yml:35-37`. The new step has `if: ${{ !cancelled() }}`, but `astral-sh/setup-uv` before it keeps the default `if: success()`.

Failure scenario: a PR with the heading and a wrong title. The first step fails, setup-uv is skipped, and the promised-tests step still runs. `uv run` then fails with "command not found", unless the runner image happens to ship uv, so `collected.txt` stays empty. The step reports every promise "not collected on the PR head", followed by an empty "its last lines:". That is a false report next to the real failure, which N3 was meant to make easier to read.

Fix: give the setup-uv step the same `if: ${{ !cancelled() }}`, and extend the N3 assertion in `test_the_pr_body_reaches_the_promised_tests_check_only_through_the_environment` (or a sibling test) to cover the setup-uv step too.

### Notes
- N1: a nested fence such as ```` ``` ```` followed by ```` ```bash ```` closes at the second line, because `FENCE_RE` also accepts an info string on a closing fence. CommonMark does not allow that. The case is contrived, and it fails closed when the section is left with no promise, so no change is asked.
- N2: an unclosed fence hides the rest of the body, headings included. That matches how GitHub renders it.

Verdict: changes requested. S1 to S3 together are about 10 lines plus one test, in one fix commit. That commit can be the one that merges `main` (c4c2de8) in before `ci:full`; round 3 then checks that diff and the three systems. S1's repo-wide check goes to an Issue.
