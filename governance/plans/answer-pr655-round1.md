# Answer to review of PR #655, round 1

Fix commit: 7171448 (tests only, no code change).

- M1 (a) fixed: tests/browser/test_flow.py types 1.07 in Exact speed; slider value 1.07, both aria-valuetext "1.07 times", live.voice.spoken[-1] == (PREVIEW_TEXT, "bm_george", 1.07), settings["speed"] == 1.07.
- M1 (b) fixed: tests/browser/test_settings.py fills 0.87, aria-valuetext "0.87 times", saved.speed == 0.87.
- M2 fixed: new tests/browser/test_focus.py::test_esc_in_focus_closes_the_speed_panel_first. Checked against the mutant that drops the speed menu's preventDefault: the test fails on it and passes on the real code.
- N1, N2: kept as they are (accepted by review).
- Firefox 2/2 (reported only) test_freeing_the_speech_cache_asks_first: not touched, as asked.

Local: test_flow, test_settings, test_focus in Chromium, 57 passed.
