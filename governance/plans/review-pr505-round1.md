# Review PR #505, round 1 (resume after Pause keeps "replace"; freeing the cache asks first, #504), CRITICAL, final round

Head reviewed: ea8faec, one commit on main 3c7482f. Labels: `bug`, `risk:high`, `lane:app` and `lane:web`, 14 files, +392 −20. Plan: plans/resume-build-plan.md, approved as D-733 with two additions. The author's `ci:full` run on ea8faec is green: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser (Chromium), ZAP, CodeQL, licences, lint and layers, security and `CI passed`.

**Verdict: approvable.** No findings. The final-round checks (mutation, nightly seeds, three systems) are all done in this round, so this is the final round.

## What I checked

### Against the plan, D-733 and the coordinator's points
- **Resume keeps the run's own "replace".**
  - `JobRecord.overwrite` is set by `JobBoard.start`. `start_job` passes `kind is JobKind.AUDIO and body.overwrite`, so a script job is never `overwrite`.
  - `snapshot()` and `JobOut` carry it. The card has `data-overwrite`, and app.js `job-again` posts `card.dataset.overwrite === "true"`.
  - A paused replace run resumes with `true` and never shows the existing-files card (unit and browser tests).
  - A paused first build resumes with `false` (the browser test reads the posted body) and is refused with `output-exists` when a file appeared meanwhile (unit test). The app-layer existing-files check (D-163) is unchanged.
- **Chunks are reused.** After a pause mid-speech, the earlier audiobook is untouched (mtimes equal). On Resume, `reused == chunks_done` at the pause, and the voice speaks exactly the rest.
- **A pause while writing**, after output removed the old read-along (D-119), resumes to a complete new set including the read-along, with no speech.
- **The existing-files card** has no cache button. The kept line ("The sentences spoken so far are kept. Replacing speaks only what is missing.") shows only when `document.speech_cache_bytes` is above 0, so it is per document. The empty case is tested (D-733 addition 2).
- **The confirm before freeing the cache** (D-733 addition 1).
  - `#cache-free` sits inside `<details id="free-box">` and is drawn disabled until app.js wires it.
  - Opening the summary sends no DELETE and leaves the cache size unchanged. Only "Delete the speech cache" deletes, and the box is then removed.
  - The test fails without the confirm: on main, and with mutants T5 and J3 below.
  - `scripts/zap_scan.py` and the three existing browser tests now open the confirm first. These are the only harness changes, and the body names them.
- **API.** `overwrite` is an additive response field with a description. The OpenAPI schema is generated from the model, and Schemathesis passes. The repo has no hand-written API document to update.
- **CLI unaffected.** No CLI, app-layer, output or `player.js` change.
- **Closing keywords.** Only `Closes #504`.

### Each named test fails on main
I put main 3c7482f's `src/` and `scripts/` under the PR's tests.
- **Unit:** 9 failed, 29 passed.
  - In `test_web_audio.py`: the paused replace, the pause while writing, the paused first build and the script jobs.
  - In `test_web_prepare.py`: `data-overwrite`, the first build's card, the kept line, the confirm and the German strings.
- **Browser:** `test_resume_of_a_paused_replace_never_asks_to_replace_again` and `test_freeing_the_speech_cache_asks_first` fail. `test_a_paused_first_build_resumes_without_replace` passes, as a guard should.
- **Note, no action:** the body lists `test_a_paused_first_build_still_refuses_a_file_that_appeared` among the guards that pass on main. It fails there, but only because main's job JSON has no `overwrite` key. Its refusal assertion holds on main.

### Mutation (13 hand mutants, one at a time, from a clean worktree; `scratchpad m505/mut.py`, `run.sh`): all killed

| mutant | killed by |
|---|---|
| P1: script jobs keep `overwrite` | `test_script_jobs_never_say_overwrite` |
| P2: `start_job` always passes false | `test_a_paused_replace_resumes_without_asking_again` |
| P3: the board drops `overwrite` | `test_a_paused_replace_resumes_without_asking_again` |
| P4: the snapshot says false | `test_a_paused_replace_resumes_without_asking_again` |
| T1: `data-overwrite` always true | `test_a_first_builds_card_does_not_say_replace` |
| T2: the kept line even with an empty cache | `test_the_existing_files_card_with_an_empty_cache_says_nothing_is_kept` |
| T3: no kept line | `test_the_existing_files_card_says_the_spoken_sentences_are_kept` |
| T4: the cache button back on the existing-files card | `test_the_existing_files_card_says_the_spoken_sentences_are_kept` |
| T5: the delete button outside the confirm | `test_the_cache_button_is_inside_a_confirm` |
| J1: Resume posts false (main's behaviour) | `test_resume_of_a_paused_replace_never_asks_to_replace_again` |
| J2: Resume always posts true | `test_a_paused_first_build_resumes_without_replace` |
| J3: the DELETE wired to the summary that opens the confirm | `test_the_main_flow` |
| J4: the box left behind after freeing | `test_freeing_the_speech_cache_asks_first` |

The P and T mutants ran against `test_web_audio.py`, `test_web_prepare.py` and `test_web_schemathesis.py` (`-x -n 4`). The J mutants ran against `tests/browser/test_flow.py` in Chromium.

### Nightly seeds
`HYPOTHESIS_PROFILE=nightly`, seeds 2024 and 123456, on `test_web_audio.py`, `test_web_prepare.py`, `test_web_schemathesis.py` and `test_web_jobs.py`: 71 passed for each seed.

### #506 (flaky marker test)
`tests/browser/test_markers.py::test_the_note_box_pauses_esc_leaves_it_and_a_note_survives_a_reload` clicks Save and reloads straight away, without waiting for the note's request. The issue's reading is right. The test came in with #490 (fc7406a, its last change on main), and #505 touches no marker, Listen page or `player.js` file. So it is older than this PR and does not block it (D-725, D-729). The failed job was re-run once and is green on ea8faec.

### Base
- Main has moved to 344db7a (#503).
- `git merge-tree` of main into ea8faec is clean (tree 99ddb92). The two PRs touch two files in common: `CHANGELOG.md`, and `api.py` in different functions.

## Merge
- Main 344db7a merged into the branch: head **7ae1c9c**, tree 99ddb92 (the clean merge-tree above). `git diff -U0 344db7a 7ae1c9c` has the same changed lines as `git diff -U0 3c7482f ea8faec`. Only the context lines differ: the #503 CHANGELOG line, and api.py hunk offsets moving 697 → 711.
- Add `ci:full` and wait for `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)` to be green on the new head.
- Squash-merge, pinned to that head, with `Closes #504` in the squash message.

## Done
- Green on 7ae1c9c: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser (Chromium), ZAP, CodeQL, licences, lint and layers, security and `CI passed`.
- Squash-merged, pinned to 7ae1c9c. Main is now **11b8b13**, and its tree (99ddb92) is identical to the reviewed head's. #504 is closed; #506 stays open for its own lane:web fix.
