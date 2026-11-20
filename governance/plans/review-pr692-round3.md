# Review PR #692, round 3, final (batch B-I2, #687)

Thread: review-infra-b-i2 (Opus 5.5). Head reviewed: 359dd9b (fix commit bb4ae8b plus merge commit 359dd9b of `main` c4c2de8). Date: 2026-11-20.
**Critical: yes** (unchanged). Plan `plans/infra-b-i2-plan.md`, section "#687", approved as D-846. Answer: `plans/answer-pr692-round2.md` (governance 3a6e0ff).

**Verdict: approved** (0 must-fix, 0 should-fix, 2 notes).

## Verified

- Fix commit `git diff 52faf88..bb4ae8b`: the same four files, +43/−12, and only the three round-2 answers.
  - S1 (narrating-comment): both docstrings now keep only the why. No line the PR adds against `main` holds "review" or "round N". The repeated kind is Issue #695 (open, v1.4, `lane:infra`, `risk:low`), which the PR body's "Out of scope" names.
  - S2: `read()` removes the backticked tokens from each section line and then reports any `\S*\.py::\S*` left over as unreadable. Probes: a bare ID gives `bad=['tests/a.py::t1']`; an unclosed one gives ``bad=['`tests/a.py::t2']``; a bare spaced ID is flagged too. A `.py::` inside a fence or after the section is still ignored, as intended. Test: `test_a_promise_without_both_backticks_fails`, which pins the exact FAIL line.
  - S3: `astral-sh/setup-uv` has `if: ${{ !cancelled() }}` (`governance-pr-checks.yml:36`). `test_the_pr_body_reaches_the_promised_tests_check_only_through_the_environment` asserts it, and it finds the step by the action name, not the version.
- Merge commit 359dd9b:
  - Its parents are bb4ae8b and c4c2de8 (= `origin/main`), and `git diff-tree --cc` shows no conflict resolution.
  - `git diff 359dd9b^1 359dd9b` is byte-identical to `git diff c4c2de8^ c4c2de8`: #691's three files and nothing else.
  - `git diff c4c2de8...359dd9b` is byte-identical to `git diff caecf7a bb4ae8b`: the PR's own four files, +423.
- PR body: the promised-tests section holds 17 node IDs. Governance pr checks runs 44797165479, 44797168140, 44797169566 and 44797221417 (pull_request, headSha 359dd9b) all print `ok   promised tests: 17 of 17 collect`.
- Security is unchanged from rounds 1 and 2: `pull_request` only, `contents: read` and `pull-requests: read`, the body only through `env:`, no `${{ }}` in `run:`, setup-uv pinned to v10.3.3, and `persist-credentials: false` asserted in the checkout step.
- Local run in a fresh `/tmp/review-692` at 359dd9b:
  - ruff check: clean. ruff format --check: 385 files formatted.
  - lint-imports: 3 kept, 0 broken. deptry src: no issues.
  - `uv run zizmor --offline .github/workflows`: no findings.
  - Fast suite with `-k "not espeak" -n auto`: 8612 passed, 6 skipped, 6 xfailed.
- Not verified here: the `ci:full` three-system run on 359dd9b was still in progress (`tests` on ubuntu, macOS and Windows pending). The coordinator checks it before the merge go (MRG-01, CLAUDE.md step 8).

## Findings

### Notes
- N1: for an unclosed promise, the FAIL line names the fragment with its leading backtick (`` `tests/...::unclosed ``). That is clear enough to fix the body, so no change is asked.
- N2: from round 2, N1 (a nested fence closes on an info-string line) and N2 (an unclosed fence hides the rest of the body) still stand. Both are contrived or match GitHub's rendering.

Verdict: approved. Merge on the coordinator's go, pinned to 359dd9b, once `tests (ubuntu-latest)`, `tests (macos-latest)` and `tests (windows-latest)` are green on that head.
