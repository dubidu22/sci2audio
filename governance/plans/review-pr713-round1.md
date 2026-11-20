# Review PR #713, round 1 (batch B-I4, #708)

Thread: review-infra-b-i2 (Opus 5.5), the infra lane's review thread. Head reviewed: b208787. Date: 2026-11-20.
**Critical: yes** (CRIT-01: it changes `.github/governance/promised_tests.py`, which the required `governance pr checks` runs; `lane:infra`, `risk:high`). Plan `plans/infra-b-i4-plan.md`, section "PR 1 design", approved as D-860 ("fail, not adopt").

**Verdict: approved** (0 must-fix, 0 should-fix, 3 notes).

## Verified

- (1) Scope: two commits on `main` b00002d: the tests first (4bac1d6), then the change (b208787). Only two files change, `.github/governance/promised_tests.py` (+39/−6) and `tests/unit/test_promised_tests.py` (+117). There is no workflow change, so zizmor has nothing new to check, and the existing exit 1 already fails the step.
- (2) Logic:
  - `check` runs in the order the plan sets: the exact heading (`promised() is not None`), then the `NEAR_RE` near-miss with its message unchanged, then `misnamed()`, then `ok … (opt-in)`.
  - `misnamed()` returns `None` when the exact heading is present outside fences. It takes a section to be the lines from a level-2 heading up to the next level-1 or level-2 heading (`END_RE`), so a `###` heading stays inside the section, as in `section()`. It counts only a backticked `.py::` (`TOKEN_RE`), so an unreadable token counts too, and it skips fenced lines.
  - The message names the heading and its 1-based body line. CRLF bodies give the same line, and the body's own line 10 in `PR_689` is confirmed by the test.
  - `files` still goes through `promised()`, which is `None` for a test-named section, so no collection runs.
  - `outside_fences()` now yields `(number, line)`, and `section()` and `near_miss()` take the line part. All 37 tests in the file pass.
- (3) Promised tests:
  - All seven node IDs exist and pass on b208787, the parametrized cases included:
    - the #689 shape;
    - `## Plan tests`, `## Tests`, `## How it was tested`, `## Tests (written first; each failed on main)` and `## TESTS`;
    - a test-named heading without node IDs;
    - a fenced node ID under such a heading;
    - `## What and why`, `### Plan tests` and `# Tests`;
    - the exact heading over a test-named section;
    - a section of tests already on `main`.
  - With `main`'s script (`git checkout b00002d -- .github/governance/promised_tests.py`, then restored), only `test_the_body_shape_of_pr_689_fails` and the 5 `…fail_as_a_near_miss` cases fail, as the plan says.
  - The three existing tests the plan names still pass: `test_a_body_without_the_heading_passes_the_check`, `test_a_near_miss_heading_fails` (6 cases) and `test_the_exact_heading_wins_over_a_near_miss`.
- (4) False positives: I ran the head's script over the bodies of the last 40 merged PRs.
  - The only test-named sections are #689, #671, #675, #691, #630, #601 and #598, which is exactly the plan's finding-1 list. All of them predate D-849. Among the last 15 merged, those are #691, #689, #675 and #671.
  - Every body with the exact heading (#707, #698, #696, #692, #690) reads as a section. The rest read as opt-in, including the decision-log PR #662 and the docs PRs.
  - The open PRs are unaffected: #715, #713 and #712 have the exact heading, and the release PR #426 is opt-in.
- (5) The PR's own body has `## Tests promised in the plan`. Governance pr checks runs 44828772169, 44827789814 and 44827790059 on b208787 print `ok   promised tests: 10 of 10 collect` (the 7 new IDs plus the 3 existing ones). The body states the presence-not-novelty point, and the module docstring says the same.
- (6) Local run in a fresh `/tmp/review-713` at b208787:
  - ruff check: clean. ruff format --check: 388 files formatted.
  - lint-imports: 3 kept. deptry src: no issues.
  - `zizmor --offline .github/workflows`: no findings.
  - Fast suite with `-k "not espeak" -n auto`: 8682 passed, 6 skipped, 6 xfailed.
- CI: `ci:full` run 44828784142 (headSha b208787) is green, with `tests` on ubuntu, macOS and Windows a success. Linux `CI passed` and `governance pr checks` are green.
- Licences: none.

## Findings

### Notes
- N1: `TESTS_HEADING_RE` (`promised_tests.py:39`, `##\s.*test`) matches "test" inside a word, as the plan words it ("contains 'test' in any case"). So `## Latest results` or `## Attestation` followed by a backticked node ID fails as a misnamed promise (probe: `misnamed("x\n## Latest results\n- `tests/a.py::t`\n")` gives `"## Latest results" (line 2)`). This fails closed, and the message names the heading. `##\s.*\btest` would keep `Tests`, `Testing` and `tested` and drop the in-word cases. It is optional, and the follow-up Issue #711 can take it along.
- N2: a plan-less quarantine PR (D-374) whose body has `## Quarantined test` with the node ID now fails. It must list that ID under the exact heading or use another heading. A quarantined test still collects, because it is skipped, not removed, so the exact heading works. The quarantine PRs so far (#698) had a plan and the heading.
- N3: when a body has both a near-miss line and a test-named section, the near-miss message wins. That follows the plan's order, though no test pins it. It is the more specific message, so no change is asked.

Verdict: approved. Merge on the coordinator's go, pinned to b208787. It is current with `main` (base b00002d = `main`), and the three-system run is green on that head.
