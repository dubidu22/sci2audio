# Review PR #507, round 1 (#473: port the release/1.1 fixes to main)

Head reviewed: c4fdcd7, which is 39e735f with main 11b8b13 (#505) merged in. Non-critical, lane:web, 7 files, +76 −10. It touches tests, docs, the changelog and the `[tool.mutmut]` setting only: no golden file, regression case, layer contract, packaging or workflow. Linux CI is green on c4fdcd7: `tests (ubuntu-latest)`, browser (Chromium), ZAP, CodeQL, licences, lint and layers, security and `CI passed`.

**Verdict: approvable, and merged.** No findings.

## What I checked

### Each #473 item against release/1.1 (e9d08ef) and release day (702a318, draft #426)
- **`[tool.mutmut]` `also_copy`** now includes `.github/`, with the comment. `test_ci_workflows.py` and `test_readme.py` pass (8 passed).
- **`test_player_position.py`** is identical to release/1.1.
- **`test_player_speed.py`** is identical to release/1.1, except main's Working Reader lines (`.chapter-button` in place of "Next chapter"), as #473 allows.
- **The EPUB test** gets `--chapters all` and the comment from the release. The release's `reused == 1` no longer holds on main, because since #436 the logo's notice reads its alt text. The new assertion is `(spoke, reused) == (total, 0)`, and the three chapter files are checked.
  - This pins main's real behaviour.
  - The reuse rule stays pinned where the comment says: `test_the_same_text_twice_is_spoken_once` (D-155) and the kill/resume test.
  - This is the "port the reason, not the line" that #473 asks for.
- **README** line 5 and `docs/listening-tests/template.md` are identical to 702a318.
- **CHANGELOG.** I compared every bullet of release/1.1's `[1.1.0]` section (43 bullets) with main's Unreleased after the PR. Every one is there word for word, except the #410 known issue, which #473 says to leave out (#450 fixed it). #92 is inside the #254 line, as in the release.
- **Closing keywords.** Only `Closes #473`.

### Runs
- **Chromium, on c4fdcd7:** `test_player_position.py` and `test_player_speed.py`, 9 passed.
- **The EPUB slow test with the real voice:** green on Ubuntu, macOS and Windows in the branch nightly 44051150185 (39e735f). It is red on all three in main's 44032949050.

### The nightly reds against main (D-731)
I compared the head's nightly 44061278538 (c4fdcd7) with main's nightly 44059174746 (11b8b13).

| job | head c4fdcd7 | main 11b8b13 |
|---|---|---|
| Firefox | 2 failures, both also on main: mark colour (#500) and dock (#501) | 4 failures and 1 error: the two on the left, the marker note reload (#506), the speed select, and the position test's error. **The PR fixes the last two.** |
| WebKit macOS | the same 10 failures as main | 11 failures: those 10 plus `test_the_speed_by_keyboard`, **which the PR fixes** |
| WebKit Linux | 3 failures (see below) | 1 failure: `test_below_1280_px_a_click_on_text_inside_the_panel_leaves_it_open` |

The two extra failures on WebKit Linux:
- `test_the_note_box_pauses_esc_leaves_it_and_a_note_survives_a_reload` is the reload-before-save race already filed as #506. Main's Firefox job fails it too.
- `test_replace_waits_until_the_page_script_runs` comes from #505's test change. It passed on main's WebKit Linux and at 39e735f. It goes through `reload_holding_back_app_js`, which acts right after a reload that waits only for "commit". The author filed that as #509.

Neither test is in a file this PR touches, and the PR changes no application code.

On the branch's first base (39e735f, on 344db7a), Firefox's `test_the_removal_button_waits_for_the_script[firefox-library]` failed three times. It passes on c4fdcd7 and on main 11b8b13, and the PR touches nothing on the library page, so it is not this PR's. I note it in case it returns.

- **Note for the coordinator:** #508 and #506 describe the same race in the same test (`test_markers.py::test_the_note_box_…_survives_a_reload`). One of them can be closed as a duplicate when the fix PR is planned.
- **Note:** the branch nightly 44051150185 has three attempts. It is not a merge gate, and each red in it was compared with main, so this is information, not a finding.

## Merge
- **Main had not moved:** it was 11b8b13, which is in the branch.
- **Squash-merged**, pinned to c4fdcd7, with `Closes #473` in the squash message. It is non-critical, so Linux CI is enough. Main is now **1e461a7**, and its tree is identical to the reviewed head's. #473 is closed.
