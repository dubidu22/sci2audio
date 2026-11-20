# Review of PR #144, round 2: the player with read-along (#78)

Reviewed 13 Nov 2026 at head e0cf812 (author's answer: PR comment issuecomment-6855616221). Round 1: `review-pr144-round1.md`.

## Round 1 items

- **M1 fixed.** One helper, `i18n.data_block`, writes `<`, `>` and `&` as `<`, `>`, `&` for both the player data and the script strings. Unit test with `</script>`, `<!--<script>` and `&` round-trips through `json.loads` and leaves none of the three characters in the block; browser test `test_text_from_the_file_cannot_change_how_the_page_parses` with the heading `Intro <!--<script>` checks both chapter buttons, the text and the parsed data.
- **M2 fixed.** The global `scroll-padding-top` is gone. `player.js` pins the bar (class `pinned`, sticky) only while it is at most a quarter of the window's height, measured on every resize, and sets the scroll padding to the bar's real height only then. My probe: pinned at 1280×800, 1024×640, 768×640 (bar 110 px); not pinned at 390×844 (281 px), 320×256 (330 px) and 844×390; no sideways scroll at any size; a chapter button focused after scrolling at 1024×640 sits at y = 128, below the bar's bottom at 110; the document page has no scroll padding. The new browser test asserts pinned exactly when it fits, pinned at 1280×800, padding exactly while pinned, and no focused chapter button under the bar at six sizes. The listen page is in `test_reflow`.
- **S1 fixed.** Issues #152 (speed control), #153 (listening position), #154 (audiobooks from the command line), #155 (read-along on PDF page images), all milestone v1.1, linked in the PR body.
- **N1 (German).** #142 merged first, so this PR adds `de.toml` keys for `[listen]`, `[player]` and `home.listen`; `player.` is in the script keys; chapter titles now sit in a span with the text's `lang` instead of inside the translated sentence. The German main-flow browser test opens the listen page and runs axe before and after a chapter jump. The string-table tests also read `player.js` and the player's error keys.

## What was run

- At b0cc419 (main 586094f merged): ruff, format, lint-imports (all contracts kept), deptry clean; fast suite **2430 passed**.
- At e0cf812 (only `app.css`, `player.js` and one browser test changed since b0cc419): browser suite **40 passed, three runs in a row**; nightly Hypothesis on `tests/unit/test_web_*.py` **277 passed**.
- CI at e0cf812: all green on Linux, macOS and Windows, browser job, CodeQL, security, licences.

## New findings

None.

## Verdict

Approved. Main has moved to 2079d12 (#162, EPUB in the jobs, merges cleanly), so the branch gets main merged through GitHub's update-branch (no force-push), and the PR merges once CI is green on that head.
