# Plan: web-b-w3, the Focus-listening marker test in WebKit (#720)

Thread: `web-b-w3`, implementation, lane:web, batch 004, Opus 5.5 high. Status: **non-critical, started at once** (D-72): `player.js` and one browser test, no golden file, no `.github/**`, no `pyproject.toml`, no other lane's files.

## 1. Runs (D-682)

| where | browser | runs | red |
|---|---|---|---|
| `isolate.yml` run 45073565421 on main 4ca072a (Linux, mode full) | WebKit | 60 | 1 (run 41) |
| same | Chromium | 60 | 0 |
| local, macOS M4 | WebKit | 60 | 0 |
| local, macOS M4 | Chromium | 40 | 0 |

Second red run without a known cause at the time (the first was PR #698's shard, run 44805485750).

## 2. Cause (from the trace of run 41)

Two Right-arrow steps, paused, about 20 ms apart, **after** the file's metadata was in (the MP3 had answered 200 at 2357 ms, the first key came at 2525 ms). Each step sets `audio.currentTime`; Linux WebKit (GStreamer) answers each seek with a Range request (`bytes=37469-` at 2539 ms, `bytes=55709-` at 2566 ms). The second step started while the first seek was still running. The trace's DOM snapshots show the dock clock at 0:02 after the first step and 0:04 after the second, then 0:00 4 ms after the second Range answer, and it stayed there: no sentence `.now`, the Marker button disabled, for 15 s. That is exactly the PR #698 snapshot (player at 0:00, nothing marked, Marker disabled), there seen after `at_sentence` had already found a sentence.

So: **a seek started while the previous one is still running loses its position in Linux WebKit**; the element ends at 0, and the page's `seeked`/`timeupdate` handler (`update()`) faithfully follows it to "nothing being read". The page asks for that overlap: `seek()` sets `currentTime` on every step whatever `audio.seeking` says. On Linux sci2audio opens in the person's browser (no app window, `web/window.py`), so someone listening in a WebKitGTK browser (GNOME Web) loses the place with two quick steps too, not only the tests.

Ruled out: the file still loading (the guard test of #719 covers that, and here the metadata was in 170 ms before the first key); the `f` and `m` keys (they never touch the audio element).

## 3. Fix

`player.js`, `seek()`: one seek at a time. While `audio.seeking`, a new jump stores its time (and whether to start) and is applied on the element's `seeked`; a later jump replaces a stored one (the last step wins, as a second jump while a file loads already does). While a jump waits, `update()` keeps the jump's own highlight, as it does while a file loads (`pending`), so a third quick step counts from the sentence the second one chose. No retry, no timeout, no raised limit (REV-06): the overlap that loses the position no longer happens.

## 4. Tests (first, failing before the fix in Linux WebKit)

1. `tests/browser/test_player.py::test_steps_while_the_audio_still_seeks_end_on_the_last_one`: on a loaded file, paused, step twice with 0 to 40 ms between the steps (13 pairs), each time from the same sentence; after the seeks settle, the sentence two steps on is marked and `currentTime` is at its start. Fails before the fix if Linux WebKit loses a seek (checked through `isolate.yml` on the branch with the test only); passes after it.
2. The test of the issue, unchanged: `tests/browser/test_markers.py::test_m_in_focus_listening_marks_the_stage_sentence`, 40 or more runs per browser through `isolate.yml` on the fixed head, the counts into #720.

If test 1 does not go red in Linux WebKit before the fix, the cause stays "probable", the PR says so, and the fix still lands only if it removes the overlap the trace shows; the quarantine then follows CLAUDE.md rule 9 instead.

## 5. Size

About 25 lines in `player.js`, one browser test of about 50 lines. One PR `web: two quick steps keep their place in Linux WebKit (#720)`, `Closes #720`, risk:low, no `ci:full`.

## 6. Results

- Test 1 before the fix (`isolate.yml` run 45074411978, head 8a80ef9, test only): Linux Chromium 19/20, red at gap 4 ms with `time: 0`; Linux WebKit 20/20. The loss is not WebKit's alone: a seek over a running one ended at 0 in Linux Chromium too.
- After the fix (run 45074919355, head dd11405): both tests 60/60 in Linux Chromium and 60/60 in Linux WebKit.
- Local, head dd11405: fast suite 8845 passed; `pytest -m browser` (Chromium) 200 passed, 5 skipped; player, markers, listen and focus tests in WebKit and Chromium 128 passed.
- PR #748.
