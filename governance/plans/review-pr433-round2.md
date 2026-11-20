# Review PR #433, round 2 (final round, critical)

Head reviewed: **45b6457**. Round 1 was on f7521e8 (see review-pr433-round1.md). The fixes are in de71c2f; d7cede7, f213eab, d62f9d7 and 45b6457 followed for CI and nightly failures.

**Verdict: one fix needed, so there is no merge on 45b6457.** Every round 1 finding is fixed and proven, all five round 1 survivors now die, and CI on three systems, the slow tests and the property tests are green. But `test_keyboard::test_the_main_flow_by_keyboard` failed in WebKit on Ubuntu on both attempts of the nightly on 45b6457, with the same assertion. Under the coordinator's ruling a repeat is a fix: there will be a new head, and round 3 (the final one) is pinned to it.

## Round 1 fix list, rechecked

1. **S1, done.**
   - `test_the_cards_buttons_wait_for_the_script` holds app.js back and checks that `#job-pause`, `#job-cancel` (with the confirm open) and `#job-again` (Resume, on a paused card) are disabled, then enabled once app.js runs.
   - `.remove-now` is now drawn `disabled`, and `removal()` enables it once its click is attached. `test_the_removal_button_waits_for_the_script` checks it on the document page and on a library row.
   - Each button drawn enabled now fails its test (mutants below).
2. **S2, done. It is a behaviour fix, and it is correct.**
   - `_running_lines` used to look only at the speaking phase, so the running card showed no chapter done while the files were written. It now calls `_stopped_in(progress)` for every phase, which is the same logic as app.js's `chapterNow`. The server card and the live card now agree in every phase.
   - The kept line for a job that failed while writing reads "Every chapter is spoken and kept. Making it again only writes the files." A unit test pins that, the title "…stopped while writing the files" and every segment done.
   - A second unit test checks that the running card shows every segment done while writing.
3. **N1, fixed.** A job paused before its first sentence says "Paused." and "Nothing is spoken yet." and offers Resume. "Cancelled. The speech cache is empty." stays for a cache freed after speaking began. A unit test holds the voice while it loads.
4. **N2, fixed by wording (D-697: Resume keeps the run's settings).** The paused, failed and exists cards say that Resume, Make it again and Replace use the run's own voice, speed and chapters, and point to "Make the audiobook" below for other settings. The buttons do the same as before.
5. **N3, fixed.**
   - Cancel waits at most `pages.STOP_WAIT_MS` (120 s, on the card as `data-stop-wait`) for the job to leave `running`.
   - Then it says the voice did not stop and nothing was deleted, sends no DELETE and gives its button back.
   - `test_cancel_gives_up_on_a_voice_that_does_not_stop` sets the limit to 1.5 s.
6. **PR body:** the round 1 mutants, with their commands and baselines, are there.

## Mutants (D-676), rerun in my own clean worktree at de71c2f

de71c2f..45b6457 changes no file that these tests or mutants touch (only `zap_scan.py`, `pdf_maker.py`, `test_keyboard.py`, `test_web_audio.py` and `test_zap_scan.py`).

**Unit.** Command: `python m433r2.py <worktree> "tests/unit/test_web_prepare.py tests/unit/test_app_audio_job.py tests/unit/test_web_audio.py"`, which runs `pytest … -q -p no:randomly -x` for each mutant. Baseline: 55 passed.

| Mutant | Result |
|---|---|
| `_stopped_in(progress)` → `("before", 0)` in `_running_lines` (author's) | killed |
| the paused-before-speaking branch → never (author's) | killed |
| `elif where == "writing"` (kept_all) → never (author's; round 1 survivor) | killed |
| running card while writing: `current` → 0 (round 1 survivor) | killed |
| `resume` offered → False | killed |
| `STOP_WAIT_MS` → 0 | survived in unit tests; killed in the browser (below) |

**Browser (Chromium).** Command: `python b433r2.py <worktree> "tests/browser/test_flow.py tests/browser/test_prepare.py" "wait_for_the_script or gives_up or cancel_deletes or pause or resume or removal"`. Baseline: 8 passed.

| Mutant | Killed by |
|---|---|
| `await stopped(…)` removed (no wait) | `test_cancel_deletes_the_speech_cache_only_once_the_voice_stopped` |
| `stopped()` never gives up | `test_cancel_gives_up_on_a_voice_that_does_not_stop` |
| `stopped()` returns at once | `test_cancel_deletes_the_speech_cache_only_once_the_voice_stopped` |
| the confirm drawn open | `test_cancel_deletes_the_speech_cache_only_once_the_voice_stopped` |
| `#job-pause` drawn enabled (round 1 survivor) | `test_the_cards_buttons_wait_for_the_script` |
| `#job-cancel` drawn enabled (round 1 survivor) | `test_the_cards_buttons_wait_for_the_script` |
| `#job-again` drawn enabled (round 1 survivor) | `test_the_cards_buttons_wait_for_the_script` |
| `.remove-now` drawn enabled | `test_the_removal_button_waits_for_the_script[document]` |
| `STOP_WAIT_MS = 0` | `test_cancel_deletes_the_speech_cache_only_once_the_voice_stopped` |

All five round 1 survivors now die. Each of Cancel's two guards still has a test that fails without it (#345): the client wait (above) and the server's 409 (`test_cancelling_while_speaking_keeps_the_chunks`).

## The later commits

- **d7cede7, `steady()` (#422).** It now replaces PDFium's `/CreationDate` as well as its `/ID`, each with a value of the same length. Removing either replacement fails `test_the_walks_uploads_are_the_same_bytes_on_every_call`. I called it eight times over 3.2 s, across a second boundary, and got one hash pair.
- **f213eab, the ZAP walk.** It waits for the load event and an enabled Update button before it downloads the report. That is right: a download clicked during page load stops the deferred app.js. That cause is filed as **#435** (v1.3, a `download` attribute is the suggested fix).
- **d62f9d7, the keyboard test.** It now tabs to the chapter before the switch, which is Prepare's DOM order. Firefox failed "'chapter-1' can't be reached with Tab" on de71c2f; it passes now.
- **45b6457, the D-695 stream test.** It checks every progress it is told about instead of assuming the last event is the job's own progress (the server's final `done` has no audio fields). It failed on macOS ci:full at d7cede7. It passed 5 of 5 runs here, and renaming `chapter_number` fails it.

## Runs

- **Local, clean worktree at de71c2f:** fast suite 6,320 passed, 2 skipped; browser suite (Chromium) 107 passed, 1 skipped (screens without their label).
- **PR checks on 45b6457** (CI run 43814322690, label `ci:full`): tests passed on ubuntu, macos and windows, plus the browser job, lint and layers, licences, security, ZAP (43814322665), CodeQL and CI passed.
- **`ui:screens`** (run 43812516528 on de71c2f; no template, CSS or JS changed after it): prepare, making, paused, failed and done match `making.png` and `failed.png` in the design. Nits, no change asked: the failed card's callout has the error wash where the design's is plain, and the paused card has one extra hint line (the N2 wording).
- **Nightly dispatch on 45b6457, run 43814664206:**
  - Chromium, benchmarks and property-based tests (many examples): green.
  - Slow tests on all three systems: only `test_cli_end_to_end::test_convert_reads_an_epub_and_keeps_its_cover` (#410, known).
  - WebKit macOS: only `test_player_speed::test_the_speed_by_keyboard` (known). The reorder test that failed once on de71c2f (`#changed` still visible 5 s after Update, the job's first test) passed, so it did not repeat.
  - Firefox: only the known speed crash and the position error.
  - WebKit Ubuntu, first attempt, two failures:
    - `test_flow::test_make_starts_nothing_until_the_report_matches_and_has_a_chapter`: after `update(page)` and a forced click on Make, `#message` stayed empty.
    - `test_keyboard::test_the_main_flow_by_keyboard`: after "Free the speech cache", `#message` had its text but not the focus.
  - WebKit Ubuntu, rerun once (attempt 2, job 133139314763): **`test_the_main_flow_by_keyboard` failed again** in the same place. 106 passed, and the Make test passed. Attempt 2 reran the whole workflow, and every other job gave the same result as attempt 1.

## Fix list (round 3)

1. **`test_the_main_flow_by_keyboard` in WebKit on Ubuntu (failed 2 of 2 on 45b6457, passed on de71c2f).**
   - What happens: the test reaches the done card at `/jobs/…-audio-N#result` and finds `#result` focused. It then presses "Free the speech cache". `#message` gets "The speech cache is empty." but never gets the focus (`test_keyboard.py:123`, "inactive" for 5 s).
   - The code is the same as on main's job page: `free.remove()`, then `say(…, true)`. What changed in this PR is that the done card now sits on Prepare, a heavier page, and that the test presses Free without waiting for that page to finish loading after `reloadAt("result")`.
   - My leading guess, not proven (I have no WebKit here): WebKit handles the `#result` fragment at the load event and moves the focus back to `#result` after `say()` has focused `#message`. If that is right, a person who presses Free while the reloaded page is still loading loses the focus move too, so it is a code cause and not only a test cause.
   - What I need:
     - find the cause;
     - fix it in the code if a person can hit it (for example, move the focus to the fragment target only while nothing else has it), otherwise in the test (`settled(page)` after the result is focused);
     - name the cause in the PR body.
   - Under D-374 a known code cause is fixed and never quarantined.
   - Proof: a nightly dispatch on the new head with `browser (webkit, ubuntu-latest)` green. If the fix is in the code, also a test that fails without it.
2. **PR body:** add the round 3 answer.

`test_make_starts_nothing_until_the_report_matches_and_has_a_chapter` failed once and did not repeat. It is not part of the fix list. It is filed in #437 with a guess at its cause.

## Round 3 scope

- The fix commit, rechecked against this list.
- The fix must change no template, CSS or card logic beyond the focus handling. If it does, I render `ui:screens` again.
- A fresh `ci:full` run on three systems and a nightly dispatch on the new head, including WebKit on Ubuntu.
- Everything else in this file holds for the new head unless the diff touches it.

## Issues filed this round

- #435: a report download clicked during page load stops app.js (v1.3).
- **#437** (v1.3): WebKit on Ubuntu fails a different browser test in most nightly runs. It names the five runs and their tests, and the once-only Make test failure.

## Before the merge

Not yet. After round 3 passes: squash-merge with the PR title, `Closes #391` and the other issues the PR body closes, pinned to the round 3 head. First check that the branch commit messages contain no closing keywords, and update the branch from main if it is behind.
