# Nightly-green PR 3: reload timing (#506, #509), plan and record

Web lane, tests only, non-critical (D-734, D-741). Author: thread "Finish the nightly reload-timing fixes", 18 Nov 2026.
Base: branch tests/nightly-reload-timing 8813e19 (fix from the previous web thread), main 96de4a3 merged in (bf33338, merge, no rebase).

## Fix (unchanged from 8813e19, see nightly-green-handoff.md)
- #506 `test_markers.py`: before `page.reload()` expect the row's `.mk-note` text (the row shows it only after the server stored the note); same after Ctrl+Enter in the markers axe test.
- #509 `test_flow.py::reload_holding_back_app_js`: set `window.beforeReload` on the old page, reload with `wait_until="commit"`, then `wait_for_function("!window.beforeReload && document.readyState !== 'loading'")`. Not `domcontentloaded` (app.js is defer). Covers 9 tests in test_flow, test_focus, test_voice_cards.
- No app code, no golden, no regression case, no CI file.

## Evidence
1. 40-run isolation (D-682) by dispatch, not locally: scratch branch `ci/isolate-reload-timing` (= fix branch + nightly.yml edit: browsers job only, Firefox Ubuntu, WebKit Ubuntu, WebKit macOS, the 11 affected tests + #517's test in one pytest call, 40 times). Never merged; delete on GitHub afterwards (threads cannot delete remote branches).
   - Run A 44310725768 (12 tests): RESULT PENDING
   - Run B (second dispatch, #518's German Tab test alone): RESULT PENDING
2. Full branch nightly on tests/nightly-reload-timing: run 44310729411, compared job by job with main nightly 44284161628 (Firefox red there: #509's test_the_removal_button_waits_for_the_script + #518). RESULT PENDING
3. PR Linux CI.

## Untracked failures filed (TST-08, one failure each, no quarantine yet per TST-07)
- #517 Firefox voice-card sample flake (nightly 44071380866).
- #518 Firefox German language switch Tab flake (main nightly 44284161628), new on 18 Nov.
Isolation results go into each issue; a second failure without a code cause means same-day quarantine.

## PR 4 (D-742): web audit follow-ups S1 #520 and S2 #521
Non-critical, lane:web, branch `web/marker-first-piece` from main, opened only after PR 3 is in review; separate from PR 3.
- #520 (S1): `api._marker_out` maps the placed chunk to its sentence's first piece (`book.firsts[...]`); `pages._markers_data` computes `sentence_starts(located.readalong)` once and does the same; models.py field description "the sentence's first chunk in this audiobook, or null". Test first: a joined read-along whose second piece is longer, whole-sentence anchor; the page data and the POST answer both name the first piece. It must fail on main.
- #521 (S2): `keys_hint` in en.toml and de.toml names M; any test pinning the string updated.
- Not in scope: N1, N2 (fold into the next web PR touching player.js / tests/browser), N3 = #522 (lane:docs, critical, later docs PR).

## Update 13:35Z: #518 has a code cause, fixed in PR 3
Second Firefox failure on #519's branch nightly (44310729411); fails 3/3 locally, also at 1e461a7. Cause: the test Tabs forward from the mid-page step heading to the header's "Einstellungen", which needs a wrap; headless Firefox goes to body and comes back in at #output-folder, cycling until MAX_TABS. Fix 17c1ba6: `press_on(page, "Einstellungen", back=True)`. PR #519 now closes #518 too. Run B (German test, unfixed) cancelled; new isolation 44313065955 (fixed test) and new branch nightly 44313070888 at 17c1ba6.

## Update 13:55Z: evidence and round 2
- Isolation A 44310725768 (old head, 11 tests + #517): Firefox Ubuntu 40/40 green; **WebKit Ubuntu 11/40 runs red**: test_the_removal_button_waits_for_the_script 8x [document] + 3x [library] (summary clicked, details stays closed, button hidden), test_replace_waits_until_the_page_script_runs 1x at line 794 (before the helper: "files exist already" not reached). Job showed success only because of "|| true". WebKit macOS cancelled: no hosted macOS arm64 runner within 15 min (capacity).
- Isolation 44313065955 (#518 fixed test, 40x): Firefox Ubuntu 40/40, WebKit Ubuntu 40/40.
- Not reproducible locally (WebKit Linux, 30 runs, with and without 4 parallel loads; a 0.5 s app.css delay does not cause it either). Diagnostic run 44316533521 on scratch `ci/isolate-reload-timing-2`: the two tests 40x with Playwright traces and screenshots on failure, job fails on any red run, per-test PASSED/FAILED counts.
- Reviewer (round 1 APPROVE pending evidence) informed; round 2 = one fix commit with the cause named in a PR comment, then a fresh strict isolation.

## PR 4 (#523) also carries the #525 quarantine (D-746)
- `test_events_keep_the_stream_alive_and_end_when_the_server_stops` quarantined on win32 (issue 525), commit c9473f0.
- Windows isolation, alone 40x: run 44316955053 on scratch `ci/isolate-keepalive-525` (main + ci.yml edit, Windows only, fails on any red). Result into #525.

## Update 16:20Z: round 2 pushed (cbd3e9c, with main f2aea0e merged as cfc1762)
- Cause (traces): clicks on a freshly drawn page while app.css and the web fonts still arrive are lost (WebKit summary click after the reload helper; WebKit Make after the Prepare link; Firefox "Listen with the text" after the job page's end reload). Fix: conftest.at_rest() (app.css applied + no FontFace loading; not document.fonts.ready, which WebKit settles only after load); used by the reload helper, make_audiobook, three Prepare-then-Make steps.
- Strict isolation (fails on any red, per-test counts): 44335482080 Firefox 16/16 items 40/40, WebKit Ubuntu 16/16 40/40; 44336526556 Chromium 16/16 40/40. WebKit macOS: no runner in earlier runs; running in 44335482080.
- #542 = #506 (known cause, fixed, no quarantine); #519 closes it. #541 filed (WebKit reading mark after paused ArrowRight, 1/40, no quarantine). #525: quarantine on main via #523, Windows 40/40 alone in the issue.
- PR comment with all evidence: https://github.com/dubidu22/sci2audio/pull/519#issuecomment-6984414555

## Hand-off (16:30Z): web batch done, #519 merged 2cb10c5, #523 merged f2aea0e
Open follow-ups: #517 (Firefox voice-card flake, 0/120 since) and #541 (WebKit reading mark after paused ArrowRight, 1/40), both lane:web, not quarantined; #525 stays quarantined on Windows until a wall-clock-free fix; #522 for the docs lane. For Colin: delete scratch branches ci/isolate-reload-timing, -2 to -6 and ci/isolate-keepalive-525 on GitHub (workflow edits only, never merged).
