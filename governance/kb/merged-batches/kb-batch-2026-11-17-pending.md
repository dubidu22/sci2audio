# KB batch D-691 to D-724: MERGED

MERGED as KB PR #53 (squash 2d21ce0, 17 Nov 01:03:09 UTC). Status notes added to D-60, D-374, D-376, D-462, D-553, D-626, D-646, D-663, D-667, D-669, D-681, D-684, D-688 and D-689. New entries go to kb-batch-2026-11-18-pending.md.

Collected by the KB thread. D-656 to D-690 were merged as KB PR #52 (57eb6ae, 16 Nov 03:29 UTC). The next KB PR is the one for 17 Nov (one per day, D-626), branched from sci2audio-design main 57eb6ae or later, merged by the KB thread without review.

## Decisions

### D-691 · Light batch audit of textprep PRs 3 and 4: 0 missed bugs
- Decision:
  - The light batch audit (D-627) of textprep PRs 3 and 4 (#408 merged as ffdd2f9, #425 merged as e107f64) found 0 missed bugs (`plans/audit-textprep-batch-2026-11-16.md`).
  - One should-fix is filed as #428: link_removals does not pass the language to _block_edits, so a German abbreviation before a link ("u. a. https://x.org.") is judged with the English list. Latent. Milestone v1.2, folded into textprep PR 5.
  - No contract touches. 36 cross-PR shapes are idempotent.
  - Thread-lifetime finding: the S1 slipped into the old lane thread's third PR after two compressions; the fresh thread did PR 4 with no fix rounds. So one lane thread per batch stays (D-626, D-627).
- Status: Decided (Claude) (coordinator, 16 Nov 03:31 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Carries out D-627; third batch audit after D-645 and D-655.
- Record: sci2audio PR #408 (merged as ffdd2f9), PR #425 (merged as e107f64), Issue #428 (v1.2); `plans/audit-textprep-batch-2026-11-16.md` (project files); D-626, D-627, D-645, D-655, D-683, D-690.

### D-692 · Textprep PR 5 plan approved (#193, #93, #191, #428)
- Decision: the plan `plans/textprep-v12-pr5-plan.md` is approved.
  - #193: a new inline step, hidden-runs (Page furniture, the first inline step), removes hidden, aria-hidden, epub:pagebreak and doc-pagebreak runs.
  - #93: a new inline step, affiliation-marks (Footnotes, after footnotes), removes small raised digit or asterisk marks in the title block (page 1 up to the first heading, after a capitalised name or before a capitalised affiliation).
    - Five corpus papers change: chi, arsiwalla, liu, waskom, biggs.
    - JOSS same-size affiliation numbers are left read, with a new issue to follow.
  - #191: uncaptioned figures read "A figure is skipped. It shows: <alt>." / "Eine Abbildung wird übersprungen. Sie zeigt: <alt>."; several pictures are joined by "; ".
    - make_document gains pictures=, and rebuilt_from_script keeps them, so the second-run check sees the alt text.
  - #428 is folded in as section D.
- Status: Decided (Claude) (coordinator, 16 Nov 03:38 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Critical plan (new steps, corpus changes). Follows D-646 and D-691.
- Record: sci2audio Issue #193, Issue #93, Issue #191, Issue #428 (all v1.2); `plans/textprep-v12-pr5-plan.md` (project files); D-646, D-691.

### D-693 · Working Reader batch B: PRs #420 and #421 approvable in round 2
- Decision:
  - PR #420 (#389) round 2 at 4235d74 and PR #421 (#390) round 2 at f9df0e9 are approvable (`plans/review-pr420-round2.md`, `plans/review-pr421-round2.md`).
  - Filed on v1.3: #429 (the announce switch test reads the cookie before the save has landed; a wait_for_url bug) and #430 (pin the read-along bounds cache key and the last-sentence edge of Continue).
  - Merge go for #420. #421 is retargeted to main and merged on green.
  - The German-book WebKit test is not quarantined; #427 is fixed first in batch C.
  - #420 was squash-merged into main as ca3458a at 03:45:21 UTC, pinned to 911509e (4235d74 plus main e107f64); #389 closed 03:45:22.
  - #421 was retargeted to main and squash-merged as f063454 at 03:52:16 UTC, pinned to 94a23e1 (the reviewed f9df0e9 with main merged in; the diff was confirmed byte-identical); #390 closed 03:52:18. Batch B is complete. Main is now f063454.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 03:38 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-687.
- Record: sci2audio PR #420 (merged as ca3458a), PR #421 (merged as f063454), Issue #389, Issue #390 (closed), Issue #429, Issue #430 (v1.3), Issue #427; `plans/review-pr420-round2.md`, `plans/review-pr421-round2.md` (project files); D-374, D-682, D-687, D-689.

### D-694 · Working Reader batch C plan approved
- Decision: the plan `plans/working-reader-batch-c-plan.md` is approved.
  - One critical PR (risk:high): #391, Prepare with the job inline.
    - Pause, Resume and Cancel use the existing endpoints.
    - Cancel frees the speech cache behind a confirm, and only after the job has stopped.
  - The same PR also takes #427, #429, #430 and #422.
  - The #365 quarantine is lifted when R3 of the v1.1 release reaches main.
  - The web lane thread is replaced after batch B (second compression). A new thread takes batch C.
- Status: Decided (Claude) (coordinator, 16 Nov 03:42 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Critical plan. Follows D-665, D-686, D-689 and D-693; thread change under D-626 and D-627.
- Record: sci2audio Issue #391, Issue #427, Issue #429, Issue #430, Issue #422, Issue #365; `plans/working-reader-batch-c-plan.md` (project files); D-626, D-627, D-665, D-689, D-693.

### D-695 · Batch C deviation: two additive fields on AudioProgress
- Decision: approved deviation from the batch C plan (D-694).
  - AudioProgress (app/audio.py) gains two additive fields: chapter_number (the 1-based position among the chapters with something to say) and chapter_done.
  - Reason: the Prepare job card must name the chapter a failed or paused job stopped in. The last progress names the chapter of the last finished chunk, which is wrong at a chapter boundary.
  - A failure in the encoding phase reads "every chapter is spoken and kept". A failure before the first chunk reads that nothing is spoken yet.
  - No endpoint or runner change.
- Status: Decided (Claude) (coordinator, 16 Nov 03:51 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). **Refines D-694**; touches a core dataclass, so critical. Follows D-665 (a failure says what is really kept).
- Record: sci2audio Issue #391; `plans/working-reader-batch-c-plan.md` (project files); D-665, D-694.

### D-696 · No 1.1.0 mutation result; the tag is not held
- Decision:
  - Mutation run 43774246928 for #412 (on release-fix/1.1.0-nightly, 5131ba1) failed with no result after about 5 hours (started 15 Nov 23:20 UTC, ended 16 Nov 04:23 UTC); the hosted runner lost contact (#246).
  - No rerun before the 1.1.0 tag. Under D-531 the tag is not held.
  - The R2 body (PR #426) records that no 1.1.0 mutation result was obtained and points to #246. (API at 04:26 UTC: the #426 body still says "still running"; check when writing the row.)
  - A rerun needs #246 done first: fewer workers, one part per package, results kept per part.
- Status: Decided (Claude) (coordinator, 16 Nov 04:24 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Applies D-531; **amends D-688** (the mutation result was to go into the R2 body).
- Record: sci2audio PR #412 (merged into release/1.1 as e9d08ef), PR #426 (draft), Issue #246 (open, milestone v1.0.1); Actions run 43774246928 (failure); D-531, D-669, D-688.

### D-697 · Working Reader batch C (PR #433) round 1: changes needed, no blocker
- Decision: PR #433 (Prepare with the audiobook job inline, and the batch C test fixes; #391, #427, #429, #430, #422; critical) round 1 at f7521e8 needs changes, with no blocker (`plans/review-pr433-round1.md`).
  - The Cancel safety mechanism is confirmed: it polls until the job has stopped, then sends DELETE; three mutants are caught; the server's 409 is a second guard.
  - S1: the card buttons and .remove-now go into the #427 hold tests.
  - S2: card tests for failed-while-writing and running-while-writing.
  - N1 (fix): Pause before the first sentence says Paused, not Cancelled.
  - N2 (wording only): the card says it continues with that run's settings. Resume keeps the run's settings, not the page's current controls.
  - N3 (fix): the stopped() poll gives up after about 2 minutes; nothing is deleted and the button comes back.
  - Review lesson: every server-drawn button wired only by app.js is in #427's scope, including buttons added in the same PR.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 05:33 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-694 and D-695.
- Record: sci2audio PR #433 (open), Issue #391, Issue #427, Issue #429, Issue #430, Issue #422; `plans/review-pr433-round1.md`, `plans/working-reader-batch-c-plan.md` (project files); D-689, D-694, D-695.

### D-698 · PR #433 round 2; a rule for when a PR goes to review
- Decision:
  - PR #433 round 2 at 45b6457 (`plans/review-pr433-round2.md`): all round 1 items are fixed and the surviving mutants are caught; ci:full is green; the screens match the design.
  - One fix remains: test_the_main_flow_by_keyboard fails twice on WebKit on Ubuntu (focus is not on #message after "Free the speech cache"). Round 3 is the final round, on a new head.
  - #437 filed (v1.3): WebKit on Ubuntu is unstable in the nightly, five runs named. No quarantine.
  - Process rule (from #433):
    - A PR goes to review only after its Linux CI is green and, for a critical PR, after the author's own ci:full dispatch is green.
    - The author freezes the branch during a review round, with one fix commit per round.
  - Merge (merge note, no new D-number): round 3 (`plans/review-pr433-round3.md`) was approvable. #433 was squash-merged into main as fbc4d12 at 08:30:41 UTC, pinned to d8b060f (the reviewed 2d1e998 plus main 8fb51ac; the diff was confirmed byte-identical). #391, #427, #429, #430 and #422 closed 08:30:43 to 08:30:46. Three review rounds (D-697, D-698, round 3). Main is now fbc4d12.
  - #437 stays open until five WebKit-Ubuntu nightlies in a row are green.
  - The coordinator told Colin the reader is usable, answering his standing request of 07:08:45 UTC (D-702). Add the chat post time if given.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 07:00 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-697. The process rule adds to D-627 (review rounds).
- Record: sci2audio PR #433 (merged as fbc4d12), Issue #391, Issue #427, Issue #429, Issue #430, Issue #422 (closed), Issue #437 (v1.3); `plans/review-pr433-round2.md`, `plans/review-pr433-round3.md` (project files); D-374, D-627, D-697.

### D-699 · Textprep PR 5 (#436) deviation: other rules skip hidden text and affiliation marks
- Decision: approved deviation in PR #436 (textprep PR 5; #193, #93, #191, #428; D-692).
  - The number, unit, statistic and abbreviation rules also skip hidden text and affiliation marks, through the existing footnote-mark mechanism.
  - Reason: a fuzz check found second-run differences.
  - The corpus is unchanged.
  - Follow-ups filed by the lane, both on Later: #431 (affiliation numbers printed in the text's own size are read; JOSS title blocks; the issue named in D-692) and #434 (a link or citation that holds or touches a hidden run reads differently on a second run).
  - Merge (merge note, no new D-number, coordinator 11:36 UTC): PR #436 (critical) was approved after three rounds (`plans/review-pr436-round1.md` to `-round3.md`) and squash-merged into main as 6a2aeb3 at 11:34:13 UTC, pinned to 3d0a6e4. #193, #93, #191, #428 and #434 closed. A probe row "40K" was swapped for "40Ca". Filed from the review on v1.2: #445 (a hidden run between a number and its unit reads differently), #448 (the mass number of a labelled molecule such as ¹³CO in a title), #449 (a raised mass number before K, ⁴⁰K, reads "40 thousand").
- Status: Decided (Claude) (coordinator, 16 Nov 07:10 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). **Refines D-692**.
- Record: sci2audio PR #436 (merged as 6a2aeb3), Issue #193, Issue #93, Issue #191, Issue #428, Issue #434 (closed), Issue #431 (Later), Issue #445, Issue #448, Issue #449 (v1.2); `plans/review-pr436-round1.md`, `plans/review-pr436-round2.md`, `plans/review-pr436-round3.md`, `plans/textprep-v12-pr5-plan.md` (project files); D-692.

### D-700 · #438 is fixed in its own small PR before #436 is reviewed
- Decision: #438 (the work-folder cache keeps an old fingerprint when a file is rewritten at the same size within one timestamp tick; a Windows test failure) is fixed in its own small PR on main, before #436 is reviewed. No quarantine.
  - API at 07:11 UTC: #438 is open with no milestone.
- Status: Decided (Claude) (coordinator, 16 Nov 07:10 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-374 and D-674 (the racy-file guard of #403 B1; #407).
- Record: sci2audio Issue #438, PR #436, PR #403 (merged into release/1.1 as 08d5965), Issue #407; D-374, D-674, D-675, D-699.

### D-701 · #439 ports the release/1.1 guard; WebKit fragment focus; attachment limit
- Decision:
  - PR #439 (the fix for #438) ports release/1.1's #403 B1 guard (app/config.py and its two tests, from 08d5965) word for word onto main, instead of a new implementation, so the R3 forward-merge stays free of conflicts.
  - Rule: before fixing a bug on main, check whether release/1.1 already fixed it.
  - Review lesson from the #433 round 2 fix (head 2d1e998): WebKit refocuses the address's #fragment when the page finishes loading, which steals focus from a later move. app.js drops the fragment once it has focused it, as player.js does with #continue. This also explains the #437 Make failure.
  - Process: a review thread hits a limit of 24 attached files; reports stay in plans/ (project files).
  - #439 had two review rounds (`plans/review-pr439-round1.md`, `plans/review-pr439-round2.md`) and was squash-merged into main as 8fb51ac at 07:59:09 UTC, pinned to 9842776; #438 closed 07:59:11. Main is now 8fb51ac.
  - #433 was open at 2d1e998 at 07:55 UTC.
- Status: Decided (Claude) (coordinator, 16 Nov 07:54 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Carries out D-700; follows D-674, D-675 and D-698.
- Record: sci2audio PR #439 (merged as 8fb51ac), Issue #438 (closed), PR #403 (merged into release/1.1 as 08d5965), PR #433 (open), Issue #437; D-674, D-675, D-698, D-700.

### D-702 · Rules consolidation (from the rules-file audit)
- Decision:
  - a) Autonomy is extended "until v1.3 finished" (Colin, 16 Nov 06:05 UTC). Extends D-80 as extended by D-462 and D-553.
  - b) A release-branch thread may run beside the app lane thread while a release is open.
  - c) One review thread may serve consecutive batches of the same lane while it passes the fitness check. D-376 is retired.
  - d) A lane thread is replaced at two context compressions.
  - e) Colin's control words keep their workflow-export meaning (his wording); only the pre-D-626 model names are dropped.
    - "slow down": at most 2 implementation threads, and reviews on the lighter setting. Under D-626 that means every review on Opus medium, critical ones included, until "continue".
    - "pause all threads": no new thread turns until "continue".
    - (Corrected by the coordinator at 08:11 UTC, after the KB thread pointed to the export's wording.)
  - f) D-374: quarantined tests are fixed before the next release, not "before v1.0".
  - g) PRs into a release branch run Linux CI only. Critical merges get one line to Colin.
  - h) Watchdog: the coordinator checks silent threads every 60 minutes (Colin, 16 Nov 08:00 UTC).
  - i) The machine-readable rules file `rules/project-rules.yaml` (project files; also project-rules.json, written 16 Nov 08:07 UTC) is the summary of the active rules. CLAUDE.md gets a docs PR pointing to the current rules.
- Colin's words (relayed by the coordinator, copied verbatim by the server):
  - 16 Nov 06:05:37 UTC: "continue working until v1.3 finished" (a).
  - 16 Nov 08:00:23 UTC: "set the time before retry to 60min." (h), and "Create a machine readable file that notes down all the claude project specific instructions we have agreed on and are currently active, such as (but not only) rules for merging, thread reusage, slow down, stop and continue commands, roles ..., how they are divided by lane, github rules ..." (i).
  - Also, 16 Nov 07:08:45 UTC, a standing request: "Notify me once the reader is working good enough for me to use it for personal uses."
- Status: a), h) and i) are Colin's: **Decided** (Colin, 16 Nov 06:05:37 and 08:00:23 UTC, in the project chat). The rest: Decided (Claude) (coordinator, 16 Nov 08:08 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). **Amends D-374** (f), **retires D-376** (c), consolidates D-626 and D-627.
- Record: `rules/project-rules.yaml`, `workflow-export.md` (project files); D-80, D-374, D-376, D-462, D-553, D-626, D-627.
- Carried out (i): PR #441, "docs: CLAUDE.md workflow follows the current project rules", two review rounds (`plans/review-pr441-round1.md`, `plans/review-pr441-round2.md`), squash-merged into main as 7a3b3ec at 08:38:32 UTC, pinned to 6fecf06 (updated with main fbc4d12, diff identical). Main is now 7a3b3ec. Add "sci2audio PR #441 (merged as 7a3b3ec)" to the record.
- Older-row notes to add: D-626 (amended by D-702 and D-705), D-376 (retired by D-702), D-374 (amended by D-702 f), D-462 and D-553 (extended to v1.3 by D-702 a), D-80.

### D-703 · Rules clarifications (answers to an outside review of the rules file)
- Subject: five questions from an outside review of `rules/project-rules.yaml`, which Colin passed on in the project chat (16 Nov 08:17:45 UTC: "please answer ... questions regarding the project-rules.yaml"). Checked against his message.
- Decision:
  - a) The lanes.yml labels are file ownership; the four lanes are execution lanes.
    - The extraction/voices lane owns extraction, voices and output. Layout owns layout. Textprep owns textprep. App/release owns app, web and cli.
    - core is cross-cutting and critical (it needs lane:infra). docs may be changed by any lane.
  - b) Linux-only CI on release branches is the automatic trigger. Critical PRs into a release branch still get a manual ci:full three-system run on the final round.
  - c) Critical KB means the process, contract and architecture docs. The daily decision-log PR is exempt (D-626).
  - d) A thread at its second compression finishes its current step and is replaced at the next hand-off, never mid-round. This applies to the KB thread too.
  - e) The round-4 hard stop with Colin's sign-off stays under the v1.3 autonomy (D-702 a).
- Status: Decided (Claude) (coordinator, 16 Nov 08:18 UTC, answering Colin's request of 08:17:45 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702; no chat line under D-626). **Refines D-702** (b, d, a) and D-627 (round limits).
- Record: `rules/project-rules.yaml` (project files); D-626, D-627, D-643, D-702.

### D-704 · Working Reader batch D plan approved; batch C audit
- Decision: the plan `plans/working-reader-batch-d-plan.md` is approved.
  - D1 Listen: #392, #393, and part of #314. D2 Library and voices: #416, #417, #419, #435. D3 Focus and shortcuts: #394.
  - All three are non-critical; D1 is reviewed on Opus high.
  - D-704 b: the Listen page draws strikes and "said as" marks only when the audiobook's recorded sci2audio version equals the running one. Otherwise it draws no marks and shows a one-line note.
  - #314 closes after Colin's VoiceOver pass at the v1.3 release.
  - Focus is a client-side mode with no address of its own.
  - #418 (captures on the library and the shelf) is proposed for v1.5; that is scope, so it waits for Colin. API at 08:43 UTC: #418 still on v1.3.
  - Batch C audit (light, D-627): clean, apart from a half-ported settled(page) line, which goes into D1, and #432 lacking a milestone (API at 08:43 UTC: still none). Findings are in the review ledger.
- Status: Decided (Claude) (coordinator, 16 Nov 08:42 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). #418's move is **Open** (Colin). Follows D-665, D-684, D-694 and D-698. Refines D-665 (#314 folds into #393: now part in D1, closed after the VoiceOver pass).
- Record: sci2audio Issue #392, Issue #393, Issue #314, Issue #416, Issue #417, Issue #419, Issue #435, Issue #394 (v1.3), Issue #418, Issue #432; `plans/working-reader-batch-d-plan.md`, `ledger/review.md` (project files); D-627, D-665, D-684, D-694.

### D-705 · One implementation thread and its review thread at a time (Colin)
- Decision:
  - From now on only one implementation thread and its one review thread are active at a time.
  - Batches already started finish: the web lane's batch D, the second textprep batch through PR 6, and the v1.1 release.
  - This supersedes the limit of three active implementation threads of D-626.
  - The rules file `rules/project-rules.yaml` is at v1.3.0 (LANE-02 rewritten; LANE-04 and CMD-04 annotated).
- Status: **Decided** (Colin, 16 Nov 08:55:32 UTC, in the project chat: "From now on only start 1 implementation and the according PR thread active at a time. All lanes finish their started batches."). **Amends D-626** (max 3 active); affects D-702 b (a release-branch thread beside the app lane), apart from the v1.1 release, which finishes.
- Record: `rules/project-rules.yaml` (project files); D-626, D-627, D-702, D-704.

### D-706 · Working Reader D1 (PR #444, Listen page) merged; the tint ruling
- Decision:
  - Tint ruling: only the sentences the voice swept in order while playing get the heard tint. Skipped sentences, and sentences a seek passed over, do not.
  - PR #444 (the Listen page shows the audiobook's own changes and a docked player; #392, #393; batch D1, D-704) had two review rounds (`plans/review-pr444-round1.md`, `plans/review-pr444-round2.md`).
    - Round 1 S1 was withdrawn after the author showed that document.json is written only by the audio job.
  - Squash-merged into main as 71ca0aa at 11:07:51 UTC (head 34fb5e7). #392 and #393 closed.
  - Leftovers: #443 (the Listen page of a long book waits for the text steps on every visit; no milestone at 11:37 UTC) and #447 (below 1280 px, a click inside the open side panel can close it; v1.3).
  - D2 (merge note, no new D-number, coordinator 12:04 UTC): PR #446 (library search and drop, voice cards with samples, download links, CLI chapter number; #416, #417, #419, #435, #432) had two rounds (`plans/review-pr446-round1.md`, `plans/review-pr446-round2.md`) with no leftovers. Squash-merged into main as 12fd90d at 12:03:20 UTC (head c98f409). The five issues closed; #432 is now on v1.3.
    - #432: the CLI progress line names the chapter just spoken. Accepted as consistent with D-695 (Decided (Claude)).
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 11:36 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Follows D-704; D2 also follows D-684 and D-695.
- Record: sci2audio PR #444 (merged as 71ca0aa), Issue #392, Issue #393 (closed), Issue #443, Issue #447 (v1.3), PR #446 (merged as 12fd90d), Issue #416, Issue #417, Issue #419, Issue #435, Issue #432 (closed); `plans/review-pr446-round1.md`, `plans/review-pr446-round2.md`, `plans/review-pr444-round1.md`, `plans/review-pr444-round2.md`, `plans/working-reader-batch-d-plan.md` (project files); D-664, D-704.

### D-707 · Textprep PR 6 plan approved (#362, #370, #374)
- Decision: the plan `plans/textprep-v12-pr6-plan.md` (the second textprep batch's PR 6: #362, #370, #374; D-646) is approved.
  - Caption labels in notices are read through the whole built-in inline chain, through a public textprep helper, read_over, which the second-run oracle shares.
  - Placeholders are rebuilt as printed (text, label, pictures) in sci2audio.testing.
  - A new conformance check: an edit inside a placeholder must replace the whole block.
- Status: Decided (Claude) (coordinator, 16 Nov 11:38 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Critical plan (textprep contract, the testing helpers). The last PR of the second textprep batch, allowed to finish under D-705. Follows D-646 and D-699.
- Record: sci2audio Issue #362, Issue #370, Issue #374; `plans/textprep-v12-pr6-plan.md` (project files); D-646, D-692, D-699, D-705.

### D-708 · #418 moves from v1.3 to v1.5 (Colin)
- Decision: #418 (captures on the library and the shelf) moves from v1.3 to v1.5 Study layer, because it needs the capture model of #396 (v1.5). v1.3 is complete without it.
  - Colin also confirmed that he does the v1.1 hand steps himself.
  - Carried out by the web lane at 12:49:46 UTC: #418 is on "v1.5 Study layer" (checked in the API at 12:51 UTC).
- Status: **Decided** (Colin, 16 Nov 12:49:11 UTC, in the project chat, answering the coordinator's 08:43 UTC proposal: "418 is fine as you propose.  I take care of the v1.1"). Settles the open point of D-704; amends D-684 for #418.
- Record: sci2audio Issue #418, Issue #396 (both v1.5 Study layer); D-666, D-669, D-684, D-704.

### D-709 · The spoken sentence gets a plain static highlight only (Colin)
- Decision: the sentence being spoken is marked with a plain static highlight only, on the Listen page and in the Focus view.
  - The running sweep animation and the underline are removed. No other animated highlight is used.
  - The heard tint of D-706 stays, visibly paler than the static highlight of the spoken sentence (Decided (Claude), coordinator, 13:04 UTC, as part of D-709; Colin's complaint was the running sweep). D-706 is not amended.
  - Issue #452; it goes into PR #451 (batch D3: Focus listening and the keyboard shortcuts sheet; #394, #447).
- Status: **Decided** (Colin, 16 Nov 13:02:59 UTC, in the project chat: "I don't like how when a sentece is highlighted there is something like a progress bar running. Lets only mark the sentence which is spoken without underlining them and without additional animated highlighted."). Changes the reading sweep of "The Working Reader" design (D-663) and the Listen sheet of #392.
- Record: sci2audio Issue #452, PR #451 (open), Issue #392, Issue #394; D-663, D-704, D-706.

### D-710 · PR #450 round 1: the whole-block conformance check is drawn by behaviour
- Decision: in PR #450 (textprep PR 6; #374, #370, #362; D-707), the whole-block conformance check is drawn by behaviour, not by step identity.
  - An edit inside a placeholder is accepted when the step, re-run on the placeholder rebuilt from the printed text, makes the same edit and nothing more.
  - It is refused when a second run changes the result.
  - There is no built-in exemption list.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov, relayed 16:21 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). **Refines D-707**.
  - Merge (merge note, no new D-number, coordinator 18:49 UTC): after three review rounds (`plans/review-pr450-round1.md` to `-round3.md`; round 3 added only the two tests S1 and S2), PR #450 was squash-merged into main as 7cd84bd at 18:46:29 UTC, pinned to b26e993. #362, #370, #374 and #410 closed. The second textprep v1.2 batch (D-646) is complete.
  - The sentence-boundary programme (D-715) started as the next implementation thread at 18:50 UTC, plan first. The light audit of textprep PRs 5 and 6 runs alongside.
- Record: sci2audio PR #450 (merged as 7cd84bd), Issue #374, Issue #370, Issue #362, Issue #410 (closed); `plans/textprep-v12-pr6-plan.md` (project files); D-707.

### D-711 · PR #451: the spoken-sentence highlight keeps 3:1 contrast
- Decision: in PR #451 (batch D3), the static spoken-sentence highlight keeps a luminance contrast of at least 3:1 against both the paper and the heard tint (WCAG 1.4.1).
- Status: Decided (Claude) (review thread / coordinator, 16 Nov, relayed 16:21 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Refines D-709.
  - Merge (merge note, no new D-number, coordinator 17:42 UTC): PR #451 (batch D3: Focus listening and the keyboard shortcuts sheet) was squash-merged into main as 1bace26 at 17:40:31 UTC, pinned to 682aad8. #394, #447 and #452 closed. Batch D and the Working Reader batches are complete. API at 17:43 UTC: milestone "v1.3 The Working Reader" has 19 closed and 1 open (#437, the WebKit-Ubuntu nightly, which stays open until five green nightlies in a row, D-698).
- Record: sci2audio PR #451 (merged as 1bace26), Issue #452, Issue #394, Issue #447 (closed), Issue #437; `plans/review-pr451-round2.md` (project files); D-698, D-706, D-709.

### D-712 · "slow down" moves only non-critical reviews to the cheaper setting (Colin)
- Decision: under "slow down", non-critical reviews run on Opus 5.5 medium (as they already do); critical reviews stay on Opus 5.5 high. The thread-count part (at most 2 implementation threads) stays, without further effect under D-705.
- Status: **Decided** (Colin, 16 Nov 16:08:30 UTC, in the project chat: "i approve your suggestions. apply all" (as quoted by the governance audit thread; check the message when writing the row), approving item S7 option (b) of the governance audit). **Amends D-702 e** ("slow down": every review on Opus medium, critical ones included).
- Record: `rules/project-rules.yaml` 1.4.0 (CMD-04, CRIT-03); `plans/governance-audit-2026-11-16.md` (S7) (project files); D-626, D-702.

### D-713 · Rules-file edits stay with the coordinator, with a one-line note to Colin (Colin)
- Decision: only the coordinator edits `rules/project-rules.yaml`, `project-rules.json` and `rules/project-state.yaml`. A rules edit records a decision that already has a D-number or a message of Colin's, bumps the version, is logged in the pending KB batch, and gets a one-line note to Colin. Other threads never edit these files and report a stale rule to the coordinator. This replaces the skill's default (owner go for every ruleset edit).
- Status: **Decided** (Colin, 16 Nov 16:08:30 UTC, "i approve your suggestions. apply all", approving item S5 of the governance audit as the coordinator proposed it).
- Record: `rules/project-rules.yaml` 1.4.0 (META-01); `plans/governance-audit-2026-11-16.md` (S5) (project files); D-702 i.

### D-714 · Governance audit fixes adopted; rules 1.4.0 and the state file (Colin)
- Subject: Colin asked at 15:43 UTC for the governance audit (Mode B) of the `project-governance-init` skill from `dubidu22/claude-project-setup-skill` against the project rules. Report: `plans/governance-audit-2026-11-16.md`.
- Decision:
  - a) Current state moves out of the rules into the new `rules/project-state.yaml` (pause, slow down, freeze, autonomy horizon, milestones, batches finishing under D-705, pending notifications). It was created with `paused: true` (the pause of 13:24 UTC).
  - b) Authority order: Colin's newer messages, then the project instructions, the KB decision log ("Decided" rows over "Decided (Claude)" rows), the pending KB batch, the rules files, CLAUDE.md, project memory. `workflow-export.md` is no longer a source.
  - c) Only the daily decision-log PR skips review; KB process, contract and architecture documents are critical and reviewed (REV-01, CRIT-01; follows D-703 c).
  - d) A critical PR gets one `ci:full` run on the head handed to review; the author then removes the label so fix commits run Linux only. The review thread adds `ci:full` again on the final round (PR-05, REV-03).
  - e) Every rule names whom it binds (`applies_to`); lanes, labels, model routing and token economy are listed in `project_profile` and `execution_profile`; duplicate and history rules are merged or removed (115 → 91 rules, 33.7 KB → 29.4 KB). New rules: META-01 (D-713), META-02 (state file); WD-01 gains two nudges then replace or escalate, and no checks during a pause; THR-01 and THR-03 replace a thread at the next hand-off, never mid-round; THR-02 names what a new thread reads (newest 20 log rows, pending batch, cited rows, its plan); MOD-03 starts a batch review thread at the effort of the batch's most critical PR.
  - f) CLAUDE.md follows the rules (sci2audio PR #453, merged into main as 1adf152 at 16:21:03 UTC, squash pinned to d0b6134, on the coordinator's go; CLAUDE.md only, +8 −8, CI green): one implementation thread at a time (D-705); release-branch PRs start Linux CI only, critical ones still get a final-round `ci:full` run (D-703 b); the KB review exception; `ci:full` timing; CI workflows and safety mechanisms in the critical list; SSPL in the licence line; a pointer to the rules files.
  - g) The coordinator updated the project instructions to match (source-of-truth order, KB wording in the critical list, replacement at the next hand-off, release-branch CI exception, control words).
- Status: **Decided** (Colin, 16 Nov 16:08:30 UTC, in the project chat: "i approve your suggestions. apply all"). Carried out 16 Nov about 16:25 UTC; `audit_rules.py` on rules 1.4.0 with the state file: exit 0, 0 errors, 1 warning (91 rules). **Amends D-702** (e, i), **refines D-626, D-698 and D-703** (b, c, d).
- Record: `rules/project-rules.yaml` 1.4.0, `rules/project-rules.json`, `rules/project-state.yaml`, `plans/governance-audit-2026-11-16.md` (project files); sci2audio PR #453 (merged as 1adf152); D-626, D-698, D-702, D-703, D-705.

Older-row notes from D-712 to D-714: D-702 (amended by D-712 for e, by D-714 for e and i), D-703 (refined by D-714), D-626 (refined by D-714), D-698 (refined by D-714 d).

### D-715 · Sentence boundaries are a priority for v1.2 (Colin)
- Decision: sentence boundaries are a priority for v1.2. The programme:
  1. A sentence-boundary test set from the corpus papers (German and English, boundaries checked by hand), with a precision and recall metric in the test suite.
  2. A layout join rule: a block that ends without closing punctuation continues into the next block.
  3. An evaluation of pySBD (MIT licence, rule-based, deterministic, offline) against our own rules on that set. It is adopted only if it wins. Step 3 is critical.
  - It starts as the next implementation work once PRs #450 and #451 are merged (D-705).
  - Related issues (all v1.2, P2): #454 (layout: a flush-right motto is cut into two paragraphs after a comma), #455 (textprep: German citations with a reprint year, slash-joined authors or a Roman page), #460 (textprep: a sentence over the length limit is cut inside a phrase).
- Status: **Decided** (Colin, 16 Nov 16:35:55 UTC, in the project chat: "I agree. This is a priority issue. start once the current threads are done.", answering the coordinator's proposal). Follows D-705; adds to the v1.2 scope of D-453 to D-460 as amended by D-666.
- Record: sci2audio Issue #454, Issue #455, Issue #460 (v1.2), PR #450, PR #451; D-57, D-414, D-705.

### D-716 · The light-mode reading mark is deep amber #B08400
- Decision: in light mode, the sentence being read is marked with deep amber #B08400 and ink text, not the Reading Yellow named in DESIGN.md, because no light yellow reaches 3:1 on white (D-711).
  - Measured: 3.42:1 against the paper, 3.18:1 against the heard tint, text 5.20:1.
  - Dark mode keeps #F2DC3A.
  - DESIGN.md (Reading Yellow = "the sentence being read") and its "Reading sweep" section get this note through the KB (`plans/review-pr451-round2.md`).
- Status: Decided (Claude) (review thread / coordinator, 16 Nov, relayed 17:42 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Consequence of D-711; deviates from the design (D-663) for contrast; follows D-709.
- Record: sci2audio PR #451 (merged as 1bace26); `plans/decisions-d712-d714.md`, `plans/review-pr451-round2.md` (project files); sci2audio-design `DESIGN.md`; D-663, D-709, D-711.
- Older-row note: D-663 (deviation for the light-mode reading mark, D-716).

### D-717 · The CLI and the web card name different chapters in the last progress line, by design
- Decision: once chapter_done is set, the last-progress line names the chapter just spoken in the CLI and the next chapter in the web job card. Both are intended and are not to be unified.
  - Both read D-695's AudioProgress from its last event (batch D audit, F2). The CLI line (#432, PR #446) names the chapter whose sentences it counts; the web card (batch C, PR #433) names where the job stands. The D2 plan asked the CLI to step like the card; review round 1 of #446 accepted the deviation. A later thread must not change one to match the other.
  - Also: v1.3 (the Working Reader) is code complete at 1bace26. The light batch D audit is clean on contracts (`plans/batch-d-audit.md`).
  - The audit filed two issues on v1.3: #461 (Listen: after P closes the panel, Space reopens it instead of playing; P2) and #462 (Working Reader housekeeping F3 to F5: Changes counts, leftover Settings keys, search cap; P3).
  - The full text is in `plans/decisions-d712-d714.md` (checked 17:48 UTC).
- Status: Decided (Claude) (coordinator, 16 Nov 17:45 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Refines D-695 and the #432 note of D-706.
- Record: sci2audio PR #446 (merged as 12fd90d), PR #433 (merged as fbc4d12), PR #451 (merged as 1bace26), Issue #432, Issue #461, Issue #462 (v1.3); `plans/batch-d-audit.md`, `plans/decisions-d712-d714.md` (project files); D-627, D-695, D-706.

### D-718 · Every implementation plan names earlier PRs built on a model it changes
- Decision: every implementation plan from now on carries one line: "Earlier PRs in this batch that built on a model this PR changes: …" (or "none").
  - Reason: the light audit of textprep PRs 5 and 6 (`plans/audit-textprep-batch-2026-11-16b.md`) found that PR 6 changed the placeholder and notice model without revisiting what PR 5 had just built on the old model. No contract touches.
  - Filed (v1.2): #463 (hidden runs and page-break markers inside a table, figure, formula or code block) and #464 (a figure's alt text in its notice is read raw). They go into the sentence-boundary batch's plan as small textprep follow-ups if they fit, otherwise into the next textprep batch.
  - The lane thread length stays as it is (0 compressions; not a context problem).
- Status: Decided (Claude) (coordinator, 16 Nov 18:52 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Fourth light batch audit under D-627 (after D-645, D-655, D-691).
- Record: sci2audio Issue #463, Issue #464 (v1.2), PR #436 (merged as 6a2aeb3), PR #450 (merged as 7cd84bd); `plans/audit-textprep-batch-2026-11-16b.md`, `plans/decisions-d712-d714.md` (project files); D-627, D-691, D-699, D-710, D-715.

### D-719 · Sentence-boundary plan approved (D-715 programme)
- Decision: `plans/sentence-boundary-plan.md` is approved as written: five PRs in order, all critical, Opus high, full process. Rulings on the open questions:
  - Q1: the sentence-boundary thread authors PR 2 (the layout lane by files, label lane:layout; one thread at a time under D-705).
  - Q2: **amends D-60** for sentence truth files. The review thread checks every disagreement between the truth file and the cutter, and 100 random boundaries per language, with the seed in the review report. Colin is not asked; he may spot-check the German file at any time.
  - Q3: yes, as a follow-up issue filed after PR 1, not blocking.
  - Q4: yes, one app/web issue for #460's pause and highlight after the batch.
  - Q5: yes, #463 and #464 are PR 5 of this batch.
  - Q6: accepted. If the PR 1 baseline is far below the targets, revised targets are posted and approved before PR 3 starts.
- Status: Decided (Claude) (coordinator, 16 Nov 18:58 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Critical plan. Carries out D-715; **amends D-60**.
  - Merge (merge note, no new D-number, coordinator 19:55 UTC): PR 1, #467 (a hand-checked sentence test set and a sentence-boundary metric with a known-errors gate), had two rounds (`plans/review-pr467-round1.md`, `plans/review-pr467-round2.md`) and was squash-merged into main as 1c45cab at 19:55:03 UTC, pinned to c136719.
    - Baseline: English precision 0.9967, recall 0.9900; German precision 0.9874, recall 0.9916. The known-errors gate holds 25 entries.
    - Filed (v1.2): #465 (sentence-rule errors found by the set, for PR 3), #466 (layout: plain-text title lines and "- " list items are joined into one sentence), #468 (a second German corpus paper for the set).
  - Merge (merge note, no new D-number, coordinator 21:08 UTC): PR 2, #476 (the layout join rule; #454), had three rounds (`plans/review-pr476-round1.md` to `-round3.md`) and was squash-merged into main as 2e2ae77 at 21:07:31 UTC, pinned to 1789d4f. #454 closed.
    - The rule as merged: flush-right and centred lines are not split by the indent rules; a short last line that ends mid-sentence joins a following lower-case line; real first-line indents, hanging outdents, "i."/"a." lists and a change from italic to upright stay breaks.
    - Corpus: Nowak's two-line link is one block; Liu's affiliation is one block, with the date separate.
    - 25 of 32 mutants caught; 7 argued equivalent.
    - Colin is still to confirm the Kehren motto.
  - Merge (merge note, no new D-number, coordinator 22:26 UTC): PR 3, #478 (sentence rules fixed from the test set, in linear time; #465), had two rounds (`plans/review-pr478-round1.md`, `plans/review-pr478-round2.md`) and was squash-merged into main as 7d866bf at 22:25:15 UTC, pinned to 4d57b9f. #465, #406, #141 and #268 closed.
    - Step 3 of D-715: pySBD and syntok were evaluated and **not adopted**; our own rules make fewer errors in both languages (`plans/sentence-boundary-eval.md`).
    - The known-errors gate shrank from 25 to 11 entries.
    - The German label guard's dot condition was dropped ("Kap. 2. Kap. 3" had been read as an ordinal). #479 is filed for "Abs. 2. Abs. 3" (milestone "v1.2.x abbreviations").
    - Review lesson: a symbol rule must also match the symbol glued to its variable.
  - Merge (merge note, no new D-number, coordinator 17 Nov 01:00 UTC): PR 4, #481 (long sentences cut at the best clause boundary; reprint years, slash authors and Roman pages are citations; #460, #455), had three rounds (`plans/review-pr481-round1.md` to `-round3.md`) and was squash-merged into main as cfeb084 on 17 Nov at 00:58:44 UTC, pinned to 7393b60. #455 and #460 closed (#460's textprep part).
    - #455: German citation shapes (reprint year, slash-joined authors, Roman page, "WBGU 2011, S. 1").
    - #460: a long sentence is cut at a colon or semicolon, then at a comma before and/which/dass, in even shares, never inside brackets or quotes.
    - Follow-ups: #480 (app/web: a pause and one whole-sentence highlight at a cut; v1.2; Q4 of D-719), #482 and #483 (v1.2.x abbreviations).
    - The known-errors gate went from 11 to 9 entries.
    - Review lessons: a cut rule ranks positions inside brackets or quotes last, and an inline "a) … b)" list must not cancel a later "("; a YEAR/YEAR citation rule must not eat one-year ranges.
    - CI note: one-off Windows failures on the flate-bomb test and the web keep-alive test passed on re-run; the reviewer is watching main.
- Record: sci2audio PR #467 (merged as 1c45cab), PR #476 (merged as 2e2ae77), PR #478 (merged as 7d866bf), PR #481 (merged as cfeb084), Issue #455, Issue #460 (closed), Issue #480, Issue #482, Issue #483, Issue #406, Issue #141, Issue #268 (closed), Issue #479, Issue #454, Issue #465 (closed), Issue #466, Issue #468, Issue #463, Issue #464 (v1.2); `plans/review-pr467-round1.md`, `plans/review-pr467-round2.md`, `plans/sentence-boundary-plan.md`, `plans/decisions-d712-d714.md` (project files); D-60, D-705, D-715, D-718.

### D-720 · Focus type and a much subtler reading mark, the same on Listen and Focus (Colin's feedback)
- Decision (issue #471):
  - Focus mode type is only slightly larger than the normal Listen text.
  - The mark on the spoken sentence is much subtler, in Focus and on the normal Listen page alike, and the two always stay identical. The 3:1 contrast rule still applies, so it is the lightest mark that passes in light and dark mode.
  - No mark at all on already-read text: the heard tint (.s.done) is removed.
  - lane:web, v1.3, non-critical. One PR with #461 and #462, queued behind the sentence-boundary batch (D-705).
- Status: Decided (Claude) (coordinator, 16 Nov 19:24 UTC), carrying out Colin's feedback: 19:21:48 UTC (with a screenshot) and 19:24:02 UTC (the normal Listen mark gets the same subtler look, and both stay identical), as quoted in `plans/decisions-d712-d714.md`; ask for his message ids before writing the row. **Amends D-716** (both views), **amends D-706 and D-709** (the heard tint is removed), keeps D-711.
- Record: sci2audio Issue #471, Issue #461, Issue #462 (v1.3); `plans/decisions-d712-d714.md` (project files); D-706, D-709, D-711, D-716.

### D-721 · Publishing is parked until the v1.4 installers (Colin)
- Decision: v1.1.0 is parked.
  - Draft PR #426 stays a draft with a parked note. No tag, no PyPI, no R3 forward-merge. Colin's listening results are no longer needed.
  - Fixes continue on main. The next publish is one release after the v1.4 installer work, cut fresh from main.
  - release/1.1 becomes stale: every fix on it must be on main or have an issue (D-701).
  - Milestone 2 (v1.1) stays open until then.
- Status: **Decided** (Colin, 16 Nov 19:28:06 UTC, in the project chat: "can we skip publishing until the installer issues are resolved?"; agreed by the coordinator at 19:29 UTC). **Amends D-667** (release v1.1 now) and D-669 (release plan); supersedes D-708's note on the v1.1 hand steps.
- Record: sci2audio PR #426 (draft, open), PR #403 (merged into release/1.1 as 08d5965), PR #412 (merged into release/1.1 as e9d08ef); `plans/release-v11-plan.md`, `plans/decisions-d712-d714.md` (project files); D-667, D-669, D-688, D-696, D-701.

### D-722 · One general marker with an optional note goes into v1.3 (Colin)
- Decision: a general marker on the current sentence, with an optional note, goes into v1.3 (lane:web, plan first in `plans/general-marker-plan.md`, built after the sentence-boundary batch under D-705).
  - The rest of the Study layer (#395 to #399, #418) stays in v1.5, after the v1.4 installer work is done and v1.4 is published (D-721).
- Status: **Decided** (Colin, 16 Nov 19:30:33 UTC, in the project chat: "add a general marker with optional notes for v1.3 the rest is for v1.5 after the installer work ist done and sci2aduio v1.4 published."). Adds to v1.3 (D-666); keeps D-708; follows D-721.
- Record: sci2audio Issues #395 to #399, Issue #418 (v1.5 Study layer); `plans/decisions-d712-d714.md` (project files); D-666, D-705, D-708, D-715, D-721.

### D-723 · General-marker plan approved; the v1.3 web batch
- Decision: `plans/general-marker-plan.md` (D-722) is approved, with three rulings:
  1. Removing a marker is undone from the toast only. There is no 30-day list of struck-through markers, so the data model stays one file with no tombstones; the scope is minimal for v1.3.
  2. M toggles the marker on the spoken sentence.
  3. The web lane batch for v1.3:
     - PR A: the follow-ups #461, #462, #471 and #472 (non-critical).
     - PR B: the marker, #474 (critical; Opus high review; fault-injection tests; markers survive web and CLI reruns; the remove box counts markers).
     - The same web thread authors both. It starts when the sentence-boundary batch is done (D-705). Code name "markers".
  - v1.5 Study-layer follow-up: #475 (core: carry the v1.3 markers into the capture model).
  - #473 (v1.2) holds the release/1.1 ports to main (D-701, D-721).
- Status: Decided (Claude) (coordinator, 16 Nov 19:37 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-702 a; no chat line under D-626). Critical plan (PR B). Carries out D-722.
- Record: sci2audio Issue #474, Issue #461, Issue #462, Issue #471, Issue #472 (v1.3), Issue #475 (v1.5), Issue #473 (v1.2); `plans/general-marker-plan.md`, `plans/decisions-d712-d714.md` (project files); D-701, D-705, D-720, D-721, D-722.

### D-724 · The reading mark: a pale fill below 3:1 plus a left-margin bar (Colin)
- Decision (option b):
  - The mark on the spoken sentence gets a much paler fill, which may sit below the 3:1 contrast rule of D-711.
  - A thin bar in the left margin is the second, non-colour cue. The bar itself passes 3:1 against the page.
  - It is not an underline (D-709 holds). The same in Focus and on the normal Listen page (D-720).
  - Issue #471, in PR A of the v1.3 web batch (D-723).
- Status: **Decided** (Colin, 16 Nov 20:35:39 UTC, in the project chat: "option b sounds good", choosing option b of the coordinator's proposal). **Amends D-711** for the reading mark only; refines D-720 and D-716.
- Record: sci2audio Issue #471 (v1.3); `plans/decisions-d712-d714.md` (project files); D-709, D-711, D-716, D-720, D-723.

- Status notes, no D-number yet (coordinator, 16 Nov 19:24 to 19:30 UTC):
  - Colin's per-project files requirement (19:18 UTC): #469 (keep every file of a library project in one per-project folder; v1.2, lane:app) and #470 (removing a project from the Library deletes all its files, after a warning; v1.2, risk:high). They supersede D-353 (the audiobook is kept on removal) once Colin answers the three questions asked at 19:21 UTC. The #469 migration gets the critical process because it moves user data.
  - #472 (drop the "Not in this audiobook" line from the Listen page's chapter panel; v1.3, lane:web).

## Merge records to add when they land
- Status note, no D-number yet (coordinator, 16 Nov 09:17 UTC): #442 filed (v1.2, lane:extraction, P1, bug): PDF fonts without any Unicode mapping (CID TrueType, Identity-H, no ToUnicode map) are read as glyph codes and voiced as nonsense. Proposed fix: detect and stop with a notice, which makes #187 (warn when a PDF's text looks garbled, v1.2) concrete. Recovering text from the glyph table is new scope and waits for Colin. Record it when a D-number is given.
- v1.1.0 release: parked by D-721 (no tag, PyPI or R3). Nothing to add.
- Working Reader batch B: done (D-693: #420 ca3458a, #421 f063454). When writing the rows, add a note on D-681: carried out by D-693.
- Milestone 2 (v1.1) stays open (D-721).

- Older-row note: D-646, the batch is complete: PR 5 merged as 6a2aeb3 (D-699), PR 6 as 7cd84bd (D-710).

## Paused
- 16 Nov 13:24 UTC: Colin's "pause all threads." (13:24:08 UTC). The KB thread starts nothing new until the coordinator sends "continue". D-691 to D-709 are collected here for the 17 Nov KB PR, which is not opened yet. Next KB branch from sci2audio-design main 57eb6ae or later.

- Lifted 16 Nov 16:21:35 UTC (Colin: "continue").

Next free D-number: D-725.
