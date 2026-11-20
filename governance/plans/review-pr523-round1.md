# Review PR #523, round 1

Head reviewed: a573b9d (base 96de4a3; main now 2979dce, branch behind). Reviewer: web-lane review thread, 18 Nov 2026 14:45Z.
PR 4 of the web batch: closes #520 (S1), #521 (S2); also quarantines #525's test on Windows (D-746). Non-critical. +37 −7 in 8 files.

## Verdict
APPROVE, no fix list.

## Verified
1. #520 api.py:419 `_marker_out` maps the placed chunk through `book.firsts`; pages.py `_markers_data` computes `sentence_starts(located.readalong)` once and maps the same way; models.py description now says "the first chunk of its sentence". These are the only two places a placed chunk leaves the server (grep of `place(` / `.chunk` in src/sci2audio/web; api.py:390 and :528 are internal and already map through firsts / on_sentence).
2. Test fails without the fix: with main's src (96de4a3) the new `test_the_api_and_the_page_name_a_marked_cut_sentence_by_its_first_piece` fails, and so does the changed pre-#480 test. Reverting api.py alone fails the new test (POST answer); reverting pages.py alone fails both (page data). Both halves are pinned. The guard `assert longest != first` keeps the test from passing vacuously. Branch: 6/6 pass locally.
3. Changed expectations (test_web_joined.py pre-#480 test, test_joined.py browser test) follow the new meaning of the field; they assert the corrected value, not a looser one. The browser test still checks the tick sits at the sentence's start.
4. #521: en and de `keys_hint` name M; no test pins the string. M's off switch is already tested (test_markers.py:197).
5. #525 quarantine: `@pytest.mark.quarantined(issue=525, platform="win32")`, issue open with milestone v1.2.x, author reports 40/40 Windows isolation in the issue (D-682). Windows only, the test still runs on Linux and macOS. Matches D-746.
6. No closing keywords in commit messages. Linux CI on a573b9d: CI passed, tests (ubuntu), browser (Linux, Chromium), lint and layers, licences, security, ZAP, CodeQL all success.

## Notes
- N1: with the server now naming the first piece, test_joined.py no longer exercises player.js's `firstOf[marker.chunk]` mapping for the tick (the data is already the first piece). The mapping is now a no-op guard; no change needed.

## Merge conditions
- Per D-753 the author merges main (after #524 lands) into the branch. If only main changes come in, CI green and the PR diff unchanged, I merge pinned. If the cut-limit change trips the guard and the author changes test_web_joined.py, that commit is round 2 and I re-check that the new test still fails without the fix.
