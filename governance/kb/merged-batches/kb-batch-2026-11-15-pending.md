# KB batch for 15 Nov 2026 (MERGED as KB PR #49, 23f913f)

Collected by the daily KB thread for the KB PR of 15 Nov 2026. The 14 Nov batch (D-436 to D-603) is in kb-batch-2026-11-14-pending.md and goes into its own KB PR.

## Decisions

- **D-604** (15 Nov 2026): the thread freeze (D-591) is lifted. Colin's words, in the project chat at 07:53:16 UTC (message cmsg_011gr2YyZJypGaV6NbzgSXQE8QXXSN8hXRZsBBf5dNKLEe): "continue everything". The coordinator recorded the consequences in post cmsg_011gr2YyZJypGaV6NbzgSXQEGamJ3Z8Jd3nQ3d41PTSrqS (07:53:31 UTC):
  - a review thread starts for PR #345 (PDF subprocess, D-581);
  - the #177 ZAP flake fix (D-602) goes to the app lane thread while the v1.0.0 tag is still pending;
  - a textprep lane thread starts to plan the v1.2 textprep follow-ups, with the plan first and approval before code.
  Status: **Decided** (Colin, 15 Nov 07:53:16 UTC). Lifts D-591.

- **D-605** (15 Nov 2026), the textprep v1.2 follow-up plan is approved (/mnt/project-files/plans/textprep-v12-followups-plan.md). It is seven critical PRs, in this order:
  1. #324: rebuilt_from_script maps labels through the script, a corpus second-run test runs on every paper, and the four notice exceptions are removed.
  2. Units: #320, #321, #335.
  3. English numbers: #336, #340, #210.
  4. German numbers and dotted labels: #334, #349, #249.
  5. Links in brackets: #326, #337.
  6. Citation nests: #338, #339, and the #278 subject row, all inside the D-599 cap.
  7. #342.
  Sub-decisions:
  - "resp." and "respektive" become German label joins, which changes the first-run reading of "resp.".
  - A numeric citation glued after a removed author-year citation goes with it.
  - Year shells around a removed citation go with it.
  - #249 joins PR 4.
  - #210 moves from v1.0.1 to v1.2 and lands on main, as #259 did under D-588 (API: #210 now v1.2).
  - #341 moves to Later as very rare (API: #341 now Later).
  The remaining 21 v1.2 textprep issues get a second plan after PR 7.
  Status: Decided (Claude) (coordinator, 15 Nov 07:59 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 07:59:26 UTC). Follows D-577, D-599 and D-603. Amends D-461 (#210 was v1.0.1) and D-593 (#341 was v1.2).

### D-606 · #214 SRT and WebVTT subtitles plan approved

- Subject: SRT and WebVTT subtitles from the read-along times (#214).
- Decision: the plan `plans/issue214-subtitles-plan.md` (project files) is approved, with two additions. Branch `output/subtitles-214`, one PR. It is critical because two golden files change.
  - The spoken text travels with each chunk. `app.audio.assemble` passes it into `output.model.Spoken.text`. Text the voice failed on (D-162) has no chunk, so it has no cue.
  - A new pure module `output/subtitles.py` builds the cues inside `write_audiobook`. It uses the same Timeline as the read-along.
  - Cue rules:
    - A cue never spans two chunks, so cues end at sentence ends.
    - A cue has at most 2 lines of 42 characters.
    - A longer chunk is cut at clause marks, and its time is shared by characters.
    - The first and last cue of a chunk use the read-along's start and end times exactly.
  - Files:
    - One `.srt` and one `.vtt` per chapter, beside the MP3s, and one pair for the whole book beside the M4B.
    - They are written atomically, before the read-along file.
    - The existing-files check before any speech covers them (D-163).
  - Settings:
    - Subtitles are off by default and the choice is remembered (`JobSettings.subtitles`, passed into `OutputSettings`).
    - The CLI gets `--subtitles` and the web form gets a checkbox.
  - Validators: the bundled ffmpeg and Chromium's WebVTT parser. No new dependency.
  - Golden files that change: the CLI help snapshot, and `"subtitles": []` in the audio record.
  - Required additions:
    - A Hypothesis test asserts that each chunk's cues are contiguous and do not overlap, with exact outer times.
    - Follow-up issues are filed for a web-player subtitle track and for word-level times.
- Status: Decided (Claude) (coordinator, 15 Nov 08:08 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:08:14 UTC). Follows D-453 (the v1.2 roadmap row with SRT/VTT), D-162 and D-163.
- Record: sci2audio Issue #214 (open, v1.2); `plans/issue214-subtitles-plan.md` (project files); D-453, D-162, D-163.

### D-607 · KB PR #48 approved and merged

- Subject: KB PR #48, the decision log of 14 Nov (D-436 to D-603), approved and merged.
- Decision: review round 1 of KB PR #48 (head 05a1c47, notes in `plans/review-kb-pr48-round1.md` (project files)) found no blocker and three fixes:
  - F-1: the D-580 addendum says that pushes run CI only on main and release/**.
  - F-2: D-600 names `plans/review-pr333-round1-answer.md` and lists it in its record cell.
  - F-3: D-443 says that #6's plugin-author docs part became #203 (moved to v1.3 by D-463), and lists #203.
  The fixes were pushed as 10a1de0. The PR was approved at head 10a1de0, the coordinator gave the merge go, and it was squash-merged pinned to that head as efd6972 at 08:13:01 UTC (title only, no body).
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 08:13 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:13:25 UTC). Follows D-373 and D-68.
- Record: sci2audio-design PR #48 (merged as efd6972); `plans/review-kb-pr48-round1.md` (project files); D-373, D-68.

### D-608 · PR #345 (PDF subprocess) review round 1

- Subject: PR #345, reading PDFs in a separate process with memory and time limits (#185, #28; D-581): review round 1.
- Decision: review round 1 at head 8611d18 (on main 99b8166). Notes are in `plans/review-pr345-round1.md` (project files). Verdict: changes needed.
  - Findings:
    - The design matches D-581.
    - CI is green on Linux, macOS and Windows.
    - The fast suite is 8.8 s slower, which is under the 15 s rule.
    - All 8 corpus papers read the same in the child as in-process.
    - Flate bombs and nested forms are stopped at 1 GB.
  - Blocker B1: the two memory tests must each prove their own mechanism.
    - The hard-limit test turns the watch off, so it fails without the hard limit (Linux RLIMIT_AS, Windows job object).
    - The watch test grows to below 2× the limit, so it fails without the watch.
    - Today either mechanism passes both tests.
  - Should fix:
    - S1: an exception from the child that cannot be unpickled falls back to RuntimeError.
    - S2: the child ends on its own when the parent is gone (plan Q9).
    - S3: the outline step and the "opening" and "outline" time messages get tests.
    - S4: a test pins the production reader cap (`_READERS`).
    - S5: "could not start its PDF reader" is shown only for a failed start, and the pipe ends are closed when the start fails.
  - Nits:
    - N1: the `run` docstring says the reader-slot wait has no limit.
    - N2: a test pins `freeze_support`.
  - Deferred to v1.2 issues:
    - D1 (lane:layout): `order.figures` grows faster than linearly with the drawings on a page. 5 pages × 100,000 drawings take 198 s of layout.
    - D2 (lane:extraction): parent memory at MAX_GRAPHICS, +497 MB per reader. Decide together with D1.
    - D3 (lane:extraction): macOS and Windows rows in docs/baseline.md, and the macOS RLIMIT_AS check.
  - Accepted deviations from the plan:
    - a read cache per worker instead of a fixture read once per module;
    - the `__main__` swap under `_MAIN`;
    - the wording of the time messages.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 08:19 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:19:14 UTC). Follows D-581.
- Record: sci2audio PR #345 (open); Issue #185, Issue #28; `plans/review-pr345-round1.md`, `plans/pdf-subprocess-plan.md` (project files); D-581. D1 to D3 were filed as #354, #355 and #356 (v1.2).

### D-609 · PR #350 (#177 ZAP flake fix) approved and merged

- Subject: PR #350, the fix for the flaky ZAP scan step (#177; D-602), approved and merged.
- Decision: review round 1 (`plans/review-pr350-round1.md`, project files) asked for R1-1: all four job-page buttons are rendered disabled and enabled only after their click handler is attached, with a browser test that holds back app.js. The author pushed it. Round 2 (`plans/review-pr350-round2.md`) approved the PR at head a55e237, and the coordinator gave the merge go. It was squash-merged as 79d0cdb at 08:24:51 UTC, which closed #177 at 08:24:52 UTC.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 08:25 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:25:10 UTC). Follows D-602.
- Record: sci2audio PR #350 (merged as 79d0cdb), Issue #177 (closed); `plans/review-pr350-round1.md`, `plans/review-pr350-round2.md` (project files); D-602.

### D-610 · PR #359 (units follow-up, D-605 PR 2): two plan deviations accepted

- Subject: PR #359, units and signs read the same on a second run (#320, #321, #335; D-605 PR 2). Two deviations from the plan are accepted.
- Decision: PR #359 is at head 0ea532e. Two deviations from `plans/textprep-v12-followups-plan.md` are accepted:
  1. A bare "less than" or "greater than" does not count as the sign before "2x". The formula case "y < 2x" (read "less than 2x", then "less than 2 times" on a second run) is filed as #358 (v1.2).
  2. For #335, the second run leaves a unit after a fraction as printed, and the first run does not change. The plan said to read "3 quarters per second". Reason: no unit after a fraction is read today, and reading only "s⁻¹" would be inconsistent.
- Status: Decided (Claude) (coordinator, 15 Nov 08:37 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:36:51 UTC). **Refines D-605.**
- Record: sci2audio PR #359 (open); Issue #320, Issue #321, Issue #335, Issue #358; `plans/textprep-v12-followups-plan.md` (project files); D-605.

### D-611 · No new threads until Colin says otherwise (second freeze)

- Subject: thread freeze, again.
- Decision: no new threads of any kind (implementation, review, design) until Colin says otherwise. Threads that are already running continue. A new PR that has no review thread waits. This is the same rule as D-591, which D-604 lifted at 07:53:16 UTC.
- Colin's words, in the project chat at 2026-11-15 08:43:06 UTC: "dont start new threads". The scope (any kind of thread, running threads continue, PRs without a review thread wait, until Colin says otherwise) is the coordinator's reading, by analogy with D-591.
- Status: **Decided** (Colin, 15 Nov 08:43:06 UTC: "dont start new threads"). Reinstates D-591 after D-604.
- Record: D-591, D-604.

### D-612 · PR #345 (PDF subprocess) approved after rounds 2 and 3, and merged

- Subject: PR #345, reading PDFs in a separate process with memory and time limits (#185, #28; D-581), approved and merged.
- Decision: the review is in `plans/review-pr345-round2.md` (project files), which also holds the round-3 section.
  - Round 2, at head 872e634 (main 79d0cdb merged in): all round-1 items (D-608) are fixed, and the reviewer's own mutants confirm each one: B1, S1 to S5, N1, N2. One test is still required, R2-1: prove that a reported step restarts the child's own clock. Without that, a long read of fast pages could end with the time message.
  - Round 3, at head 3743c7a:
    - R2-1 is resolved by `test_each_reported_step_starts_the_childs_own_clock_anew`, which fails under the mutant.
    - CI with ci:full is green on all three systems (run 43695798175): ubuntu 5207 passed, windows 5205 passed, macos 5206 passed with 2 skipped.
    - The new commit has no closing keyword.
  - The PR was approved at 3743c7a and the coordinator gave the merge go. It was squash-merged as 6c91465 at 08:49:48 UTC, which closed #185 (08:49:49) and #28 (08:49:51).
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 08:50 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:50:14 UTC, and of the merge at 2026-11-15 08:50:23 UTC). Follows D-581 and D-608.
- Record: sci2audio PR #345 (merged as 6c91465), Issue #185, Issue #28 (closed); `plans/review-pr345-round1.md`, `plans/review-pr345-round2.md`, `plans/pdf-subprocess-plan.md` (project files); deferred Issue #354, Issue #355, Issue #356 (v1.2); D-581, D-608.

### D-613 · PR #357 (#214 subtitles) review round 1

- Subject: PR #357, SRT and WebVTT subtitles on the read-along's times (#214; D-606): review round 1.
- Decision: round 1 at head 9420cd8, notes in `plans/review-pr357-round1.md` (project files). Verdict: changes requested, no blocker. The design matches the plan and D-606.
  - The failure clean-up goes beyond the plan, and it is accepted as right and needed. Output takes back the subtitle files it newly wrote when a run fails later (for example at the read-along file). It only removes files that did not exist before and whose inode is still the one this run committed. Without it, the leftover files would refuse the next run without `overwrite`.
  - Should fix (tests only):
    - S1: pin the 42-character line on both sides with literal numbers.
    - S2: a cut prefers `;` or `:` over a later `,`, and a test pins the half-full threshold.
    - S3: pin the inner cue times exactly: `start + (end - start) * done // total`.
    - S4: pin the inode guard (or remove it), and check that subtitle files contain only `\n` line ends.
  - Nits:
    - N1: in `split`, the fallback cannot be reached.
    - N2: `str.split()` also breaks at no-break spaces. No case today.
  - Nothing is deferred beyond #351 and #352.
  - ci:full on 9420cd8 was green on all three systems. The fixed head needs this again before the merge.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 08:50 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:50:14 UTC). Follows D-606.
- Record: sci2audio PR #357 (open), Issue #214; `plans/review-pr357-round1.md`, `plans/issue214-subtitles-plan.md` (project files); Issue #351, Issue #352; D-606.

### D-614 · PR #361 (D-605 PR 3): a sequence like "10−410^2" stays as printed

- Subject: PR #361, minus signs and powers read the same on a second run (#336, #340, #210; D-605 PR 3). A digit sequence with no right reading stays as printed.
- Decision: a sequence shaped like the ones Hypothesis generates, for example "10−410^2", stays as printed, because no reading of it is right. This follows D-57 (text as printed). PR #361 is at head eca58a9 on main 6c91465 and waits for review in the batch review thread for the D-605 PRs.
- Status: Decided (Claude) (coordinator, 15 Nov 08:57 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:57:55 UTC). Follows D-57 and D-605.
- Record: sci2audio PR #361 (open); Issue #336, Issue #340, Issue #210; `plans/textprep-v12-followups-plan.md` (project files); D-57, D-605.

### D-615 · German decimal labels: captions now, formula labels in a new issue

- Subject: German decimal labels in D-605 PR 4 (#249).
- Decision: D-605 PR 4 reads German decimal labels for captions only. For example, "Tabelle 2.1" is read "2 Punkt 1". Formula labels (such as "Formel 3.2", the case #249 names) are left out of this PR. They go to a new v1.2 issue: a rebuild rule for placeholder labels, which touches the plugin conformance check. The reason is that mapping formula labels would break the second-run idempotency guarantee, because placeholder labels are not rebuilt (see the PR #353 review, B1).
- Status: Decided (Claude) (coordinator, 15 Nov 08:59 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 08:59:36 UTC). **Refines D-605** (PR 4 scope).
- Record: sci2audio Issue #249 (open, v1.2); Issue #362 (v1.2, the formula labels); `plans/review-pr353-round1.md`, `plans/textprep-v12-followups-plan.md` (project files); D-605. Add the PR 4 number when it opens.

### D-616 · main red on macOS after PR #345: fix it, do not skip it

- Subject: main 6c91465 fails `tests (macos-latest)` after PR #345.
- Decision: main 6c91465 fails `tests (macos-latest)` in `test_each_reported_step_starts_the_childs_own_clock_anew`, a test from PR #345. The child stops with reason time at step "opening". This was seen on main (CI run 43696317547, which failed on the macOS job and "CI passed") and on PR #353's head 38ae4b6.
  - The layout lane fixes it today with a small fix PR. The test is not skipped.
  - Merges to main wait until macOS is green.
- Status: Decided (Claude) (coordinator, 15 Nov 09:02 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:02:46 UTC). Follows D-612 and the testing rules (D-374, as D-568 did after #300).
- Record: sci2audio PR #345 (merged as 6c91465); CI run 43696317547; D-612, D-374, D-568.
- Update (coordinator, 15 Nov 09:08 UTC; Colin informed in the project chat at 2026-11-15 09:08:22 UTC): the macOS failure is a code bug, not a flaky test. The reader's start-up was counted against the first 60 s step. The fix is PR #363, "extraction: a reader's start is not counted as its first step (D-616)": the step clock starts once the child runs, and the start is limited to 30 s. It was opened at head 89accb1 on main and reviewed in the #345 review thread (D-622, D-625). Merged as 0af10d0 at 09:32:59 UTC, after which main is green again.

### D-617 · PR #353 round 2: approvable at 38ae4b6, merge held for D-616

- Subject: PR #353 (D-605 PR 1, #324), review round 2.
- Decision: round 2 at head 38ae4b6 (notes in `plans/review-pr353-round2.md`, project files). The fixes for B1, N1 and N2 from round 1 are verified. The PR is approvable once `tests (macos-latest)` on 38ae4b6 is green. The merge is held for D-616.
- Status: Decided (Claude) (coordinator, 15 Nov 09:02 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:02:46 UTC). Follows D-605 and the round 1 review.
- Record: sci2audio PR #353 (open), Issue #324; `plans/review-pr353-round1.md`, `plans/review-pr353-round2.md` (project files); D-605, D-616.

### D-618 · PR #359 round 1: the German sibling of #335 is required

- Subject: PR #359 (D-605 PR 2: units and signs, #320 #321 #335), review round 1.
- Decision: round 1 at head 9fc815f (notes in `plans/review-pr359-round1.md`, project files). Verdict: not approvable yet. There is no blocker, one should-fix and one nit.
  - S1: the plan's "German fraction words likewise" is missing. In German, a fraction followed by a unit chain that ends in a letter power reads differently on the two runs. For example, "2/3 m s⁻²" reads "2 Drittel m s⁻²" on the first run and "2 Drittel m s hoch minus 2" on the second.
    - Both runs must agree. Option (a) is recommended: `numbers_de._fractions` leaves such a fraction as printed, as it already does when a letter power follows directly ("1/5 m⁶").
    - Any first-run change is listed in the PR body.
    - A German regression case covers "2/3 m s⁻²", "3/4 m s⁻¹" and "3/4 kg m²", with "1/4 cm²" as a control. It must fail on 9fc815f's second-run check.
  - N1: two look-behinds are not pinned by any test: `(?<![\w^.])` in `_UNIT_CHAIN_AFTER_FRACTION` and `(?<![\w.,])` in `_OUT_OF`.
- Status: Decided (Claude) (coordinator, 15 Nov 09:02 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:02:46 UTC). Follows D-605 and D-610.
- Record: sci2audio PR #359 (open), Issue #335; `plans/review-pr359-round1.md` (project files); D-605, D-610.

### D-619 · PR #357 (#214 subtitles) approved after round 2 and merged; the scope of the D-616 hold

- Subject: PR #357, SRT and WebVTT subtitles (#214; D-606), approved and merged. Also: which merges the D-616 hold covers.
- Decision: round 2 (`plans/review-pr357-round2.md`, project files) approved the PR at head 5cf1378, after the round-1 test items S1 to S4 (D-613). The coordinator gave the merge go. It was squash-merged as 87c6503 at 09:04:56 UTC, which closed #214 at 09:04:57 UTC. #351 and #352 stay open.
  - It was merged even though main was red on macOS (D-616), because the PR's own head passed `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)`.
  - The D-616 hold applies to PR heads whose macOS job failed.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 09:05 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:05:26 UTC). Follows D-606 and D-613. **Refines D-616** (scope of the hold).
- Record: sci2audio PR #357 (merged as 87c6503), Issue #214 (closed); Issue #351, Issue #352 (open); `plans/review-pr357-round1.md`, `plans/review-pr357-round2.md` (project files); D-606, D-613, D-616.

### D-620 · #360 "CI passed" after cancelled runs: option A approved

- Subject: #360, a "CI passed" check that turns red when a newer run cancels the old one.
- Decision: the plan `plans/issue360-ci-passed-plan.md` (project files) is approved with option A.
  - `ci.yml` drops the `labeled` trigger. Other labels then no longer start runs that a newer run cancels.
  - A new workflow `ci-full-label.yml`, with `actions: write` at job level only, dispatches `ci.yml` on the PR branch when the label ci:full is added to a PR from the same repository.
  - "CI passed" stays strict. A run cancelled by hand on its own stays red and is never skipped.
  - Option B (`!cancelled()`) is rejected, because a skipped required check counts as passing.
- Status: Decided (Claude) (coordinator, 15 Nov 09:08 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:08:22 UTC). **Refines D-580** (how the ci:full label starts the three-system run).
- Record: sci2audio Issue #360 (open, v1.2); `plans/issue360-ci-passed-plan.md`, `plans/ci-lean-plan.md` (project files); D-580. Implementation waits until PR #357 is merged (done, D-619). Add the PR number when it opens.

### D-621 · PR #361 (D-605 PR 3, English numbers) review round 1

- Subject: PR #361, minus signs and powers read the same on a second run (#336, #340, #210; D-605 PR 3): review round 1.
- Decision: round 1 at head 44998bb (opened as eca58a9). Notes are in `plans/review-pr361-round1.md` (project files). Verdict: not approvable yet. There is no blocker, one should-fix and two nits.
  - S1: allow an optional sign before a grouped exponent, so that "10^-250 000 000" reads the same on both runs. Three regression rows.
  - N1: pin the grouped look-ahead: "10^250 000 000 5" stays as printed.
  - N2: add three first-run changes to the PR's table.
  - Nothing is deferred.
- Status: Decided (Claude) (coordinator, 15 Nov 09:18 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:29:33 UTC). Follows D-605 and D-614.
- Record: sci2audio PR #361 (open), Issue #336, Issue #340, Issue #210; `plans/review-pr361-round1.md` (project files); D-605, D-614.

### D-622 · PR #363 (macOS start-up fix, D-616) review round 1

- Subject: PR #363, a reader's start is not counted as its first step (D-616): review round 1.
- Decision: round 1 at head 89accb1. Notes are in `plans/review-pr363-round1.md` (project files). Verdict: changes needed, 2 small items. The mechanism is accepted, and CI is green on all three systems.
  - R1-1: the starting state uses START_SECONDS alone, not the larger of it and the step limit. The test for a reader that never starts gets a step limit above START_SECONDS.
  - R1-2: a test pins START_SECONDS == 30.
  - The PR gets the label risk:high.
  - The 30 s start limit stands. The measured start times on macOS and Windows go to #356.
  - By design, the memory limits do not cover the starting state.
- Status: Decided (Claude) (coordinator, 15 Nov 09:18 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:29:33 UTC). Follows D-616, D-581 and D-612.
- Record: sci2audio PR #363 (open); Issue #356; `plans/review-pr363-round1.md` (project files); D-616, D-581, D-612.

### D-623 · #343 and #344 plan approved: PDF page progress and cancel

- Subject: page progress while a PDF is read (#343) and cancel stopping the PDF reader (#344).
- Decision: the plan `plans/issue343-344-pdf-progress-cancel-plan.md` (project files) is approved as one PR that closes both issues. The PR is not critical, because it changes no layer, core or golden file.
  - The child reports page progress, shown as "page N of M".
  - Cancel kills the child and frees its reader slot.
  - A new ReadCancelled is not an ExtractionError. The app maps it to JobCancelledError.
  - Conditions: a cancel is never shown as a damaged PDF, and a test keeps the per-step deadline pinned.
- Status: Decided (Claude) (coordinator, 15 Nov 09:20 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:29:33 UTC). Follows D-581, D-594 and D-612.
- Record: sci2audio Issue #343, Issue #344 (open, v1.2); `plans/issue343-344-pdf-progress-cancel-plan.md` (project files); D-581, D-594, D-612.

### D-624 · PR #359 round 2: blocker B1 in the German fraction rule

- Subject: PR #359 (D-605 PR 2: units and signs, #320 #321 #335), review round 2.
- Decision: round 2 at head ff55995. Notes are in `plans/review-pr359-round2.md` (project files). Verdict: not approvable yet, because the S1 fix (D-618, option a) caused one blocker.
  - B1: the German rule for a fraction before a unit chain leaves the fraction as printed only when the powers rule's own check would also leave the trailing letter power as printed. That check is `_unit_chain` / `_NUMBER_BEFORE`, plus the statistics square.
    - Six regression rows must fail on ff55995: "3/4 kg x²", "3/4 m x⁻¹", "3/4 m s x²", "1/2 kg R²", "1/5 m R²" and "2/3 s t²".
  - N1 is accepted as fixed.
  - Nothing is deferred.
- Status: Decided (Claude) (coordinator, 15 Nov 09:20 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:29:33 UTC). Follows D-618. **Refines D-618** (when option (a) applies).
- Record: sci2audio PR #359 (open), Issue #335; `plans/review-pr359-round1.md`, `plans/review-pr359-round1-answer.md`, `plans/review-pr359-round2.md` (project files); D-605, D-610, D-618.

### D-625 · PR #363 (macOS start-up fix) approved after round 2

- Subject: PR #363, a reader's start is not counted as its first step (D-616, D-622), approved.
- Decision: round 2 at head 31913ff. The notes are appended to `plans/review-pr363-round1.md` (project files).
  - R1-1 and R1-2 are fixed. All 8 mutants are killed, and CI is green on all three systems. The PR is approved at 31913ff.
  - Merge go: main bd3be17 is merged in first, and the new head must be green on all three systems before the merge. The author pushed e1c1382 (main merged in).
  - Flake note: one browser test failed once, `test_pasted_text_opens_and_is_analysed` with "Execution context was destroyed", and passed on re-run. If it fails a second time today without a code cause, it is quarantined the same day with an issue, per D-374.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 09:28 UTC, under D-80 as extended by D-462 and D-553; Colin informed in the project chat at 2026-11-15 09:29:33 UTC). Follows D-616, D-619 and D-622.
- Merge: squash of head e1c1382 (main bd3be17 merged in, green on all three systems) as 0af10d0 at 09:32:59 UTC. Colin informed of the merge in the project chat at 2026-11-15 09:33:13 UTC. Flake issue #365 "testing: browser test runs axe while the document page reloads after its analysis" was filed by the layout thread (v1.2, lane:web, testing) for `test_pasted_text_opens_and_is_analysed`.
- Record: sci2audio PR #363 (merged as 0af10d0), Issue #365; `plans/review-pr363-round1.md` (project files); D-616, D-619, D-622, D-374.

### D-626 · Token-saving workflow (Colin)

- Subject: a workflow that uses fewer tokens: lane batches, review rounds, the KB without review, and fewer reports.
- Decision: Colin's answers in the project chat at 10:43:15 UTC to the coordinator's six proposals. The coordinator wrote them into the project instructions and confirmed them at 10:44:10 UTC.
  1. PRs are batched by lane. The lanes are extraction/voices, layout, textprep and app/release, with at most three threads active at once. A lane thread lives for one batch (its plan and its PRs). The coordinator replaces it when the PRs are merged or its conversation gets long. Implementation stays on Opus high.
  2. One review thread per issue batch handles all its PRs and rounds. A thread's effort is set when it starts: medium for non-critical reviews, high for critical ones. In the coordinator's note, heavy checks (mutation, nightly seeds, three-system CI) run only for critical PRs on the final round, and move into label-triggered GitHub workflows where possible.
  3. At most 2 review rounds, and leftovers become issues. Critical PRs may go up to round 4, then wait for Colin's approval.
  4. KB PRs are merged without review, one per day, by one long-lived KB thread.
  5. Every new thread first reads the newest changes in the KB, the plans and the decision log. The coordinator decides when a thread gets too long and starts a new one.
  6. The coordinator reports to Colin only when he asks about progress or when a decision is critical.
- Colin's words: "1: approved. … 3: approved, except if the issue is critical - then continue until 4 - after that stop and ask for my approval 4: merge KB PRs without review. all KB PRs should use the same thread … 5: approved. make sure that before the work starts, it reads the newest changes in the KB, plans and decision log. Start a new thread before the conversation gets too long. you decide when it's the right point to start a new thread. 6. report only when i ask about the progress or if some decision was critical."
- Status: **Decided** (Colin, 15 Nov 10:43:15 UTC; the coordinator's answers to his questions were confirmed in the project chat at 2026-11-15 10:44:10 UTC). **Amends D-68** (KB PRs are no longer reviewed), **D-73** (non-critical reviews run at medium effort), **D-373** (the KB thread merges its own PR), **D-375** (lanes, and a lane thread lives one batch), **D-376** (one review thread per issue batch), and the chat line per decision of D-80 and D-462.
- Record: project instructions (15 Nov); D-68, D-73, D-80, D-373, D-375, D-376, D-462.

### D-627 · Measuring thread reuse (Colin)

- Subject: how the reuse of threads is measured.
- Decision: the coordinator's suggestion is approved, and it applies from the next issue started.
  - Two ledgers, `/mnt/project-files/ledger/implementation.md` and `/mnt/project-files/ledger/review.md`, each with one line per PR.
  - A fitness check runs before a thread gets a new issue.
  - A light batch audit of a lane's merged diff runs when the lane thread finishes.
  - Outsourcing work to Gemini is rejected.
  - The coordinator recorded this as rule 6 of the project instructions.
- Colin's words, in the project chat at 11:15:04 UTC: "Your suggestion is approved. all changes take effect from the next issue that is started."
- Status: **Decided** (Colin, 15 Nov 11:15:04 UTC; recorded in the project instructions, confirmed in the project chat at 2026-11-15 11:15:40 UTC). Follows D-626.
- Record: project instructions rule 6; `ledger/implementation.md`, `ledger/review.md` (project files); D-626.

### Work resumes (no D-number)

- Colin, in the project chat at 13:36:29 UTC: "continue the before started threads, don't start new ones yet." This ends the 09:29 stop. The D-611 freeze on new threads stays.

## Merge records to add when they land

- PR #350 (fix for #177 under D-602, app lane): opened on head a11dfe8, on main 99b8166. Two-line fix: the Replace button starts disabled and app.js enables it once it has bound the click. Plus a browser test that reproduces the race. Review thread started. Colin informed in the project chat at 2026-11-15 08:02:32 UTC. Merged as 79d0cdb at head a55e237 (D-609).
- KB PR #48 (dubidu22/sci2audio-design, D-436 to D-603, head 05a1c47) opened 15 Nov (Colin informed in the project chat at 2026-11-15 08:05:07 UTC). Review round 1 (plans/review-kb-pr48-round1.md): three fixes F-1 to F-3, pushed as 10a1de0. Squash-merged at head 10a1de0 as efd6972 at 08:13:01 UTC (D-607). Colin informed of the merge in the project chat at 2026-11-15 08:13:25 UTC. The 15 Nov KB branch starts from efd6972.
- PR #353 (D-605 PR 1, #324) opened, critical: rebuilt_from_script keeps rewritten caption labels, the corpus second-run test covers all eight papers, and four notice exceptions are removed. Head f5b2a37 on main 99b8166. One batch review thread covers all seven D-605 PRs. The author moved #210 to v1.2 and #341 to Later with comments, as D-605 said (checked in the API: #210 v1.2, #341 Later). Colin informed in the project chat at 2026-11-15 08:20:52 UTC. Merged as bd3be17 at head 1b8bb1e (D-617, D-619).
- PR #357 (#214 SRT and WebVTT subtitles, D-606, app lane) opened, critical (two golden files). Head 9420cd8 on main 79d0cdb. Follow-up issues filed as D-606 required: #351 "Player: show the subtitles as a track while listening" (v1.2) and #352 "Word-level times from the voice for subtitles and read-along" (Later). Review thread started. Colin informed in the project chat at 2026-11-15 08:30:12 UTC. Merged as 87c6503 at head 5cf1378 (D-619).
- PR #345: round-1 fixes (D-608) pushed, head 8dca21e. D-608's deferred items were filed on v1.2: D1 = #354 (layout: grouping figures slows down sharply with many drawings on a page), D2 = #355 (extraction: a PDF at the drawing limit costs the parent about 500 MB), D3 = #356 (docs: PDF reader costs on macOS and Windows, and a macOS hard-limit check). Not in a chat post of its own (the 08:30:12 post names only PR #357). When writing the D-608 row, put #354 #355 #356 in its record cell.
- PR #353 review round 1 at f5b2a37 (no D-number; notes `plans/review-pr353-round1.md`, project files):
  - Blocker B1: rebuilt_from_script maps footnote introductions into labels (for example maass "∗" becomes "Fußnote."). Fix: map labels only for captions, with English and German footnote tests and a corpus assertion.
  - Nits: N1, the pause checks cannot fail. N2, extend the corpus second-run test to EPUB, Markdown and text.
  - Colin informed in the project chat at 2026-11-15 08:36:51 UTC (the D-610 post).
  - When writing the PR #353 merge row, cite this round.
- Issue #360 filed 08:39:02 UTC on v1.2 (bug, lane:app): "CI: a run cancelled by a newer one no longer shows a failed 'CI passed'". The "CI passed" job should skip, not fail, when the PR concurrency group cancelled its run (seen on PRs #350 and #357). A run cancelled by hand on its own must never leave the required check skipped. Implementation waits until PR #357 is merged. No D-number and no chat post given. Relates to D-580.
- Release v1.0.0 (#80) is published. Colin pushed the annotated tag v1.0.0 (tag object 7499457, tagger Colin Meng, tagger date 08:43:41 UTC) on b787309, the release/1.0 commit from PR #251. The "Release" workflow run 43695852014 (https://github.com/dubidu22/sci2audio/actions/runs/43695852014) started at 08:43:44 UTC. dubidu22 approved the pypi deployment. The run ended green at 08:46:27 UTC.
  - PyPI: https://pypi.org/project/sci2audio/1.0.0/ (uploaded 08:45:38 UTC).
  - GitHub release "sci2audio 1.0.0": https://github.com/dubidu22/sci2audio/releases/tag/v1.0.0 (published 08:45:49 UTC).
  - Install from PyPI passed on Linux, macOS and Windows.
  - Colin informed in the project chat at 2026-11-15 08:47:16 UTC.
  - When writing the rows: add a status note "released 15 Nov" to D-570 (release go) and to the #80 release-plan rows (D-484 to D-489). #80 is to be closed by the app thread; add its closing time when that happens. No D-number.
- Main tip after the PR #345 merge: 6c91465 (15 Nov 08:49:48 UTC); after the PR #357 merge: 87c6503 (09:04:56 UTC).
- PR #353 is now at head 38ae4b6 and PR #359 at 9fc815f, after each merged main (6c91465).
- PR #359: round-1 fixes (D-618) pushed at head ff55995. S1 uses option (a), and nothing is deferred. The author's answer is in `plans/review-pr359-round1-answer.md` (project files).
- Issue #362 filed on v1.2 for the formula part of D-615: "testing: a rebuild rule for placeholders whose notice reads the label differently (German 'Formel 3 Punkt 2')". When writing the D-615 row, put #362 in its record cell.
- PR #363: round-1 fixes (D-622) pushed at head 31913ff.
- PR #364, "ci: labels start no CI run; ci:full starts one by hand" (#360, D-620), is open at head c3f9728. Because of the D-611 freeze it has no review thread yet. When writing the D-620 row, add PR #364.
- PR #353 is approvable at head 1b8bb1e. "CI passed" and the ubuntu, macos and windows jobs are green, checked in the API at 09:21 UTC. At first the coordinator held its merge for #363. After this thread pointed out D-619's scope, the coordinator said at 09:22 UTC that this was its error: D-619 stands, and a head that is green on all three systems may merge. The merge go for #353 at 1b8bb1e was given at 09:22 UTC. Record it as approved at 1b8bb1e under D-617 and D-619 (no new number). Squash-merged at head 1b8bb1e as bd3be17 at 09:22:41 UTC, which closed #324 only (09:22:43 UTC). Main tip is now bd3be17. Colin informed in the project chat at 2026-11-15 09:29:33 UTC.

## Resume notes (thread stopped 15 Nov 09:29 UTC on Colin's order, weekly limit)

- Everything up to D-625 is in this file. No KB PR has been opened for 15 Nov yet. Branch it from sci2audio-design main efd6972.
- Still missing:
  - Merge shas for any PR that lands after 0af10d0 (main tip at the stop).
  - The PR numbers for the #343/#344 work and for D-605 PR 4.
- When writing rows, add status notes to the older rows that later decisions touch:
  - D-591 (reinstated by D-611);
  - D-605 (refined by D-610, D-615);
  - D-616 (refined by D-619);
  - D-618 (refined by D-624);
  - D-580 (refined by D-620);
  - D-570 and D-484 to D-489 (released 15 Nov).

- KB PR #49 (D-604 to D-627, head a5de450) was merged by this thread without review (D-626) as 23f913f on sci2audio-design main. Entries after D-627 go into the next day's batch.

Next free D-number: D-628.
