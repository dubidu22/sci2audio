# KB batch D-656 to D-690: MERGED

MERGED as KB PR #52 (squash 57eb6ae, 16 Nov 03:29:10 UTC). Status notes added to D-646, D-462, D-454, D-288, D-458, D-459 and D-374. New entries go to kb-batch-2026-11-17-pending.md.

Collected by the KB thread. D-628 to D-655 were merged as KB PR #50 (3b0c57a). Branch the next KB PR from sci2audio-design main 3b0c57a, or later. It is one per day, merged by the KB thread without review (D-626).

## Decisions

### D-656 · PR #377 round 2: approvable

- Subject: PR #377 (alphanumeric citation keys and a reference list without a heading; #254, #92; D-646 PR 1), review round 2.
- Decision: round 2 at head 739a6ac found the PR approvable. Notes are in `plans/review-pr377-round2.md` (project files).
  - B1, S1, S2 and N1 from D-649 are fixed.
  - 13 of 16 mutants are caught. The three test pins that survive go to #383 ("textprep: pin three guards of the key and unheaded-list rules with tests", v1.2), which fits PR 3.
  - The nightly seeds are clean, and ci:full is green on all three systems.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 19:25 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-646 and D-649.
- Record: sci2audio PR #377, Issue #383 (v1.2); `plans/review-pr377-round1.md`, `plans/review-pr377-round1-answer.md`, `plans/review-pr377-round2.md` (project files); D-646, D-649.

### D-657 · PR #377 merged

- Subject: PR #377 merged.
- Decision: the coordinator gave the merge go pinned to 739a6ac. The PR was squash-merged as 8a8f863 at 19:25:48 UTC, which closed #254 and #92 (19:25:49).
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 19:25 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-656.
- Record: sci2audio PR #377 (merged as 8a8f863), Issue #254, Issue #92 (closed); D-646, D-656.

### D-658 · Five textprep issues move to Later

- Subject: #97, #114, #131, #100 and #287 move to the Later milestone.
- Decision: as D-646 planned, the five issues are moved to Later. The API at 19:26 UTC shows all five on Later.
  - Note: the textprep lane is told not to start PR 3 of the second textprep batch until Colin opens work beyond v1.1 again. This follows Colin's "resume normally until v1.1" (19:01:05 UTC).
- Status: Decided (Claude) (coordinator, 15 Nov 19:25 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Carries out D-646.
- Record: sci2audio Issue #97, Issue #114, Issue #131, Issue #100, Issue #287; D-646.

### D-659 · PR #382 (second textprep batch PR 2) review round 1

- Subject: PR #382, "textprep: German readings, units after per and legal-form abbreviations" (#230, #231, #233, #250, #265, #358, #264; D-646 PR 2, D-650), review round 1.
- Decision: round 1 at head 7189d6a. Notes are in `plans/review-pr382-round1.md` (project files). Verdict: not approvable. The fix list goes to the textprep lane.
  - B1: ordinals and dates after "i. S. d." read the same on both runs.
  - S1: "i. S. d." is only treated as legal before §, §§, Art. or Abs.
  - S2: there is no sentence end after "a. F." or "n. F." before a capital, §, a label, or "Satz" with a number.
  - N1: the scope of "Hs.".
  - Accepted: "lit." is read as "Buchstabe".
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 19:28 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-646 and D-650.
- Record: sci2audio PR #382 (open), Issue #230, Issue #231, Issue #233, Issue #250, Issue #265, Issue #358, Issue #264; `plans/review-pr382-round1.md` (project files); D-646, D-650.

### D-660 · PR #382 round 2: approvable

- Subject: PR #382 (German readings, units after per and legal-form abbreviations; D-646 PR 2), review round 2.
- Decision: round 2 at head 51abd44 found the PR approvable. Notes are in `plans/review-pr382-round2.md` (project files).
  - B1, S1, S2 and N1 from D-659 are fixed, and "§§" is covered.
  - A side effect is accepted: "gem. 3. Abschnitt" now reads "gemäß 3. Abschnitt". This matches the printed text, and no corpus text has the shape.
  - 13 of 19 mutants are caught. The 3 survivors that change a reading go to #384 ("textprep: pin three guards of the German legal-form readings with tests", v1.2). The other 2 change no reading.
  - The nightly seeds are clean, and ci:full is green on all three systems.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 19:56 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-659.
- Record: sci2audio PR #382, Issue #384 (v1.2); `plans/review-pr382-round1.md`, `plans/review-pr382-round2.md` (project files); D-646, D-659.

### D-661 · PR #382 merge go

- Subject: PR #382 merge.
- Decision: the merge go is pinned to 51abd44. The merge closes #230, #231, #233, #250, #265, #358 and #264. It was squash-merged as a9e0e2d at 19:56:17 UTC. Main is now a9e0e2d.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 19:56 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-660.
- Record: sci2audio PR #382 (merged as a9e0e2d), Issue #230, Issue #231, Issue #233, Issue #250, Issue #265, Issue #358, Issue #264; D-646, D-650, D-660.

### D-662 · The v1.1 milestone is complete

- Subject: v1.1 (German reading and the player wins) is complete.
- Decision: the v1.1 milestone is complete at 19:56 UTC, with 46 of 46 issues closed (API: 0 open, 46 closed). The release decision is Colin's. Work beyond v1.1 is paused until Colin opens it again ("resume normally until v1.1", 19:01:05 UTC).
- Status: Decided (Claude) (coordinator, 15 Nov 19:56 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat post id given). Ends the D-462 extension ("until v1.1 is finished"); D-553 (v1.2 work in free lanes) is paused with it.
- Record: sci2audio milestone v1.1; PR #382 (merged as a9e0e2d); D-454, D-462, D-553, D-626.

### D-663 · Adopt "The Working Reader" as the app's design (Colin)

- Subject: the design proposal "The Working Reader", which Colin merged into sci2audio-design main as b4a7523 (PR #51, "design: The Working Reader, a design for the whole desktop app", merged 21:51:56 UTC).
- Decision: "The Working Reader" is the binding design for the whole sci2audio interface. The full text is the D-663 draft in `plans/working-reader-plan.md` §1 (project files). In short:
  - `DESIGN.md` and `.impeccable/design.json` are binding for every interface PR.
  - `PRODUCT.md` replaces the hosted-service `PRODUCT.md`.
  - `IMPLEMENTATION-PROMPT.md` is the input for the issues.
  - The hosted-service design files are superseded and kept as a record.
  - Existing rules win where the prototype differs: D-45 (server-rendered, no hash router), D-57, D-414, 127.0.0.1 only, and everything bundled.
  - The prototype's synthetic data and simulated audio do not enter the product.
  - Not decided here: the study layer, which needs its own ADR, and the wordmark, which is a proposal.
- Status: **Decided** (Colin, 15 Nov 21:53:49 UTC, in the project chat; checked against his message, relayed by the coordinator: "I've merged dubidu22/sci2audio-design#51 · design: The Working Reader … into `main`. It went in as a single commit, `b4a7523`" and "log adopting the design as a decision in the knowledge base"). The same message says "You are now free to continue working on v1.1 until it's finished".
- Record: sci2audio-design PR #51 (merged as b4a7523); `plans/working-reader-plan.md` (project files); D-45, D-57, D-414.

### D-664 · The player bar shows on Listen and Focus only, at first

- Subject: the docked player bar.
- Decision: at first, the docked player bar shows only on the Listen page and in Focus listening. Other pages show a "Continue listening" item at the top of the rail's "Reading and recent" shelf, with the title, the remembered position and the listened meter. It opens the Listen page at that position, and nothing plays by itself (#153).
  - Reasons:
    - Server-rendered pages (D-45) stop the audio on every navigation.
    - Keeping audio alive across pages needs a client router or a persistent frame, which is a larger change to the contract.
    - The remembered position (PR #373) makes returning cheap.
    - The installers (#215) change the shell anyway.
  - Revisit: a Later issue "Keep playing while moving between pages" (WR-16), decided after the installers.
- Status: Decided (Claude) (coordinator, 15 Nov, under D-80 as extended by D-462 and D-553, and D-626; Colin asked the coordinator to decide, 21:53:49 UTC). Follows D-663.
- Record: `plans/working-reader-plan.md` (project files); sci2audio Issue #153, Issue #215; D-45, D-663.

### D-665 · The Working Reader plan approved; issues filed

- Full text: the D-665 entry appended to `plans/working-reader-plan.md` (project files); use it as the row text. Key facts, checked in the API at 22:03 UTC:
  - 17 issues were filed:
    - batch A (PR 1, critical): #385 to #388;
    - batch B: #389 and #390;
    - batch C: #391, which folds in #365;
    - batch D: #392 to #394, with #393 closing #314;
    - study layer: #395 to #399;
    - Later: #400 (D-664's revisit) and #401 (finished chapters on failure).
  - Issue changes:
    - #351 is closed as not planned, superseded.
    - #155 is on Later.
    - #14 closes when #386 lands.
  - Threads: one web-lane thread (Opus high) runs batches A to D in order, with a fitness check before each batch. One review thread covers the series, on Opus high for A and medium for B to D.
  - Choices adopted:
    - Pause is today's cancel, Resume reruns from the speech cache, and Cancel frees the cache after a confirm.
    - A failure notice says what is really kept.
    - The Changes panel is read-only.
    - Strikes and "said as" come from the job's recorded settings.
    - Study-layer exports are files first.
- Status: Decided (Claude) (coordinator, 15 Nov 21:58 UTC, under D-80 as extended by D-462 and D-553, and D-626). Follows D-663 and D-664.
- Record: sci2audio Issues #385 to #401, #351 (closed), #155 (Later), #365, #314, #14; `plans/working-reader-plan.md` (project files); D-663, D-664.

### D-666 · New milestone "v1.3 The Working Reader" (Colin)

- Subject: where the redesign goes on the roadmap.
- Decision: a new milestone "v1.3 The Working Reader" for batches A to D. The old v1.3 "ready for others" (installers, update check, plugin interface) becomes v1.4. The study layer gets v1.5 once its ADR is decided.
- Status: **Decided** (Colin, decision card answered 15 Nov 21:59:44 UTC: option 1, "New v1.3 Working Reader"). **Amends D-458 and D-459** (and the D-453 to D-460 roadmap order: v1.3 was "ready for others").
- Detail from the plan's D-666 entry:
  - batches A to D (#385 to #394) go to v1.3 The Working Reader;
  - v1.4 keeps the old v1.3 issues;
  - v1.5 Study layer holds #395 to #399;
  - #400 and #401 go to Later.
  This amends D-458 (installers in v1.3) and D-459 (public plugin interface in v1.3), which move to v1.4.
- Carried out on 15 Nov, after Colin wrote his go in the planning thread. Checked in the API at 22:05 UTC:
  - milestone 5 is renamed v1.4 (19 open);
  - milestone 8 is "v1.3 The Working Reader", with #385 to #394 (10 open);
  - milestone 9 is "v1.5 Study layer", with #395 to #399 (5 open);
  - #400 and #401 are on Later.
- Record: GitHub milestones of sci2audio; Issues #385 to #401, #215, #216, #217; `plans/working-reader-plan.md` §2 (8) (project files); D-453 to D-460, D-665.

### D-667 · v1.1 is released now, and v1.2 textprep work resumes (Colin)

- Subject: the v1.1 release and the work after v1.1.
- Decision: v1.1 is released now, and v1.2 textprep work resumes in parallel with the Working Reader. This lifts the pause of D-662 for the textprep lane.
- Colin's words, in the project chat at 22:00:23 UTC: "both yes." The coordinator read these as answers to its two questions (release v1.1 now; resume v1.2 textprep in parallel). Check that post's wording when writing the row.
- Status: **Decided** (Colin, 15 Nov 22:00:23 UTC). Follows D-662.
- Record: sci2audio milestone v1.1; D-570, D-662, D-646. Add the release run, tag and PyPI version when they land.

### D-668 · Second textprep batch PR 3 plan approved

- Subject: the plan for PR 3 of the second textprep batch (#257, #258, #372, #375, #383, #384; D-646).
- Decision: the plan `plans/textprep-v12-pr3-plan.md` (project files) is approved.
  - #257:
    - "references 1 and 3" is read as a pair.
    - A join word goes away with a removed link.
    - "[12, p. 3]" reads "reference 12, page 3" where needed.
  - #258: a pause instead of "..".
  - #372: subject nests are read flat.
  - #375: a year shell with several inner citations goes away whole.
  - #383 and #384: their guards are pinned with tests.
  - Unchanged: "or" pairs, and page brackets with several sources.
- Status: Decided (Claude) (coordinator, 15 Nov 22:03 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-646, D-656, D-660 and D-667.
- Record: sci2audio Issue #257, Issue #258, Issue #372, Issue #375, Issue #383, Issue #384; `plans/textprep-v12-pr3-plan.md`, `plans/textprep-v12-second-batch-plan.md` (project files); D-646, D-667.

### D-669 · v1.1.0 release plan approved

- Subject: how v1.1.0 is released (D-667).
- Decision: the plan `plans/release-v11-plan.md` (project files) is approved.
  - Branch release/1.1 from main a9e0e2d.
  - R1 sets the version and updates CHANGELOG and README. It also fixes #365, instead of batch C (#391), which **amends D-665**.
  - The nightly, ZAP and mutation runs go on the branch.
  - Colin's hand steps: a listening test, a VoiceOver pass, a speed run on the M4, Dependabot, the tag, and PyPI.
  - R2 is the release-day PR, and R3 forward-merges into main. Main then moves to 1.2.0.dev0.
  - The merge freeze on main is lifted.
- Status: Decided (Claude) (coordinator, 15 Nov 22:05 UTC, under D-80 as extended by D-462 and D-553, and D-626; critical, as a release; add the chat post time if one is given). Follows D-667. Same pattern as the v1.0.0 release (#80, D-484 to D-490, D-570).
- Record: sci2audio Issue #365; `plans/release-v11-plan.md` (project files); D-484, D-570, D-665, D-667.

### D-670 · Working Reader batch A plan approved

- Subject: the plan for Working Reader batch A (#385 to #388; D-665).
- Decision: the plan `plans/working-reader-batch-a-plan.md` (project files) is approved, as one PR on the branch web/working-reader-a from main.
  - Fonts: Atkinson Hyperlegible 1.006 and Literata 3.103 are bundled with their OFL texts and SHA-256 sums. The latin-ext and Greek subsets load by unicode-range.
  - The icon sprite is inline.
  - A workflow runs on the ui:screens label (the screenshot workflow, #386).
  - There is no "Keyboard shortcuts" item at the foot of the rail until #394.
- Status: Decided (Claude) (coordinator, 15 Nov 22:09 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-663 and D-665.
- Record: sci2audio Issue #385, Issue #386, Issue #387, Issue #388; `plans/working-reader-batch-a-plan.md` (project files); D-663, D-665.

### D-671 · Appearance and announce choices are cookies

- Subject: where the interface keeps its appearance and announce choices.
- Decision: they are cookies, `sci2audio-theme` and `sci2audio-announce`, under the same rules as the language cookie (D-288, D-321). The settings file and the API do not change.
- Status: Decided (Claude) (coordinator, 15 Nov 22:09 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-288, D-321 and D-670.
- Record: sci2audio Issue #388; `plans/working-reader-batch-a-plan.md` §5 and §8 (project files); D-288, D-321.

### D-672 · The document scrolls and the rail is sticky

- Subject: how the pages scroll in the Working Reader shell.
- Decision: the document scrolls and the rail is sticky. This deviates from the prototype's inner scroll but keeps its look; the reasons are in §4 of the plan. Below 760 px the rail becomes a band at the top, which the design does not cover, to keep the D-257 reflow.
- Status: Decided (Claude) (coordinator, 15 Nov 22:09 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-257 and D-663.
- Record: sci2audio Issue #387; `plans/working-reader-batch-a-plan.md` §4 and §8 (project files); D-257, D-663.

### D-673 · The language switch moves to the Settings page

- Subject: where the language switch is.
- Decision: the language switch moves from the header to the Settings page (#388), which every page's rail links to.
- Status: Decided (Claude) (coordinator, 15 Nov 22:09 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). **Amends D-288** (the switch was in the header). Follows D-663.
- Record: sci2audio Issue #388; `plans/working-reader-batch-a-plan.md` §8 (project files); D-288, D-663.

### D-674 · v1.1 release R1 (PR #403) review round 1

- Subject: PR #403, release: version 1.1.0, changelog, README and the pasted-text test fix (#365; D-669 R1), review round 1.
- Decision: round 1 at head 6fb9b6e. Notes are in `plans/review-pr403-round1.md` (project files). Verdict: not approvable yet.
  - B1: `file_id` goes stale on Windows when a file of the same size is rewritten within one clock tick. This is code from #378, and the fix is a guard for such racy files.
  - C1 to C3: CHANGELOG wording.
  - The #365 fix is confirmed as a real wait, not a timeout.
  - Filed on v1.2:
    - #406, textprep: German "Az." before a file number ends the sentence;
    - #407, web: the read-along cache serves an old file of the same size and time, because its key has no `st_ino`.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 22:31 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-648, D-653 and D-669.
- Record: sci2audio PR #403 (open), Issue #365, Issue #406, Issue #407 (v1.2), PR #378; `plans/review-pr403-round1.md`, `plans/release-v11-plan.md` (project files); D-648, D-669.

### D-675 · v1.1 release R1 (PR #403) approved after round 2

- Subject: PR #403 (D-669 R1), review round 2 and the merge go.
- Decision: round 2 at head 016b990 found the PR approvable. Notes are in `plans/review-pr403-round2.md` (project files).
  - Three mutants on the racy-file guard are caught.
  - Three Windows dispatch runs are green.
  - The merge go is pinned to 016b990, into release/1.1. It was squash-merged into release/1.1 as 08d5965 at 22:44:18 UTC. #365 was closed by hand at 22:44:28 UTC, because a merge into release/1.1 does not close it. The fix reaches main with R3.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 22:44 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-674.
- Record: sci2audio PR #403 (merged into release/1.1 as 08d5965), Issue #365 (closed); `plans/review-pr403-round1.md`, `plans/review-pr403-round2.md` (project files); D-669, D-674.

### D-676 · Textprep PR 3 (#408): #258 without a pause; a rule for mutation claims

- Subject: PR #408, the second textprep batch's PR 3 (D-668), and how mutation claims are stated.
- Decision:
  - PR #408, "textprep: citation pairs and pages, link join words and full stops, subject nests and year shells" (head cf58992), closes #257, #258, #372, #375, #383 and #384.
  - #258 is implemented without a pause, unlike D-668. The second-run check renders pauses, so a pause would fail it. The text is one utterance on both runs. This is accepted for review.
  - #405 is filed on v1.2: three citation and abbreviation shapes that a fuzz run found read differently on a second run. They are differences that already exist on main.
  - Lesson: the author's mutation claims for #377 and #382 ("30/30", "13/13") were void, because the test path did not exist. The reviewer's own mutant runs (D-656, D-660) stand.
  - Rule: a mutation claim names its command and test path, and first shows a clean run.
- Status: Decided (Claude) (coordinator, 15 Nov 22:46 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). **Refines D-668** (#258). Follows D-656 and D-660.
- Record: sci2audio PR #408 (open), Issue #257, Issue #258, Issue #372, Issue #375, Issue #383, Issue #384, Issue #405 (v1.2); `plans/textprep-v12-pr3-plan.md` (project files); D-656, D-660, D-668.

### D-677 · Working Reader batch A (PR #409) review round 1

- Subject: PR #409, "web: The Working Reader foundation, cobalt rail and Settings" (#385 to #388; D-670), review round 1.
- Decision: round 1 at head 8982fcc. Notes are in `plans/review-pr409-round1.md` (project files). Verdict: not approvable yet. The fix list goes to the web lane.
  - B1: the no-internet check must report every "//" in HTML, CSS and SVG.
  - B2: the shelf must not open its own event stream. There is one EventSource per URL, and polling everywhere else. With three job tabs open, the browser's six connections ran out.
  - S1: the wheel's licence expression is "GPL-3.0-or-later AND OFL-1.1", the OFL files go in license-files, and the licences rule is amended to match.
  - S2: the token test covers redeclarations.
  - N1: a test for the wrong-Origin case.
  - N2: the `run:` steps are each one line.
  - The fonts are verified byte-identical to Fontsource 5.3.0.
  - Review lesson: a rail widget on every page must not hold one connection per tab, because of the browser's connection limit.
- Status: Decided (Claude) (review thread / coordinator, 15 Nov 23:09 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-670. Amends the licences rule (S1); name the rule's D-number when writing the row.
- Record: sci2audio PR #409 (open), Issue #385, Issue #386, Issue #387, Issue #388; `plans/review-pr409-round1.md`, `plans/working-reader-batch-a-plan.md` (project files); D-663, D-670.

### D-678 · v1.1 release checklist runs: fixes and two accepted points

- Subject: the release/1.1 checklist runs (ZAP, nightly, mutation; D-669).
- Decision: the results are in `plans/release-v11-checklist-runs.md` (project files).
  - ZAP passed.
  - The nightly and mutation failures are fixed on the branch release-fix/1.1.0-nightly (5131ba1):
    - the EPUB cover test passes `--chapters all`, because of #190;
    - the Firefox position test lets the first server's requests through;
    - the Firefox speed test reads its options through `page.evaluate`;
    - mutmut's `also_copy` includes `.github/`.
  - A: on WebKit and macOS, the speed test checks focus only, because the select menu there is native. The other engines keep the value check.
  - B: a table inside the reference list gets a notice on a second run. This has been so since v1.0.0, and the first run is correct. It goes to #410 (v1.2). It is accepted for 1.1.0 and named in the known issues.
- Status: Decided (Claude) (coordinator, 15 Nov 23:21 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-669 and D-675.
- Record: sci2audio Issue #190; `plans/release-v11-checklist-runs.md`, `plans/release-v11-plan.md` (project files); D-669. The fix PR is #412 (D-680); add its merge sha.

### D-679 · Working Reader batch A (PR #409) approved and merged; WebKit flake quarantined

- Subject: PR #409 (Working Reader batch A; #385 to #388), review round 2 and merge. Also: a WebKit test is quarantined.
- Decision:
  - Round 2 at head ffd4a57 found the PR approvable. Notes are in `plans/review-pr409-round2.md` (project files).
    - All six fixes of D-677 are verified with mutants.
    - CI is green on all three systems.
    - 78 screenshots match the design, apart from the decided deviations (D-672).
  - The merge go was pinned to ffd4a57. It was squash-merged as e517873 on 16 Nov at 00:52:28 UTC, which closed #385 to #388 (00:52:29 to 00:52:31). #14 was closed by hand (00:52:40 UTC), as D-665 planned. Main is now e517873.
  - #411 is filed: WebKit document-page tests on Linux race the page reload after an analysis. `test_make_starts_nothing_until_the_report_matches_and_has_a_chapter` failed twice without a code cause. It is quarantined in WebKit today (D-374), and must be fixed before the next release after v1.1.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 00:52 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-670 and D-677.
- Record: sci2audio PR #409 (merged as e517873), Issue #385, Issue #386, Issue #387, Issue #388 (closed), Issue #14, Issue #411; `plans/review-pr409-round1.md`, `plans/review-pr409-round2.md` (project files); D-374, D-665, D-670, D-672, D-677.

### D-680 · v1.1 release fix PR #412 review round 1

- Subject: PR #412, "tests, ci: the nightly and mutation runs on release/1.1 pass (v1.1.0 checklist)", from release-fix/1.1.0-nightly into release/1.1 (D-678), review round 1.
- Decision: round 1 at head 8f98a62. Notes are in `plans/review-pr412-round1.md` (project files). The PR changes only tests, the CHANGELOG and the mutmut config.
  - P1: the route in the position test lets only the first page's exit save through.
  - K1: the known-issues wording for #410 (plugin authors and `rebuilt_from_script`; code blocks are new in 1.1).
  - The nightly is green, except for the #410 property case.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 00:57 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-678.
- Record: sci2audio PR #412 (open), Issue #410 (v1.2); `plans/review-pr412-round1.md`, `plans/release-v11-checklist-runs.md` (project files); D-669, D-678.

### D-681 · Working Reader batch B plan approved

- Subject: the plan for Working Reader batch B (#389, #390; D-665).
- Decision: the plan `plans/working-reader-batch-b-plan.md` (project files) is approved.
  - #389: the library as a table, plus the shelf. #390: Voices, Privacy, the not-found page and removal, restyled. They go in two stacked PRs.
  - New records per document in the work folder: `opened.json` and `about.json`. Only web/ writes them, and they never make a page fail.
  - The shelf order is: Continue listening, then the running job, then up to three recent documents.
  - Deferred to follow-up issues: search, drag and drop, the Captures column, and the voice-preview cards, filed as #416, #417, #418 and #419 (see D-684).
- Status: Decided (Claude) (coordinator, 16 Nov 01:05 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-664, D-665 and D-679.
- Record: sci2audio Issue #389, Issue #390; `plans/working-reader-batch-b-plan.md` (project files); D-664, D-665.

### D-682 · PR #413: fix the chapter test instead of quarantining it

- Subject: PR #413, "tests: wait for the settled document page after an analysis" (#411), review round 1 at 01:25 UTC.
- Decision: the WebKit quarantine of the chapter test (D-679) is replaced by a fix.
  - The test helper `update()` did not wait for `settled()` after an analysis. The test had also been flaky in Chromium since #409 (7 of 80 runs failed on 228205e).
  - Fix list, in `plans/review-pr413-round1.md` (project files):
    - `settled()` in `update()` and in the keyboard test;
    - the quarantine is dropped;
    - unknown `browser=` values are refused;
    - the PR body gives run counts of 60 or more.
  - #411 stays open for the player test.
  - Lesson: before quarantining a flaky test, run it alone 40 or more times per browser.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 01:44 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). **Amends D-679** (the WebKit quarantine). Refines how D-374 is applied.
- Record: sci2audio PR #413 (open), Issue #411, PR #409 (merged as e517873); `plans/review-pr413-round1.md` (project files); D-374, D-679.

### D-683 · Textprep PR 3 (#408) approved and merged

- Subject: PR #408 (the second textprep batch's PR 3; D-668, D-676), approved and merged.
- Decision: round 1 at head 7056689 found the PR approvable (`plans/review-pr408-round1.md`, project files). It was squash-merged into main as ffdd2f9 at 01:43:20 UTC, which closed #257, #258, #372, #375, #383 and #384 (01:43:22 to 01:43:25).
  - Leftovers filed on v1.2:
    - #414: a list of three or more citation brackets.
    - #415: subject nests that still lose names.
  - The hold on merges until the v1.1 tag was dropped, because main has been open for v1.2 since D-667 and #409.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 01:44 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-668 and D-676.
- Record: sci2audio PR #408 (merged as ffdd2f9), Issue #257, Issue #258, Issue #372, Issue #375, Issue #383, Issue #384 (closed), Issue #414, Issue #415 (v1.2); `plans/review-pr408-round1.md` (project files); D-667, D-668, D-676.

### D-684 · Working Reader batch B follow-ups go into v1.3
- Decision:
  - The batch B follow-ups go into milestone 8, "v1.3 The Working Reader":
    - #416: search titles and authors in the library.
    - #417: drop a file onto the library's opener.
    - #418: captures on the library and the shelf.
    - #419: voice cards with previews on the Voices page.
  - They are scheduled after batches B to D. The coordinator may move them to Later if v1.3 runs long.
- Status: Decided (Claude) (coordinator, 16 Nov 01:52 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Fills in D-681's deferred follow-ups.
- Record: sci2audio Issue #416, Issue #417, Issue #418, Issue #419 (all open, milestone "v1.3 The Working Reader", checked 16 Nov); D-666, D-681.

### D-685 · Textprep PR 4 plan approved (#240, #223)
- Decision: the plan in `plans/textprep-v12-pr4-plan.md` is approved.
  - #240: a German line-end hyphen after a hyphenated word joins before a lower-case rest, unless the last part is a chain word (zu, to, the, ...).
    - Accepted cost: "E-Mail-/basiertes" becomes "E-Mailbasiertes".
    - The #96 regression case de-hyphen-inside-word-kept changes to a capital "Analyse".
  - #223: adjective pairs keep the hyphen when the first part ends in sch, lich, ig, al, iv, iell, uell, rell, nell, mell or är, with stems of 3 or 4 letters.
    - Measured: 87 wrong keeps in 701,565 dictionary split points.
    - Pairs without an adjective ending (rot-grüne) are left out; an issue will follow.
  - Corpus: one maass line changes, and the truth file loses its one [[miss]].
- Status: Decided (Claude) (coordinator, 16 Nov 02:00 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Critical plan (regression cases), approved by the coordinator. Follows D-646 and D-683.
- Record: sci2audio Issue #240, Issue #223, Issue #96; `plans/textprep-v12-pr4-plan.md` (project files); D-646, D-683.

### D-686 · PR #413 round 2 approvable and merged
- Decision:
  - Round 2 of PR #413 is approvable with nothing left over (`plans/review-pr413-round2.md`; 24 joint runs of test_flow and test_keyboard were green).
  - Merged into main as 6ee82d4 at 02:05 UTC, pinned to head 661fc84 (69c1e3a plus main).
  - #411 stays open, with two new WebKit one-offs: the German-book Make click, and the subtitles page before the reload.
  - #422 filed on v1.2: the ZAP PII rule flags Luhn-valid digits in a random SHA-256 of the walk's test PDF. It is to be fixed in the web lane's batch C PR.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 02:00 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-682.
- Record: sci2audio PR #413 (merged as 6ee82d4), Issue #411 (open, no milestone), Issue #422 (v1.2); `plans/review-pr413-round2.md` (project files); D-679, D-682.

### D-687 · Working Reader PR #420 round 1 needs changes; PR #421 round 1
- Decision:
  - PR #420 (#389, library and shelf) round 1 at 980911d needs changes (`plans/review-pr420-round1.md`):
    - B1 (blocker): a deeply nested record raises RecursionError, which passes the OSError/ValueError catches, so every page answers 500.
    - S1: the privacy page must name opened.json, about.json and the listening position.
    - Four tests for surviving mutants.
    - N1: the shelf offers Continue where Listen offers nothing.
  - PR #421 (#390, stacked on #420) round 1 at 3cd37cf is approvable once it carries the fixed #420 plus one download-size test (`plans/review-pr421-round1.md`).
  - Lesson: json.loads can raise RecursionError, so a record reader must catch it together with OSError and ValueError.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 02:17 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-681.
- Record: sci2audio PR #420 (open), PR #421 (open, base web/working-reader-b1), Issue #389, Issue #390; `plans/review-pr420-round1.md`, `plans/review-pr421-round1.md` (project files); D-681.

### D-688 · Release fix PR #412 round 2 approvable and merged into release/1.1
- Decision:
  - Round 2 of PR #412 at 2a598c1 is approvable (`plans/review-pr412-round2.md`):
    - P1: the position route is POST-only.
    - K1: the known-issues wording for #410.
    - ci:full, the PR run, ZAP and the nightly browser jobs are green. The property job fails only on the accepted #410 case.
    - The mutation run was still running at the merge. Its result goes into the R2 body (D-531).
  - Merged into release/1.1 as e9d08ef at 03:00 UTC.
  - Also: textprep PR 4 is PR #425 at 12de0d3, in review. Filed: #423 (an English hyphenated word split again at a line end keeps its second hyphen, no milestone yet) and #424 (German adjective pairs without an adjective ending, such as "rot-/grüne", are joined; on Later; the follow-up named in D-685).
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 03:00 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-678 and D-680.
- Record: sci2audio PR #412 (merged into release/1.1 as e9d08ef), PR #425 (open), Issue #410, Issue #423, Issue #424 (Later); `plans/review-pr412-round2.md` (project files); D-531, D-678, D-680, D-685.

### D-689 · #427 (early click on the main-flow button) is not a 1.1.0 blocker; R2 round 1
- Decision:
  - #427: the German main-flow "Hörbuch erstellen" button is wired only by the deferred app.js, so an early click is lost. Present since v1.0.0; seen once in the Linux browser job of PR #426.
    - Not a 1.1.0 blocker. Milestone v1.2.
    - Fixed in the Working Reader batch C PR the way #350 was (the button stays disabled until it is wired), together with #422.
    - No quarantine. A Known-issues line only if a 30-repeat run fails more than once.
  - R2 of the v1.1.0 release is draft PR #426 at 702a318 (into release/1.1). Round 1 has nothing to fix (`plans/review-pr426-round1.md`). It waits for Colin's hand steps.
- Status: Decided (Claude) (coordinator, 16 Nov 03:23 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-669 and D-688.
- Record: sci2audio Issue #427 (v1.2), PR #426 (draft, base release/1.1), Issue #350, Issue #422; `plans/review-pr426-round1.md` (project files); D-374, D-669, D-686, D-688.

### D-690 · Textprep PR 4 (#425) approved and merged
- Decision:
  - PR #425 is approvable in round 1 at 12de0d3 (`plans/review-pr425-round1.md`): about 50 probe rows on both runs, a 9000-text fuzz run clean, 10 mutants rerun and all killed, nightly seeds 629 each, ci:full green on three systems. The text change of the #96 case is accepted.
  - Merged into main as e107f64 at 03:25 UTC. #240 and #223 closed at the merge.
- Status: Decided (Claude) (review thread / coordinator, 16 Nov 03:25 UTC, under D-80 as extended by D-462 and D-553, and D-626; no chat line under D-626). Follows D-685.
- Record: sci2audio PR #425 (merged as e107f64), Issue #240, Issue #223 (closed, v1.2), Issue #96; `plans/review-pr425-round1.md` (project files); D-646, D-685.

## Resume notes (paused 15 Nov 19:57 UTC at the coordinator's request, after v1.1 was finished)

- D-656 to D-666 are in this file. D-665 and D-666 still need their full texts from the plan, the issue numbers, and the times from the card and the chat. Fold them into the next KB PR. Branch it from sci2audio-design main 3b0c57a or later, check the rows yourself and merge without review (D-626).
- When writing the rows, add status notes to older rows:
  - D-646: refined by D-658 (Later moves done);
  - D-462: v1.1 finished, D-662;
  - D-454: v1.1 finished, D-662.
  - D-288: amended by D-673.
  - D-458 and D-459: amended by D-666 (v1.4).
  - D-665: amended by D-669 (#365 in R1).

## Merge records to add when they land
- Main tip after the PR #377 merge: 8a8f863.
- v1.1.0 release (D-669), status at 22:23 UTC:
  - release/1.1 was cut from a9e0e2d.
  - R1 is PR #403, "release: version 1.1.0, changelog, README and the pasted-text test fix (#365)", on base release/1.1 at head 6fb9b6e. The CHANGELOG lists 72 issues.
  - #404 ("scripts: speed.py measures the German voice (dm_thorsten) too", no milestone) is filed: the speed script knows only English voices, so this release has no German speed row.
  - The review thread "Review the v1.1 release PRs" has started.
  - Add the R1 to R3 merge shas, the tag and PyPI when they land.
- Working Reader batch A (D-670) is PR #409 at head 8982fcc. CI is green, including ZAP and CodeQL. The review thread "Review the Working Reader PRs" has started (Opus high). Merged as e517873 (D-679).

Next free D-number: D-691.
