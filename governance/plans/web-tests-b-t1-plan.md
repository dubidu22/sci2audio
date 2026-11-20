# Plan: batch B-T1, the WebKit failures (#699, #714) and the Firefox resume test (#697)

Thread: web-tests-b-t1, web lane implementation, Opus 5.5 high. Branch `claude/web-tests-b-t1-7db4ad` from main b00002d. Status: **one page change in `src/sci2audio/web/static/player.js` (§3) waits for the coordinator's word on risk**; the test-only parts are non-critical and started at once.

Sources read: `governance/rules/implementation.yaml`, CLAUDE.md (rule 9), `.claude/rules/tests.md`, Issues #699 and #697, `tests/conftest.py` (quarantine), `tests/browser/conftest.py`, `test_flow.py`, `test_joined.py`, `test_player_figures.py`, `test_markers.py`, `test_updates.py`, `test_player.py`, `test_player_speed.py`, `ci.yml` and `nightly.yml` (browser jobs), `.github/scripts/browser_shard.py`, `plans/review-pr698-round{1,2}.md`, `plans/audit-batch-2026-11-20b.md` (N6), D-374, D-682, D-702f, D-739, D-851, D-858; the logs of nightly run 44716711464 and of every WebKit shard in the last 60 PR runs of `ci.yml`.

## 1. What the reproduction found (corrects the brief and audit N6)

**The four #699 tests do not fail on every WebKit run.** Over the WebKit shards of the last 60 PR runs (Linux, report-only):

| Test (`[webkit]`) | Passed | Failed | Failure |
|---|---|---|---|
| `test_joined.py::test_the_mark_and_the_bar_stay_on_the_sentence_through_its_pieces` | 8 | 1 | `wait_for_url(/jobs/…)` after "Make the audiobook" (run 44803313163) |
| `test_player_figures.py::test_the_page_with_a_figure_passes_axe_in_light_dark_and_german` | 8 | 1 | same line, same run, same job |
| `test_markers.py::test_m_in_focus_listening_marks_the_stage_sentence` | 9 | 1 | "Marker set." never shown; player at 0:00, Marker button disabled (run 44805485750) |
| `test_updates.py::test_the_update_check_is_off_until_turned_on` | 7 | 2 | `uncheck`: "Clicking the checkbox did not change its state" (runs 44805485750, 44816838084) |

In the nightly of 20 Nov (run 44716711464) all four **passed** on Linux and macOS WebKit (test_updates did not exist yet).

**Why they failed 4 of 4 locally (the issue's "fails locally on two heads"):** WebKit on macOS asks for the system's languages. On this Mac (de-DE) every page came in German, so "Open and analyse" and "Look for new versions" were never found. With `locale="en-US"` pinned for the browser tests, all four pass locally; `test_m_in_focus…` passed 25 of 25 in a loop.

**Why the nightly is red:** its two macOS WebKit shards fail seven *other* tests, all with the player's speed panel from #651 (PR #655, merged after the 19 Nov nightly): six in `test_player_speed.py` and `test_listen.py::test_the_sentence_being_read_is_marked_plainly_and_a_heard_one_has_no_tint`. They fail 7 of 7 locally on macOS WebKit and pass on Linux WebKit. Filed as **#714** (milestone v1.4, lane:web, risk:low).

## 2. Causes and fixes, test side (non-critical, started)

1. `tests/browser/conftest.py`: session fixture `browser_context_args` pins `locale="en-US"` (test_german.py's own fixture still asks for de-DE on top of it). Without it, macOS WebKit runs on a non-English Mac fail every English test.
2. `test_player.py::listen_to` (used by test_joined and test_player_figures): `at_rest(page)` before the click on "Make the audiobook" and before "Listen with the text", as `make_audiobook` has had since #509. The CI failure is the click on Make doing nothing (the URL stayed on the document page), the kind `at_rest` was made for. Not reproduced locally.
3. `test_updates.py`: `at_rest(page)` after the second `goto("/settings")`, before `uncheck`. The first `check()` comes after `check_axe` (load and app.css applied); the `uncheck` came straight after a `goto`. This is the probable cause, the same kind of lost click, **but not proven**: an experiment with the fonts held back 0.6 s server-side did not reproduce it in 2 runs × 4 clicks.
4. `test_markers.py::test_m_in_focus…`: **cause not found.** The snapshot shows the player back at 0:00 with nothing marked after `at_sentence` had seen a marked sentence. A deterministic test of two steps before the file loads, `tests/browser/test_player.py::test_a_second_step_while_the_file_loads_stays_on_its_sentence`, passes in all three browsers, so that race is ruled out; the test stays as a guard. No change to this test; it stays open in #699 (it failed once, so no quarantine under D-374).

## 3. Causes and fixes, page side: `player.js`, the speed panel (#714), waits for the word on risk

Safari's focus rules, which the panel's code did not allow for (traced with a pointer/focus log in WebKit):
- A mousedown on a button in the panel moves the focus out to the page (`focusout: speed` → the listen article), so `focusout` closed the panel and the click landed on `#listen`. Preset, Faster and Slower clicks were lost.
- A click gives a button no focus (#498), so after a pointer opened the panel Esc, listened for on the menu only, did nothing.

Fix: a pointer press inside the menu keeps it open (`pressedInside`, set on `pointerdown`, cleared on `pointerup`), and Esc closes the open panel from the document. In `test_the_usual_speeds…` the assertion "a pointer leaves the focus on the button" runs only where `click_focuses(page)` (macOS WebKit gives no focus, as in test_focus.py for #498). That is the one changed assertion, and the PR says why. Proposed **risk:low**: interface behaviour, no safety mechanism, no file writing, no network. The app window on macOS is WebKit (D-47), so this is a user-visible fix.

## 4. #697, the Firefox resume test

Hypothesis from the code: the refused run's card is server-drawn after the page reloads itself (`reloadAt("result")`). The URL is then already `/jobs/<id>-audio-N`, so `wait_for_url` returns at once even if the click on "Replace these files" did nothing. The hold then waits 30 s for a job that never started. Check: 40 isolated Firefox runs with an instrumented test that records page requests on failure (a POST `/api/v1/jobs` or none). Results go here and into #697. If the cause is confirmed: `at_rest(page)` before the click, and `expect_request(POST /api/v1/jobs)` around it so a lost click fails at once with a clear message. Then 40 isolated runs per browser (Firefox, Chromium, and WebKit as audit N6 asks), one pytest process each; the quarantine is lifted only on 40 of 40 in Firefox with the cause explained.

## 5. Tests promised in the plan

- `tests/browser/test_player.py::test_a_second_step_while_the_file_loads_stays_on_its_sentence`
- `tests/browser/test_joined.py::test_the_mark_and_the_bar_stay_on_the_sentence_through_its_pieces`
- `tests/browser/test_player_figures.py::test_the_page_with_a_figure_passes_axe_in_light_dark_and_german`
- `tests/browser/test_markers.py::test_m_in_focus_listening_marks_the_stage_sentence`
- `tests/browser/test_updates.py::test_the_update_check_is_off_until_turned_on`
- `tests/browser/test_player_speed.py::test_the_usual_speeds_set_the_rate_and_keep_the_pitch`
- `tests/browser/test_player_speed.py::test_the_speed_stays_across_chapters_and_jumps`
- `tests/browser/test_player_speed.py::test_at_2x_the_highlight_stays_with_the_voice`
- `tests/browser/test_player_speed.py::test_a_typed_speed`
- `tests/browser/test_player_speed.py::test_the_speed_in_german`
- `tests/browser/test_player_speed.py::test_the_speed_stays_on_the_m4b`
- `tests/browser/test_listen.py::test_the_sentence_being_read_is_marked_plainly_and_a_heard_one_has_no_tint`
- `tests/browser/test_flow.py::test_resume_of_a_paused_replace_never_asks_to_replace_again`

The seven #714 tests are the failing tests for the page fix (7 of 7 failing in WebKit before it, 10 of 10 with test_player_speed's other tests passing in WebKit, Chromium and Firefox after it).

## 6. PR

One PR, `web: the speed panel keeps its clicks in WebKit and the browser tests wait for a page at rest (#699)`. Body: `Closes #714`; #699 is closed only if the coordinator accepts §2.4 (markers cause not found) as a follow-up Issue; #697 is closed if §4 ends in 40 of 40. Licence: none. Size: about 60 lines.

Hand-off (THR-07): goal: #699/#714/#697 fixed; done: §1–§3; next: the Firefox loop (§4), then the PR.
