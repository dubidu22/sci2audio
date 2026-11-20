# Plan: infra lane, batch B-I4 (#708, #695, #706)

Thread: implementation infra-b-i4, Opus 5.5. Date: 2026-11-20. Base: `main` at b00002d.
Two PRs with no shared file, both branched from current `main`:

- **PR 1** (#708): **critical** (it changes `.github/governance/promised_tests.py`, CRIT-01). Labels `lane:infra`, `risk:high`. Branch `claude/infra-b-i4-promised-sections`. Title `infra: a test-named section with node IDs fails the promised-tests check (#708)`. Waits for coordinator approval (PLAN-02).
- **PR 2** (#695, #706): non-critical. Labels `lane:infra` (as the lock for a repo-wide comment edit), `risk:low`. Branch `claude/infra-b-i4-review-tags`. Title `infra: a test keeps review-round tags out of comments and docstrings (#695)`. Starts once this plan is posted.

## What I found

1. **Merged bodies (last 40, probe at b00002d).** Seven bodies without the exact heading have a level-2 heading containing "test" whose section holds a backticked `.py::` outside fences: #689 (`## Plan tests`, 16 IDs), #671 (`## Tests (written first; each failed on main)`), #675 (`## Tests`), #691, #630, #601, #598 (`## How it was tested`). All of them predate D-849, which now requires the exact heading in a plan's PR. No docs-only, decision-log or Dependabot body is among them. Bodies that carry the exact heading (#690, #692, #696, #698, #707) also have other test-named sections (`## Test summary`, `## Tests`, `## Tests added in review round 1`); they stay untouched because the exact heading wins.
2. **Review tags (#695).** The issue's grep finds 106 lines. The forms in the repo are wider: `(#667 review S1)`, `(#481 review)`, `(review M1)`, `(review R1-2, R2-1)`, `(review of PR #228)`, `(review of #530, F1)`, `Review round 1 of #692, S1:`, `(#569 round 1, R3)`, `(round 2, N1)`, `(round 1 S1a)`, `(round 1)`. A prototype pattern over comments and docstrings of `.py` files and over comments of `.js` and `.toml` files finds about 440 tags in about 120 files outside `tests/regression/`. It has no hit on `preview`, `reviewers`, "for a review, see" (citation data) or the corpus sidebar word "Review".
3. **`tests/regression/*.toml`** carries 72 more tags, all in `goal = "..."` strings, not in comments. The regression cases are golden files (critical), and a goal string is data, so they are outside #695's "comments and docstrings". The scan skips `tests/regression/`, `tests/corpus/` and `__snapshots__/`; a follow-up Issue covers the goal strings.
4. **`governance/github-setup/` (#706).** `pr_checks.py` and `pr-check-exemptions.json` equal their live copies. `pr-checks.json` is stale. So are `labeler.yml` (lacks the nine governance critical globs), `pr-checks-workflow.yml` (unpinned actions, no promised-tests step) and `labeler-workflow.yml` (unpinned). `CODEOWNERS` is meant to differ (the README says "add its lines"). The README presents the folder as the owner's copy-from source, which is the scaffold's layout.

## PR 1 design (#708)

Changes to `.github/governance/promised_tests.py` only; no workflow change (exit 1 already fails the step).

- When the exact heading is absent and no `NEAR_RE` line exists, the check looks for a **test-named section**: a level-2 heading (`^##\s`, not `###`) whose text contains "test" in any case, whose section (up to the next level-1 or level-2 heading, outside fenced code) holds at least one backticked `.py::` token (`TOKEN_RE`, so an unreadable token counts too).
- **Choice: fail, not adopt.** Such a section fails as a near miss: `FAIL promised tests: "## Plan tests" (line 22) lists node IDs; list the plan's tests under ## Tests promised in the plan`. Adopting it as the promised section would quietly accept a heading PLAN-01 forbids, and would turn every "How it was tested" note that names a removed test into a confusing collection failure. Failing names the heading and its line, and the fix (renaming the heading) is one edit. `files` keeps returning nothing for it, so no collection runs.
- Order in `check`: exact heading, then `NEAR_RE` near miss (unchanged message), then the test-named section, then "no section (opt-in)".
- A body with no node ID under a test-named heading still passes (decision log, Dependabot, docs). Node IDs under a heading without "test" (`## What and why`) still pass, as today.
- **Presence, not novelty, by design.** A section that lists only tests already on `main` passes. The module docstring says the check proves that each promise collects on the head; whether the promises are the plan's is the reviewer's call against the plan. The PR body says so too. (Audit draft B's "list the promises that already collect on the base" is not in #708's criteria; it is not built.)
- `outside_fences` yields `(line number, line)` so the message can name the line; its two callers take the line part.
- Size: script about 30 lines, tests about 110.

## PR 2 design (#695, #706)

**(a) The test** `tests/unit/test_review_tags.py`, standard library only:
- `REVIEW_TAG`, the one pattern (case-insensitive words, case-sensitive finding letters): `#N review`, `#N round N`, `review round N`, `review of (PR) #N`, `review X1` (one or two capitals, digits), `round N, X1` / `round N of #N`, and `(round N)`. Comments in the test say which form each alternative is for.
- What is read: `.py` files under `src/` and `tests/`: `#` comments (via `tokenize`) and docstrings of modules, classes and functions (via `ast`, matched across the docstring's lines, reported at the matching line); `.js` and `.css` files: `//` and `/* */` comments; `.toml` files: `#` comments outside quoted strings; `.html` templates: `{# #}` and `<!-- -->`. Skipped: `tests/regression/`, `tests/corpus/`, `__snapshots__/`. Plain string literals in Python are data and not read.
- The failure lists every hit as `path:line: <match>`.

**(b) The clean-up.** Each tag is removed; an issue or PR number in it stays where it points to the reason (`(#667 review S1)` becomes `(#667)`, `(review of PR #228)` becomes `(#228)`, `(round 2, N1)` goes). Where a docstring opens with the tag (`Review round 1 of #692, S1: ...`), the sentence is rewritten to the why, which the text already gives in every case I looked at. No code, no string literal, no golden file and no file under `src/sci2audio/core/`, `.github/` or `tests/regression/` changes, so the PR stays non-critical. It touches files of every lane in comments and docstrings only; the PR body says so, and `lane:infra` is the lock label.

**(c) #706.** Keep the copy (the folder is the scaffold's layout and its README names `pr-checks.json` as the file to copy), make it byte-identical to `.github/governance/pr-checks.json`, and add a test in `tests/unit/test_lanes.py` that compares the bytes. A scaffold re-run that writes its own derivation (finding 3 of `infra-b-i3-plan.md`) then fails the test. The other stale copies (finding 4) get a follow-up Issue rather than silent edits here.

## Tests promised in the plan

PR 1, written first; the first two fail on `main`, the rest pass there and guard against over-matching or a revert:
- `tests/unit/test_promised_tests.py::test_the_body_shape_of_pr_689_fails`
- `tests/unit/test_promised_tests.py::test_node_ids_under_a_test_named_heading_fail_as_a_near_miss` (parametrized: `## Plan tests`, `## Tests`, `## How it was tested`, `## Tests (written first; each failed on main)`, `## TESTS`)
- `tests/unit/test_promised_tests.py::test_a_test_named_heading_without_node_ids_passes`
- `tests/unit/test_promised_tests.py::test_a_fenced_node_id_under_a_test_named_heading_passes`
- `tests/unit/test_promised_tests.py::test_node_ids_under_another_heading_pass` (also `### Plan tests`, level 3, which #708 leaves alone)
- `tests/unit/test_promised_tests.py::test_the_exact_heading_wins_over_a_test_named_section`
- `tests/unit/test_promised_tests.py::test_a_section_of_tests_already_on_main_passes`

Existing tests stay green unchanged, in particular `tests/unit/test_promised_tests.py::test_a_body_without_the_heading_passes_the_check`, `tests/unit/test_promised_tests.py::test_a_near_miss_heading_fails` and `tests/unit/test_promised_tests.py::test_the_exact_heading_wins_over_a_near_miss`.

PR 2, written first; the first and the last fail on `main`:
- `tests/unit/test_review_tags.py::test_no_comment_or_docstring_carries_a_review_tag`
- `tests/unit/test_review_tags.py::test_the_pattern_catches_every_known_form` (parametrized over the forms of finding 2, including both forms named in #695)
- `tests/unit/test_review_tags.py::test_the_pattern_leaves_plain_words_alone` (parametrized: "for a review, see", `preview`, "#3 reviewers", "round 2 decimals", "a review of the literature")
- `tests/unit/test_review_tags.py::test_only_comments_and_docstrings_are_read` (a Python string literal, a TOML string value and a JS string are not read; a Python comment, a docstring line, a TOML comment and a JS comment are, with their line numbers)
- `tests/unit/test_lanes.py::test_the_scaffold_copy_of_pr_checks_json_equals_the_live_one`

## Checks, PRs, ledger

- Before each PR, one `uv run` at a time: `uv run ruff check && uv run ruff format --check && uv run lint-imports && uv run deptry src && uv run pytest -m "not slow and not benchmark and not browser" -k "not espeak"` and `uv run zizmor --offline .github/workflows`. `.github/governance` is never passed to `ruff format` by name. PR 2 also runs `uv run pytest -m browser` once, since it edits comments in `static/*.js` and browser tests (no behaviour change expected).
- Bodies: `Closes #708` / `Closes #695` and `Closes #706`; the section `## Tests promised in the plan` with the node IDs above; licence note "none"; risk; follow-ups. PR 1's body states the presence-not-novelty point and the probe of finding 1.
- Ledgers `governance/ledger/prs/pr-<N>.yaml` like `pr-707.yaml`.

## Out of scope, follow-ups

- Issue: the 72 review tags in `goal` strings of `tests/regression/*.toml` (golden files, critical, `lane:textprep`).
- Issue: the other stale copies in `governance/github-setup/` (`labeler.yml`, `pr-checks-workflow.yml`, `labeler-workflow.yml`), with the same equality test or removal.
- Audit N4 (`promised_tests.py` reads every collected line with `::`; keeping only `tests/` lines would match #698's fix) and audit draft B's base-commit listing: only if the coordinator wants them, as one infra Issue.
- `pr_checks.py`'s PR-05 comment warning could reuse `REVIEW_TAG`; it is a scaffold copy, so that is an upstream change.
