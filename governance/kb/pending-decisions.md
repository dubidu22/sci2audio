# Pending decisions — sci2audio

Decisions that are made but not yet in `decision-log.md`. One writer: the
coordinator. It adds an entry here at the hand-off where the decision is made,
with the next D-number, and removes an entry once it sees it in the decision
log. The KB thread reads this file and compiles it into the decision log on
its cadence (`ROLE-08`); it never edits this file.

Entry format, the same as in the decision log:

    ## D-<n> (<date>, owner | coordinator)
    What was decided, why, and what it supersedes.
    Owner message: "<the owner's words and their date>"   (owner decisions only, `KB-01`)

Until an entry is compiled it ranks just below the decision log (`authority`).

## Entries

## D-891 (2026-11-23, coordinator)

Outcome of D-890, which was compiled before it was known: #749 squash-merged as 1cbfbd2; main CI run 45139630420 green on Linux, macOS and Windows. Backup tag `governance-before-d874` at f12fe96 was pushed by Colin ("done", 2026-11-23T08:37Z), because the cloud proxy refused tag pushes (HTTP 403). The one-time merge is 6409f52, with both diffs empty. Decision-log PR #752 (0994f97) compiled D-834 to D-890.

Batch 004 audit (`plans/audit-batch-004.md`, 3cd4a3b): 0 blocking, 3 should-fix, 7 notes.
- F1, data: `merged:` filled in `ledger/prs/pr-741.yaml` (3fb4d1b) and `pr-721.yaml` (207ea14, release/1.4). Check: `ledger_tool.py check` fails on a PR entry without a merge record whose `(#N)` closes a squash subject on main or release/*. This goes into batch 005, slot A (lane:infra, critical).
- F2, data: `ledger/deferred/pr745-1.yaml` records S4 as planned in #747. Check: a round entry field `deferred: <n>`, and `check` fails when fewer `deferred/pr<N>-*.yaml` exist. Same batch-005 item as F1.
- F3: v1.4 stays open only for #731. Moving #731 to another milestone goes to Colin (ROLE-01).
- `stats`: `narrating-comment` regressed after #712's fix (seen again in #739), so it goes one step up the META-03 ladder: a lint check in batch 005, slot A.
- Owner PR #751 (ruleset 1.14.0, the claude.ai Project, Colin's "Yes, apply" 23 Nov) gets its critical review now that the lane:infra lock is free.

## D-892 (2026-11-23, owner)

#731 is closed as not planned, so the Fable advisor second opinion of PREF-01 is dropped. Colin chose "Close it as not planned" (2026-11-23T08:48Z) on the card "Move #731 (coordinator's advisor) out of v1.4 so v1.4 can close?", whose consequence read: "The Fable advisor second opinion (PREF-01) is dropped; that rule then needs a ruleset change."
- From now on the coordinator asks no advisor thread before a decision it puts to Colin.
- The PREF-01 text is removed by the next ruleset PR after #751 (META-01, batch 005, slot A), not inside #751, which is under review.
- With #731 closed, milestone v1.4 has no open Issue.

## D-893 (2026-11-23, coordinator)

Batch 004 is done (v1.4 has no open Issue). Batch 005 is composed as `plans/batch-005.md`. Slot A is #723 (critical, plan first), then #725 and #726. Slot B is #744, then the infra check PR (D-891 F1, F2 and narrating-comment, plus D-892's PREF-01 removal) once #751 has merged, then #724. #723 to #726 all carry acceptance criteria (PLAN-04). No dispatcher runs, so the coordinator asks the project for each thread (D-889).

## D-894 (2026-11-23, owner)

Work stops once batch 005 is finished. Colin: "stop working after this batch is finished." (2026-11-23T09:00:47Z). Batch 004 had closed before the message, so it is read as batch 005. The coordinator asked Colin once to confirm that reading, and he chose "Finish batch 005, then stop" (2026-11-23T09:35Z).
- `autonomy_horizon` becomes "until batch 005 is finished, then pause".
- Batch 005 runs to its end: its PRs, its audit, its decision-log PR and the batch report. #751, already in flight, finishes too.
- Then the coordinator sets `paused: true`, composes no batch 006 and starts no thread.

## D-895 (2026-11-23, coordinator)

Plan impl-723 (`plans/impl-723-plan.md`, f79a009, #723 LW-01) is approved as written, with 4.1 as recommended.
- The plan has two PRs, both risk:high. A (lane:output) splits `write_audiobook` into chapter, read-along and book parts, with byte-identical proof. B (lane:app plus one line in `web/tasks.py`) encodes each chapter right after it is spoken, closes #723, and starts only after A merges.
- 4.1: until #725, the web job passes `OutputSettings()` explicitly and keeps writing the M4B, so no web test changes. #725 removes that line when it adds the on-demand download.
- Accepted rule change: a killed or cancelled job keeps whole, recorded chapters (instead of all or nothing, D-119/D-160). Book-level files stay all or nothing. The five named fault tests change their assertion to the new rule and are renamed where "no file" no longer holds. This is a changed rule, not a weakened test: every one still asserts no partial file and no overwrite on the rerun, and the PR body lists each change.
- The CLI keeps writing the M4B with byte-identical output.
- Lanes: PR A (lane:output) runs alongside #744 (lane:voices) in the same execution lane. They share no files (LANE-02).

## D-896 (2026-11-23, coordinator)

Merge go for #751 (ruleset 1.14.0, the claude.ai Project, Colin's change), pinned to bf417b9 (`ledger/gos/pr-751.yaml`).
- Rounds: round 1 stopped on preconditions (no three-system run, behind main). Round 2 found 1 must-fix: the Project chat instructions had every thread opened by Colin, against D-889. The rewording is pinned by tests. Round 3 approved with 0 must-fix and 0 should-fix.
- Three-system run 45150607713 is green on that head.
- After the merge, Colin re-pastes the Project instructions from `governance/project_chat_instructions.md` (an owner hand step).
- The next ruleset PR (batch 005, slot B, item 2) also fixes the test comment that cites PREF-01 for "few clicks" (round 3 note).

## D-897 (2026-11-23, coordinator)

Merge go for #754 (PR A of #723, lane:output), pinned to e07c3f1 (`ledger/gos/pr-754.yaml`).
- Round 1 found 1 must-fix: the join byte test could not fail. Round 2 approved with 0 must-fix and 0 should-fix.
- Byte identity holds: 98 files across 12 inputs.
- Three-system run 45150916921 is green on that head.
- If the branch needs an update from main first, MRG-01's `updated_head` path applies.
- PR B of #723 starts after the merge.
Outcome: #754 merged as f1a9c1f. #751 merged as c63fc76.

## D-898 (2026-11-23, coordinator)

Merge go for #753 (#744, lane:voices, not critical), pinned to dae7c19.
- Round 1 approved with 0 must-fix and 0 should-fix.
- Three-system run 45144703459 is green.
- The coordinator gives this go because no dispatcher runs (D-889).
- Review note N2: a user with a non-ASCII Windows profile now gets a clear error but still cannot use Kokoro. Filed as an Issue for milestone Later (lane:voices): pass espeak-ng the 8.3 short path. It is an improvement inside the existing scope, not new scope.
Outcome: #753 squash-merged as 8965914 (#744 closed). impl-744 says it recorded the merge and did not run it.

## D-899 (2026-11-23, coordinator)

Plan impl-infra-b005 (`plans/impl-infra-b005-plan.md`, 9f7f074) is approved as written, as one critical PR for #756, #757, #758 and #759 (v1.5, lane:infra, risk:high).
- F1 (#756): `check` reads squash subjects from git, falls back to a `--subjects` file, exits 2 when it has neither, and counts only the last `(#N)`.
- F2 (#757): `deferred:` is required from this PR's number on and summed over a PR's rounds. Only the ledger README changes.
- Narrating comments (#758):
  - a strict change-history phrase list fails added comments in the PR check, and a fast test scans every comment and docstring;
  - the broad list stays a warning;
  - accepted limit: a comment that says what instead of why (#739 N2) has no word to match, so it stays a review finding. The PR body says so.
  - So `narrating-comment` counts as fixed only for change-history comments. If a what-comment comes up again, the next step is a design change in the review template, not another word list.
- PREF-01 (#759): the ruleset is regenerated to 1.15.0 through the governance skill on Colin's word in D-892, and the test comment is fixed.
- The trial gap on `prs/pr-753.yaml` is closed: impl-744 recorded 8965914. review-b005 fills `merged:` in `rounds/pr753-round1.yaml`.

## D-900 (2026-11-23, coordinator)

Merge go for #760 (ruleset 1.15.0 plus the ledger and narration checks, closes #756 to #759), pinned to a25a67e.
- Round 1 approved with 0 must-fix and 0 should-fix.
- Every ruleset file changes exactly two lines: the version and PREF-01. The D-882 and D-849 texts are byte-identical to main.
- ci:full run 45160343600 is green.
- After the merge, every new round entry carries `deferred:`.
Outcome: #760 merged as e3a328e; main CI 45164259001 green on three systems.

## D-901 (2026-11-23, coordinator)

Merge go for #761 (PR B of #723, lane:app; closes #723), pinned to a839955.
- Round 1 found 1 must-fix (B1): a stop between the hash record and the rename left a file that the record no longer vouched for.
- The fresh thread impl-723b fixed it: the new hash stays pending until the rename is done, and a new kill test covers the window.
- Round 2 approved with 0 must-fix.
- Every changed test follows from the D-895 rule and none of them checks less.
- Three-system run 45172191271 is green.

## D-902 (2026-11-23, coordinator)

Plan impl-724 (`plans/impl-724-plan.md`, 69ccf6a, #724) is approved with three rulings.
1. Option A: `app/audio.py` writes `document.json` before the first chapter, and `audio.json` still comes only at the end. The PR is lane:web plus lane:app.
2. It counts as critical (risk:high). It changes when the job runner writes a file into the job folder that the D-895 rule governs, and `app/audio.py` was critical in #723. So it needs a fault test: a kill after `document.json` and before the first chapter, after which the rerun needs no overwrite. The review is on Opus 5.5 high, with ci:full before review.
3. LANE-02: #724 goes first. #725 and #726 share web files with it, and #726 also `app/audio.py`, so their code starts only after #724 merges. impl-725 may write its plan now, on top of #724's plan.

## D-903 (2026-11-23, coordinator)

Plan impl-725 (`plans/impl-725-plan.md`, fd1fd5c, #725 and #726) is approved as four PRs in order:
1. output (critical): the whole book as one M4B or MP3 with chapter marks;
2. app and CLI (critical): build that file on request, add chapters later, `--keep-settings`;
3. web #725: the download dialog, which removes the D-895 line from `web/tasks.py`;
4. web #726: chapter states and Generate buttons on top of #724.

Choice 4.1, as recommended: a chapter's number comes from its place among the book's speakable chapters, not among the chosen ones. Chapters added later then need no renaming or re-encoding. A full-book export stays byte-identical. The only golden change is the MP3 track total of a partial run (n/12 becomes n/13). This is a technical choice that serves #726's accepted criteria, not new scope. The PR shows the snapshot diff and explains it.

No code is written until #724 merges (D-902). If the wait goes past the cache window, a fresh thread codes from the plan's handoff (THR-07).
Amended (2026-11-23T12:42Z): PR 1 (lane:output) shares no file with #724, so it started at once as #762 (impl-725b). PR 2 onward waits for #724.

## D-904 (2026-11-23, coordinator)

The plan-promised test `tests/unit/test_app_audio_chapters.py::test_the_laid_out_document_is_written_before_the_first_chapter_is_spoken` (impl-724 plan, D-902) is renamed to `..._is_playable` in #764 (PLAN-01). The promise is unchanged. `document.json` is written where the records are cleared, which is before the first chapter is playable. "Spoken" named the wrong moment. The governance check of promised tests reads the new name, and the plan notes the rename.

## D-905 (2026-11-23, coordinator)

Merge go for #764 (#724, lane:web plus lane:app, critical), pinned to 9d38cec.
- Round 1 approved with 0 must-fix. All 27 promised tests are present, and the D-902 kill test stops before chapter 1.
- Three-system run 45184320620 is green.
- WebKit (report-only): two tests each failed once and passed on the rerun and on main's nightly. That is not a second failure, so D-374 does not apply. `test_joined` stays on watch.
- Review note N2: `book_key` includes `planned`, which matters for #726 (PR 4 of D-903).
- After this merge, PR 2 of D-903 can start.
Outcome: #764 merged as eab9fb2; main CI 45202066107 green on three systems.

## D-906 (2026-11-23, coordinator)

Merge go for #762 (PR 1 of D-903, lane:output, critical), pinned to 16b6e7a.
- Round 1 found 1 must-fix: a book byte test that could not fail, the same kind as #754's M1.
- The META-03 step for that repeat: `quiet_edged_job` and `assert_joins_trim` are now shared in `tests/unit/output_helpers.py`.
- Round 2 approved with 0 must-fix. ci:full run 45202299756 is green.
- The merge waits until impl-725b fixes `prs/pr-762.yaml` (`fixes_kinds: vacuous-test`, `handback: done`) and the gate passes.
- Note: the flaky-watch line in `project-state.yaml` (889257c) was written by a worker thread after the coordinator's request was relayed. The content is right, but the file's writer is the coordinator (META-02); later edits stay with the coordinator.
Outcome: #762 merged as 51dd21d; main CI 45211348862 green on three systems.

## D-907 (2026-11-23, owner)

Colin asked for batch 005 to go faster. On a decision card in the project chat (about 16:35Z) he chose to start PR 3 of D-903 (#725 web) now, on top of #765's branch, rather than after #765 merges. The card text was not relayed, so this entry ranks without a quote (KB-01).
- impl-725c branches from #765's head and opens no PR while #765 is open.
- After #765 merges, it merges main into its branch (no rebase or force-push) and follows any API change from #765's review.
- PR 4 (#726) follows PR 3. review-b005 reviews both.

## D-908 (2026-11-23, coordinator)

Merge go for #765 (PR 2 of D-903, lane:app plus lane:cli, critical), pinned to adeba28.
- Round 1 found 1 must-fix: another book's version-1 record in a shared work folder was refused before the book check. It also had 2 should-fix (`--keep-settings` without the book check, `_pair_current` untested). All three are fixed.
- Round 2 approved with 0 must-fix. 1 should-fix is deferred to #767 (no test for re-reading the document when the kept language differs).
- ci:full run 45216903017: tests on ubuntu, macOS and Windows are green. The report-only WebKit markers test failed once (flaky watch, D-374 not met).
Outcome: #765 merged as ebd6e40; main CI 45221066638 green on three systems.

## D-909 (2026-11-23, coordinator)

Three changes to impl-725 plan §2.3 and §2.4 for PR 4 (#726, web) are accepted:
1. Changed settings end the job as a failed job, with error kind `settings-changed` and a `changes` list, instead of a synchronous 409. The making card offers "Keep the old settings" and "Replace all chapters". This matches the rule that the pipeline never stops mid-run to ask the user. The promised test is renamed to `test_changed_settings_end_the_job_with_both_choices` (PLAN-01).
2. A saved position stores the chapter's document index and the time within that chapter. Positions saved before this change must still be read, or mapped, and this needs a test: no saved place is lost.
3. Generate on the Listen page uses `keep_settings`, and the project page uses the form's settings.
#726 was closed by #765's merge although its web criteria are still open. It is reopened, and PR 4 closes it.

## D-910 (2026-11-23, coordinator)

Amends D-909 for PR 4 (#726):
- (a) The project page's Generate buttons also use `keep_settings`, as #726 AC2 asks. The settings-changed choice still comes up from "Make the audiobook" when more chapters are chosen under other settings, and a browser test covers it. This replaces D-909 item 3's "the project page uses the form's settings".
- (b) #726 AC1 (the Listen page lists every chapter, with its state) replaces #472's "the Chapters panel names no other chapter". The newer accepted criterion of milestone v1.5 (D-870) wins, so this is a changed requirement and not a weaker test. `test_player`'s #472 assertion changes to the AC1 behaviour, and the PR body names both Issues.

## D-911 (2026-11-23, coordinator)

Merge go for #768 (PR 3 of D-903, #725, lane:web, not critical), pinned to 8a2a12a.
- Round 1 found 1 must-fix (no test that a stale whole-book file is never served) and 3 should-fix. All are fixed with tests that fail without their checks.
- Round 2 approved with 0 must-fix.
- The merge waits until impl-725c sets `fixes_kinds: missing-test` and `handback: done` in `prs/pr-768.yaml` and the gate passes.
