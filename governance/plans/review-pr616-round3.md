# PR #616 review, round 3 (head 8655836)

Reviewer: textprep B6 review thread, 19 Nov 2026 ~06:05Z. Verdict: **approved**, merged pinned to 8655836.

- Fix commit 8655836 changes `tests/unit/test_textprep_utterances.py` only (+21): "Abs. 2. Abs. 3 gilt." at the paragraph start, `_joined` cases at the start and end of the text ("unter anderem bbb", "5 Komma 3", "aaa per s"), `test_no_joined_place_is_past_the_last_place`. The PR body states the equivalents with reasons and lists #619 as out of scope.
- CI on 8655836: `CI passed`, `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, both Chromium shards, lint and layers, licences, security, CodeQL: all success.
- Mutation on 8655836: `x__label_again*` run 44467784363: 25 killed, 1 survived (14, the stated speed bound). `x__joined*` run 44467777882: 56 killed, 7 survived (3, 6, 14, 25, 36, 56, 57), exactly the stated equivalents; 8, 16, 26, 37, 55, 58 now killed. `x__cut_point*` (round 2, unchanged code): 80 killed; 27 equivalent, the other 8 → #619.
- Main moved to e658c17 (#512 ruff 0.17.5 / syrupy 7.0.1, #611 web) since the PR's base; no shared file but CHANGELOG (auto-merges). Local merge of 8655836 into e658c17 with main's lock: ruff 0.17.5 check and format clean, cutter, both regression files and the gate 1,330 passed, 6 xfailed. No branch update needed (MRG-03).
- Earlier rounds: nightly seeds 2024 and 8080 green, corpus utterances identical to a1f030b, probes in `plans/b6-review/`.
