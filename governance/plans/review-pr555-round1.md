# Review PR #555, round 1 (docs batch B4: #522, #526)

Reviewer: review thread "Review the contract and CLAUDE.md wording PR", 18 Nov 2026 ~20:55Z. Critical (layer contract document, CLAUDE.md process text), Opus high.
Head reviewed: 8d9d81b. Base: main 1797ceb (unchanged since the branch was cut, checked with ls-remote).

## Verdict: APPROVED, 0 findings. Merge pinned to 8d9d81b.

## Checks

1. **Diff scope.** `git diff 1797ceb 8d9d81b --stat`: 2 files, 3 insertions, 3 deletions (`CLAUDE.md` 2 lines, `docs/readalong-format.md` 1 line). Word diff shows three insertions only; no other word changed. No code, test or golden file touched.
2. **#522 sentence.** Inserted text equals the issue's acceptance criterion character for character: "It is never set on a chapter's first chunk and only joins a chunk to the one before it in the same block; a reader treats any other `joins` as false." No new key, format version stays 1, Changes section untouched (AC 2 met).
3. **#522 sentence matches the code.** Writer: `app/audio.py` (chapters/spoken builder) resets `linked` at each chapter start, so a chapter's first chunk never `continues`; `output/write.py:_trim_joins` uses the same rule. Reader: `web/player.py:sentence_starts` (984-1010) follows `joins` only when the chunk before is the one drawn just before it in the same block and ignores any other `joins`. The contract now states both sides.
4. **#526 item 2.** Clause "except that a bug Colin marks as priority gets its own parallel implementation thread (D-732)" after "per lane". Matches LANE-02 in rules 1.4.6 (`project-rules.yaml:176`, source lists D-732). D-732 (KB decision log row 60; decisions-d712-d714.md:91) is the priority-bug parallel-thread exception. Citation correct.
5. **#526 item 9.** "(per browser for a browser test, D-682)" after "run the test alone 40 or more times". Matches TST-08 ("The 40-run isolation per browser (D-682)"). D-682 (KB decision log row 110) ends "Lesson: before quarantining a flaky test, run it alone 40 or more times per browser." Citation correct.
6. **No contradiction with rules 1.4.6.** Item 2 now equals LANE-02; item 9 equals TST-07/TST-08 order (same-day quarantine, isolation after, D-739).
7. **CI on 8d9d81b.** `CI passed` success (run 44391375682), `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` success, browser Chromium 1/2 and 2/2 success, lint and layers, licences, security, CodeQL success. Three-system run green (CLAUDE.md item 8 / D-580 met).
8. **PR body.** Attribution lines present; `Closes #522`, `Closes #526`; commit message has no closing keyword; labels documentation, risk:high, lane:docs.

## Note for the coordinator (out of scope, not a finding)

CLAUDE.md item 2 still lists the lanes as "extraction/voices, layout, textprep, app/release" while the project now also runs web and docs lanes. Pre-existing wording; #526 forbids other changes, so it is left for the coordinator to file or fold into the next CLAUDE.md PR.

Correction (20:55Z): rules 1.4.6 `execution_lanes` also lists only these four, and `lane_mapping_note` maps the web lane into app/release, so CLAUDE.md matches the rules file today. The drift is between the rules and current practice (B4 runs as a docs lane, B8 as a web lane). Filed as #560, which waits for the coordinator's rules change first.
