# Review of PR #105, round 2 (issue #91)

Reviewed head: 73bd190 (round 1 fixes in 1cae9ed, main b82eb66 with #107 and #108 merged in).

## Round 1 items

- **M1, fixed.** The initials check runs on `whole.lstrip(_OPENING)` again; the split word is used only for the abbreviation check. All six sentences from round 1 are table rows and cut into two utterances; "(J. Smith)" still counts as an initial. My 24-sentence edge probe matches main everywhere except the intended glued abbreviations.
- **S1, fixed.** `_GLUED_BEFORE` also splits at en dash, em dash and "/". Three new rows, and the Hypothesis property glues them too. No entry of `ABBREVIATIONS` contains any of the split characters, so no abbreviation can be split apart.
- **N1, kept (reason given):** the test imports the module's own list so it cannot drift. Accepted.

## What I ran on 73bd190

- ruff check, ruff format --check, lint-imports (3 kept, 0 broken), deptry: clean.
- Fast suite: 1749 passed, 17 subtests, 54 snapshots passed.
- `HYPOTHESIS_PROFILE=nightly`, `tests/unit -k "textprep or core or utterance"`: 733 passed, 23 snapshots.
- Corpus diff against main, 7 papers, with default steps and with no edits: identical to round 1 (only hardt with no edits changes, 328 to 326 utterances, the two "[p." sentences). No golden file changes.
- CI on 73bd190: all jobs green on Linux, macOS and Windows.

## Verdict

Clean. Squash-merge.
