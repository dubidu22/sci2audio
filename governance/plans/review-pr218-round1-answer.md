# PR #218, answer to review round 1

New head 4ff05f1 (one commit on top of 368e1f5; main 31b6d16 is already merged in, and main has not moved since).

## Must fix: the macOS WebKit row. Fixed.

1. **`test_the_player_by_keyboard_only[webkit]` ("no focus ring on BODY").** The player tests now press `tab_key(page)` (Alt+Tab in WebKit) at all three places: the round of the player's stops, the press on to the chapters, and the chapter-button loop of the reflow test. `TAB` and `tab_key` moved from `test_keyboard.py` to `conftest.py`, and `test_keyboard.py` imports them from there. The assertion message now names the whole tab order (`after {order}`), so a future failure says where the round went.
2. **`test_the_document_page_says_when_the_server_is_gone_while_it_analyses[webkit]` ("Navigation canceled by policy check").** The cause is the race you suspected. `open_paper` returned once `#summary` showed, but a page drawn while the first analysis is still the running job keeps `data-events` and calls `reloadAt("step-check")` when that job ends (app.js 77–80, the same race as #138). The test's `page.reload()` then met the page's own reload, and WebKit on macOS cancels one of them. `open_paper` in `test_flow.py` now ends with `settled(page)`, as `test_german.py`'s `open_paper` already does. That covers every caller, including `make_audiobook` and the other `test_flow.py` tests.

## Nightly run on 4ff05f1

Run https://github.com/dubidu22/sci2audio/actions/runs/43537596420 (workflow_dispatch on the branch):

| Row | Result |
|---|---|
| browser (chromium, ubuntu-latest) | success, 48 passed |
| browser (firefox, ubuntu-latest) | success, 48 passed |
| browser (webkit, ubuntu-latest) | success, 48 passed |
| browser (webkit, macos-latest) | success, 48 passed |

The slow, property and benchmark jobs of the same run were still running when this was written. They don't touch anything this PR changes.

## Local checks on 4ff05f1

- `uv run pytest -m browser` in Chromium, WebKit (Linux) and Firefox (with PulseAudio): 48 passed each.
- ruff check and ruff format are clean on `tests/browser`.

## Other checks on the PR

`ZAP baseline scan (Linux)` is red on 4ff05f1. It is the known flaky walk of #177: the walk's "Make the audiobook" step ended with "The audiobook files exist already", so the scan never ran. I commented on the PR. ZAP is not a required check.
