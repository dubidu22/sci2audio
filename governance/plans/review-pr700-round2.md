# Review PR #700, round 2, final (batch B-D1, #678, #686)

Thread: review-docs-b-d1 (Opus 5.5). Head reviewed: 5465f8f (fix commit on 1636cc7). Date: 2026-11-20.
**Critical: no** (unchanged). Answer: `plans/answer-pr700-round1.md` (governance 2b3e9e0).

**Verdict: approved** (0 must-fix, 0 should-fix, 1 note).

## Verified

- Fix commit `git diff 1636cc7 5465f8f`: one line, `docs/design/PRODUCT.md:67`, and nothing else. The branch has one commit since round 1, and against `main` 9066c3d it still touches only the same three files (+5/−3).
- S1 (stale-doc-claim) is fixed at its root. `PRODUCT.md:67` now reads "There are no network calls except the voice download the user starts and the update check the user turned on.", as `CLAUDE.md:11` says. It agrees with line 40.
  - A grep of `docs/design` for "update check", "no network" and "only network" finds no other claim about the product's behaviour.
  - `IMPLEMENTATION-PROMPT.md:3` states the rule for the planning brief of 15 Nov; it is a frozen brief, so the answer is right to leave it.
- The round-1 notes N1 to N3 are answered with reasons (N1: the prototype is frozen at b4a7523, and the plan limits the change to line 578). That is accepted.
- Merge with #701 at its round-2 head: `git merge-tree 5465f8f 92c2894` is clean. The `PRODUCT.md` hunks are at 37–43, 64–70 (#700) and 52–58, 75–81 (#701).
- Local run in a fresh `/tmp/review-700` at 5465f8f: `uv run ruff check` clean.
  - Fast suite `-m "not slow and not benchmark and not browser" -k "not espeak" -n auto`: the first run gave 1 failed and 8637 passed. It ran in 212 s, against about 130 s for the others, and printed only its summary line, so the failing test's name is not recorded.
  - A second run gave 8638 passed, 6 skipped, 6 xfailed.
  - The only tests that read `docs/design` (`test_lanes.py`, `test_ci_workflows.py`) pass alone (63 passed).
  - The diff is one Markdown line, so the failure has no cause in this PR. It fits the timing tests known to fail once under `-n auto` (#671 body). Not a finding.
- CI on 5465f8f: `governance pr checks`, `label critical paths` and CodeQL are green; `CI` was running at review time. The coordinator checks `CI passed` before the merge go (MRG-01).

## Findings

### Notes
- N1: `prototype/app.js:579` ("The one exception: the voice download you start") stays, as round 1 N1 allowed. It is a design record, not product text.

Verdict: approved. Merge on the coordinator's go, pinned to 5465f8f, once `CI passed` is green on that head.
