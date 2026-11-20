# Decisions D-712 to D-714 (for the KB thread, next KB PR)

Written by the governance audit thread, 16 Nov 2026. Add to the pending KB batch in the usual format. D-710 and D-711 (review rulings on #450 and #451) are not in this file; the coordinator holds their texts.

### D-712 · "slow down" moves only non-critical reviews to the cheaper setting (Colin)
- Decision: under "slow down", non-critical reviews run on Opus 5.5 medium (as they already do); critical reviews stay on Opus 5.5 high. The thread-count part (at most 2 implementation threads) stays, without further effect under D-705.
- Status: **Decided** (Colin, 16 Nov 16:08:30 UTC, in the project chat: "i approve your suggestions. apply all", approving item S7 option (b) of the governance audit). **Amends D-702 e** ("slow down": every review on Opus medium, critical ones included).
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
  - f) CLAUDE.md follows the rules (sci2audio PR #453): one implementation thread at a time (D-705); release-branch PRs start Linux CI only, critical ones still get a final-round `ci:full` run (D-703 b); the KB review exception; `ci:full` timing; CI workflows and safety mechanisms in the critical list; SSPL in the licence line; a pointer to the rules files.
  - g) The coordinator updated the project instructions to match (source-of-truth order, KB wording in the critical list, replacement at the next hand-off, release-branch CI exception, control words).
- Status: **Decided** (Colin, 16 Nov 16:08:30 UTC, in the project chat: "i approve your suggestions. apply all"). Carried out 16 Nov about 16:25 UTC; `audit_rules.py` on rules 1.4.0 with the state file: exit 0, 0 errors, 1 warning (91 rules). **Amends D-702** (e, i), **refines D-626, D-698 and D-703** (b, c, d).
- Record: `rules/project-rules.yaml` 1.4.0, `rules/project-rules.json`, `rules/project-state.yaml`, `plans/governance-audit-2026-11-16.md` (project files); sci2audio PR #453; D-626, D-698, D-702, D-703, D-705.

## Merge record to add
- sci2audio PR #453 ("docs: CLAUDE.md follows project rules 1.4.0 (governance audit)", head d0b6134, lane:docs, risk:low): opened 16 Nov 16:12 UTC. Merged 16 Nov 16:21 UTC as 1adf152 on main (squash pinned to d0b6134) by the Working Reader review thread on the coordinator's go; CLAUDE.md only, +8 −8, CI passed green.

## D-716: light-mode reading mark is deep amber #B08400, not Reading Yellow, because no light yellow reaches 3:1 on white

Consequence of D-711 (16 Nov 2026, PR #451, merged as 1bace26): in light mode the sentence being read is marked with deep amber #B08400 and ink text (3.42:1 against the paper, 3.18:1 against the heard tint, text 5.20:1). Dark mode keeps #F2DC3A. DESIGN.md (Reading Yellow = "the sentence being read") and the "Reading sweep" section need this note in the KB (review-pr451-round2.md).

## D-717: the last-progress line names a different chapter in the CLI and on the web card; both are intended, do not unify

From the Working Reader batch D audit (16 Nov 2026, plans/batch-d-audit.md, F2). Both read D-695's `AudioProgress` from its last event:
- The CLI progress line (`cli.py:641`, #432 in PR #446) names the chapter of the sentence just spoken (`chapter_number`). That is the chapter whose sentences it counts.
- The web job card (`pages._stopped_in`, `app.js chapterNow`, batch C) names the next chapter once `chapter_done` is set. That is where the job stands.
The D2 plan asked the CLI to step like the card; review #446 round 1 accepted the deviation. A later thread must not change one to match the other.
- Status: **Decided (Claude)** (coordinator, 16 Nov 2026 17:45 UTC). Record: plans/batch-d-audit.md F2; sci2audio PRs #446, #433; D-695.

## D-718 (Decided, Claude, 16 Nov 2026 18:52Z) — plan template line after textprep batch 2 audit
The audit of textprep PRs 5 and 6 (plans/audit-textprep-batch-2026-11-16b.md, issues #463 and #464) found that PR 6 changed the placeholder/notice model without revisiting what PR 5 had just built on the old model. Every implementation plan from now on carries one line: "Earlier PRs in this batch that built on a model this PR changes: …" (or "none"). Lane thread length stays as it is (0 compressions, not a context problem). #463 and #464 go into the sentence-boundary batch's plan as small textprep follow-ups if they fit, otherwise into the next textprep batch.

## D-719 (Decided, Claude, 16 Nov 2026 18:58Z) — sentence-boundary plan approved
plans/sentence-boundary-plan.md (D-715 programme) is approved as written, five PRs in order, all critical, Opus high, full process. Rulings on the open questions: Q1 the sentence-boundary thread authors PR 2 (layout lane by files, label lane:layout, one thread at a time under D-705). Q2 amends D-60 for sentence truth files: the review thread checks every truth/cutter disagreement and 100 random boundaries per language with the seed in the review report; Colin is not asked; he may spot-check the German file at any time. Q3 yes, as a follow-up issue filed after PR 1, not blocking. Q4 yes, one app/web issue for #460's pause and highlight after the batch. Q5 yes, #463 and #464 are PR 5 of this batch. Q6 accepted: if the PR 1 baseline is far below the targets, revised targets are posted and approved before PR 3 starts.

## D-720 (Decided, Claude, 16 Nov 2026 19:24Z) — Focus mode mark and type (Colin's feedback, issue #471)
Colin (19:21:48Z, screenshot): Focus mode type only slightly larger than the normal Listen text; the mark on the spoken sentence in Focus much more subtle; no mark at all on already-read text. Amends D-716 for BOTH views: Colin (19:24:02Z) ruled that the normal Listen mark gets the same much subtler look and that the two always stay identical; the 3:1 contrast rule still applies, so it is the lightest mark that passes in light and dark mode. Already-read tint (.s.done) is removed. lane:web, v1.3, non-critical, one PR with #461 and #462, queued behind the sentence-boundary batch (D-705).

## Note on #469/#470 (16 Nov 19:24Z)
Colin's per-project files requirement (19:18Z) supersedes D-353 (audiobook kept on removal) once he answers the three questions asked at 19:21Z; the #469 migration gets the critical process because it moves user data.

## D-721 (Colin, 16 Nov 2026 19:28Z, cmsg_011gr2YyZJypGaV6NbzgSXQEHVw8b3mVjzttqSJNQj7dvJ) — publishing parked until installers
"Can we skip publishing until the installer issues are resolved?" Agreed by Claude 19:29Z. v1.1.0 is parked: draft #426 stays a draft with a parked note, no tag, no PyPI, no R3 forward-merge, Colin's listening results no longer needed. Fixes continue on main. The next publish is one release after the v1.4 installer work, cut fresh from main; release/1.1 becomes stale (every fix on it must be on main or have an issue, D-701). Milestone 2 (v1.1) stays open until then.

## D-722 (Colin, 16 Nov 2026 19:30Z, cmsg_011gr2YyZJypGaV6NbzgSXQEHB38wd6bmE76FUgKgFCuKE) — one general marker with optional notes in v1.3; Study layer stays v1.5
A general marker on the current sentence with an optional note goes into v1.3 (lane:web, plan first, plans/general-marker-plan.md, build after the sentence-boundary batch under D-705). The rest of the Study layer (#395–#399, #418) stays v1.5, after the v1.4 installer work is done and v1.4 is published (D-721).

## D-723 (Decided, Claude, 16 Nov 2026 19:37Z) — general marker plan approved (D-722, issue #474, v1.5 follow-up #475)
plans/general-marker-plan.md is approved with three rulings: (1) removing a marker is undone from the toast only (no 30-day struck-through list; keeps the data model to one file with no tombstones, scope minimal for v1.3); (2) M toggles the marker on the spoken sentence; (3) the web lane batch for v1.3 is: PR A = follow-ups #461 #462 #471 #472 (non-critical), PR B = marker #474 (critical, Opus high review, fault-injection tests, markers survive web and CLI reruns, remove box counts markers). The same web thread authors both; it starts when the sentence-boundary batch is done (D-705). Code name "markers".

## D-724 (Colin, 16 Nov 2026 20:35Z, cmsg_011gr2YyZJypGaV6NbzgSXQEEeF542VyyKpcgSc9mipvEF) — reading mark: pale fill below 3:1 plus a left-margin bar
Option (b) chosen: the mark on the spoken sentence gets a much paler fill that may sit below the 3:1 contrast rule (D-711), and a thin bar in the left margin is the second, non-colour cue; the bar itself passes 3:1 against the page. Not an underline (D-709 holds). Same in Focus and normal Listen (D-720). Amends D-711 for the reading mark only. Issue #471, web v1.3 batch PR A.

## D-725 (17 Nov 2026 02:56Z, Decided (Claude)) Windows flate-bomb test quarantine
Test test_a_flate_bomb_is_stopped_at_the_memory_limit_and_this_process_stays_small failed twice on Windows without a code cause (#481 run 23:20Z; #484 dispatch run 44005330346 at 64adb70, child exit 1, no stderr; PR run on same head green). Ruling: review thread runs the D-682 isolation dispatch (only this test, Windows, 40+ runs) on main cfeb084 and records the result in the issue; the test is quarantined today per D-374 regardless. Quarantine PR: authored by the sentence-boundary implementation thread from a fresh branch off main, skip marker + issue link only, non-critical, Linux CI, one pinned review round, review thread merges. Afterwards #484 merges main; that is a base move, not the PR's one re-run, and the following three-system run is the round 3 run if the diff against the reviewed head is otherwise only the round 3 fix commit.

## D-726 (17 Nov 2026 03:40Z, Decided (Claude)) sentence-boundary batch audit follow-ups
Audit plans/audit-sentence-boundary-batch-2026-11-17.md: 0 blocking, 2 should-fix, 2 nits; no contract touched beyond the approved D-725 marker. #487: a notice-off table or figure reads its printed text through the same textprep path as a paragraph; the two regression rows that pin the raw reading are corrected in that fix. #488: German "et al." before a capital noun must not end the sentence; next textprep batch. Both v1.2.x, lane:textprep. "(WBGU 2011)" row noted on #477. Lane threads keep their current batch length; follow-ups are folded into a batch only when they share its model.

## D-727 (17 Nov 2026 04:02Z, Decided (Claude)) light-mode reading bar #9A7400
Amends D-724's colour only: the 3 px left bar in light mode is #9A7400, not #B08400, because #B08400 measures 2.97:1 on the Focus desk background #EDEFF2. #9A7400 measures 4.31:1 on paper, 3.74:1 on desk, 4.02:1 on the fill. Rule: the bar passes 3:1 on every background it sits on, pinned by a unit test. Dark bar stays #F2DC3A. PR A #489.

## D-728 (17 Nov 2026 04:08Z, Decided (Claude)) marker PR B plan revision approved
plans/general-marker-plan.md (revision with D-718 lines for PR A's mark and panel, #460/#480, D-727 contrast for flag edge and tick, section 7a with all 8 test-harness changes) is approved for #474, critical process per its section 6. Rulings: (1) a test fails without the broken-file guard, and a test fails if a not-found marker is dropped from the list or the file; (2) undo restore uses the same locked read-modify-write path as a set; (3) the removal-box marker count is read from the file when the box is drawn, pinned by the extended #120 test. PR B branches from main after #489 merges; same review thread.

## D-729 (17 Nov 2026 05:40Z, Decided (Claude)) #492 unassigned code point in output names
#490's ci:full fails on macOS because Schemathesis generated a document name holding U+E57EE (unassigned), which APFS refuses and output.names.clean() did not strip (issue #491, older than PR B). #492 (lane:output, non-critical) is reviewed by the web batch's review thread, max 2 rounds, merged only after its own three-system run is green; then #490 merges main as a base move. Reviewer checks the rule covers all unassigned and surrogate code points and that corpus output names are unchanged.

## D-730 (17 Nov 2026 06:05Z, Decided (Claude)) #480 joined-sentence plan approved
plans/480-joined-sentence-plan.md approved. C1 (output + app: Pause.CLAUSE 0.25 s, edge-silence trim at clause joins, additive "joins" key in the read-along, version stays 1) is CRITICAL because docs/readalong-format.md is a contract document; the additive key is accepted instead of a version 2, with a test that a version-1 reader without the key and a new reader on an old file both work. C2 (web: one element per sentence, sentence steps by element, marker anchors the whole sentence) is non-critical; C1 merges first. B (raise DEFAULT_MAX_CHARS 300→400, textprep, critical) is option (1): its own PR after C1 and C2, filed as an issue now. The sentence gap itself stays out of scope. Author: a new web/app thread (the batch thread reached 3 compressions and stays only for #490 fix rounds). Same review thread as the web batch.

## D-731 — Nightly red on main fc7406a: no block on #495, untracked failures get owners (2026-11-17 06:57Z)
Report (author thread, #480): every red job in the #495 nightly also fails on main fc7406a. Ruling, same pattern as D-725/D-729:
1. Pre-existing main nightly failures do not block #495. Reviewer compares each red job against the main run and records the match in the round report; #495 is judged on its own jobs and the nightly seeds.
2. Tracking: EPUB cover test stays with #473 (release/1.1 ports). Firefox (4 tests), WebKit macOS (11 tests, mostly v1.3 Focus/panel/shortcut tests) and WebKit Ubuntu (1 panel test) get GitHub issues, lane:web, filed by the #480 author thread; WebKit items join #437 where they are the same cause. The WebKit marker-test failure is a post-merge defect of #490 → ledger entry.
3. Owner: the web lane. Order after C1 merges: C2 → #473 → "nightly green" fix PR(s) for the new issues (non-critical unless they touch tests pinned as goldens) → web batch audit. v1.3 stays "complete" subject to the already-open #437; the WebKit v1.3 test failures are #437 scope unless the issue triage finds a real Safari bug, which goes to Colin.

## D-732 — Priority fix: resuming a paused audiobook build (2026-11-17 08:26Z)
Colin (08:24Z, cmsg_011gr2YyZJypGaV6NbzgSXQEJShCheUVcy1Yccyf5Ensc4): pause works, resume shows "files exist already, replace / clear voice cache" and looks like progress is lost; "critical issue that needs prio fixing". Ruling: CRITICAL (safety dialog that can delete user files and the cache; output contract). Own thread "Fix resuming a paused audiobook build" (Opus high) runs in parallel with the #480 thread as an exception to D-705 on Colin's priority order. Plan first (plans/resume-build-plan.md, my approval), one PR lane:app, test failing without the fix, ci:full, critical review up to 4 rounds. #503 review continues; the resume PR is reviewed ahead of anything else when it arrives.

## D-733 — Resume plan approved (2026-11-17 08:30Z)
plans/resume-build-plan.md approved as written incl. item 4 (cache button behind the confirm box). Diagnosis: progress is NOT lost with "Diese Dateien ersetzen" (chunks reused); only the cache button loses it. Cause: Resume posts overwrite=false although the paused run started with overwrite=true; JobRecord keeps no record. Fix: JobRecord/JobOut gain overwrite (additive), card carries data-overwrite, Resume reposts it; existing-files card drops the cache button and says spoken sentences are kept (only when the cache holds some); cache button behind confirm box naming the loss. Additions: confirm-box test must fail without the confirm step; empty-cache case tested. Labels lane:app lane:web risk:high bug, milestone v1.3. Colin given the workaround 08:30Z.

## D-734 — Nightly-green batch (2026-11-17 10:20Z)
After #507 (1e461a7, #473 closed): web lane fixes #496–#502, #506, #509 (#508 closed as duplicate of #506), at most three PRs grouped by cause, #502 in the first (blocks #437's five green runs). Non-critical unless a PR changes a golden or regression case. Each PR: Linux CI green, nightly dispatch on the branch proving the targeted browser tests, review max 2 rounds, one at a time. #498 ruling: tests follow Safari's click-focus rule, except the narrow panel Close button, where the app moves focus back to the toggle on every browser (recommended to Colin 08:25Z, no objection yet). Web batch audit after this batch covers #489 #490 #495 #503 #505 #507 + these PRs.

- **D-735** (17 Nov 11:05Z, Decided (Claude)): PR 2 plan of the nightly-green batch approved as posted by the fresh web thread: #499 drop the macOS Back chord (Meta+ArrowRight and Control+ArrowLeft instead, Listen-URL assertion kept on every chord), Control+a becomes ControlOrMeta+a; #500 a change_theme() helper waits for CSS transitions only and only after a theme change, all == 0 stays elsewhere (D-709 intact; cause confirmed in Firefox as a background-color transition on input#follow.switch); #501 abs(bottom - height) < 0.5. Tests only, non-critical, from main 68f322d (#510 merged 11:02Z, 1 round, no findings).

- **D-736** (17 Nov 11:15Z, Colin, cmsg_011gr2YyZJypGaV6NbzgSXQE8ZZya3chpfvWoHLCbbWpd4): no new issues are started from now on; Colin preserves the rest of his weekly token limit (80% used). Coordinator reading: PR 2 (#499 #500 #501, already started) finishes leanly and gets one review; PR 3 (#506 #509), the web batch audit, #469/#470 and the textprep batch wait until Colin lifts it. thread_freeze: true in project-state.yaml.

## D-737 (18 Nov 2026 13:00Z, Decided (Claude)): rules 1.4.1 after the 18 Nov governance audit
Audit thread "Audit the project governance rules" (report: https://claude.ai/artifact/FqZefdv4cGoRG5MABZSsuH) found 0 script errors and four blocking gaps. Coordinator edits (META-01): CMD-07 writes the D-736 freeze into the rules (no new threads or issues, running rounds finish, daily KB PR continues, threads answer Colin); TST-07 and TST-08 merged into one order (40-run isolation first, then same-day quarantine with issue); project-state.yaml cleared of the stale implementation_thread_active text and stamped. project-rules.json regenerated. Open for Colin: new autonomy horizon (item 1). The six minor items in the report are deferred until the freeze lifts.

## D-738 (18 Nov 2026 13:10Z, Decided (Colin)): rules 1.4.2, audit minor items applied
Colin (13:00:57Z, cmsg_011gr2YyZJypGaV6NbzgSXQECBXhVTXvvtDP5fnpD8Szc8): "fix all issues". Applied by the audit thread on the coordinator's instruction (13:01Z): REV-09 (a failure that also fails on main does not block; a bug older than the PR is fixed first in its own lane PR; D-725, D-729, D-731); LANE-02 gains the D-732 priority-bug exception; REV-06 now has the review thread send the round-report path to the author directly, coordinator gets one line; PLAN-04 (no acceptance criteria, no start; from CLAUDE.md); AUTO-02 points to autonomy_messages in the state file; CMD-04 loses its dead thread-count clause; WD-01 fires no checks during a freeze while no thread owes a result. State file: frozen_queue added, dead pause exception and finishing_under_old_limit cleared, open_owner_items gains the #469/#470 questions and the milestone 7 rename (GitHub title is still "v1.2.x abbreviations"; Colin's hand step, ROLE-02). plans/roadmap-after-v1.md gets a "superseded in part" note (D-666, D-721, D-722). CLAUDE.md: PR for horizon-neutral autonomy wording, a current-goal section and the acceptance-criteria rule (critical, review and merge by the coordinator). Not applied: the autonomy horizon (Colin, open) and WD-01's 60 minutes (Colin's value; the 55-minute suggestion stays with him); moving CI and release rules out of the ruleset (token trim) is left for a later version.

## D-739 (18 Nov 2026 13:15Z, Decided (Claude)): rules 1.4.3, audit M2 and M4 taken as proposed
D-737 had put the 40-run isolation before the quarantine; the audit's M4 reasoning stands (a browser isolation takes longer than a day, PR 3 sits at 4/40; D-725 quarantined the same day regardless), so TST-07 quarantines the same day and TST-08 runs the isolation afterwards with the result in the issue. CMD-07 now allows filing issues during a freeze (filing only), so GH-01 and TST-08 keep working; the unfiled Firefox voice-card flake from plans/nightly-green-handoff.md is filed when the next web thread starts, not now. JSON twin regenerated.

## D-740 (18 Nov 2026 13:04Z, Decided (Colin)): autonomy horizon
Colin (cmsg_011gr2YyZJypGaV6NbzgSXQELq58FgdhSWK8dGHRJmDbCv): "autonomy runs until i ask to stop or there are no more issues to work on." Replaces "until v1.3 finished" (D-702a) and settles audit item M1. autonomy_horizon in project-state.yaml set; AUTO-01 already points to that value. Roadmap, product scope and the round-4 stop stay with Colin. The D-736 freeze is not lifted by this.

## D-741 (18 Nov 2026 13:06Z, Decided (Colin)): freeze lifted, lanes run in parallel
Colin (cmsg_011gr2YyZJypGaV6NbzgSXQE5cwtWasr7uD9azqtazxBfd): "continue working on multiple lanes as long as they dont block each other." Lifts the D-736 freeze (CMD-06) and replaces the one-thread limit of D-705: rules 1.4.4, LANE-02. Coordinator reading: one implementation thread and one review thread per lane; lanes that share files, goldens, regression cases or a layer contract do not run side by side. Started: web lane (PR 3 #506 #509, voice-card flake issue), textprep batch (#494 critical, #487, #488, #477), light web batch audit. Waiting: layout (#456 to #459) behind textprep because of shared goldens; app (#469, #470) on Colin's three answers; docs PR #516 on CI. Watchdog 60 min restarted.

## D-742 (18 Nov 2026 13:14Z, Decided (Claude)): web batch audit follow-ups
Audit plans/audit-web-batch-2026-11-18.md: 0 blocking, 2 should-fix, 4 notes; no undeclared contract touch; the 2-compression replacement rule stays, and a big critical PR gets its own thread. S1 (marker API and Listen-page marker data use the longest piece of a joined sentence, not the first) and S2 (shortcut hint omits M) become issues and one small non-critical PR by the web thread after PR 3; N3 (where `joins` may appear in docs/readalong-format.md) becomes a lane:docs issue for a later critical docs PR. KB main is 7e5b1ce (KB PR #54, D-725 to D-741).

## D-743 (18 Nov 2026 13:24Z, Decided (Claude)): textprep batch 3 plan approved with four additions
Plan plans/textprep-batch-3-plan.md (#494, #488, #477, #487) approved: whole batch critical, three PRs (PR 1 #494; PR 2 #488 + #477; PR 3 #487), one review thread on Opus high, PR 3 written during PR 1's review, PR 2 after PR 1 merges. Additions: A1 the P1.7 phoneme measurement runs BEFORE the constant changes and is a gate: if any corpus utterance of 300 to 400 characters passes the voice's token limit, or a number-dense 400-character sentence loses audio in either voice, stop and report (a slow test with such a sentence in English and German proves no text is lost; "the voice splits it itself" is not accepted unproven). A2 P1.8 also covers saved user data: a marker (markers.json) and a saved position (position.json) inside a sentence whose cut moves or disappears still land on that sentence after a rebuild, shown by a test or by naming the existing re-anchoring test that covers it. A3 P1.5: tests may pin max_chars=300, but one estimator test stays on the default; the docstring edit in app/estimate.py is allowed in PR 1 and named in the PR. A4 PR 2: the new data/en/sentence_openers.toml is covered by the packaged-data check (wheel contains it), and the "in the U.S. Researchers found" loss is recorded as a regression row or known-errors entry with its cause, whichever the gate result calls for.

## D-744 (18 Nov 2026 13:24Z, Decided (Claude)): #477 ruling
Rows 1 and 2 ("the U.S. | Census Bureau", "called A. | Then") are fixed by an English sentence-opener rule (twin of the German ordinal rule, D-530) only if the sentence gate shows zero new errors, the natural-set floors hold, every regression row stays and no corpus snapshot moves except listed fixes; a part that fails the gate is dropped and its row closes as a limit. Row 3 (lower-case sentence starts such as "seaborn.", "iOS") and row 4 (German "Es waren 3. | Studien", D-530) close as deliberate limits; so does the WBGU note (N2). Their known-errors entries point at D-744.

## D-745 (18 Nov 2026 13:39Z, Decided (Claude)): layout and app lanes start beside textprep and web
Colin (13:37Z, cmsg_011gr2YyZJypGaV6NbzgSXQEHvfACEDkDhH8rNR1uKZZ8J) asked why more lanes are not running. The two waiting lanes were held on soft blocks only, so both start: layout (#456 to #459; the shared corpus snapshot is regenerated after merging main, never hand-resolved, behind textprep PR 1) and app (#469, #470, both critical; plan first on the recommended defaults as marked assumptions: audiobook deleted by default with a keep box, cache outside Documents, v1.2; #469 first; the delete behaviour of #470 is not coded before Colin answers question 1). Web review thread started 13:33Z for #519 (approved round 1, merges after the isolation runs) and PR 4 (#520 #521).

## D-746 (18 Nov 2026 13:45Z, Decided (Claude)): Windows keep-alive flake, and #516 review started
tests/unit/test_web_jobs.py::test_events_keep_the_stream_alive_and_end_when_the_server_stops failed twice on Windows without a code cause (main 1e461a7 run 44063376376; #516 head 294cbb3 run 44313882649, docs-only PR). TST-07: the governance thread files the issue; the web lane quarantines it today on Windows only (in PR 4 #523 if not yet in review, else a tiny PR) and runs the 40-run isolation afterwards with the result in the issue (TST-08). #519 round 1 approval withdrawn: the author's 40-run job reported green while its loop ignored failures (WebKit "waits for the script" tests failed 11 of 40); round 2 after one fix and a repeat job that fails on any failed iteration. Lesson appended to memory/MEMORY-archive-2026-11-18.md. #516 (CLAUDE.md, critical) in review at f6d1294 with Linux CI and ci:full green, thread "Review the CLAUDE.md governance update" (Opus high).

Merge note (18 Nov 13:45Z): #516 CLAUDE.md governance update MERGED 2979dce (pinned f6d1294, 1 round, 0 findings; verified ls-remote). Follow-up #526 (lane:docs, risk:high: priority-bug thread and per-browser isolation wording). Windows flake issue #525 (D-746). Governance audit thread and its review thread resolved.

## D-747 (18 Nov 2026 13:50Z, Decided (Claude)): data root moves to the user data folder
Per-project work files (source copy, analysis, speech cache, records, position.json, markers.json) live in <user data>/sci2audio/projects/<id>/ (platformdirs user_data_path; was the OS cache folder). Inner layout unchanged (AudioChunk.file keeps its meaning, L2); id names kept (L3); speech cache stays inside (Q2), with a follow-up issue for backup exclusion (L5). The Documents folder holds the audiobook only (Q1). Plan plans/per-project-folders-plan.md §1.

## D-748 (18 Nov 2026 13:50Z, Decided (Claude)): migration algorithm
M1 to M12 of the plan: migration lock, candidates by id only, links and junctions never followed, busy folders skipped and retried, atomic rename fast path, copy-verify-commit path on EXDEV, merge into from-earlier-version/ when the target exists, never overwrite, idempotent and resumable (crash-point property test MT2), legacy folders listed until moved, Documents never touched, old flat audiobooks never moved. PR 1 may merge on assumption A2 before Colin answers question 2 (Q7): the engine is root-agnostic and a later root change moves projects again without data risk.

## D-749 (18 Nov 2026 13:50Z, Decided (Claude)): project audiobook folder
<output folder>/<project name>/, name cleaned by output.names.clean and capped at 60 characters / 80 bytes; claimed with mkdir(exist_ok=False), " (2)" suffixes, recorded in project.json before the job; a folder sci2audio did not create is never taken over (A1 to A3). Supersedes the flat output folder for new audiobooks; old ones stay where they are (M12).

## D-750 (18 Nov 2026 13:50Z, Decided (Claude)): project.json manifest
Format sci2audio-web-project version 1 (A4, A5): folders and files written with size and SHA-256; decisions by size + SHA-256 only, never mtime; read strictly, a bad file means no manifest and no audiobook deletion; old-reader and old-file tests (D-730 lesson).

## D-751 (18 Nov 2026 13:50Z, Decided (Claude)): removal with warning, ruling on the mechanics
R1 to R6 as planned: keep_audiobook is a required API parameter; order busy-check, plan, audiobook files, data folder; folder and file checks (links, outside, changed, shared, unreadable); only listed files, rmdir only, system clutter exception (Q5); audiobooks made before #469 are never deleted, only named as staying (Q4, narrows #470's seeding idea). Supersedes D-353 and amends D-358, D-359, D-361. The default state of the keep box (A1) and the start of PR 3 wait for Colin's answer to question 1.

## D-752 (18 Nov 2026 13:50Z, Decided (Claude)): per-project folders plan approved
Plan plans/per-project-folders-plan.md approved with Q1 to Q7 as recommended, three critical PRs (PR 1 migration, PR 2 folder + manifest, PR 3 removal), one review thread on Opus high, mutation probing, nightly seeds and the three-system run on each final round. Cross-lane files accepted (Q6); PR 3 starts after web PR 4 (#520 #521) merges. Additions: the backup-exclusion follow-up issue is filed with PR 1; MT2 covers M8 crash points too; PR 1 keeps --work-folder behaviour unchanged with a test; each PR body names its mutants for the S tests.

## D-753 (18 Nov 2026 13:53Z, Decided (Claude)): #524 may change one browser fixture
PR #524 (#494) replaces the LONG constant in tests/browser/test_joined.py with an own 456-character sentence, because at 400 the old 412-character one is cut 305+106 and the marker lands on the first piece. The change stays in the textprep PR (the limit change is what breaks the fixture), is listed as a test-harness change with the before/after cut, and nothing else in tests/browser changes; the web lane was told. A1 gate passed (47 corpus utterances of 300 to 400 characters, none over 510 tokens; number-dense sentences heard whole, slow tests). A2: marker test added; position.json is dropped by design on a rebuild (#153).

## D-754 (18 Nov 2026 13:53Z, Decided (Colin), cmsg_011gr2YyZJypGaV6NbzgSXQEKzjCmRRN5y4P1WZSdKyPg4): per-project folder answers
Colin: "i approve your recom" to the three questions of 16 Nov: (1) on project removal the audiobook is deleted by default, with a "Keep the audiobook files" tick box; (2) Documents/sci2audio/<project>/ holds the audiobook, everything else lives outside Documents in the app data folder; (3) milestone v1.2. Assumptions A1 to A3 of plans/per-project-folders-plan.md become decisions; PR 3 (#470) is unblocked after PR 2 and web PR 4.

## D-755 (18 Nov 2026 13:56Z, Decided (Claude)): layout batch plan; front matter as publisher sections
Plan plans/layout-batch-german-pdf-plan.md approved. PR A (running heads, #457 footnote numbers, #459 heading "I": a heading needed two letters) and PR B (#458 crop box) are non-critical and run without a wait; if a golden or the corpus snapshot moves, the PR becomes critical and stops. PR C (#456) takes option 1: C1 outline-named front matter becomes a level-1 section starting at its page's first block (cover sheet found through the outline only), C2 `Section.publisher: bool = False` in core (critical, lane:core + lane:infra; Section is in no versioned file, named in the PR), C3 app/chapters.py marks the chapter as the publisher's (deselected by default like EPUB publisher pages, #190) and names the blocks after it with the document title. One critical PR after PR A merges, plan steps pinned, the corpus-truth test exception named. The app lane's #469/#470 batch does not touch chapters.py; PR C merges main first if both land close together. Review: one thread for the batch, Opus medium for A and B, Opus high for C.

## D-756 (18 Nov 2026 14:34Z, Decided (Claude)): #523 merges ahead of #524
#523 (web PR 4, #520 #521) approved round 1 with 0 findings; it does not wait for #524 (textprep, round 2 with a blocking finding). The web review merges #523 pinned to a573b9d after merging main; the textprep thread merges main into #524 before its round-2 push so the test_joined.py changes of both PRs are tested together. Round-1 results: #524 changes requested (1 blocking: an older bracket-cut test stopped checking anything in English at 400; 3 should-fix; 1 nit; #533 filed for 7 cutter mutants that also survive on main); #530 changes requested (2 must-fix: the L4 note stack swallows a tight small footer or page number below the footnotes, a regression against main; 4 test gaps; 1 nit).

Merge note (18 Nov 14:43Z): #523 web PR 4 MERGED f2aea0e (pinned c6fc1ad, 1 round, 0 findings; closes #520 #521). #532 round 1: 11 findings, 2 blocking (startup hang in the merge loop; job lock released during copy/merge).

Merge note (18 Nov 15:01Z): #530 layout PR A MERGED 158f1ae (pinned 2fcebdf, 2 rounds: 2 must-fix + 4 test gaps in round 1, 0 in round 2; closes #457 #459).

Merge note (18 Nov 15:32Z): #538 layout PR B MERGED 94a4353 (pinned d52f0a6, 1 round, 0 blocking; closes #458; follow-up #543). #524 approved round 2 (1b27a7f, main merged 6bfe161), merge waits for the branch nightly re-run (WebKit test_two_quick_presses, unrelated). #528 round 1: 3 findings, 0 blocking (#540 filed). #539 PR C (critical) open at fdc27a0, ci:full running. New issues #537 #541 #542 (#542 fixed by #519).
- #528 textprep PR 3 APPROVED round 2 at d5f9c01 (0 new findings, plans/review-pr528-round2.md); merges after #524. #524 branch nightly: slow + property tests green; WebKit Linux failure and queued macOS slow job re-run once (18 Nov 15:42Z).
- D-757 (18 Nov 16:05Z, Colin cmsg_011gr2YyZJypGaV6NbzgSXQE2cgupaDcF5ps8T8bUaQjHG "think about how to make the ci faster. this is not sustainable."): CI speed lane started (thread cmsg_011gr2YyZJypGaV6NbzgSXQE2cgupaDcF5ps8T8bUaQjHG, Opus high). Plan plans/ci-speed-plan.md first; CI is critical, coordinator approves before any PR; touches .github/ only until approved.
- #519 web PR 3 APPROVED round 2 at cbd3e9c (0 findings, plans/review-pr519-round2.md); strict isolation Firefox/WebKit Ubuntu/Chromium 40/40 on 16 items, WebKit macOS no runner; head 0f8506a, merge pinned on green Linux CI. FOR COLIN: delete scratch branches ci/isolate-reload-timing, -2 to -6, ci/isolate-keepalive-525 (and ci/isolate-flate-bomb-d725) on GitHub (18 Nov 16:20Z).
Merge note (18 Nov 16:29Z): #519 web PR 3 MERGED 2cb10c5 (pinned 0f8506a, 2 rounds, 0 findings); closes #506 #509 #518 #542; #517 #541 stay open. Web batch (PR 3 + PR 4) DONE; web review thread resolved.
- D-758 (18 Nov 16:33Z): MERGE SLOT. While several lanes merge, one PR at a time holds the merge slot to main (ruleset requires up-to-date branches; #524 lost two CI rounds to races). Slot order: #524, #528, then free; other review threads hold merges until told.
- D-759 (18 Nov 16:35Z): CI speed plan plans/ci-speed-plan.md APPROVED, items 1-5 in order + item 6 merge queue vs up-to-date rule (report only). Item 4 terms: Firefox/WebKit in PR check only for web paths, nightly stays safety net, green browser checks end the nightly-rerun wait. Item 2 keeps a full-40 flag for TST-08. One critical PR per item, review thread Opus high.
- D-759 OWNER-APPROVED by Colin 16:55Z (cmsg_011gr2YyZJypGaV6NbzgSXQEHWuUJ1XWjZ53XxHG4UczTB "i approve this plan. lets do it").
- D-759 amendment (16:36Z): O4 Firefox/WebKit in PR CI for web paths is reported-only until #437 closes, then required. Coordinator updates TST-08 and nightly-before-merge rule text when the workflows land.
- #532 app PR 1 APPROVED round 2 (29 mutants, gap filed #544, plans/review-pr532-round2.md); head 4877887; merge held for the D-758 slot after #524 #528 (16:33Z).
Merge note (18 Nov 16:53Z): #524 textprep PR 1 MERGED 712ec4c (pinned 5d5a6ce, 2 rounds; closes #494; critical). WebKit marker test failed once, passed on re-run, not quarantined (second failure anywhere → TST-07). #528 next in the slot (7df7187, ci:full running).
- #539 layout PR C round 1 (17:41Z): changes requested, 2 must-fix (front-matter-only outline can deselect whole document; front-matter starts taken in outline order), 2 mutant gaps, 2 nits; plans/review-pr539-round1.md. #539 head 3f93b7e green three systems.
Merge note (18 Nov 17:52Z): #528 textprep PR 3 MERGED c3b79c2 (pinned 7df7187, 2 rounds; closes #487; critical). D-758 slot passes to app #532, then layout #539 when approved. Textprep PR 2 = #547 (#488 #477) round 1 started.
- CI lane (17:55Z): #545 nightly speed PR green at 5c91fa5 (property job 12.2 min was 29; browser shards 4-6 min were 8-13) → review thread 'Review the CI speed-up PRs' cmsg_011gr2YyZJypGaV6NbzgSXQEBRnbMmhURuosWPcbkiTDMy (Opus high) started. Side findings: 'CI passed' green while macOS leg cancelled (run 44349877322, fix PR 3); mutation baseline broken on main, THIRD_PARTY_LICENSES.md missing in also_copy (fix PR 5).
- CI lane (17:56Z): #546 isolate workflow green at 311e4eb, in review with #545. FOR COLIN: also delete scratch branch ci/isolate-workflow-try.
- #547 textprep PR 2 round 1 (17:59Z): changes requested, 1 blocking (sentence-opener list holds surnames He, An, So, To → initials cut), 1 nit; plans/review-pr547-round1.md.
- CI review round 1 (18:02Z): #545 1 must-fix (nightly drops 30,000-text size of two fuzz tests); #546 3 must-fix (summary green-ish with cancelled runners; ref-wide concurrency cancels other isolations; +1). Reports plans/review-pr545-round1.md, plans/review-pr546-round1.md; TST-08 and #437 counting notes inside for the rules update.
- #539 round 2 (18:20Z): 1 must-fix (multi-section front matter can take every block → empty default selection); round 1 fixes verified, 10/10 mutants killed; round 3 checks the fix only; plans/review-pr539-round2.md.
- #547 textprep PR 2 APPROVED round 2 at 08061b5 (0 new findings, plans/review-pr547-round2.md); slot queue: #532 → #547 → #539 (18:29Z).
- CI review round 2 (18:37Z): #545 APPROVED at b0dcb39, #546 APPROVED at fade972 (plans/review-pr545-round2.md, review-pr546-round2.md; dispatched Nightly green, isolate try runs full + stop mode). Slot queue: #532 → #547 → #545 → #546 → #539.
- #539 layout PR C APPROVED round 3 at 17fa700 (0 findings, plans/review-pr539-round3.md). Slot queue (18:38Z): #532 → #547 → #539 → #545 → #546.
Merge note (18 Nov 18:53Z): #532 app PR 1 migration MERGED 1cf1f65 (pinned 69a1f86, 2 rounds; critical; follow-up #544). Slot → #547 → #539 → #545 → #546. App PR 2 opens next. Lesson: review threads must poll the run, not wait for a second CI run that never comes (two threads lost ~1 h today).
- D-760 (18 Nov 19:08Z, PROPOSED to Colin, his hand step): drop 'Require branches to be up to date before merging' in ruleset main (id 26932142; strict_required_status_checks_policy true→false; 'CI passed' stays required); same for release-branches ruleset 27255463 optional. GitHub merge queue not available (personal account). New rule once applied (MRG-xx): a red main is fixed or reverted by the lane that merged last before anything else merges; D-758 slot stays until then. Fallback O6a: catch-up head needs Linux CI only, three-system run stays on the reviewed head.
Merge note (18 Nov 19:09Z): #547 textprep PR 2 MERGED f126875 (pinned 1f101fb, 2 rounds; closes #488 #477; critical). TEXTPREP BATCH 3 DONE (#524 #528 #547). Slot → #539 → #545 → #546.
- CI lane (19:15Z): #551 scoped mutation (item 5, closes #549) round 1: 2 must-fix (summary hides no-tests mutants, says Survived 0; mutmut runs under dev Hypothesis profile); plans/review-pr551-round1.md.
Merge note (18 Nov 19:20Z): #539 layout PR C MERGED 73e26df (pinned c2b06c8, 3 rounds; closes #456; critical). LAYOUT BATCH DONE (#530 #538 #539; #456-#459 closed; follow-ups #529 #535 #537 #543). Slot → #545 → #546 → #552.
- D-760 APPLIED (Colin 19:25Z cmsg_011gr2YyZJypGaV6NbzgSXQEFzDF1mVMk9fg9fep4eJwUB "it's now turned off"): ruleset main no longer requires up-to-date branches. Rules 1.4.5: MRG-03 reworded, new MRG-04 (red main fixed/reverted by last merger before further merges; slot only while red or on shared files). D-758 slot retired.
Merge note (18 Nov 19:26Z): #546 isolate workflow MERGED bb8e1e3 (pinned fade972, 2 rounds; critical CI). #545 waits for CI on d760bc2. FOR COLIN: also delete scratch branch ci/isolate-try-r2.
- #552 app PR 2 round 1 (19:29Z): changes required, 4 findings (R1 trusts project.json name as folder name; R2 records a remade folder twice; none data loss); plans/review-pr552-round1.md.
Merge note (18 Nov 19:33Z): #545 nightly speed MERGED 2cad344 (pinned d760bc2, 2 rounds; critical CI). #551 scoped mutation APPROVED r2 (plans/review-pr551-round2.md), updated to d11425c (shares pyproject.toml with #545), merges on green Linux CI.
Merge note (18 Nov 19:47Z): #551 scoped mutation MERGED 312e5c7 (pinned d11425c, 2 rounds; closes #549; critical CI). CI items 1, 2, 5 done; PRs 3 (browser shards + CI-passed fix) and 4 (Firefox/WebKit reported-only) remain.
- CI lane (19:48Z): PR 3 #553 green, in review (PR CI ~9 → 5.2 min; "CI passed" fails on any cancelled leg, #548). Rules-file note for 1.4.6: PR browser checks are "browser (Linux, Chromium, 1/2)" and "2/2"; "CI passed" keeps its name. PR 4 after #553.
Merge note (18 Nov 19:49Z): #553 PR browser shards + strict "CI passed" MERGED 025b67a (1 round; closes #548; critical CI). CI PR 4 (Firefox/WebKit reported-only for web paths) remains.
Merge note (18 Nov 20:18Z): #554 Firefox/WebKit reported-only on web PRs MERGED 1797ceb (1 round). CI SPEED LANE DONE (D-759): #546 bb8e1e3, #545 2cad344, #551 312e5c7, #553 025b67a, #554 1797ceb; PR CI ~9→5 min, property job 29→11.6 min. Rules 1.4.6: TST-08 names isolate.yml, ci_browser_nightly reference rewritten. Threads resolved. FOR COLIN: scratch branches ci/isolate-workflow-try, ci/isolate-try-r2, ci/isolate-reload-timing(-2..-6), ci/isolate-keepalive-525, ci/isolate-flate-bomb-d725.
- FOLLOW-UP when #437 closes (from CI lane, 20:18Z): make Firefox/WebKit required on web PRs: drop "reported only" from the job name, add browser-reported to the needs of "CI passed", accept skipped for PRs touching no web path; then rules 1.4.x marks them required.
- D-761 (18 Nov 20:30Z): plans/next-batches-2026-11-18.md APPROVED. Start now: B1 extraction (#442 A, #537+#543, #485), B2 textprep (#445 #449, #448), B3 layout (#529+#535, #466), B4 docs (#522+#526). Conditions C1 (B1 PR 1 Content change additive, else B3 PR 2 waits) and C2 (corpus snapshot: merge main + regenerate) apply. Acceptance criteria AC-442.1-4, AC-445, AC-448, AC-449, AC-485, AC-293 approved as written; the planning thread writes them into the issues. #442 part 3 (glyph-ID recovery) is Colin's roadmap call. B5 after B2; B6 after B5 and B3 PR 2; B7/B8 after app PR 3 (#470). #541: planning thread dispatches isolate.yml mode=full on main and records counts. Triage of the 32 other v1.2 issues and milestones for #526 #527 go to Colin.
- D-762 (18 Nov 20:40Z): B1 plan plans/extraction-batch-b1-plan.md APPROVED. Q1: AC-442.1 narrowed, simple fonts with unknown glyph names not counted in Page.unmapped (TeX math + matplotlib Type 3 fonts in 4 corpus papers; text check covers them). Q2: legibility module in extraction. B7 policy pinned: stop before voices when unreadable pages hold >50% of characters, else #187 report warning. #485 has a code cause (isolate._wait poll outside try, Windows BrokenPipeError) → PR 3 critical.
- D-763 (18 Nov 20:42Z): B3 plan plans/layout-batch-b3-plan.md APPROVED. PR 1 #529+#535 is CRITICAL (PrivacyScore printed page labels move 431 printed_page fields in test_app_corpus.ambr, one layout golden line, corpus page-label truth test, one unit test). PR 2 #466: rule in extraction/text.py, numbered items need a run of two (lone "1." stays paragraph, German dates safe), TITLE_SHARE 0.6, four known-errors rows leave, en/de floors rise.
- D-764 (18 Nov 20:48Z): B2 plan plans/textprep-batch-b2-plan.md APPROVED. PR 1 #445+#449, PR 2 #448. AC-445.2 read as fuzz445 (a)=0 and (b)=0 apart from one residual ("<" glued to a removed link across a hidden run), accepted and filed; no runner change. #449 raised mass number before "K" → superscript digits, plain "40K" stays "thousand". #448 cue: marks removed only after an author line; three regression rows and 11 parametrised cases gain an author line. C2: no corpus snapshot change.
- B4 (20:48Z): #555 docs PR green at 8d9d81b (closes #522 #526), review thread started.
Merge note (18 Nov 20:49Z): #555 docs B4 MERGED f919d81 (pinned 8d9d81b, 1 round, 0 findings; closes #522 #526; critical). B4 DONE. Out of scope: CLAUDE.md item 2 lane list omits web and docs → issue to be filed by the review thread (docs lane, next docs batch).
- D-765 (18 Nov 20:53Z): rules 1.4.7: execution_lanes gains web and docs (six lanes, matching practice and LANE-02 use); lane_mapping_note rewritten. #560 (CLAUDE.md item 2 lane list) precondition met; #560 itself goes to the next docs batch.
- #541 isolate.yml run on main: WebKit Linux 40/40, macOS 40/40 -> no quarantine; B8 fix not needed unless it recurs; planning thread resolved (20:50Z)
- B1 review thread started 20:57Z (Opus high): #556 (#485) first, then #559, then #562 when green. Scratch branch ci/isolate-485 added to Colin's delete list.
- B3 review thread started 21:04Z (Opus high): #558 (#529 #535) c27ce9d, #561 (#466) 3836204, both ci:full green. #557 (German time before date, second-run drift, pre-existing) filed by B3 → textprep B5 list.
- B1 review round 1 (21:08Z): #556 APPROVED 0 findings, merge pending one allowed security-job re-run; #559 CHANGES REQUESTED 1 must-fix (angle wrap); #562 Content change additive (Page.unmapped last field, default omitted) → B3 PR 2 unblocked (C1 met).
- #556 (#485 isolate.py Windows pipe fix, critical) MERGED d2ffcac 21:09Z, pinned 6ca1f02; #485 closed.
- B1 review 21:17Z: #562 round 1 CHANGES REQUESTED 2 must-fix (font copy before map-error check; three test groups); #559 round 2 APPROVED at 41a1a44, merge when Linux CI green.
- #559 (#537 #543 turned pages + spread crop boxes, non-critical) MERGED 56d937f 21:18Z, pinned 41a1a44.
- 21:25Z: flate-bomb test (un-quarantined by #556) failed once on Windows in #561's ci:full run 44399793442 (OSError WinError -536870904). B3 re-runs once; B1 impl checks the log; recurrence → B1 re-quarantines Windows same day and reopens #485.
- D-766 (18 Nov 21:27Z): flate-bomb Windows failure 0xE0000008 is a code cause (PDFium PartitionAlloc OOM exception reaching ctypes before the memory watch), not the #485 pipe bug; B1 fixes it in a small critical PR (child maps the winerror to MEMORY_EXIT). Until merged, this test failing alone on Windows is pre-existing (D-731) and does not block other PRs or trigger an MRG-04 revert of #556.
- #552 (per-project folders PR 2, critical) MERGED 8622f85 21:27Z, pinned 5c9bec0; #469 closed. PR 3 (#470 removal) opens next in the app lane.
- 21:32Z: D-766 fix is PR #568 (lane:extraction, critical), ci:full running; #562 round 1 fix 38b7717 to review.
- #558 (#529 #535 layout B3 PR 1, critical) MERGED c51e846 21:32Z, pinned 8f147ce; #529 #535 closed.
- #562 (#442 part A, unreadable-font detection, critical) MERGED 215405c 21:46Z, pinned b88c7e2; #442 stays open for part B (B7). #568 (D-766 fix) approved in code, waits on AC-485.2 proof (40 isolated Windows runs x2 tests + 3 full Windows runs).
- D-767 (18 Nov 22:20Z, Decided (Claude)): #574 (post-merge defect from #562: Page.__post_init__ rejects unmapped > characters, textprep _read_in_place builds a subset page with replace() and keeps unmapped, so table-figure-notices fails on glyph-number pages) is fixed at once in a small critical PR in the extraction lane (lane:infra). Criteria as the B1 audit recommends: core checks only unmapped >= 0; extraction's tests keep the "unmapped <= characters" bound; a regression test covers _read_in_place on a page with unmapped > 0 and a captioned block; corpus unchanged. Reviewer: the B1 review thread (Opus high, critical rules). Review lesson added: for a new core invariant, grep every replace(<dataclass> in src/ for consumers.
- D-768 (18 Nov 22:20Z, Decided (Claude)): CHANGELOG. From now on every lane PR with a user-visible change adds an Unreleased line (reviewers check it). Missing lines for #556/#568, #559, #558, #561 go into the #574 fix PR; the line for #552 and #470 goes into #569.
- D-769 (18 Nov 22:23Z, Decided (Claude)): #574 plan plans/issue574-unmapped-bound-plan.md APPROVED as written (core refuses only unmapped < 0; _read_in_place unchanged; strict regression tests for captioned table, figure, formula; extraction bound test incl. turned page; five D-768 CHANGELOG lines; no snapshot or golden updates).
- D-770 (18 Nov 23:40Z, Decided (Claude)): #569 (#470 removal, critical) MERGED 5a605e5 after round 3; per-project folders batch complete (#532 #552 #569). Per the batch plan (D-761 step 3) B7 app (#442 B, #187, #493, #544) and B8 web (#293, #534, #541) start side by side; both plans must list files and stay disjoint (B7: web/documents.py, app/job.py, output/write.py, web strings; B8: web/player.py, web/api.py, templates, static/player.js); each plan waits for coordinator approval (critical: #493 CRIT-02, #293). Review threads start when each batch's first PR is green.
- D-771 (18 Nov 23:45Z, Decided (Claude)): B8 plan plans/web-batch-b8-plan.md APPROVED as written: one critical PR (#293 + #534 comment), route /api/v1/documents/{id}/figures/{block}/{n}, crops in the isolated child, cache in the project data folder under store.unchanged, 64 MB cap. Q1 no Markdown image in this PR (AC-293.2 narrowed, follow-up issue v1.2.x); Q2 no images for CLI jobs (follow-up issue); Q3 JPEG/PNG only, SVG never (follow-up for GIF/WebP); Q4 caps as written. Extraction touches allowed under D-756 (lane idle). #541 closes as met once the PR's three browser legs are green (80/80 counts in the comment).
- D-772 (18 Nov 23:47Z, Decided (Claude)): B7 plan plans/app-batch-b7-plan.md APPROVED as written, Q1 PDF only: PR 1 #442 B + #187 (stop before voices when unreadable pages hold more than half the characters, D-762 rule; report key only when set, no golden moves), PR 2 #493 + #544 (names decided before work; probe only for names with post-Unicode-3.2 code points; CRIT-02 guarantee as stated). B7/B8 file lists confirmed disjoint except CHANGELOG.md and tests/unit/pdf_maker.py (append-only; second to land merges main).
## D-773 (19 Nov 01:20Z) B7 and B2 complete; B5 starts
- App batch B7 done: #577 ee02e56, #583 9333ce0, main green, light audit clean (plans/audit-app-batch-b7-2026-11-19.md). App lane idle; both app threads resolved.
- Textprep batch B2 done: #572 0a72357, #585 ad6b94f, main ad6b94f. B2 review thread does the B2 light audit (plans/audit-textprep-batch-b2-2026-11-19.md), then is resolved.
- B5 "German readings" (#536, #483, #527, plus #557 from the B3 audit) starts now in a new textprep implementation thread per plans/next-batches-2026-11-18.md: plan first (critical rows: regression rows en + de), coordinator approves the plan, review Opus high. B6 waits for B5 (shared textprep files).
- B5 and web B8 are disjoint (textprep vs web); CHANGELOG.md is the only shared file, handled by merge main (D-768).

## D-774 (19 Nov 01:27Z) B5 plan approved
- plans/textprep-batch-b5-plan.md approved as written: one critical PR for #536 #557 #483 #527 from ad6b94f; readings as chosen (#557 "dritter Mai" both runs; #527 two-glyph arrows joined, "(I − P)−1" as printed with the row's goal naming the voice's "minus one"); #483 single-word period list with structural cues.
- Conditions: the corpus script diff (every document, figures on and off) is listed in the PR; the review checks every new row against "rows must not lock in wrong readings"; F1–F3 filed after approval with v1.2.x proposed.
- Review: new textprep B5 review thread, Opus high, when Linux CI and ci:full are green.

## D-775 (19 Nov 02:30Z) B8 complete
- Web batch B8 done: #582 merged 678fe3c (pinned ba33026) after 3 rounds, main green, light audit clean (plans/audit-web-batch-b8-2026-11-19.md); #293 #534 closed, #541 closed as met; follow-ups #579 #580 #581 #587 #596 (v1.2.x proposed). Web lane idle; both web threads resolved.
- Remaining open lane: textprep (B5 #593 in review, then B6). No new lane starts until B5 merges unless a new batch plan is approved.

## D-776 (19 Nov 02:40Z) Next batches B9–B17 approved; B12 PR 1, B16, B17 and Dependabot start
- plans/next-batches-2026-11-19.md approved: batches B9–B17 as grouped; the §2 criteria (AC-175.1–3, AC-292.1–3, AC-249.1–2 narrowed, AC-281.2 amended, AC-381.1–4 from the fix list, #329 numbers before bound) are approved under PLAN-04.
- Start now, idle lanes: B17 web (#299 #407 #381, non-critical, Opus medium), B16 app (#186 #207, non-critical, Opus medium), B12 layout PR 1 (#281 #283 + the #284 decision; PR 2 #282 after its route is chosen). Conditions C3 (B17 adds no web/strings line; B16 does not touch app.js) and the AC-281.2 rule (no regression row while a textprep PR is open) hold.
- Dependabot #513 → #515 → #514 → #512, one at a time, in one infra review thread (Opus high, critical: uv.lock/pyproject): update branch, Linux CI (ci:full for #514 and #512), merge; #512 only when no browser PR is in review; THIRD_PARTY_LICENSES.md version cells go into the next docs PR. Colin's release-time Dependabot check stays his.
- Textprep order B5 → B6 → B9 → B10 → B11; B13, B14, B15 wait as the plan's §4 says. §5 items (#178, #220, #249 narrowing, #284 closure, #468 truth check, #442 p3) go to Colin in the next catch-up.

## D-777 (2026-11-19 03:40Z) B14 plan approved as written (extraction-batch-b14-plan.md)
- q1 vendor CPython 3.13.18 html/parser.py + _markupbase.py as src/sci2audio/extraction/htmlparser.py. Licence gate: PSF-2.0 passes (permissive, GPL-compatible, already accepted in THIRD_PARTY_LICENSES.md for dependencies). Conditions: PSF notice at top, new THIRD_PARTY_LICENSES.md row, verbatim copy and `ruff format` as separate commits so the review can diff against CPython. Follow-up: .claude/rules/licences.md to name PSF-2.0 among allowed licences in the next docs PR (hand/docs item).
- q2 folded white space does not start a line: approved (no golden moves).
- q3 MAX_MARKUP = 2,000,000 per book; q4 MAX_LINE = 4,000,000; q5 MAX_BLOCK = 4,000,000 before parsing: approved as measured. test_the_limits_are_the_decided_ones pins them.
- q6 fold #602 into the PR: approved.
- §6 follow-ups filed when the PR opens (v1.2.x). PR critical, Opus-high review; coordinator starts the review thread when the PR is green.

## D-778 (2026-11-19 03:44Z) B16 app done
- PR #598 (#186 #207) merged 7e68106, main green, audit plans/audit-app-batch-b16-2026-11-19.md clean, #605 deferred v1.2.x. App lane idle; no next app batch in next-batches-2026-11-19.md.

## D-779 (2026-11-19 03:47Z) B5 textprep done, B6 starts
- PR #593 (#536 #557 #483 #527) merged b32612d after round 3; follow-ups #588–#592, #594 #595 #597 #606. B5 review thread audits (plans/audit-textprep-batch-b5-2026-11-19.md).
- B6 "Sentence cutter" (#479 #482 #533, next-batches-2026-11-18.md B6) starts now: plan first (critical: #479 regression row and the sentence gate), one PR, Opus-high review. B3 PR 2 and B5 are merged, so its known-errors.toml dependency is clear. B13 waits for B6 and B12.

## D-780 (2026-11-19 04:02Z) B6 plan approved as written (textprep-batch-b6-plan.md)
- #479 same-label rule `_label_again` beside `_after_label` (structural cue, not a longer list); #482 rank 5 "space inside a reading", bracket penalty +6, readings found from the steps' own tables; #533 all seven mutants get a rule-named test, literal 40 instead of the MIN_PIECE import.
- Conditions: rows written first and failing on main; corpus utterance diff main vs branch on both runs listed in the PR body (expected none); SECOND_RUN_CUT_EXCEPTIONS entries each carry the reason; hand-mutant run of the new code in the PR body; F1–F3 filed (v1.2.x) when the PR opens.
- One critical PR, Opus-high review, final round ci:full/mutation/nightly seeds.

## D-781 (2026-11-19 04:05Z) B17 web done; B12 PR 2 and Dependabot #512 released
- PR #601 (#299 #407 #381) merged ff7bf8d after 2 rounds; audit by the B17 review thread pending. Web lane idle after the audit.
- B12 PR 2 (#282) starts from ff7bf8d (player route free); Dependabot #512 proceeds (no browser PR in review).

## D-782 (2026-11-19 04:08Z) B14 PR #609 to review
- PR #609 head 37ec25d, ci:full green, branch frozen; review thread started (Opus high, critical). Addition beyond plan (navigation document counts toward MAX_MARKUP, outline dropped past it, D-311) left to the reviewer. Follow-ups #607 (plain-text paragraph bound) #608 (NCX bound) filed, v1.2.x proposed.

## D-783 (2026-11-19 04:22Z) MAX_TAG for #609 (review round 1 must-fix)
- markup.MAX_TAG = 1,000,000 characters per start or end tag (corpus longest 272; one 8 MB tag cost 1.27 GB in the parser's tag regex). Over the limit: TooMuchText with its own message, same as the other #329 limits; pinned in test_the_limits_are_the_decided_ones; a test that an over-limit tag is refused with a tracemalloc bound; CHANGELOG line names the tag bound too. Fits in #609's round 1 fix commit.

## D-784 (2026-11-19 04:24Z) Main green again
- MRG-04 fix PR #610 (web #407 tests write bytes) merged by the B17 reviewer; #601 stays. Dependabot #512, B12 #611 and B14 #609 released to merge on green main.

## D-785 (2026-11-19 04:38Z) B12 layout done
- PR 2 #611 (#282) merged e658c17 after 1 round; PR 1 #600 a9dad14. Follow-ups #599 #603 #604 #612; #284 to Colin to close. B12 review thread audits plans/audit-layout-batch-b12-2026-11-19.md. B13 waits only for B6 now.

## D-786 (2026-11-19 04:38Z) B6 PR #616 to review
- PR #616 head a1f030b green on all three systems, frozen; review thread started (Opus high, critical). Deviation (6 cuts move with "Tables and figures" off, same on both runs) left to the reviewer. Follow-ups #613 #614 #615 filed, milestone 7.

## D-787 (2026-11-19 04:50Z) — Owner closures (Colin, cmsg_...JfhZvQZEG748eHh1iJbGQA)
- #178 close as met; #220 close; #284 close. Thread "Close three decided issues" executes with the owner message attached.

## D-788 (2026-11-19 04:53Z) — #442 part 3 scheduled (Colin: "lets do part 3")
- Glyph-ID text recovery for no-Unicode fonts becomes extraction batch B18, after B14 and B15. Plan first: plans/extraction-batch-b18-plan.md (thread "Plan glyph-ID text recovery for unreadable fonts"), coordinator approves before implementation; critical-PR status decided in the plan.

## Status notes 04:55Z
- D-787 executed: #178 closed completed, #220 and #284 closed not planned (04:54Z), thread resolved.

## Status notes 04:53Z
- B6 #616 review round 1 requested changes (must-fix: fractions/ratios, two-word units, statistics terms cut inside readings; "12/20" regression vs main; probe 83/300 vs 168; should-fix 18x slowdown, 7 untested mutants). Round 2 is final.

## D-789 (2026-11-19 05:25Z) — B18 plan approved (plans/extraction-batch-b18-plan.md, #442 part 3)
- q1–q9 approved as recommended: recovery in the PDF child per document; own bounded TrueType reader (fontTools scripts-only); reference drawings from Tinos, Arimo, Cousine, Caladea (Apache-2.0) and Carlito (OFL-1.1, drawings are output not the font; THIRD_PARTY_LICENSES.md row per family, licences confirmed at source in the PR); shape matching approach C with refusal thresholds pinned in the PR; core field Page.recovered (critical); D-402 amended for fonts with no Unicode source only (flagged to Colin); PR 2 app lane inside B18; fixtures from Apache-2.0 subsets only; §6 as follow-up issues.
- Conditions: the close-call step (c/e) must be proven on the fixture with the word step patched out failing; if it does not settle c/e, the bigram fallback, reported in the PR body. AC-442.13 is a measure, not a merge gate. PR 1 critical, Opus high; PR 2 Opus medium. Order: after B15 merges. Sub-issue #618 filed 05:23Z (no milestone; Colin sets it by hand). Plan thread resolved.

## D-790 (2026-11-19 05:58Z) — B6 done; B9 and B13 start
- PR #616 merged b6355cc 05:53Z (three rounds; round 3 added the "Abs. 2. Abs. 3" test and boundary cases), closes #479 #482 #533; follow-ups #613 #614 #615 #617 #619 (v1.2.x). B6 audit by the review thread → plans/audit-textprep-batch-b6-2026-11-19.md.
- B9 textprep (#414 #415 #402) and B13 layout (#156 #238; #322 #354) implementation threads started, plan first; coordinator approves each plan.
- Hand-step guide posted to Colin 05:57Z (branch deletes, milestone 7 → v1.2.x, follow-ups → v1.2.x, #618 his call v1.2 or v1.2.x).

## D-791 (2026-11-19 06:06Z) — B9 plan approved (plans/textprep-batch-b9-plan.md)
- One PR for #414 #415 #402, critical, Opus high. Decision A: a run of two or more citation brackets joined by commas and a last "and"/"und" is one citation (aside goes whole, needed reads "references 1, 2 and 3"); a needed two-item list reads "references 1 and 3" (D-668 row line 4 changes); comma-only lists included; aside "and" pairs keep D-668 (F3 ruling later). Decision B: one-item nests "((Smith, 2019)) is cited" read "Smith is cited" (D-605 "as before" superseded for this case; three pinned tests change). #402: join word before a removed last link goes when the word before is a capitalised name; German noun limit pinned and documented. Follow-ups F1 F2 F3 (F4 if needed) → v1.2.x.

## D-792 (2026-11-19 06:18Z) — Reporting rule: only what is open now
- Colin (06:17Z): "Never tell me what i have to do later. I only want to know what is open at the moment." Posts to Colin list only items open right now; no "later", "after merge" or "still yours later" items. Such items stay in memory/plans and are raised only when they become open.

## D-793 (2026-11-19 06:24Z) — B13 plan approved (plans/layout-batch-b13-plan.md)
- Three PRs: PR 1 #156 #238 (critical, Opus high, starts now; furniture unchanged on all 8 papers, no golden moves, NOT_YET_COLUMNS loses its one entry per plan 238.3; the earlier "maass p3 keeps NOT_YET_COLUMNS" wording was a coordinator transcription error, corrected 07:19Z); PR 2 #322 (critical, liu golden at two sites; starts after B9 merges under LANE-02, regenerate from main, never hand-resolve; liu list test to find the list by its first entry); PR 3 #354 (not critical, Opus medium, after PR 1, does not wait for B15; B15 decides #355 on memory alone).
- AC-322.1 example corrected to the rendered page: "−egsgν 12π me m∗" (numerator first, as #202); noted on the issue.
- B13 touches no sentence-set file, so B11 PR 2 (#468) no longer waits for B13.

## D-794 (2026-11-19 06:48Z) — #620 to critical review
- B13 PR 1 #620 (#156 #238) head 1134ed5, Linux CI and ci:full green on first push; review thread started (Opus high). PR 3 #354 ready on layout/issue354-figure-speed e1cf449, opens after #620 merges; PR 2 #322 after B9 #621 merges.

## D-795 (2026-11-19 06:59Z) — Colin: ship to testers first (cmsg_011gr2YyZJypGaV6NbzgSXQE4x4sXTrVCmWBkZ4DBnKEMY "lets do it like that")
- Scope change by Colin (06:54Z): a perfect product is not the goal; get to the point where others can install it and give feedback.
- Only the three batches already running finish: B9 (#621), B13 (#620, PR 3 #354, PR 2 #322), B14 (#609).
- Queued batches B10 (#379 #405 #150), B11 (#468 + its code-line and formula-notice issues), B15 (#355 #367 #356), B18 (#618, #442 part 3) and all v1.2.x issues move to a new milestone v2. The B18 plan stays on file for v2.
- Next batch: installers for macOS, Windows and Linux with app window and smoke tests (#215, #13), then tag and publish (publishing parked by D-721 resumes with it). Critical (packaging/release), plan first, Opus high, app/release lane.
- Plugin interface (#216, #203) and update check (#217) stay out of that release.
- A re-scoping thread creates the milestone, moves the issues (Colin's message attached for the milestone guard), and writes plans/roadmap-share-first-2026-11-19.md.

## D-796 (2026-11-19 07:04Z) — Quarantined tests are release preconditions
- Milestone v2 (#10) created; 73 issues moved (51 from v1.2.x, 11 from v1.2: B10 #379 #405 #150, B11 #292 #249 #468, B15 #355 #367 #356, B18 #618 + #442; 11 from v1.0.1). v1.2 holds only B9, B13, B14 issues. #602 stays in v1.2 (B14).
- Ruling: the standing rule (a quarantined test is fixed before the next release) stands. #525 (Windows flake) goes to v1.4 and into the installers plan before the tag. #437 is not quarantined (reported-only WebKit leg, waits on #502) and stays in v1.3. Result: v1.4 20 issues, v2 72.

## D-797 (2026-11-19 07:11Z) — Installers plan approved (plans/release-installers-plan.md)
- PyInstaller bundles + pywebview window (optional `window` extra); macOS .dmg ad-hoc signed Apple Silicon only; Windows Inno Setup per-user installer, uninstall never touches user files; Linux AppImage. Voice files not bundled. SHA256SUMS, build attestations, GPL source tar for FFmpeg and espeak-ng.
- Smoke tests #13: reusable installers.yml (+ label ci:installers), three systems, real install, script + English and German speech, Linux offline check in a network namespace, real window on macOS/Windows, Windows uninstall check; publish only when all pass.
- Four PRs: PR 0 #525 fix (quarantine lifted), PR 1 window, PR 2 installers + workflows, PR 3 version, CHANGELOG, install docs, tester report form. All critical (packaging/release/CI), Opus high review, author ci:full before review.
- Open questions: q1 L1 Linux browser mode with Quit + idle stop (#215 AC-2 amended for Linux); q2 voices not bundled, consent download; q3 version 1.4.0; q4 no paid certificates, SignPath/notarisation → v2; q5 release-checklist hand items (listening test, screen-reader pass, M4 speed) skipped for this tester release as under D-721, mutation + ZAP via workflow dispatch with results in the release issue; q6 the review thread pushes the tag on the coordinator's go after PR 3 merges; q7 fallback to actions/setup-python 3.12 for installer builds only if PyInstaller cannot freeze the uv-managed Python (D-378 reason gone once #609 merges).
- Colin's only hand step: the pypi deployment approval tap (told to him when the run waits).

## D-798 (2026-11-19 07:34Z) — Installers ship their own audio-only FFmpeg (option B)
- imageio-ffmpeg's bundled FFmpeg is a full BtbN GPL build with ~70 linked libraries; redistributing it in installers would need the complete corresponding source for all of them (GPL-3.0 §6), which the planned source tar cannot provide.
- Decided: the installers workflow builds a minimal audio-only FFmpeg (LAME MP3, native AAC, ipod/M4B muxer, WAV input, cover images) from pinned source tarballs per system, LGPL with LAME; IMAGEIO_FFMPEG_EXE points at it, imageio's binary is left out. Source tar = FFmpeg + LAME + espeak-ng + build script. Fast output tests and the speaking smoke test run against this build. PyPI installs unchanged (D-120). Option A (incomplete source offer) rejected.

## D-799 (2026-11-19 07:41Z) — Release PR 0 #630 to critical review
- #630 (#525 fix, quarantine lifted; 40/40 alone + 4 full-suite runs on Windows) head 699af2c, three-system CI green. One release review thread (Opus high) started; it reviews all four release PRs, pushes tag v1.4.0 only on the coordinator's go after PR 3, then writes plans/audit-release-installers-2026-11-19.md. PR 1 #631 (window) open at ec17b3a, ci:full running; PR 2 in progress (minimal FFmpeg 9.0.2 + LAME builds on Linux, 2.8 MB).

## D-800 (2026-11-19 07:46Z) — #630 merged
- Release PR 0 #630 merged 12f85a7 after round 1, no findings; #525 closed, no quarantined test remains. Review thread continues with #631.

## D-801 (2026-11-19 07:53Z) — #621 to critical review
- B9 PR #621 (#414 #415 #402) head efae3c7, three-system CI green, 41/41 hand mutants killed, quadratic nested-bracket cost fixed with a work-counting test; follow-ups #622–#629 on v2 (#629 pre-existing on main). Review thread started (Opus high); B13 PR 2 #322 waits for its merge.

## D-802 (2026-11-19 08:03Z) — B14 done
- PR #609 merged 805da4e after three rounds; #175 #328 #329 #602 closed. Follow-ups #607 #608 → milestone v2 (D-795). Extraction lane closes for this release; no B15/B18. B14 review thread closed out 08:10Z: ledger written, audit plans/audit-extraction-batch-b14-2026-11-19.md 0 blocking findings, #607 #608 #632 #633 on v2; both B14 threads resolved.

## D-803 (2026-11-19 08:05Z) — #631 to critical review
- Release PR 1 #631 (app window, #215 part 1) head ec17b3a, Linux CI + ci:full green (one rerun: pip-audit network timeout). Handed to the release review thread. PR 2: Linux AppImage 444 MB works end to end offline with the minimal FFmpeg; macOS and Windows parts next.

## D-804 (2026-11-19 08:18Z) — #620 merged
- B13 PR 1 #620 merged bf25945 after two rounds (round 2 clean; main merged in for the CHANGELOG conflict, diff unchanged); #156 #238 closed. PR 3 #354 opens now (Opus medium review); PR 2 #322 after B9 #621.

- D-805 (19 Nov 09:02Z): PR #621 (B9) handed to the B9 review thread for round 2 FINAL at head 747edd7, three systems green; two fix commits accepted as a deviation because the second only removes an unreachable check and adds mutation-found test rows.
- D-806 (19 Nov 09:03Z): PR #631 (app window) handed to the release review thread for round 2 FINAL; one fix commit covers all round 1 findings plus a macOS self-test hang found by the installer test run; reviewer pins to the current head.

- D-807 (19 Nov 09:14Z): PR #631 (app window, installers PR 1) MERGED e45d655 after round 2 by the release review thread; all 21 planted mutants caught, three systems green; report plans/review-pr631-round2.md. Next: PR 2 #635 once the author's three-system runs are green.

- D-808 (19 Nov 09:37Z): PR #621 (B9 textprep) MERGED 9f2cbaa after round 2 (no must-fix); reviewed head f5b5ad6 = 747edd7 + update-branch from main because #631 touched CHANGELOG, diff unchanged; follow-ups #634 #646 on v2. B13 PR 2 #322 released to start from main 9f2cbaa.

- D-809 (19 Nov 09:47Z): B9 textprep batch DONE: #621 merged 9f2cbaa, main CI green on three systems, #414 #415 #402 closed, ledger line appended, audit plans/audit-textprep-batch-b9-2026-11-19.md 0 blocking (notes on #634, #626); both B9 threads resolved. Textprep lane closed for this release (D-795).

- D-810 (19 Nov 10:07Z): B13 PR 2 #647 (closes #322, critical, liu goldens 133 → 129 blocks) head 05d76f9 handed to the B13 review thread for round 1; Linux CI + ci:full green on three systems; #322 criterion me/m∗ swap corrected on the issue; page-break gap #648 on v2.

- D-811 (19 Nov 10:16Z): B13 PR 3 #645 (#354, not critical) MERGED fac140c after round 2; exact segment-tree sweep, groups match main on 9,000 fuzz pages; test gap #649 on v2; report plans/review-pr645-round2.md. #647 round 1 under way.

- D-812 (19 Nov 10:26Z): Colin's ask (10:24Z cmsg_011gr2YyZJypGaV6NbzgSXQE2QA8NZrgT6pqsdgWp5AGdc): bracketed page pairs like (121/120) in German academic texts are page references → new issue #650 on v2, lane:textprep (no existing issue covered it; #455 and #131 are different). Criteria: follows the citations setting (dropped by default, else "Seite 153 beziehungsweise 150" / "page 153, or 150"), never a fraction, ratio or date; real fractions unchanged. Thread resolved.

- D-813 (19 Nov 10:27Z): Colin's ask (10:27Z cmsg_011gr2YyZJypGaV6NbzgSXQEM2v4tG7T4sa6iET5mmq9MN): playback speed and generation speed adjustable in 0.01 steps, usability first → thread "Make speed controls adjustable in 0.01 steps" (design plans/speed-fine-control-plan.md, issue on v1.4, one non-critical PR, web/app lane). Put on v1.4 because Colin asked during the tester push; he can move it to v2.

- D-814 (19 Nov 10:32Z): Colin's ask (10:31Z cmsg_011gr2YyZJypGaV6NbzgSXQEWXarSDDCzP2bTjkpEt3WeB): a single unspoken character like "-" must never be a separate block, fix in v2 → issue #652 on v2, lane:textprep (links #571, #623); joins neighbour or dropped, script and read-along keep the same block count, player steps over such blocks in older books. Thread resolved.

- D-815 (19 Nov 10:34Z): Colin's ask (10:33Z cmsg_011gr2YyZJypGaV6NbzgSXQEGpuNPrE3txSRpnBcXQNAfs): "Menschen/Gruppen" spoken as "Menschen und Gruppen", same rule in English, put in v2 → thread "Speak word slashes as and" files a v2 issue (lane:textprep), no fix now.

- D-816 (19 Nov 10:36Z): word/word slash → "und"/"and" filed as #653 on v2 (lane:textprep; exclusions: numbers, dates, units, URLs, paths, gender forms, and/or; open question ja/nein → "oder"). Colin's second page-reference form "(1998, 195; 2019, 150)" (10:35Z cmsg_011gr2YyZJypGaV6NbzgSXQE7cMHbzAapmS8GhBki9Vo1z) goes onto #650 as a second pattern.

- D-817 (19 Nov 10:40Z): #13 AC-2 reading for installers PR #635: hosted Windows runners run elevated, an elevated WebView2 ignores WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, so no debugging port; Playwright (with axe + Quit) runs against the installed Linux AppImage and Windows keeps the window self test. Windows Playwright = #654 (v2); SmartScreen switch side effect = #644 (v2, fix via IsReputationCheckingRequired noted in PR body).

- D-818 (19 Nov 11:00Z): B13 PR 2 #647 (#322, critical) MERGED fb48c1c after 2 rounds; B13 layout batch complete (#620 bf25945, #645 fac140c, #647 fb48c1c); #648 on v2. B13 impl thread resolved; review thread owes ledger line + audit plans/audit-layout-batch-b13-2026-11-19.md, then resolves. Layout lane closed for this release (D-795).

- D-819 (19 Nov 11:14Z): speed controls PR #655 (#651, v1.4, lane:web, not critical) head 524fb94 Linux green → review thread "Review the speed controls PR" started (Opus medium, one round, squash-merge on approval). #649 moved to v2 by the B13 review thread.

- D-820 (19 Nov 11:18Z): installers PR 2 #635 (critical) head 7a60fc1 handed to the release review thread for round 1; Linux CI, ci:full (macOS, Windows) and ci:installers run 44507750405 all green; sizes dmg 384 MB, setup.exe 340 MB, AppImage 443 MB; branch frozen. PR 3 opens as a draft stacked on #635.

- D-821 (19 Nov 11:24Z): #635 round 1 changes requested (plans/review-pr635-round1.md): Windows install into Documents\sci2audio would let the uninstaller delete audiobooks; Torch libraries bundled twice plus test programs (~530 MB); AppImage runtime LGPL source not yet offered; three licence notices missing; 11 of 32 mutants untested. FFmpeg audio-only LGPL, source archive exact, no voices, workflows locked down all confirmed. Fix commit then round 2 FINAL. PR 3 = #656 (draft, checks running).

- D-822 (19 Nov 11:42Z): speed controls PR #655 (#651, not critical) MERGED 28d65ed after one round (two test items fixed in 7171448); plans/review-pr655-round1.md, answer plans/answer-pr655-round1.md; main CI running at merge time. Impl thread resolved itself 11:35Z.

- D-823 (19 Nov 13:04Z): PR #635 round 2 FINAL handed to the release review (head 2dccc2a; fix commits b85201d 6066504 2dccc2a; sizes Windows 277 MB, macOS 381 MB, Linux 429 MB; mutants all killed per author); then PR #656 (head 9f48307) to the same review; tag v1.4.0 only on my go after #656 merges.
- D-824 (19 Nov 13:10Z): PR #635 installers MERGED bed21bd (round 2 FINAL passed, plans/review-pr635-round2.md; closes #215 #13; verified via ls-remote). PR #656 round 1 started on head d9c4b1f (three-system CI running). Merge note to Colin held while he is away.
- D-825 (19 Nov 13:12Z): PR #656 round 1 changes requested (head d9c4b1f; plans/review-pr656-round1.md): F1 bundled torch 2.15 needs macOS 14, so LSMinimumSystemVersion, install docs, CHANGELOG and README say macOS 14 or newer; F2 tester form points to the start-up log line and --version instead of the privacy page. Fix list went to the author directly; round 2 FINAL needs Linux CI, ci:full and ci:installers on the fix commit.
- D-826 (19 Nov 14:07Z): PR #656 round 2 FINAL handed to the release review (head c5edccf; F1 macOS 14 floor in spec, docs, CHANGELOG, README; F2 tester form version hint; CI green on all systems per author). Tag v1.4.0 only on my go after the merge.
- D-827 (19 Nov 14:09Z): PR #656 MERGED 5c18f8c (round 2 FINAL passed before my hand-off landed, plans/review-pr656-round2.md; verified via ls-remote). Installers batch complete (#630 #631 #635 #656). Go given to the release review to push tag v1.4.0 on 5c18f8c; PyPI approval tap stays with Colin; release audit + thread resolution follow. Impl thread resolved.
- D-828 (19 Nov 14:11Z): tag v1.4.0 NOT pushed: git push of the tag got HTTP 403 and the review thread's permission guard denied the API route; thread stopped and stays open. Only Colin can clear it (push the tag from his clone on 5c18f8c, or approve in the thread). Release audit plans/audit-release-installers-2026-11-19.md: nothing blocking. Posted to Colin when he is back (held while away).
- D-829 (19 Nov 14:50Z): Colin pushed tag v1.4.0 (083d0bc, on 5c18f8c) at 14:48Z; release run 44547770638 started, package build passed, installers building; review thread watches it to the PyPI approval step. Held merge summary posted to Colin 14:49Z.
- D-830 (19 Nov 17:12Z): sci2audio 1.4.0 RELEASED. Colin approved the pypi deployment; release run 44547770638 fully green (PyPI installs on 3 systems). GitHub release v1.4.0 (083d0bc on 5c18f8c): macOS dmg, Windows setup.exe, Linux AppImage, source archive (FFmpeg + LAME + espeak-ng), wheel, sdist, SHA256SUMS.txt; 1.4.0 live on PyPI (verified HTTP 200). Release review thread resolved. Posted to Colin 17:12Z with notify. No lanes active; next work starts only on Colin's ask (D-795 scope: v2 backlog).
NEXT FREE: D-831
