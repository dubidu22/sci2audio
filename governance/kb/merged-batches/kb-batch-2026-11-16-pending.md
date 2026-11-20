# KB batch D-628 to D-655 (MERGED as KB PR #50, 3b0c57a, 15 Nov 19:04:55 UTC)

Collected by the KB thread. The batch for 15 Nov up to D-627 was merged as KB PR #49 (23f913f). Entries made after that merge (15 Nov from 13:42 UTC onward) are collected here for the next KB PR (one per day; D-626: merged by the KB thread without review). Branch it from sci2audio-design main 23f913f, or later.

Under D-626 (the reporting rule: Colin's point 6, which the coordinator calls rule 5), the coordinator reports non-critical decisions to Colin only when he asks. Those rows say "no chat line (D-626)" in place of a "Colin informed" time.

## Decisions

### D-628 · PR #366 (#343, #344 page progress and cancel) review round 1

- Subject: PR #366, page progress while a PDF is read and cancel stopping the reader (#343, #344; D-623): review round 1.
- Decision: round 1 at head 766d56a. Notes are in `plans/review-pr366-round1.md` (project files). Verdict: not approvable yet.
  - B1: a SIGINT that reached the reader child during its start was reported as an unreadable file instead of "cancelled". Fix: the child ignores SIGINT, so only the parent's cancel path stops it. A test sends a real SIGINT.
  - S1: the test of the per-step deadline times its upper bound at the decision point, or uses 2.0 s.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 13:53 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-623.
- Record: sci2audio PR #366 (open), Issue #343, Issue #344; `plans/review-pr366-round1.md`, `plans/issue343-344-pdf-progress-cancel-plan.md` (project files); D-623, D-626.

### D-629 · PR #359 (units, D-605 PR 2) approved after round 3 and merged

- Subject: PR #359, units and signs read the same on a second run (#320, #321, #335; D-605 PR 2), approved and merged.
- Decision: round 3 (`plans/review-pr359-round3.md`, project files) approved the PR at head f876880.
  - B1 (D-624) is fixed: the fraction stays as printed only where `_unit_chain` also leaves the power as printed. The six rows read the same on both runs.
  - About 140 probe shapes were tried, 8 mutants were killed, and CI is green on all three systems.
  - Squash-merged as 739f69c at 14:06:19 UTC, which closed #320 (14:06:20), #321 (14:06:22) and #335 (14:06:24).
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 14:06 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-610, D-618 and D-624.
- Record: sci2audio PR #359 (merged as 739f69c), Issue #320, Issue #321, Issue #335 (closed); `plans/review-pr359-round1.md`, `plans/review-pr359-round2.md`, `plans/review-pr359-round3.md` (project files); D-605, D-610, D-618, D-624.

### D-630 · Textprep thread passes the fitness check; D-605 PRs 5 to 7 become one PR

- Subject: the first D-627 fitness check, and one combined PR for D-605 PRs 5 to 7.
- Decision:
  - The textprep thread passed the first D-627 fitness check: at least one compression, and it stated its plan and open items from memory. It keeps the next work.
  - The plan `plans/textprep-v12-pr5-7-plan.md` (project files) is approved. D-605 PRs 5 to 7 become one critical PR, in this order:
    1. links in brackets, #326 and #337;
    2. citation nests, #338, #339 and the #278 subject row;
    3. #342.
  - Tests come first for each part, the readings follow D-605, and the probes and samples are done before the PR opens.
- Status: Decided (Claude) (coordinator, 15 Nov 14:19 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-605 and D-627. **Refines D-605** (PRs 5 to 7 merged into one).
- Record: sci2audio Issue #326, Issue #337, Issue #338, Issue #339, Issue #278, Issue #342; `plans/textprep-v12-pr5-7-plan.md`, `plans/textprep-v12-followups-plan.md` (project files); D-599, D-605, D-627.

### D-631 · PR #361 (English numbers, D-605 PR 3) approved after round 2 and merged

- Subject: PR #361, minus signs and powers read the same on a second run (#336, #340, #210; D-605 PR 3), approved and merged.
- Decision: round 2 (`plans/review-pr361-round2.md`, project files) approved the PR at head 2e3d50d, after the round-1 fixes of D-621. It was squash-merged as eb28274 at 14:24:44 UTC, which closed #336 (14:24:45), #340 (14:24:47) and #210 (14:24:49).
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 14:36 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-605, D-614 and D-621.
- Record: sci2audio PR #361 (merged as eb28274), Issue #336, Issue #340, Issue #210 (closed); `plans/review-pr361-round1.md`, `plans/review-pr361-round2.md` (project files); D-605, D-614, D-621.

### D-632 · PR #366 (page progress and cancel) approved after round 2 and merged; flake #365 quarantined

- Subject: PR #366, page progress while a PDF is read and cancel stopping the reader (#343, #344; D-623), approved and merged. Also: flake #365 is quarantined.
- Decision:
  - Round 2 (`plans/review-pr366-round2.md`, project files) approved the PR at head 4108d81, after B1 and S1 of D-628.
  - Main eb28274 was merged in as 98300bb. The PR was squash-merged as 0e830ee at 14:35:45 UTC, which closed #343 (14:35:47) and #344 (14:35:49).
  - One gap is accepted: on Windows, a Ctrl-C (SIGINT) in the reader child's first millisecond or so can still be misreported. It is filed as #367 (v1.2).
  - The browser flake #365 (`test_pasted_text_opens_and_is_analysed`) failed a second time today without a code cause. Under D-374 a quarantine PR is ordered, and the test must be fixed before v1.2.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 14:36 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-374, D-623, D-625 and D-628.
- Record: sci2audio PR #366 (merged as 0e830ee), Issue #343, Issue #344 (closed), Issue #367, Issue #365 (open, v1.2); `plans/review-pr366-round1.md`, `plans/review-pr366-round2.md` (project files); D-374, D-623, D-625, D-628. The quarantine PR is #369, merged as 3fcba56 (D-634).

### D-633 · PR #368 (German numbers and labels, D-605 PR 4) review round 1

- Subject: PR #368, German date ranges, section numbers and caption labels read the same on a second run (#334, #349, the caption part of #249; D-605 PR 4, D-615): review round 1.
- Decision: round 1 at head 0919637. Notes are in `plans/review-pr368-round1.md` (project files). Verdict: not approvable yet.
  - S1: the ordinal guard after "Punkt" applies only after a digit.
  - S2: caption and notice agree on decimal labels like "2.1a" and "S3.1".
  - S3: the second-run differences on "1.2-1.4" and "3,1" are fixed in this PR, not deferred.
  - N1: the date-range readings go into the PR's table.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 14:36 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-605 and D-615.
- Record: sci2audio PR #368 (open), Issue #334, Issue #349, Issue #249; `plans/review-pr368-round1.md` (project files); D-605, D-615.

### D-634 · Flake #365 is quarantined

- Subject: the browser test `test_pasted_text_opens_and_is_analysed` is quarantined (#365).
- Decision: the test failed a second time today without a code cause, so it is quarantined under D-374. PR #369, "testing: quarantine the pasted-text browser test until #365 is fixed" (head 792197d), was squash-merged as 3fcba56 at 14:41:32 UTC. #365 stays open on v1.2 with the label P1 (testing, lane:web) and must be fixed before the v1.2 release. Main is now 3fcba56.
- Status: Decided (Claude) (coordinator, 15 Nov 14:41 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Carries out D-374, as ordered in D-632.
- Record: sci2audio PR #369 (merged as 3fcba56), Issue #365 (open, v1.2, P1); D-374, D-625, D-632.

### D-635 · The app-lane thread fails its fitness check and is stopped

- Subject: the first failed D-627 fitness check (app lane).
- Decision:
  - The app-lane thread failed its first D-627 fitness check. Its five or more compressions could not be verified, and it could not state its next issues from memory. It is stopped.
  - The v1.1 player wins, #152, #153, #154, #119 and #190, go to a fresh app-lane thread as one non-critical PR, once new threads are allowed again (D-611).
  - Lesson: new threads get their issue list in their instructions.
- Status: Decided (Claude) (coordinator, 15 Nov 14:43 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-627. Waits for D-611 to be lifted.
- Record: sci2audio Issue #152, Issue #153, Issue #154, Issue #119, Issue #190; D-611, D-626, D-627.

### D-636 · PR #368 round 2: the notice must follow the caption

- Subject: PR #368 (D-605 PR 4: German numbers and labels), review round 2.
- Decision: round 2 at head 7936a1c. Notes are in `plans/review-pr368-round2.md` (project files), and the author's answer to round 1 is in `plans/review-pr368-round1-answer.md`. Verdict: not approvable yet.
  - S1: the notice honours a switched-off Numbers step, as `footnotes.py` does, so that caption and notice agree.
  - S2: the notice reads its label from the caption text inside the label span, which covers fraction labels such as "Abb. 3/4".
  - "Tab. 3x" (a German notice keeps "3x" while the caption reads "3 mal") is the same on main. It is filed as #370 (v1.2).
  - Round 3 is the approving round. Under D-626, a non-critical PR has at most 2 rounds, but this PR is critical, so it may go up to 4.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 14:57 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-615 and D-633.
- Record: sci2audio PR #368 (open), Issue #370 (v1.2), Issue #249; `plans/review-pr368-round1-answer.md`, `plans/review-pr368-round2.md` (project files); D-595, D-615, D-626, D-633.

### D-637 · PR #368 (D-605 PR 4) approved after round 3 and merged

- Subject: PR #368, German date ranges, section numbers and caption labels read the same on a second run (#334, #349, the caption part of #249; D-605 PR 4), approved and merged.
- Decision: round 3 (`plans/review-pr368-round3.md`, project files) approved the PR at head d0fb704, after S1 and S2 of D-636. It was squash-merged as 82d9e0d at 15:24:51 UTC, which closed #334 (15:24:53) and #349 (15:24:55). #249 stays open for its formula part, #362 (D-615). One more shape was added to #370.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 15:25 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-615, D-633 and D-636.
- Record: sci2audio PR #368 (merged as 82d9e0d), Issue #334, Issue #349 (closed), Issue #249 (open), Issue #362, Issue #370; `plans/review-pr368-round1.md`, `plans/review-pr368-round2.md`, `plans/review-pr368-round3.md` (project files); D-605, D-615, D-633, D-636.

### D-638 · PR #371 (D-605 PRs 5 to 7) review round 1

- Subject: PR #371, links in brackets, citation nests and German closing quotes read the same on a second run (#326, #337, #338, #339, #278, #342; D-630): review round 1.
- Decision: round 1 at head 245323a. Notes are in `plans/review-pr371-round1.md` (project files). Verdict: not approvable yet.
  - S1: when a removed link bracket is glued to a kept bracket, one space is left before the kept bracket. The cases are "(see URL)(more)", "(Fig. 3)" and the German equivalents.
  - A subject nest with a second bracketed citation (it loses names) is the same on main and outside D-605. It is filed as #372 (v1.2).
  - Round 2 is the approving round.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 15:29 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-605 and D-630.
- Record: sci2audio PR #371 (open), Issue #326, Issue #337, Issue #338, Issue #339, Issue #278, Issue #342, Issue #372 (v1.2); `plans/review-pr371-round1.md` (project files); D-599, D-605, D-630.

### D-639 · The thread freeze is lifted (Colin)

- Subject: the D-611 thread freeze is lifted, and work continues as usual under D-626 and D-627.
- Decision: Colin's words, in the project chat at 15:48:44 UTC: "continue as usual". The coordinator's consequences:
  - a review thread starts for PR #364 (#360, D-620);
  - a fresh app-lane thread starts for the v1.1 player wins #152, #153, #154, #119 and #190, as one PR (D-635).
- Status: **Decided** (Colin, 15 Nov 15:48:44 UTC; the coordinator's consequences were posted in the project chat at 2026-11-15 15:49:02 UTC). Lifts D-611.
- Record: sci2audio PR #364, Issue #152, Issue #153, Issue #154, Issue #119, Issue #190; D-611, D-620, D-626, D-627, D-635.

### D-640 · PR #364 ("CI passed" after cancelled runs) review round 1

- Subject: PR #364, "ci: labels start no CI run; ci:full starts one by hand" (#360; D-620), review round 1.
- Decision: round 1 at head c3f9728. Notes are in `plans/review-pr364-round1.md` (project files). Verdict: not approvable yet.
  - S1: the "CI passed" test must anchor the job-level `if: always()`, so that option B (`!cancelled()`, rejected in D-620) would fail it.
  - Accepted as they are: the permissions, the label behaviour, the run ids and the zizmor result.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 15:53 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-620.
- Record: sci2audio PR #364 (open), Issue #360; `plans/review-pr364-round1.md`, `plans/issue360-ci-passed-plan.md` (project files); D-580, D-620.

### D-641 · PR #371 round 2: a trailing space in a script piece

- Subject: PR #371 (D-605 PRs 5 to 7 combined), review round 2.
- Decision: round 2 at head 0f43871. Notes are in `plans/review-pr371-round2.md` (project files), and the author's answer to round 1 is in `plans/review-pr371-round1-answer.md`. Verdict: not approvable yet.
  - S1: the empty-string check at the end of a block leaves a trailing space in a script piece. Fix it and add a test on the script piece.
  - Nits:
    - N1: pin the three new checks with tests.
    - N2: handle or explain a spaced "/" after a link.
    - N3: add the PR table rows.
  - The heavy checks are all green on 0f43871, so round 3 re-checks S1 only. This is critical-PR round 3 of at most 4 (D-626).
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 15:55 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-630 and D-638.
- Record: sci2audio PR #371 (open); `plans/review-pr371-round1-answer.md`, `plans/review-pr371-round2.md` (project files); D-605, D-626, D-630, D-638.

### D-642 · v1.1 player wins plan: two PRs

- Subject: the plan for the v1.1 player wins (#152, #153, #154, #119, #190).
- Decision: the plan `plans/v11-player-wins-plan.md` (project files) is approved as two PRs.
  - **PR A, not critical:**
    - #152: a native speed select from 0.75× to 2×.
    - #153: `position.json` is tied to the read-along hash. It is saved through a POST that checks a token and the origin, and nothing plays by itself.
    - #190: publisher pages are deselected by default, found through the EPUB's tags. The title page stays selected.
  - **PR B, critical:**
    - #154: a `sci2audio listen` command that serves only the two named folders.
    - #119: an ordered `JobSettings.chapters` with Move up and Move down. The report gets a line only when the order differs.
  - PR B branches from main, not from PR A.
- Status: Decided (Claude) (coordinator, 15 Nov 15:55 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). **Refines D-635**, which had planned one non-critical PR.
- Record: sci2audio Issue #152, Issue #153, Issue #154, Issue #119, Issue #190; `plans/v11-player-wins-plan.md` (project files); D-69, D-635, D-639.

### D-643 · PR #364 ("CI passed" after cancelled runs) approved after round 2 and merged

- Subject: PR #364, "ci: labels start no CI run; ci:full starts one by hand" (#360; D-620 option A), approved and merged.
- Decision: round 2 (appended to `plans/review-pr364-round1.md`) approved the PR at head 356cc10, after S1 of D-640 (7a63955 merged main 82d9e0d in, then the S1 fix followed). It was squash-merged as 3d66b93 at 16:03:35 UTC, which closed #360 at 16:03:36 UTC. Under D-580 as refined by D-620, CI now works like this:
  - Labels other than ci:full start no run.
  - ci:full dispatches one full run.
  - "CI passed" stays strict.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 16:04 UTC, under D-80 as extended by D-462 and D-553, and D-626; critical, so Colin was informed in the project chat at 2026-11-15 16:04:16 UTC). Follows D-620 and D-640.
- Record: sci2audio PR #364 (merged as 3d66b93), Issue #360 (closed); `plans/review-pr364-round1.md`, `plans/issue360-ci-passed-plan.md` (project files); D-580, D-620, D-640.

### D-644 · PR #371 (D-605 PRs 5 to 7) approved and merged; the textprep follow-up batch is complete

- Subject: PR #371, links in brackets, citation nests and German closing quotes read the same on a second run, approved and merged. This completes D-605.
- Decision:
  - Round 3 (`plans/review-pr371-round3.md`, project files) approved the PR at head 81ba6a3, after S1 of D-641.
  - Main 3d66b93 was merged in as 0285e3b, which was green on all three systems. The PR was squash-merged as 342a8f5 at 16:14:51 UTC, which closed #326, #337, #338, #339, #278 and #342 (16:14:53 to 16:15:02).
  - The textprep v1.2 follow-up batch (D-605, PRs 1 to 7) is complete:
    - #353 (bd3be17)
    - #359 (739f69c)
    - #361 (eb28274)
    - #368 (82d9e0d)
    - #371 (342a8f5)
  - The follow-ups that stay open on v1.2 are #358, #362, #370 and #372.
  - Next steps:
    - A light batch audit of the textprep batch (#353, #359, #361, #368, #371) starts under D-627.
    - The second textprep plan for the remaining v1.2 textprep issues (D-605), starting with #254 and #92, starts in a new thread.
  - Main tip is now 342a8f5.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 16:15 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-605, D-630, D-638 and D-641.
- Record: sci2audio PR #371 (merged as 342a8f5), Issue #326, Issue #337, Issue #338, Issue #339, Issue #278, Issue #342 (closed); Issue #358, Issue #362, Issue #370, Issue #372 (open); `plans/review-pr371-round1.md`, `plans/review-pr371-round2.md`, `plans/review-pr371-round3.md` (project files); D-599, D-605, D-627, D-630.

### D-645 · The first light batch audit (textprep batch)

- Subject: the D-627 light batch audit of the textprep batch (#353, #359, #361, #368, #371).
- Decision: the audit is done. Notes are in `plans/audit-textprep-batch-2026-11-15.md` (project files).
  - Result: no missed bugs, 2 should-fix items and 2 nits. The batched workflow (D-626) did not lower the quality of the reviews.
  - S1: an English notice is not idempotent with ranges. It is the English twin of #249.
  - S2: the nested citation "(; 2021)".
  - S1 and S2 become v1.2 issues. The thread for the second textprep batch files them and takes them into its batch. They were filed as #374 (S1) and #375 (S2), see D-646.
- Status: Decided (Claude) (coordinator, 15 Nov 16:20 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Carries out D-627. Follows D-644.
- Record: sci2audio PR #353, PR #359, PR #361, PR #368, PR #371; Issue #249; `plans/audit-textprep-batch-2026-11-15.md` (project files); D-626, D-627, D-644.

### D-646 · Second textprep v1.2 batch plan: six critical PRs

- Subject: the plan for the second textprep v1.2 batch.
- Decision: the plan `plans/textprep-v12-second-batch-plan.md` (project files) is approved as six critical PRs:
  1. #92 and #254.
  2. #230, #231, #233, #250, #265 and #358.
  3. #257, #258, #372 and #375.
  4. #240 and #223.
  5. #193, #93 and #191.
  6. #362, #370 and #374.
- Scope changes:
  - #292 goes to the next batch.
  - #97, #114, #131, #100 and #287 move to Later. At 16:23 UTC the API still showed them on v1.2; check the move when writing the row.
- Sub-decisions:
  - Reference keys are read as printed, for example "Quelle MH17" or "reference MH17". Look-alikes such as [PM10] stay as printed.
  - The Liu note [59] is removed together with the unheaded list.
  - Under #265, only four-digit years lose the ordinal reading.
  - Affiliation marks (#93) go in the Footnotes category.
- Issues filed from the D-645 audit:
  - #374 (S1: English figure and table notices read a label range differently).
  - #375 (S2: a year shell around two inner citations leaves "(; 2021)").
- Also: PR #373 (app PR A, #152 #153 #190, not critical; D-642), "web, app: player speed, listening position, and publisher pages left out by default", is in review round 1 at head a604e77.
- Status: Decided (Claude) (coordinator, 15 Nov 16:22 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-605 (its second plan after PR 7), D-644 and D-645.
- Record: sci2audio Issue #92, #254, #230, #231, #233, #250, #265, #358, #257, #258, #372, #375, #240, #223, #193, #93, #191, #362, #370, #374, #292, #97, #114, #131, #100, #287; PR #373 (open); `plans/textprep-v12-second-batch-plan.md` (project files); D-605, D-642, D-644, D-645. When writing the row, link each issue as `Issue [#N](...)`.

### D-647 · PR #373 (app PR A) review round 1

- Subject: PR #373 (player speed, listening position and publisher pages; #152, #153, #190; D-642 PR A), review round 1.
- Decision: round 1 at head a604e77. Notes are in `plans/review-pr373-round1.md` (project files).
  - S1: a position save carries the page's read-along stamp, and the server answers 409 when it does not match.
  - N1: the Continue and Start buttons are drawn disabled until they are wired, the same pattern as the #177 fix (D-609).
  - Accepted deviation: #373 has no web hint for "publisher's page". The hint is filed as #376 and goes into the critical PR B (#154, #119).
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 16:30 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-642.
- Record: sci2audio PR #373 (open), Issue #152, Issue #153, Issue #190, Issue #376; `plans/review-pr373-round1.md`, `plans/v11-player-wins-plan.md` (project files); D-609, D-642.

### D-648 · PR #373 round 2: passes, but Windows CI is red

- Subject: PR #373 (app PR A), review round 2.
- Decision: round 2 passes at head 7a7acb1 (`plans/review-pr373-round2.md`, project files), but Windows CI is red.
  - W1: the cache of audiobook stamps is keyed by mtime and size, and on Windows two files collide. It is now keyed by file identity as well (head e31eb40).
  - W2: the Windows error wording in the folder test.
  - The merge go is pinned to e31eb40, once it is green on all three systems.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 16:53 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-642 and D-647.
- Record: sci2audio PR #373 (open); `plans/review-pr373-round1.md`, `plans/review-pr373-round2.md` (project files); D-642, D-647. Merged as 514dc2f (D-651).

### D-649 · PR #377 (second textprep batch PR 1) review round 1

- Subject: PR #377, "textprep: read alphanumeric citation keys and leave out a reference list without a heading" (#254, #92; D-646 PR 1), review round 1.
- Decision: round 1 at head a578dc0. Notes are in `plans/review-pr377-round1.md` (project files). Verdict: not approvable yet.
  - B1: a citation key counts only when every key is printed as an entry label in the same document.
  - S1: the list ends at its last entry.
  - S2: a run of entries right after a heading is not an unheaded list.
  - N1: a stronger entry sign for numbered lists.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 16:54 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-646.
- Record: sci2audio PR #377 (open), Issue #254, Issue #92; `plans/review-pr377-round1.md`, `plans/textprep-v12-second-batch-plan.md` (project files); D-646.

### D-650 · #264 joins PR 2 of the second textprep batch; v1.1 status

- Subject: #264, German legal abbreviations such as "i. S. v." and "i. V. m." (v1.1).
- Decision: #264 is added to PR 2 of the second textprep batch (D-646).
  - The v1.1 status at 16:54 UTC: 38 of 45 issues closed (API: 7 open, 38 closed).
  - The rest closes through three PRs:
    - PR #373 (#152, #153, #190);
    - PR #378, "app, cli, web: read the chapters in the chosen order, and `sci2audio listen`" (#119, #154, plus #376; D-642 PR B), open at head ed60ec6;
    - #264.
- Status: Decided (Claude) (coordinator, 15 Nov 16:55 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). **Refines D-646** (the scope of PR 2).
- Record: sci2audio Issue #264 (v1.1), PR #373, PR #378 (open), Issue #376; `plans/textprep-v12-second-batch-plan.md` (project files); D-642, D-646.

### D-651 · PR #373 (player wins A) merged

- Subject: PR #373, player speed, listening position, and publisher pages left out by default (#152, #153, #190; D-642 PR A), merged.
- Decision: the merge go was pinned to head e31eb40 (D-648), and that head was green on all three systems. Squash-merged as 514dc2f at 16:57:54 UTC, which closed #152 (16:57:56), #153 (16:57:58) and #190 (16:57:59). #376 stays open for PR B (#378). Main tip is now 514dc2f.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 16:58 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-642, D-647 and D-648.
- Record: sci2audio PR #373 (merged as 514dc2f), Issue #152, Issue #153, Issue #190 (closed), Issue #376 (open), PR #378; `plans/review-pr373-round1.md`, `plans/review-pr373-round2.md` (project files); D-642, D-647, D-648.

### D-652 · PR #378 (player wins B) review round 1

- Subject: PR #378, read the chapters in the chosen order, and `sci2audio listen` (#119, #154, #376; D-642 PR B, critical), review round 1.
- Decision: round 1 at head ed60ec6. Notes are in `plans/review-pr378-round1.md` (project files).
  - S1: listen jobs started from the CLI (outside the web app) get a key that cannot collide (`cli-<hash>`), so they never shadow web documents.
  - S2: tests of the serving scope for the folder of a recorded `audiobook.json` and for the output folder in the settings.
  - Nits:
    - N1: a test for the `document.json` check.
    - N2: the file is hashed once while it is streamed.
    - N3: the text and the code of the Move buttons agree.
  - Accepted deviations from the plan:
    - `sci2audio listen` opens the start page, not the listen page.
    - The exit codes are 3 and 1 instead of 2.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 17:00 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line, because it is non-critical under D-626). Follows D-642.
- Update, round 2 (the coordinator gave it as D-652 at 17:29 UTC; recorded here so the numbers stay unique):
  - The author answered the round-1 list at 5d8e520 (`plans/answer-pr378-round1.md`).
  - Round 2 at 5d8e520 found the PR approvable (`plans/review-pr378-round2.md`): ci:full green on all three systems, and 148 nightly Hypothesis tests passed.
  - One nit is deferred to #380 (testing: check the publisher's page hint with axe in dark mode, v1.1).
- Record: sci2audio PR #378 (merged as c841f3d, D-653), Issue #119, Issue #154, Issue #376, Issue #380; `plans/review-pr378-round1.md`, `plans/answer-pr378-round1.md`, `plans/review-pr378-round2.md`, `plans/v11-player-wins-plan.md` (project files); D-642.

### D-653 · PR #378 (player wins B) merged

- Subject: PR #378, read the chapters in the chosen order, and `sci2audio listen` (#119, #154, #376; D-642 PR B, critical), merged.
- Decision: squash-merged pinned to head 5d8e520 as c841f3d at 17:29:09 UTC, which closed #119 (17:29:10), #154 (17:29:11) and #376 (17:29:12). Listen jobs use `cli-` addresses and keep their listening position in their own working folder. Main is now c841f3d. #380 stays open on v1.1.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 17:29 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat post id given). Follows D-642 and D-652.
- Record: sci2audio PR #378 (merged as c841f3d), Issue #119, Issue #154, Issue #376 (closed), Issue #380 (open, v1.1); `plans/review-pr378-round2.md` (project files); D-642, D-652.

### D-654 · #380 is closed as already done

- Subject: #380, checking the publisher's page hint with axe in dark mode (v1.1; deferred from the PR #378 round 2 nit, D-652).
- Decision: #380 is closed as already done, because `check_axe` already covers dark mode. The app batch audit (`plans/audit-app-batch-2026-11-15.md`, project files, on PRs #373 and #378) found that the round-2 nit misread the shared helper. At 19:02 UTC the API still showed #380 open; check that it is closed when writing the row.
- Status: Decided (Claude) (coordinator, 15 Nov 19:01 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat post id given). **Corrects D-652** (the nit deferred to #380).
- Record: sci2audio Issue #380, PR #378 (merged as c841f3d); `plans/audit-app-batch-2026-11-15.md`, `plans/review-pr378-round2.md` (project files); D-627, D-652.
- Work resumed: Colin, in the project chat at 19:01:05 UTC: "resume normally until v1.1". This ends the 17:31 stop.

### D-655 · Second light batch audit: the app lane (#373, #378)

- Subject: the D-627 light batch audit of the app lane (PRs #373 and #378).
- Decision: the audit is done. Notes are in `plans/audit-app-batch-2026-11-15.md` (project files).
  - Result: no missed bugs. All contract touches were already reviewed as critical in #378, and the lane's quality held. This is the second audit that confirms D-645.
  - T1: when the web app and `sci2audio listen` open the same file with the default folders, they share `position.json` and `audiobook.json`. This is safe but untested. It is filed as #381 (v1.2, lane:app).
- Status: Decided (Claude) (coordinator, 15 Nov 19:03 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Carries out D-627. Follows D-645.
- Record: sci2audio PR #373 (merged as 514dc2f), PR #378 (merged as c841f3d); `plans/audit-app-batch-2026-11-15.md` (project files); D-627, D-645.

## Merge records to add when they land

- PR #368 (D-605 PR 4: #334, #349 and the caption part of #249; D-615), "textprep: German date ranges, section numbers and caption labels read the same on a second run", opened at head 0919637. Merged as 82d9e0d at head d0fb704 (D-637).
- PR #371, "textprep: links in brackets, citation nests and German closing quotes read the same on a second run" (#326, #337, #338, #339, #278, #342; D-605 PRs 5 to 7 combined, D-630), opened at head 4a47d47. Merged as 342a8f5 at head 0285e3b (D-644).

## Resume notes (stopped 15 Nov 17:31 UTC on Colin's order)

- The entries D-628 to D-653 are complete in this file. No KB PR has been opened for them. Branch from sci2audio-design main 23f913f, write the rows as in KB PR #49, self-check them, and squash-merge pinned to the head (D-626).
- Still to do when writing the rows:
  - Check that #97, #114, #131, #100 and #287 moved to Later (D-646).
  - Add status notes to the older rows that are refined or lifted: D-605 (D-630), D-611 (D-639), D-635 (D-642), D-646 (D-650), D-580 (D-643).
  - Mark D-605 complete (D-644).

- KB PR #50 (D-628 to D-655, head dbd1311) was merged by this thread without review (D-626) as 3b0c57a. New entries go into kb-batch-2026-11-16b-pending.md.

Next free D-number: D-656.
