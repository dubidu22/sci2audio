# KB batch D-742 to D-769: MERGED

MERGED as KB PR #55 (squash 74640aa, 18 Nov 23:07:42 UTC = 19 Nov 00:07 Berlin). Status notes added to D-353, D-358, D-359, D-361, D-725 and D-738. New entries go to kb-batch-2026-11-20-pending.md.

Collected by the KB thread. D-725 to D-741 were merged as KB PR #54 (7e5b1ce, 18 Nov 13:09 UTC). The next KB PR is the one for 19 Nov (one per day, D-626), branched from sci2audio-design main 7e5b1ce or later, merged by the KB thread without review.

## Decisions

### D-742 · Web batch audit follow-ups
- Decision: Audit `plans/audit-web-batch-2026-11-18.md`: 0 blocking, 2 should-fix, 4 notes; no undeclared contract touch; the 2-compression replacement rule stays, and a big critical PR gets its own thread. S1 (marker API and Listen-page marker data use the longest piece of a joined sentence, not the first) and S2 (shortcut hint omits M) become issues and one small non-critical PR by the web thread after PR 3; N3 (where `joins` may appear in docs/readalong-format.md) becomes a lane:docs issue for a later critical docs PR. KB main is 7e5b1ce (KB PR #54, D-725 to D-741).
- Status: Decided (Claude) (coordinator, 18 Nov 13:14 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). Keeps D-703 d.
- Record: sci2audio Issue #520, Issue #521, Issue #522; `plans/audit-web-batch-2026-11-18.md`, `plans/decisions-d712-d714.md` (project files); D-703, D-741.

### D-743 · Textprep batch 3 plan approved with four additions
- Decision: Plan `plans/textprep-batch-3-plan.md` (#494, #488, #477, #487) approved: whole batch critical, three PRs (PR 1 #494; PR 2 #488 + #477; PR 3 #487), one review thread on Opus high, PR 3 written during PR 1's review, PR 2 after PR 1 merges. Additions: A1 the P1.7 phoneme measurement runs BEFORE the constant changes and is a gate: if any corpus utterance of 300 to 400 characters passes the voice's token limit, or a number-dense 400-character sentence loses audio in either voice, stop and report (a slow test with such a sentence in English and German proves no text is lost; "the voice splits it itself" is not accepted unproven). A2 P1.8 also covers saved user data: a marker (markers.json) and a saved position (position.json) inside a sentence whose cut moves or disappears still land on that sentence after a rebuild, shown by a test or by naming the existing re-anchoring test that covers it. A3 P1.5: tests may pin max_chars=300, but one estimator test stays on the default; the docstring edit in app/estimate.py is allowed in PR 1 and named in the PR. A4 PR 2: the new data/en/sentence_openers.toml is covered by the packaged-data check (wheel contains it), and the "in the U.S. Researchers found" loss is recorded as a regression row or known-errors entry with its cause, whichever the gate result calls for.
- Status: Decided (Claude) (coordinator, 18 Nov 13:24 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Status at 17:00 UTC: PR #528 (textprep PR 3, #487) approved in round 2 at d5f9c01 with 0 new findings (`plans/review-pr528-round2.md`); it holds the merge slot next (D-758). PR 1 is merged (see D-753).
- Merge note (18 Nov 17:52 UTC): PR #528 (textprep PR 3, critical) was squash-merged into main as c3b79c2 at 17:52:07 UTC, pinned to 7df7187 (2 rounds). #487 closed.
- Merge note (18 Nov 19:09 UTC): PR #547 (textprep PR 2, critical; #488 and #477) had two rounds (round 1: 1 blocking, the sentence-opener list held the surnames He, An, So and To, so initials were cut; `plans/review-pr547-round1.md`, `plans/review-pr547-round2.md`) and was squash-merged into main as f126875 at 19:08:57 UTC, pinned to 1f101fb. #488 and #477 closed. Textprep batch 3 (#524, #528, #547) is done.
- Record: sci2audio Issue #494, Issue #488, Issue #477, Issue #487, PR #524, PR #528; `plans/textprep-batch-3-plan.md`, `plans/decisions-d712-d714.md` (project files); D-741, D-744, D-753.

### D-744 · #477 ruling: English sentence openers only behind the gate; the rest are limits
- Decision: Rows 1 and 2 ("the U.S. \| Census Bureau", "called A. \| Then") are fixed by an English sentence-opener rule (twin of the German ordinal rule, D-530) only if the sentence gate shows zero new errors, the natural-set floors hold, every regression row stays and no corpus snapshot moves except listed fixes; a part that fails the gate is dropped and its row closes as a limit. Row 3 (lower-case sentence starts such as "seaborn.", "iOS") and row 4 (German "Es waren 3. \| Studien", D-530) close as deliberate limits; so does the WBGU note (N2). Their known-errors entries point at D-744.
- Status: Decided (Claude) (coordinator, 18 Nov 13:24 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Record: sci2audio Issue #477 (closed by PR #547, merged as f126875); `plans/textprep-batch-3-plan.md`, `plans/decisions-d712-d714.md` (project files); D-530, D-743.

### D-745 · Layout and app lanes start beside textprep and web
- Decision: Colin (13:37 UTC) asked why more lanes are not running. The two waiting lanes were held on soft blocks only, so both start: layout (#456 to #459; the shared corpus snapshot is regenerated after merging main, never hand-resolved, behind textprep PR 1) and app (#469, #470, both critical; plan first on the recommended defaults as marked assumptions: audiobook deleted by default with a keep box, cache outside Documents, v1.2; #469 first; the delete behaviour of #470 is not coded before Colin answers question 1). Web review thread started 13:33Z for #519 (approved round 1, merges after the isolation runs) and PR 4 (#520 #521).
- Status: Decided (Claude) (coordinator, 18 Nov 13:39 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). Follows Colin's question in the project chat at 13:37 UTC; applies D-741.
- Record: sci2audio Issues #456 to #459, Issue #469, Issue #470, PR #519, Issue #520, Issue #521; `rules/project-rules.yaml` 1.4.4, `plans/decisions-d712-d714.md` (project files); D-741, D-754, D-755.

### D-746 · Windows keep-alive flake quarantined; #519 approval withdrawn; #516 review started
- Decision: tests/unit/test_web_jobs.py::test_events_keep_the_stream_alive_and_end_when_the_server_stops failed twice on Windows without a code cause (main 1e461a7 run 44063376376; #516 head 294cbb3 run 44313882649, docs-only PR). TST-07: the governance thread files the issue; the web lane quarantines it today on Windows only (in PR 4 #523 if not yet in review, else a tiny PR) and runs the 40-run isolation afterwards with the result in the issue (TST-08). #519 round 1 approval withdrawn: the author's 40-run job reported green while its loop ignored failures (WebKit "waits for the script" tests failed 11 of 40); round 2 after one fix and a repeat job that fails on any failed iteration. Lesson appended to `memory/MEMORY-archive-2026-11-18.md`. #516 (CLAUDE.md, critical) in review at f6d1294 with Linux CI and ci:full green, thread "Review the CLAUDE.md governance update" (Opus high).
- Status: Decided (Claude) (coordinator, 18 Nov 13:45 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). Applies D-374, D-682 and D-739.
- Merge note (18 Nov 13:45 UTC): PR #516 (CLAUDE.md governance update, D-738) was squash-merged into main as 2979dce at 13:45:32 UTC, pinned to f6d1294 (1 round, 0 findings). Follow-up Issue #526 (lane:docs, risk:high: priority-bug thread and per-browser isolation wording). The Windows flake is Issue #525. The governance audit thread and its review thread were resolved.
- Merge note (18 Nov 16:29 UTC): PR #519 (web PR 3) was approved in round 2 at cbd3e9c with 0 findings (`plans/review-pr519-round2.md`); the strict isolation runs were 40/40 on 16 items for Firefox, WebKit Ubuntu and Chromium (no WebKit macOS runner). It was squash-merged into main as 2cb10c5 at 16:29:17 UTC, pinned to 0f8506a (2 rounds). #506, #509, #518 and #542 closed; #517 and #541 stay open. The web batch (PR 3 and PR 4) is done.
- Record: sci2audio Issue #525, PR #523, PR #519, PR #516 (merged as 2979dce), Issue #526; Actions runs 44063376376 and 44313882649; `memory/MEMORY-archive-2026-11-18.md`, `plans/decisions-d712-d714.md` (project files); D-374, D-682, D-738, D-739.

### D-747 · The data root moves to the user data folder
- Decision: Per-project work files (source copy, analysis, speech cache, records, position.json, markers.json) live in <user data>/sci2audio/projects/<id>/ (platformdirs user_data_path; was the OS cache folder). Inner layout unchanged (AudioChunk.file keeps its meaning, L2); id names kept (L3); speech cache stays inside (Q2), with a follow-up issue for backup exclusion (L5). The Documents folder holds the audiobook only (Q1). Plan `plans/per-project-folders-plan.md` §1.
- Status: Decided (Claude) (coordinator, 18 Nov 13:50 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). Confirmed by Colin's answers (D-754).
- Record: sci2audio Issue #469, PR #532; `plans/per-project-folders-plan.md`, `plans/decisions-d712-d714.md` (project files); D-748, D-752, D-754.

### D-748 · Migration algorithm
- Decision: M1 to M12 of the plan: migration lock, candidates by id only, links and junctions never followed, busy folders skipped and retried, atomic rename fast path, copy-verify-commit path on EXDEV, merge into from-earlier-version/ when the target exists, never overwrite, idempotent and resumable (crash-point property test MT2), legacy folders listed until moved, Documents never touched, old flat audiobooks never moved. PR 1 may merge on assumption A2 before Colin answers question 2 (Q7): the engine is root-agnostic and a later root change moves projects again without data risk.
- Status: Decided (Claude) (coordinator, 18 Nov 13:50 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Record: sci2audio Issue #469, PR #532; `plans/per-project-folders-plan.md`, `plans/decisions-d712-d714.md` (project files); D-747, D-752, D-754.

### D-749 · The project audiobook folder
- Decision: <output folder>/<project name>/, name cleaned by output.names.clean and capped at 60 characters / 80 bytes; claimed with mkdir(exist_ok=False), " (2)" suffixes, recorded in project.json before the job; a folder sci2audio did not create is never taken over (A1 to A3). Supersedes the flat output folder for new audiobooks; old ones stay where they are (M12).
- Status: Decided (Claude) (coordinator, 18 Nov 13:50 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Record: sci2audio Issue #469; `plans/per-project-folders-plan.md`, `plans/decisions-d712-d714.md` (project files); D-748, D-750, D-752, D-754.

### D-750 · The project.json manifest
- Decision: Format sci2audio-web-project version 1 (A4, A5): folders and files written with size and SHA-256; decisions by size + SHA-256 only, never mtime; read strictly, a bad file means no manifest and no audiobook deletion; old-reader and old-file tests (D-730 lesson).
- Status: Decided (Claude) (coordinator, 18 Nov 13:50 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Record: sci2audio Issue #469, Issue #470; `plans/per-project-folders-plan.md`, `plans/decisions-d712-d714.md` (project files); D-730, D-749, D-751, D-752.

### D-751 · Removal with warning: ruling on the mechanics
- Decision: R1 to R6 as planned: keep_audiobook is a required API parameter; order busy-check, plan, audiobook files, data folder; folder and file checks (links, outside, changed, shared, unreadable); only listed files, rmdir only, system clutter exception (Q5); audiobooks made before #469 are never deleted, only named as staying (Q4, narrows #470's seeding idea). Supersedes D-353 and amends D-358, D-359, D-361. The default state of the keep box (A1) and the start of PR 3 wait for Colin's answer to question 1.
- Status: Decided (Claude) (coordinator, 18 Nov 13:50 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). **Supersedes D-353**; **amends D-358, D-359 and D-361**. Colin answered question 1 at 13:52 UTC (D-754).
- Record: sci2audio Issue #470, Issue #469; `plans/per-project-folders-plan.md`, `plans/decisions-d712-d714.md` (project files); D-353, D-358, D-359, D-361, D-752, D-754.

### D-752 · Per-project folders plan approved
- Decision: Plan `plans/per-project-folders-plan.md` approved with Q1 to Q7 as recommended, three critical PRs (PR 1 migration, PR 2 folder + manifest, PR 3 removal), one review thread on Opus high, mutation probing, nightly seeds and the three-system run on each final round. Cross-lane files accepted (Q6); PR 3 starts after web PR 4 (#520 #521) merges. Additions: the backup-exclusion follow-up issue is filed with PR 1; MT2 covers M8 crash points too; PR 1 keeps --work-folder behaviour unchanged with a test; each PR body names its mutants for the S tests.
- Status: Decided (Claude) (coordinator, 18 Nov 13:50 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Status at 16:33 UTC: PR #532 (app PR 1, #469 part a) approved in round 2 (29 mutants; the gap is Issue #544; `plans/review-pr532-round2.md`), head 4877887; its merge waits for the merge slot after #524 and #528 (D-758).
- Merge note (18 Nov 18:53 UTC): PR #532 (app PR 1, migration, critical) was squash-merged into main as 1cf1f65 at 18:52:37 UTC, pinned to 69a1f86 (2 rounds); follow-up Issue #544. App PR 2 is PR #552 (in review at 19:17 UTC).
- Status at 19:29 UTC: PR #552 (app PR 2) round 1: changes required, 4 findings, none data loss (`plans/review-pr552-round1.md`). App PR 3 (#470) follows PR 2.
- Merge note (18 Nov 21:27 UTC): PR #552 (app PR 2: each project's audiobook in a folder of its own, with a record of its files) was squash-merged into main as 8622f85 at 21:26:49 UTC, pinned to 5c9bec0. #469 closed. App PR 3 (#470) is next.
- Record: sci2audio Issue #469 (closed), Issue #470, PR #532 (merged as 1cf1f65), PR #552 (merged as 8622f85), Issue #544, PR #523; `plans/per-project-folders-plan.md`, `plans/decisions-d712-d714.md` (project files); D-747 to D-751, D-754.

### D-753 · #524 may change one browser fixture
- Decision: PR #524 (#494) replaces the LONG constant in tests/browser/test_joined.py with an own 456-character sentence, because at 400 the old 412-character one is cut 305+106 and the marker lands on the first piece. The change stays in the textprep PR (the limit change is what breaks the fixture), is listed as a test-harness change with the before/after cut, and nothing else in tests/browser changes; the web lane was told. A1 gate passed (47 corpus utterances of 300 to 400 characters, none over 510 tokens; number-dense sentences heard whole, slow tests). A2: marker test added; position.json is dropped by design on a rebuild (#153).
- Status: Decided (Claude) (coordinator, 18 Nov 13:53 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Merge note (18 Nov 16:53 UTC): PR #524 (textprep PR 1, critical) was squash-merged into main as 712ec4c at 16:49:41 UTC, pinned to 5d5a6ce (2 rounds). #494 closed. A WebKit marker test failed once and passed on its re-run; it was not quarantined (a second failure anywhere goes to TST-07).
- Record: sci2audio PR #524, Issue #494, Issue #153; `plans/textprep-batch-3-plan.md`, `plans/decisions-d712-d714.md` (project files); D-743.

### D-754 · Per-project folder answers (Colin)
- Decision: Colin approved the recommendations to the three questions of 16 Nov: (1) on project removal the audiobook is deleted by default, with a "Keep the audiobook files" tick box; (2) Documents/sci2audio/<project>/ holds the audiobook, everything else lives outside Documents in the app data folder; (3) milestone v1.2. Assumptions A1 to A3 of `plans/per-project-folders-plan.md` become decisions; PR 3 (#470) is unblocked after PR 2 and web PR 4.
- Status: **Decided** (Colin, 18 Nov 13:52:58 UTC, in the project chat: "i approve  your recom"). Recorded by the coordinator at 13:53 UTC. Confirms D-747 to D-752.
- Record: sci2audio Issue #469, Issue #470; `plans/per-project-folders-plan.md`, `plans/decisions-d712-d714.md` (project files); D-353, D-747 to D-752.

### D-755 · Layout batch plan; front matter becomes publisher sections
- Decision: Plan `plans/layout-batch-german-pdf-plan.md` approved. PR A (running heads, #457 footnote numbers, #459 heading "I": a heading needed two letters) and PR B (#458 crop box) are non-critical and run without a wait; if a golden or the corpus snapshot moves, the PR becomes critical and stops. PR C (#456) takes option 1: C1 outline-named front matter becomes a level-1 section starting at its page's first block (cover sheet found through the outline only), C2 `Section.publisher: bool = False` in core (critical, lane:core + lane:infra; Section is in no versioned file, named in the PR), C3 app/chapters.py marks the chapter as the publisher's (deselected by default like EPUB publisher pages, #190) and names the blocks after it with the document title. One critical PR after PR A merges, plan steps pinned, the corpus-truth test exception named. The app lane's #469/#470 batch does not touch chapters.py; PR C merges main first if both land close together. Review: one thread for the batch, Opus medium for A and B, Opus high for C.
- Status: Decided (Claude) (coordinator, 18 Nov 13:56 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Merge note (18 Nov 15:01 UTC): PR #530 (layout PR A) was squash-merged into main as 158f1ae at 15:01:16 UTC, pinned to 2fcebdf (2 rounds: 2 must-fix and 4 test gaps in round 1, 0 in round 2). #457 and #459 closed.
- Merge note (18 Nov 15:32 UTC): PR #538 (layout PR B) was squash-merged into main as 94a4353 at 15:31:57 UTC, pinned to d52f0a6 (1 round, 0 blocking). #458 closed; follow-up Issue #543. PR C is PR #539 (critical), open at fdc27a0 with ci:full running.
- Merge note (18 Nov 19:20 UTC): PR #539 (layout PR C, critical) was squash-merged into main as 73e26df at 19:20:25 UTC, pinned to c2b06c8 (3 rounds; round 3 at 17fa700 with 0 findings, `plans/review-pr539-round3.md`). #456 closed. The layout batch (#530, #538, #539) is done; #456 to #459 are closed; follow-ups are #529, #535, #537 and #543.
- Record: sci2audio Issues #456 to #459, Issue #190, PR #530 (merged as 158f1ae), PR #538 (merged as 94a4353), PR #539 (merged as 73e26df), Issue #543, Issue #537, Issue #529, Issue #535; `plans/layout-batch-german-pdf-plan.md`, `plans/decisions-d712-d714.md` (project files); D-745.

### D-756 · #523 merges ahead of #524
- Decision: #523 (web PR 4, #520 #521) approved round 1 with 0 findings; it does not wait for #524 (textprep, round 2 with a blocking finding). The web review merges #523 pinned to a573b9d after merging main; the textprep thread merges main into #524 before its round-2 push so the test_joined.py changes of both PRs are tested together. Round-1 results: #524 changes requested (1 blocking: an older bracket-cut test stopped checking anything in English at 400; 3 should-fix; 1 nit; #533 filed for 7 cutter mutants that also survive on main); #530 changes requested (2 must-fix: the L4 note stack swallows a tight small footer or page number below the footnotes, a regression against main; 4 test gaps; 1 nit).
- Status: Decided (Claude) (coordinator, 18 Nov 14:34 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Merge note (18 Nov 14:43 UTC): PR #523 (web PR 4) was squash-merged into main as f2aea0e at 14:43:17 UTC, pinned to c6fc1ad after main was merged into the branch (1 round, 0 findings). #520 and #521 closed. #532 round 1: 11 findings, 2 blocking (a startup hang in the merge loop; the job lock released during copy/merge).
- Status at 15:32 UTC: #524 approved in round 2 (1b27a7f, main merged 6bfe161); its merge waits for the branch nightly re-run (WebKit test_two_quick_presses, unrelated, D-731). #528 round 1: 3 findings, 0 blocking (#540 filed). New issues #537, #541 and #542 (#542 is fixed by #519).
- Record: sci2audio PR #523 (merged as f2aea0e), Issue #520, Issue #521, PR #524, PR #530, PR #532, PR #528, Issue #533, Issue #540, Issue #541, Issue #542; `plans/decisions-d712-d714.md` (project files); D-731, D-753.


### D-757 · A CI speed lane starts (Colin)
- Decision: Colin asked to make CI faster ("this is not sustainable"). A CI speed lane started on Opus high. Plan `plans/ci-speed-plan.md` first; CI is critical, the coordinator approves before any PR; the lane touches .github/ only until the plan is approved.
- Status: **Decided** (Colin, 18 Nov 16:05:24 UTC, in the project chat: "think about how to make the ci faster. this is not sustainable."). Lane started by the coordinator at 16:05 UTC under D-741.
- Record: `plans/ci-speed-plan.md`, `plans/decisions-d712-d714.md` (project files); D-741, D-758, D-759.

### D-758 · One PR at a time holds the merge slot to main
- Decision: MERGE SLOT. While several lanes merge, one PR at a time holds the merge slot to main (ruleset requires up-to-date branches; #524 lost two CI rounds to races). Slot order: #524, #528, then free; other review threads hold merges until told.
- Status: Decided (Claude) (coordinator, 18 Nov 16:33 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). Refines D-741.
- Later: retired at 19:25 UTC when D-760 was applied (rules 1.4.5, MRG-04).
- Record: sci2audio PR #524 (merged as 712ec4c), PR #528, PR #532; `plans/decisions-d712-d714.md` (project files); D-741, D-753, D-759.

### D-759 · CI speed plan approved (Colin approved it too)
- Decision: CI speed plan `plans/ci-speed-plan.md` APPROVED, items 1-5 in order + item 6 merge queue vs up-to-date rule (report only). Item 4 terms: Firefox/WebKit in PR check only for web paths, nightly stays safety net, green browser checks end the nightly-rerun wait. Item 2 keeps a full-40 flag for TST-08. One critical PR per item, review thread Opus high. Amendment (16:36 UTC): O4 Firefox/WebKit in PR CI for web paths is reported-only until #437 closes, then required. Coordinator updates TST-08 and nightly-before-merge rule text when the workflows land.
- Status: Decided (Claude) (coordinator, 18 Nov 16:35 UTC, amended 16:36 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740); **approved by Colin** (18 Nov 16:55:27 UTC, in the project chat: "i approve this plan. lets do it").
- Merge notes (CI speed lane, all critical CI): PR #546 (isolation runs as a workflow, `isolate.yml`) merged as bb8e1e3 at 19:26:15 UTC, pinned to fade972 (2 rounds); PR #545 (nightly speed) merged as 2cad344 at 19:33:21 UTC, pinned to d760bc2 (2 rounds); PR #551 (scoped mutation, item 5) merged as 312e5c7 at 19:46:38 UTC, pinned to d11425c (2 rounds; #549 closed); PR #553 (PR browser tests in two shards; "CI passed" fails on any cancelled leg) merged as 025b67a at 19:49:27 UTC (1 round; #548 closed); PR #554 (Firefox and WebKit on Linux, reported only, for PRs that change a web path) merged as 1797ceb at 20:18:09 UTC (1 round).
- Outcome (18 Nov 20:18 UTC): the CI speed lane is done. PR CI went from about 9 to about 5 minutes and the property job from 29 to 11.6 minutes. Rules 1.4.6: TST-08 names `isolate.yml`, and the ci_browser_nightly reference is rewritten. The PR browser checks are "browser (Linux, Chromium, 1/2)" and "2/2"; "CI passed" keeps its name.
- Record: sci2audio PR #546 (merged as bb8e1e3), PR #545 (merged as 2cad344), PR #551 (merged as 312e5c7), PR #553 (merged as 025b67a), PR #554 (merged as 1797ceb), Issue #548, Issue #549, Issue #437; `rules/project-rules.yaml` 1.4.6, `plans/ci-speed-plan.md`, `plans/decisions-d712-d714.md` (project files); D-682, D-731, D-739, D-757, D-758.


### D-760 · The main ruleset no longer requires up-to-date branches (applied by Colin)
- Decision: Drop 'Require branches to be up to date before merging' in ruleset main (id 26932142; strict_required_status_checks_policy true→false; 'CI passed' stays required); same for release-branches ruleset 27255463 optional. GitHub merge queue not available (personal account). New rule once applied (MRG-xx): a red main is fixed or reverted by the lane that merged last before anything else merges; D-758 slot stays until then. Fallback O6a: catch-up head needs Linux CI only, three-system run stays on the reviewed head.
- Status: Proposed by the coordinator (18 Nov 19:08 UTC) as Colin's own hand step; **applied by Colin** (18 Nov 19:25:08 UTC, in the project chat: "it#s now turned off."). The main ruleset (26932142) now has strict_required_status_checks_policy false with "CI passed" still required (checked in the API). Rules 1.4.5: MRG-03 reworded, new MRG-04 (a red main is fixed or reverted by the last merger before further merges; the slot is used only while main is red or on shared files). **Retires D-758** (the merge slot).
- Record: sci2audio PR #551, PR #552, PR #539; `rules/project-rules.yaml` 1.4.5, `plans/ci-speed-plan.md`, `plans/decisions-d712-d714.md` (project files); D-758, D-759.


### D-761 · The next batches B1 to B8 are approved; four lanes start
- Decision: `plans/next-batches-2026-11-18.md` APPROVED. Start now: B1 extraction (#442 A, #537+#543, #485), B2 textprep (#445 #449, #448), B3 layout (#529+#535, #466), B4 docs (#522+#526). Conditions C1 (B1 PR 1 Content change additive, else B3 PR 2 waits) and C2 (corpus snapshot: merge main + regenerate) apply. Acceptance criteria AC-442.1-4, AC-445, AC-448, AC-449, AC-485, AC-293 approved as written; the planning thread writes them into the issues. #442 part 3 (glyph-ID recovery) is Colin's roadmap call. B5 after B2; B6 after B5 and B3 PR 2; B7/B8 after app PR 3 (#470). #541: planning thread dispatches isolate.yml mode=full on main and records counts. Triage of the 32 other v1.2 issues and milestones for #526 #527 go to Colin.
- Status: Decided (Claude) (coordinator, 18 Nov 20:30 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). The four lanes B1 to B4 started at 20:30 UTC (rules 1.4.6).
- Merge note (18 Nov 20:49 UTC): PR #555 (docs B4, critical: where read-along joins may appear; the priority-bug and per-browser details in CLAUDE.md) was squash-merged into main as f919d81 at 20:49:26 UTC, pinned to 8d9d81b (1 round, 0 findings). #522 and #526 closed; B4 is done. Out of scope and filed as Issue #560: CLAUDE.md item 2 lists only four lanes.
- Status at 21:10 UTC: the #541 isolation run on main (`isolate.yml`, mode full) was 40/40 on WebKit Linux and 40/40 on WebKit macOS; no quarantine. #557 (a German time before a day and month reads differently on a second run; older than this batch) was filed for textprep B5.
- Record: sci2audio Issue #442, Issue #537, Issue #543, Issue #485, Issue #445, Issue #449, Issue #448, Issue #529, Issue #535, Issue #466, Issue #522, Issue #526, PR #555 (merged as f919d81), Issue #560, Issue #293, Issue #470, Issue #541, Issue #557, Issue #527; `plans/next-batches-2026-11-18.md`, `plans/decisions-d712-d714.md` (project files); D-741, D-759.

### D-762 · B1 extraction plan approved, with rulings on Q1 and Q2
- Decision: B1 plan `plans/extraction-batch-b1-plan.md` APPROVED. Q1: AC-442.1 narrowed, simple fonts with unknown glyph names not counted in Page.unmapped (TeX math + matplotlib Type 3 fonts in 4 corpus papers; text check covers them). Q2: legibility module in extraction. B7 policy pinned: stop before voices when unreadable pages hold >50% of characters, else #187 report warning. #485 has a code cause (isolate._wait poll outside try, Windows BrokenPipeError) → PR 3 critical.
- Status: Decided (Claude) (coordinator, 18 Nov 20:40 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Merge note (18 Nov 21:09 UTC): PR #556 (#485: a closed reader pipe on Windows no longer escapes as an error; the D-725 quarantine is lifted) was squash-merged into main as d2ffcac at 21:09:26 UTC, pinned to 6ca1f02. #485 closed. The B1 review thread (#556, #559, #562) started at 20:57 UTC; the B3 review thread (#558, #561) at 21:04 UTC.
- Merge note (18 Nov 21:18 UTC): PR #559 (turned pages and inherited media boxes read as shown; #537, #543) was squash-merged into main as 56d937f at 21:17:56 UTC, pinned to 41a1a44. #537 and #543 closed.
- Merge note (18 Nov 21:46 UTC): PR #562 (#442 part A, critical: fonts with no Unicode source are counted and each page's text measured) was squash-merged into main as 215405c at 21:46:23 UTC, pinned to b88c7e2. #442 stays open for part B (B7). A post-merge defect followed (#574, D-767).
- Record: sci2audio Issue #442, Issue #485 (closed), PR #556 (merged as d2ffcac), PR #559 (merged as 56d937f), Issue #537, Issue #543, PR #562 (merged as 215405c), Issue #574, Issue #187; `plans/extraction-batch-b1-plan.md`, `plans/decisions-d712-d714.md` (project files); D-725, D-761.

### D-763 · B3 layout plan approved; its PR 1 is critical
- Decision: B3 plan `plans/layout-batch-b3-plan.md` APPROVED. PR 1 #529+#535 is CRITICAL (PrivacyScore printed page labels move 431 printed_page fields in test_app_corpus.ambr, one layout golden line, corpus page-label truth test, one unit test). PR 2 #466: rule in extraction/text.py, numbered items need a run of two (lone "1." stays paragraph, German dates safe), TITLE_SHARE 0.6, four known-errors rows leave, en/de floors rise.
- Status: Decided (Claude) (coordinator, 18 Nov 20:42 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Merge note (18 Nov 21:32 UTC): PR #558 (B3 PR 1, critical; #529, #535) was squash-merged into main as c51e846 at 21:32:26 UTC, pinned to 8f147ce. #529 and #535 closed.
- Merge note (18 Nov 21:59 UTC): PR #561 (B3 PR 2; #466: plain-text title lines and list items are blocks of their own) was squash-merged into main as 0bbb991 at 21:58:40 UTC, pinned to ad82259. #466 closed; follow-ups Issue #570 and Issue #571.
- Record: sci2audio Issue #529, Issue #535, Issue #466, PR #558 (merged as c51e846), PR #561 (merged as 0bbb991), Issue #570, Issue #571; `plans/layout-batch-b3-plan.md`, `plans/decisions-d712-d714.md` (project files); D-761.

### D-764 · B2 textprep plan approved, with three rulings
- Decision: B2 plan `plans/textprep-batch-b2-plan.md` APPROVED. PR 1 #445+#449, PR 2 #448. AC-445.2 read as fuzz445 (a)=0 and (b)=0 apart from one residual ("<" glued to a removed link across a hidden run), accepted and filed; no runner change. #449 raised mass number before "K" → superscript digits, plain "40K" stays "thousand". #448 cue: marks removed only after an author line; three regression rows and 11 parametrised cases gain an author line. C2: no corpus snapshot change.
- Status: Decided (Claude) (coordinator, 18 Nov 20:48 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Record: sci2audio Issue #445, Issue #449, Issue #448; `plans/textprep-batch-b2-plan.md`, `plans/decisions-d712-d714.md` (project files); D-761.

### D-765 · Rules 1.4.7: web and docs join the execution lanes
- Decision: rules 1.4.7: execution_lanes gains web and docs (six lanes, matching practice and LANE-02 use); lane_mapping_note rewritten. #560 (CLAUDE.md item 2 lane list) precondition met; #560 itself goes to the next docs batch.
- Status: Decided (Claude) (coordinator, 18 Nov 20:53 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). Applies D-741 (LANE-02).
- Record: sci2audio Issue #560; `rules/project-rules.yaml` 1.4.7, `plans/decisions-d712-d714.md` (project files); D-741, D-761.


### D-766 · The Windows flate-bomb failure 0xE0000008 has its own code cause
- Decision: The flate-bomb Windows failure 0xE0000008 is a code cause (PDFium PartitionAlloc OOM exception reaching ctypes before the memory watch), not the #485 pipe bug; B1 fixes it in a small critical PR (child maps the winerror to MEMORY_EXIT). Until merged, this test failing alone on Windows is pre-existing (D-731) and does not block other PRs or trigger an MRG-04 revert of #556.
- Status: Decided (Claude) (coordinator, 18 Nov 21:27 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626). Applies D-731 and MRG-04 (D-760).
- Merge note (18 Nov 22:15 UTC): PR #568 (read PDFium's Windows out-of-memory error as the memory limit, critical) was squash-merged into main as d44cf5d at 22:15:14 UTC, pinned to 5c05c14, after the AC-485.2 proof on Windows. Issue #573 records that `isolate.yml` cannot run a unit test alone on Windows.
- Record: sci2audio Issue #485, PR #556 (merged as d2ffcac), PR #568 (merged as d44cf5d), Issue #573; `plans/decisions-d712-d714.md` (project files); D-725, D-731, D-760, D-762.


### D-767 · The #574 post-merge defect is fixed at once in a small critical PR
- Decision: #574 (post-merge defect from #562: Page.__post_init__ rejects unmapped > characters, textprep _read_in_place builds a subset page with replace() and keeps unmapped, so table-figure-notices fails on glyph-number pages) is fixed at once in a small critical PR in the extraction lane (lane:infra). Criteria as the B1 audit recommends: core checks only unmapped >= 0; extraction's tests keep the "unmapped <= characters" bound; a regression test covers _read_in_place on a page with unmapped > 0 and a captioned block; corpus unchanged. Reviewer: the B1 review thread (Opus high, critical rules). Review lesson added: for a new core invariant, grep every replace(<dataclass> in src/ for consumers.
- Status: Decided (Claude) (coordinator, 18 Nov 22:20 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Merge note (18 Nov 22:48 UTC): PR #575 (a page with glyph-number text keeps its notices) was squash-merged into main as 675d1c6 at 22:47:51 UTC, pinned to c826c99. #574 closed.
- Record: sci2audio Issue #574 (closed), PR #575 (merged as 675d1c6), PR #562; `plans/decisions-d712-d714.md` (project files); D-762, D-768, D-769.

### D-768 · Every user-visible lane PR adds a CHANGELOG line
- Decision: CHANGELOG. From now on every lane PR with a user-visible change adds an Unreleased line (reviewers check it). Missing lines for #556/#568, #559, #558, #561 go into the #574 fix PR; the line for #552 and #470 goes into #569.
- Status: Decided (Claude) (coordinator, 18 Nov 22:20 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Record: sci2audio PR #556, PR #568, PR #559, PR #558, PR #561, PR #575, PR #552, PR #569, Issue #470; `plans/decisions-d712-d714.md` (project files); D-767, D-769.

### D-769 · The #574 plan is approved as written
- Decision: #574 plan `plans/issue574-unmapped-bound-plan.md` APPROVED as written (core refuses only unmapped < 0; _read_in_place unchanged; strict regression tests for captioned table, figure, formula; extraction bound test incl. turned page; five D-768 CHANGELOG lines; no snapshot or golden updates).
- Status: Decided (Claude) (coordinator, 18 Nov 22:23 UTC, under D-80 as extended by D-462 and D-553, D-626 and D-740; no chat line under D-626).
- Record: sci2audio Issue #574, PR #575 (merged as 675d1c6); `plans/issue574-unmapped-bound-plan.md`, `plans/decisions-d712-d714.md` (project files); D-767, D-768.

## Open points carried over (no D-number yet)
- #442 (v1.2, P1, lane:extraction): PDF fonts without a Unicode mapping; glyph-table recovery is new scope for Colin (part 3 stays his roadmap call under D-761).
- Colin still to confirm the Kehren motto (PR #476, D-719).
- Filed on 18 Nov (for the record): Issues #517, #518, #520, #521, #522, #525, #526, #527, #529, #531, #533, #537, #540, #541, #542, #543. Also #534, #536, #544, #549, #550, #557, #560, #563 to #567, #570, #571, #573, #574 and #576. At 23:05 UTC app PR 3 (#569, #470) is open, B3 is merged (#558, #561), and B1 and B2 are in progress. The web, textprep batch 3, layout and CI speed batches are done. Rules file at 1.4.7 (D-765).
- Older-row notes for the 19 Nov PR: D-353 superseded by D-751 (confirmed by D-754); D-358, D-359, D-361 amended by D-751; D-738 merge sha 2979dce (PR #516); D-725 quarantine lifted by PR #556 (d2ffcac, D-762); the remaining Windows failure has its own cause (D-766).
- Eight coordinator notes (15:35 to 21:27 UTC) are in; D-767 to D-769 and the merges of #558, #561, #562, #568 and #575 were taken from `plans/decisions-d712-d714.md` and the API at 23:05 UTC. The PR opens at 23:05 UTC (00:05 Berlin, 19 Nov); a later merge gets a note only if it lands before then.

Next free D-number: D-770.
