# Answer to review round 1 of PR #707

Thread: infra-b-i3. Fix commit 32235db on top of ffb0d7b; `main` has not moved (9066c3d).

## Fixed

- **S1**: `promised_tests.py` now finds the exact heading only among the lines `outside_fences()` yields.
  - `section()` starts at the first unfenced heading. A fenced example before the real section no longer starts the section or swallows it.
  - `near_miss()` ignores a fenced heading, so a near-miss outside fences is reported.
  - New tests, both failing on ffb0d7b and passing on 32235db:
    - `tests/unit/test_promised_tests.py::test_a_fenced_example_of_the_heading_does_not_start_the_section`, the reviewer's scenario 1.
    - `tests/unit/test_promised_tests.py::test_a_fenced_heading_does_not_hide_a_near_miss`, scenario 2.
- **N2**: the PR body's test summary now gives the true counts. Of the 20 cases promised first, 9 failed on `main`; 11 passed there, and the body names them and why they are kept. The plan's sentence "each one fails on main" is corrected in the same way. Both new IDs are added to the body's `## Tests promised in the plan` and to the plan.
- **N3**: `test_every_extract_repeats_the_rules_and_the_profile_of_the_ruleset` now also asserts that an extract holds exactly the ruleset rules whose `applies_to` names its role or `all`. That selection matches the generator for all six extracts today. Checked by deleting THR-09 from `kb.yaml`: the test fails, naming `THR-09`. The file was restored afterwards.
- **N4**: `profile()` skips blank lines and comment lines inside `project_profile` and ends only at the next unindented line.

## Not changed

- N1: follows D-855; no change.
- N5: the coordinator's step after the merge.

## Checks on 32235db

ruff check, ruff format --check, lint-imports (3 kept), deptry src: clean. Fast suite with `-k "not espeak"`: 8660 passed, 6 skipped, 6 xfailed. zizmor: no findings.
