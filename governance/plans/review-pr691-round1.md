# Review PR #691, round 1 (batch B-I2, #681)

Thread: review-infra-b-i2 (Opus 5.5). Head reviewed: d33cf73. Date: 2026-11-20.
**Critical: yes** (CRIT-01: `critical_paths` in `.github/governance/pr-checks.json` and the `risk:high` labeler under `.github/**`; `risk:high` set). Plan `plans/infra-b-i2-plan.md`, section "#681", approved as D-846.

**Verdict: approved** (0 must-fix, 0 should-fix, 4 notes).

## Verified

- Scope: 3 files, exactly the plan's PR A list (`.github/governance/pr-checks.json`, `.github/labeler.yml`, `tests/unit/test_lanes.py`). All are lane:infra or tests. The PR shares no file with #692, and `governance-config.json` and `project_profile` are untouched (#683 stays with Colin). #681's acceptance criteria are met: the name-prefix convention covers every process, contract and architecture document, the labeler and `critical_paths` list them, `test_lanes.py` passes, and the decision-log PR stays non-critical.
- Globs: the four globs (`governance/kb/README.md`, `governance/kb/**/adr-*.md`, `governance/kb/**/playbook-*.md`, `governance/kb/**/doc-*.md`) are appended to `critical_paths` (`pr-checks.json:89-92`) and under `risk:high` (`labeler.yml:18-21`), in the same order. `test_the_labeler_marks_the_paths_the_check_holds_critical` compares the two lists in full. In `pr_checks.matches`, `**/` also matches zero folders, as minimatch does in the labeler: `governance/kb/adr-009-x.md` and `governance/kb/a/b/doc-x.md` both match.
- Every KB file is in exactly one list. I checked this by hand with `git ls-tree` and `pr_checks.matches`, apart from the PR's test, against the test's `KB_CRITICAL` and `KB_RECORDS`:
  - `origin/main`: 50 files, 20 critical, 0 in both lists or in neither.
  - The PR head d33cf73: the same 50 files and the same result.
  - `origin/governance`, where the KB is written before a sync: 50 files, 0 wrong.
  - The 20 critical files are 6 `adr-*`, 6 `playbook-*`, 7 `doc-*` and `governance/kb/README.md`.
  - Every records glob matches at least one file, so none is dead.
- The decision log stays non-critical. A dry run of `run_checks` on `decision-log.md` plus `pending-decisions.md` with no label and a `kb:` title gives commits ok, scope ok (governance-only) and new docs ok, with no `critical` result. A governance-only sync that edits `playbook-phase-0-foundation.md` without `risk:high` gives `critical FAIL`, the consequence D-846 accepted.
- Promised tests: the three new node IDs exist as named, and the body lists them as node IDs:
  - `test_kb_process_contract_and_architecture_documents_are_critical`, with 4 parameters;
  - `test_the_decision_log_and_the_kb_records_are_not_critical`, with 5 parameters;
  - `test_every_kb_file_is_critical_or_a_record`.
- The tests fail without the change: with `pr-checks.json` from `origin/main`, 6 of the 35 tests in `test_lanes.py` fail (the labeler sync, the 4 critical cases and the every-file guard).
- Local run in `/tmp/review-691` at d33cf73 (macOS M4):
  - ruff check: clean. ruff format --check: 384 files formatted.
  - lint-imports: 3 kept, 0 broken. deptry src: no issues. zizmor: no findings.
  - `test_lanes.py` and `test_ci_workflows.py`: 59 passed.
  - Fast suite with `-k "not espeak" -n auto`: 8595 passed, 6 skipped, 6 xfailed.
- CI at d33cf73: `CI passed`, `tests (ubuntu-latest)`, `governance pr checks`, `label`, `security`, `licences`, `lint and layers`, both browser shards and CodeQL are green. `ci:full` run 44791861553 (workflow_dispatch, headSha d33cf73) is green, including `tests (macos-latest)` and `tests (windows-latest)`.
- Licences: none.

## Findings

### Notes
- N1: the every-file guard sees only files tracked on the product repository's branches. A new KB file is written on `governance`, so the guard fires at the sync PR that brings it to `main`, not when the file is written. That is still before it lands, which is what the plan asks. The KB thread should expect the failure there and rename the file.
- N2: a `doc-*`, `adr-*` or `playbook-*` file under `merged-batches/`, `00-index/` or `tools/` would be in both lists. The guard fails on it loudly, which is the right outcome; no such file exists today.
- N3: the body lists the tests under "How it was tested" rather than under `## Tests promised in the plan`. That is correct while #692 is unmerged. Once #692 is on `main`, an edit of this body triggers the check, so use the heading if the body changes.
- N4: CRIT-01 also names the KB contract documents in `project_profile.critical_paths`. They join #683's list, as the PR body says.

Verdict: approved. Ready to merge on the coordinator's go, pinned to d33cf73 (MRG-01). It is not behind `main` in any file it touches: its base caecf7a is the current `main`.
