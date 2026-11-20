# KB batch D-725 to D-741: MERGED

MERGED as KB PR #54 (squash 7e5b1ce, 18 Nov 13:09:40 UTC). Status notes added to D-80, D-374, D-462, D-553, D-702, D-705, D-715, D-719, D-722 and D-724. New entries go to kb-batch-2026-11-19-pending.md.

Collected by the KB thread. D-691 to D-724 were merged as KB PR #53 (2d21ce0, 17 Nov 01:03 UTC). The next KB PR is the one for 18 Nov (one per day, D-626), branched from sci2audio-design main 2d21ce0 or later, merged by the KB thread without review.

## Decisions

### D-725 · The Windows flate-bomb test is quarantined
- Decision: test_a_flate_bomb_is_stopped_at_the_memory_limit_and_this_process_stays_small is quarantined on Windows today (D-374).
  - It failed twice on Windows without a code cause: the #481 three-system run (16 Nov 23:20 UTC), and the #484 dispatch run 44005330346 at 64adb70 (the child exited with status 1, no stderr; the PR run on the same head was green).
  - The D-682 isolation run (Actions run 44006516928: Windows only, the test alone, 40 times, on main cfeb084): 0 of 40 failed (`plans/flate-bomb-isolation-d725.md`). The test fails only inside the full fast suite under `-n auto` on the 4-core Windows runner; the likely cause is the memory limit or timing under load, not the code.
  - The quarantine PR comes from the sentence-boundary implementation thread on a fresh branch off main: a skip marker and the issue link only, non-critical, Linux CI, one pinned review round, merged by the review thread. Afterwards #484 merges main; that is a base move, not the PR's one re-run.
  - Merge: PR #486 (skip marker on Windows only) was squash-merged into main as 6525212 at 03:06:13 UTC, pinned to de2f777. #485 stays open (milestone "v1.2.x abbreviations").
  - Note: the scratch branch ci/isolate-flate-bomb-d725 could not be deleted from the session and is to be deleted on GitHub.
- Status: Decided (Claude) (coordinator, 17 Nov 02:56 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Applies D-374 as amended by D-702 f, and D-682.
- Record: sci2audio PR #486 (merged as 6525212), Issue #485, PR #481 (merged as cfeb084), PR #484; Actions runs 44005330346 and 44006516928; `plans/flate-bomb-isolation-d725.md`, `plans/decisions-d712-d714.md` (project files); D-374, D-682, D-702, D-719.

### D-726 · Sentence-boundary batch complete; audit follow-ups
- Merge note (sentence-boundary PR 5): PR #484 (hidden runs go in placeholders read as printed; figure alt text read as a paragraph; #463, #464) had three rounds (`plans/review-pr484-round1.md` to `-round3.md`) and was squash-merged into main as 4bb8f81 at 03:26:48 UTC, pinned to 33108b7. #463 and #464 closed. The sentence-boundary batch (D-715, D-719) is complete; the known-errors gate went from 25 to 9 entries over the batch.
- Decision: the light audit of the batch (`plans/audit-sentence-boundary-batch-2026-11-17.md`) found 0 blocking, 2 should-fix and 2 nits; no contract touched beyond the approved D-725 marker.
  - #487: a table or figure read as printed (notice off) reads its printed text through the same textprep path as a paragraph. The two regression rows that pin the raw reading are corrected in that fix.
  - #488: German "et al." before a capital noun must not end the sentence. Next textprep batch.
  - Both on "v1.2.x abbreviations", lane:textprep. The "(WBGU 2011)" row is noted on #477.
  - Lane threads keep their current batch length. Follow-ups are folded into a batch only when they share its model.
  - The web v1.3 batch (D-723) started at 03:30 UTC from 4bb8f81.
- Status: Decided (Claude) (coordinator, 17 Nov 03:40 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Fifth light batch audit under D-627; follows D-718 and D-719.
- Record: sci2audio PR #484 (merged as 4bb8f81), Issue #463, Issue #464 (closed), Issue #487, Issue #488, Issue #477; `plans/audit-sentence-boundary-batch-2026-11-17.md`, `plans/review-pr484-round3.md`, `plans/decisions-d712-d714.md` (project files); D-627, D-715, D-718, D-719, D-723, D-725.

### D-727 · The light-mode reading bar is #9A7400
- Decision: in light mode the 3 px left bar of the reading mark is #9A7400, not #B08400, because #B08400 measures 2.97:1 on the Focus desk background #EDEFF2.
  - #9A7400 measures 4.31:1 on the paper, 3.74:1 on the desk and 4.02:1 on the fill.
  - Rule: the bar passes 3:1 on every background it sits on, pinned by a unit test.
  - The dark bar stays #F2DC3A.
  - In PR A, #489.
- Merge note: PR #489 (the pale reading mark with a margin bar, P keeps the focus, counts match the sheet; #461, #462, #471, #472) had two rounds (`plans/review-pr489-round1.md`, `plans/review-pr489-round2.md`) and was squash-merged into main as 9377cd8 at 04:40:14 UTC, pinned to b847ce8. The four issues closed.
- Status: Decided (Claude) (review thread / coordinator, 17 Nov 04:02 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). **Amends D-724** (the colour only); refines D-716.
- Record: sci2audio PR #489 (merged as 9377cd8), Issue #461, Issue #462, Issue #471, Issue #472 (closed); `plans/review-pr489-round1.md`, `plans/review-pr489-round2.md`, `plans/decisions-d712-d714.md` (project files); D-711, D-716, D-720, D-723, D-724.

### D-728 · Marker PR B plan revision approved
- Decision: the revised `plans/general-marker-plan.md` is approved for #474, under the critical process of its section 6. The revision adds the D-718 lines for PR A's mark and panel, #460/#480, the D-727 contrast for the flag edge and tick, and section 7a with all 8 test-harness changes. Rulings:
  1. A test fails without the broken-file guard, and a test fails if a not-found marker is dropped from the list or the file.
  2. Undo restore uses the same locked read-modify-write path as a set.
  3. The removal box's marker count is read from the file when the box is drawn, pinned by the extended #120 test.
  - PR B branches from main after #489 merges, with the same review thread. It started at 04:41 UTC on web-v13-pr-b from 9377cd8.
- Merge note: PR #490 (markers with a note on the Listen page; #474) had two rounds (`plans/review-pr490-round1.md`, `plans/review-pr490-round2.md`) and was squash-merged into main as fc7406a at 06:28:24 UTC, pinned to c0c21ba. #474 closed. v1.3 is complete apart from #437, #411 and #443 (at 06:30 UTC milestone "v1.3 The Working Reader" has only #437 open; #411 and #443 have no milestone). The coordinator told Colin at 06:30 UTC.
- Status: Decided (Claude) (coordinator, 17 Nov 04:08 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Critical plan. Refines D-723; applies D-718.
- Record: sci2audio PR #490 (merged as fc7406a), Issue #474 (closed), Issue #480, Issue #120, Issue #437; `plans/general-marker-plan.md`, `plans/review-pr490-round1.md`, `plans/review-pr490-round2.md`, `plans/decisions-d712-d714.md` (project files); D-718, D-722, D-723, D-727.

### D-729 · Unassigned code points in output file names fixed first (#491, PR #492)
- Decision: the macOS ci:full failure of PR #490 (markers, #474) came from an older bug: Schemathesis generated a document name holding U+E57EE (unassigned), which APFS refuses, and output.names.clean() did not strip it (#491, older than PR B).
  - PR #492 (lane:output, non-critical) is reviewed by the web batch's review thread, at most 2 rounds, and merged only after its own three-system run is green. Then #490 merges main as a base move.
  - The reviewer checks that the rule covers all unassigned and surrogate code points, and that the corpus output names are unchanged.
- Merge note: #492 had one round (`plans/review-pr492-round1.md`) and was squash-merged into main as 5812d2d at 05:46:31 UTC, pinned to 7e07e5c. #491 closed. Leftover: #493 (a name with a character newer than the Mac's Unicode tables still fails on macOS; "v1.2.x abbreviations").
- Status: Decided (Claude) (coordinator, 17 Nov 05:40 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Follows D-728.
- Record: sci2audio PR #492 (merged as 5812d2d), Issue #491 (closed), Issue #493, PR #490 (open); `plans/review-pr492-round1.md`, `plans/decisions-d712-d714.md` (project files); D-723, D-728.

### D-730 · The #480 joined-sentence plan approved
- Decision: `plans/480-joined-sentence-plan.md` is approved.
  - C1 (output and app): Pause.CLAUSE of 0.25 s, edge silence trimmed at clause joins, and an additive "joins" key in the read-along file; the format version stays 1. Critical, because docs/readalong-format.md is a contract document. The additive key is accepted instead of a version 2, with a test that a version-1 reader without the key and a new reader on an old file both work.
  - C2 (web): one element per sentence, sentence steps by element, and a marker anchors the whole sentence. Non-critical. C1 merges first.
  - B: raising DEFAULT_MAX_CHARS from 300 to 400 (textprep, critical) is its own PR after C1 and C2, filed now as #494 (v1.2, risk:high).
  - The sentence gap itself stays out of scope.
  - Author: a new web/app thread, "Make cut sentences sound joined" (started 06:06 UTC), because the batch thread reached 3 compressions and stays only for the #490 fix rounds. Same review thread as the web batch.
  - #490 (markers) was handed to review at 06:02 UTC at 7aac6ba.
  - C1 is PR #495 (the audio half of #480), in review since 06:28 UTC.
  - C2 is PR #503 (the pieces of a cut sentence are one sentence on the page and for markers; non-critical), handed to review at 08:00 UTC at 763595d. Round 1 asked for tests only: S1, the edit mark and a hyphen across the cut are untested; S2, the grouping rule for overlapping pieces is untested.
  - Merge note: round 2 (tests only; each new test fails when its rule is broken; the nightly seeds pass) was approvable (`plans/review-pr503-round1.md`, `plans/review-pr503-round2.md`). #503 was squash-merged into main as 344db7a at 08:28:07 UTC (head deb732f). #480 closed 08:28:08.
  - Merge note: C1, PR #495 (critical), had one review round with no findings (`plans/review-pr495-round1.md`) and was squash-merged into main as 3c7482f at 07:17:33 UTC, pinned to 19afadc. The nightly real-voice gap at a cut is 0.31 s in English and German on all three systems (it was 0.56 to 0.80 s). 21 of 23 mutants caught, 2 argued equivalent; both nightly seeds passed; the old-reader and old-file tests pass. #480 stayed open for C2.
- Status: Decided (Claude) (coordinator, 17 Nov 06:05 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Critical plan (C1, the read-along contract). Follows D-719 (Q4) and D-703 d (thread replacement).
- Record: sci2audio Issue #480 (closed), Issue #494 (v1.2), PR #495 (merged as 3c7482f), PR #503 (merged as 344db7a), PR #490 (merged as fc7406a); `plans/480-joined-sentence-plan.md`, `plans/review-pr495-round1.md`, `plans/review-pr503-round2.md`, `plans/decisions-d712-d714.md` (project files); D-703, D-705, D-719, D-728.

### D-731 · Nightly red on main fc7406a: no block on #495; untracked failures get owners
- Decision: the author thread of #480 reported that every red job in the #495 nightly also fails on main fc7406a. Ruling (same pattern as D-725 and D-729):
  1. Failures already on main's nightly do not block #495. The reviewer compares each red job against the main run and records the match in the round report; #495 is judged on its own jobs and the nightly seeds.
  2. Tracking: the EPUB cover test stays with #473 (release/1.1 ports). Firefox (4 tests), WebKit macOS (11 tests, mostly v1.3 Focus, panel and shortcut tests) and WebKit Ubuntu (1 panel test) get lane:web issues, filed by the #480 author thread; WebKit items join #437 where the cause is the same. The WebKit marker-test failure is a post-merge defect of #490 and goes into the ledger.
  3. Owner: the web lane. Order after C1 merges: C2, then #473, then the "nightly green" fix PRs for the new issues (non-critical unless they touch tests pinned as goldens), then the web batch audit. v1.3 stays complete, subject to the open #437. The WebKit v1.3 test failures are #437 scope unless the triage finds a real Safari bug, which goes to Colin.
- Addendum (coordinator, 07:01 UTC): the failures are now #496 to #502 (lane:web, no milestone). #496 (the markers panel keyboard-order test on WebKit macOS) is a post-merge defect of #490, with a ledger line. #502 (WebKit: Tab after a press on panel text) is noted on #437 as a prerequisite for its five green runs. The rest of the Firefox, WebKit and EPUB failures were already in #473. The triage found only test-harness causes, no Safari bug.
- Merge note (10:17 UTC): PR #507 (port the release/1.1 fixes to main; #473; D-701, non-critical) had one round with no findings (`plans/review-pr507-round1.md`) and was squash-merged into main as 1e461a7 at 10:16:58 UTC (head c4fdcd7). #473 closed. It fixes in the nightly the EPUB cover test on all three systems, the Firefox position and speed tests, and the WebKit macOS speed-keyboard test.
  - New flaky-test issues: #508 (a duplicate of #506, closed) and #509 (the "waits for the script" tests act before the reloaded page is parsed).
  - The nightly-green batch (#496 to #502, #506, #509) starts in the web lane.
  - Status (coordinator, 11:01 UTC): nightly-green PR 1 is PR #510 (branch tests/webkit-focus-tab from main 1e461a7; opened 10:59 UTC; Linux CI green; in review, non-critical, at most 2 rounds), for #496, #497, #498 and #502. Branch nightly run 44065741504: WebKit macOS down from 10 failures to 3, WebKit Ubuntu green, Firefox only the 2 failures main already has; the rest belongs to PR 2.
    - #502's real cause: WebKit starts Tab from the pressed panel text, focus leaves to the body, and the panel closes one Tab later. The app is right; the test now checks that path.
    - #498 ruling applied: the narrow panel's Close button moves focus back to the toggle in every browser.
    - The web thread "Make the browser nightly green on main" stopped at 2 compressions after its hand-off (`plans/nightly-green-handoff.md`, D-703 d). A fresh web thread, "Finish the nightly-green PRs 2 and 3" (Opus high), started at 11:01 UTC for #499, #500, #501, #506 and #509.
    - Merge note: #510 had one round with no findings (`plans/review-pr510-round1.md`) and was squash-merged into main as 68f322d at 11:01:50 UTC (head 2c70529); #496, #497, #498 and #502 closed. The one app change: the narrow panel's Close button returns focus to the toggle in every browser, with a test that fails on the old code.
- Status: Decided (Claude) (coordinator, 17 Nov 06:57 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Follows D-725, D-729 and D-730.
- Record: sci2audio PR #495 (merged as 3c7482f), PR #490 (merged as fc7406a), PR #507 (merged as 1e461a7), PR #510 (merged as 68f322d), Issue #473 (closed), Issue #437, Issues #496 to #502, Issue #506, Issue #508 (closed), Issue #509; `plans/review-pr507-round1.md`, `plans/decisions-d712-d714.md` (project files); D-374, D-701, D-721, D-725, D-729, D-730.

### D-732 · Priority fix: resuming a paused audiobook build (Colin's priority)
- Decision: Colin reports that pausing works, but resuming shows the "files exist already, replace / clear voice cache" dialog and looks as if the progress is lost.
  - Critical: it is a safety dialog that can delete user files and the cache, and it touches the output contract.
  - Its own thread, "Fix resuming a paused audiobook build" (Opus high), runs in parallel with the #480 thread, as an exception to D-705 on Colin's priority order.
  - Plan first (`plans/resume-build-plan.md`, approved by the coordinator), then one PR, lane:app: a test that fails without the fix, ci:full, and a critical review of up to 4 rounds.
  - The #503 review continues; the resume PR is reviewed ahead of anything else when it arrives.
- Status: Decided (Claude) (coordinator, 17 Nov 08:26 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a), on Colin's priority request (17 Nov 08:24:11 UTC, in the project chat, with a screenshot: "pausing works. resuming not. it looks like whatever i do i will lose the progress. this is a critical issue that needs prio fixing"). An exception to D-705. Follows D-665 (Pause, Resume and Cancel) and D-694.
- Record: sci2audio Issue #504, PR #505 (merged as 11b8b13, D-733); `plans/resume-build-plan.md`, `plans/decisions-d712-d714.md` (project files); D-665, D-694, D-695, D-705.

### D-733 · Resume plan approved: Resume keeps the run's overwrite choice
- Decision: `plans/resume-build-plan.md` is approved as written, including item 4 (the cache button behind a confirm box).
  - Diagnosis: progress is not lost with "Diese Dateien ersetzen" (the spoken chunks are reused); only the cache button loses it. Cause: Resume posts overwrite=false although the paused run started with overwrite=true, and JobRecord keeps no record of it, so a paused replace run hits the existing-files check again.
  - Fix: JobRecord and JobOut gain overwrite (additive); the job card carries data-overwrite and Resume reposts it. The existing-files card drops the cache button and says the spoken sentences are kept (only when the cache holds some). The cache button sits behind a confirm box that names the loss.
  - Additions: the confirm-box test must fail without the confirm step; the empty-cache case is tested.
  - Labels lane:app, lane:web, risk:high, bug; milestone v1.3.
  - Colin was given the workaround at 08:30 UTC.
  - Merge note: PR #505 (Resume after Pause continues a replace run; freeing the cache asks first; #504) had one round with no findings (`plans/review-pr505-round1.md`): 13 of 13 mutants caught, the nightly seeds pass, three systems green. Squash-merged into main as 11b8b13 at 09:21:53 UTC, pinned to 7ae1c9c. #504 closed (v1.3).
  - Also filed: #506 (the marker note-survives-reload test reloads before the save has finished; origin #490; lane:web, "v1.2.x abbreviations").
- Status: Decided (Claude) (coordinator, 17 Nov 08:30 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a). Critical plan (a safety mechanism; an additive field on a core record). Carries out D-732; follows D-694 and D-695.
- Record: sci2audio PR #505 (merged as 11b8b13), Issue #504 (closed), Issue #506; `plans/resume-build-plan.md`, `plans/review-pr505-round1.md`, `plans/decisions-d712-d714.md` (project files); D-665, D-694, D-695, D-697, D-732.

### D-734 · The nightly-green batch
- Decision (found in `plans/decisions-d712-d714.md`; not relayed to the KB thread): after #507 (1e461a7, #473 closed), the web lane fixes #496 to #502, #506 and #509 (#508 closed as a duplicate of #506).
  - At most three PRs, grouped by cause, one at a time; #502 goes in the first, because it blocks #437's five green runs.
  - Non-critical unless a PR changes a golden or regression case. Each PR: Linux CI green, a nightly dispatch on the branch proving the targeted browser tests, a review of at most 2 rounds.
  - #498 ruling: the tests follow Safari's click-focus rule, except the narrow panel's Close button, where the app moves focus back to the toggle in every browser (recommended to Colin at 08:25 UTC, no objection yet).
  - The web batch audit after this batch covers #489, #490, #495, #503, #505, #507 and these PRs.
- Status: Decided (Claude) (coordinator, 17 Nov 10:20 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Carries out D-731 point 3.
- Record: sci2audio PR #507 (merged as 1e461a7), PR #510 (merged as 68f322d), Issues #496 to #502, Issue #506, Issue #508 (closed), Issue #509, Issue #437; `plans/decisions-d712-d714.md` (project files); D-731.

### D-735 · Nightly-green PR 2 plan approved
- Decision: the PR 2 plan of the nightly-green batch, as posted by the fresh web thread, is approved. Tests only, non-critical, from main 68f322d.
  - #499: no macOS Back chord in the key test; Meta+ArrowRight and Control+ArrowLeft instead, with the Listen-URL assertion kept on every chord. Control+a becomes ControlOrMeta+a.
  - #500: the cause is confirmed in Firefox as a background-color transition on input#follow.switch after the theme change. A change_theme() helper waits for CSS transitions only, and only after a theme change; the all == 0 rule stays elsewhere (D-709 intact).
  - #501: abs(bottom - height) &lt; 0.5.
- Merge note: PR #511 (tests only, non-critical; opened 12:17 UTC from main 68f322d; branch nightly 44079398176 green in all four browser jobs) had one round with no findings and was squash-merged into main as 96de4a3 at 12:18:20 UTC (head b1cb33a); #499, #500 and #501 closed. Finding: Ctrl+Left is also Back in WebKit on macOS, so the key test uses right-arrow chords only.
- Then (D-736): PR 3 (#506, #509) is stopped. Its fix is committed on the branch tests/nightly-reload-timing with no PR (a 40-run check at 4 of 40). A Firefox voice-card test failed once on that branch and has no issue yet. The web and review threads are resolved; the batch pauses before PR 3 and the web batch audit.
- Status: Decided (Claude) (coordinator, 17 Nov 11:05 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Follows D-734.
- Record: sci2audio PR #511 (merged as 96de4a3), Issue #499, Issue #500, Issue #501 (closed); `plans/decisions-d712-d714.md` (project files); D-709, D-731, D-734.

### D-736 · No new issues are started, to save Colin's weekly token limit (Colin)
- Decision: from now on no new issues are started, to preserve Colin's weekly token limit (at 80%).
  - PR 2 of the nightly-green batch, already in progress, finishes and is reviewed.
  - PR 3 (#506, #509), the web batch audit, and #469 and #470 wait.
  - The 18 Nov decision-log PR is written as planned, kept short.
- Status: **Decided** (Colin, 17 Nov 11:15:50 UTC, in the project chat: "dont start working on new issues from now on. I must preserve the rest of my weekly token limit. its at 80% already"). Pauses D-734 after PR 2.
- Record: sci2audio Issue #506, Issue #509, Issue #469, Issue #470; D-705, D-734, D-735.

### D-737 · Rules 1.4.1 after the 18 Nov governance audit
- Decision: the audit thread "Audit the project governance rules" found 0 script errors and four blocking gaps. Coordinator edits (META-01): CMD-07 writes the D-736 freeze into the rules (no new threads or issues, running rounds finish, the daily KB PR continues, threads answer Colin); TST-07 and TST-08 put into one order (changed again by D-739); project-state.yaml cleared of stale text and stamped; project-rules.json regenerated. The new autonomy horizon was left to Colin (D-740). The six minor items were deferred (applied by D-738).
- Status: Decided (Claude) (coordinator, 18 Nov 13:00 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Follows D-713, D-714 and D-736.
- Record: `rules/project-rules.yaml` 1.4.1, `rules/project-state.yaml`, `plans/decisions-d712-d714.md` (project files); D-713, D-714, D-736.

### D-738 · Rules 1.4.2: the audit's minor items applied (Colin)
- Decision: applied by the audit thread on the coordinator's instruction (13:01 UTC):
  - REV-09: a failure that also fails on main does not block; a bug older than the PR is fixed first in its own lane PR (D-725, D-729, D-731).
  - LANE-02 gains the D-732 priority-bug exception.
  - REV-06: the review thread sends the round-report path to the author directly; the coordinator gets one line.
  - PLAN-04: no acceptance criteria, no start (from CLAUDE.md).
  - AUTO-02 points to autonomy_messages in the state file; CMD-04 loses its dead thread-count clause; WD-01 fires no checks during a freeze while no thread owes a result.
  - State file: frozen_queue added; stale entries cleared; open_owner_items gains the #469/#470 questions and the milestone 7 rename (the GitHub title is still "v1.2.x abbreviations"; Colin's hand step).
  - `plans/roadmap-after-v1.md` gets a "superseded in part" note (D-666, D-721, D-722).
  - CLAUDE.md: PR #516 (horizon-neutral autonomy wording, a current-goal section and the acceptance-criteria rule; critical, reviewed and merged by the coordinator).
  - Not applied: the autonomy horizon (D-740) and WD-01's 60 minutes (Colin's value). Moving the CI and release rules out of the ruleset is left for a later version.
- Status: **Decided** (Colin, 18 Nov 13:00:57 UTC, in the project chat: "fix all issues"). Recorded by the coordinator at 13:10 UTC.
- Record: sci2audio PR #516 (open); `rules/project-rules.yaml` 1.4.2, `rules/project-state.yaml`, `plans/roadmap-after-v1.md`, `plans/decisions-d712-d714.md` (project files); D-666, D-721, D-722, D-725, D-729, D-731, D-732, D-737.

### D-739 · Rules 1.4.3: same-day quarantine first, isolation after
- Decision: the audit's M2 and M4 are taken as proposed.
  - TST-07 quarantines a flaky test the same day; TST-08 runs the 40-run isolation afterwards, with the result in the issue. Reason: a browser isolation takes longer than a day (PR 3 sat at 4 of 40), and D-725 quarantined the same day regardless.
  - CMD-07 allows filing issues during a freeze (filing only), so GH-01 and TST-08 keep working. The unfiled Firefox voice-card flake (`plans/nightly-green-handoff.md`) is filed when the next web thread starts.
- Status: Decided (Claude) (coordinator, 18 Nov 13:15 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). **Amends D-737** (the order); refines D-374 and D-682.
- Record: `rules/project-rules.yaml` 1.4.3, `plans/nightly-green-handoff.md`, `plans/decisions-d712-d714.md` (project files); D-374, D-682, D-725, D-737.

### D-740 · Autonomy runs until Colin stops it or no issues are left (Colin)
- Decision: autonomy runs until Colin asks to stop or there are no more issues to work on. This replaces "until v1.3 finished" (D-702 a). autonomy_horizon in project-state.yaml is set; AUTO-01 points to it. Roadmap, product scope and the round-4 stop stay with Colin. The D-736 freeze was not lifted by this (see D-741).
- Status: **Decided** (Colin, 18 Nov 13:04:30 UTC, in the project chat: "autonomy runs until i ask to stop or there are no more issues to work on."). **Amends D-702 a**; extends D-80, D-462 and D-553.
- Record: `rules/project-state.yaml`, `plans/decisions-d712-d714.md` (project files); D-80, D-462, D-553, D-702.

### D-741 · The freeze is lifted; lanes run in parallel while they do not block each other (Colin)
- Decision: the D-736 freeze is lifted (CMD-06), and the one-thread limit of D-705 is replaced (rules 1.4.4, LANE-02).
  - Coordinator reading: one implementation thread and one review thread per lane. Lanes that share files, goldens, regression cases or a layer contract do not run side by side.
  - Started: the web lane (nightly-green PR 3, #506 and #509, and the voice-card flake issue), a textprep batch (#494 critical, #487, #488, #477), and the light web batch audit.
  - Waiting: layout (#456 to #459) behind textprep, because of shared goldens; the app lane (#469, #470) on Colin's three answers; the docs PR #516 on CI. The 60-minute watchdog restarted.
- Status: **Decided** (Colin, 18 Nov 13:06:43 UTC, in the project chat: "continue working on multiple lanes as long as they dont block each other."). **Amends D-705** (one thread at a time) and **lifts D-736**.
- Record: sci2audio Issue #506, Issue #509, Issue #494, Issue #487, Issue #488, Issue #477, Issues #456 to #459, Issue #469, Issue #470, PR #516; `rules/project-rules.yaml` 1.4.4, `plans/decisions-d712-d714.md` (project files); D-705, D-734, D-736, D-740.

## Open points carried over (no D-number yet)
- #442 (v1.2, P1, lane:extraction): PDF fonts without a Unicode mapping are read as glyph codes. Proposed fix: detect and stop with a notice (makes #187 concrete). Recovering text from the glyph table is new scope for Colin.
- #469 and #470 (v1.2): Colin's per-project files requirement (16 Nov 19:18 UTC). They supersede D-353 once Colin answers the three questions asked at 19:21 UTC. #469 gets the critical process.
- Colin still to confirm the Kehren motto (PR #476, D-719).

Next free D-number: D-742.
