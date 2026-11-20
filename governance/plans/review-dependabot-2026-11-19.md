# Review: Dependabot PRs #513, #515, #514, #512 (19 Nov 2026)

lane:infra, critical (packaging). Order D-776: #513 → #515 → #514 → #512. One round each.
Each branch was updated with main by merge (no rebase) and squash-merged pinned to its green updated head (MRG-03);
main CI was checked green on each merge commit before the next merge (MRG-04).

| PR | change | updated head | CI on head | merged | main CI on merge commit |
|---|---|---|---|---|---|
| #513 | fastapi 0.162.5 → 0.162.7 (uv.lock) | ec788e9 | Linux green, ZAP green | 02:45Z, c155d8c | green on Linux, macOS, Windows |
| #515 | markdown-it-py 4.2.0 → 4.3.0 (uv.lock) | 0be1b3a | Linux green, ZAP and CodeQL green | 02:56Z, 64c0c59 | green on Linux, macOS, Windows |
| #514 | mdit-py-plugins 0.6.1 → 0.7.0, pyproject bound `<0.7` → `<0.8` (+ uv.lock) | 181198f | Linux green; ci:full run 44448221715 green on ubuntu, macOS, Windows; ZAP green | 03:08Z, 0c8ebb2 | green on Linux, macOS, Windows |
| #512 | dev group: playwright 1.65.2, ruff 0.17.5, syrupy 7.0.1 (uv.lock) | cb19b26 | PR run 44457671746 with ci:full green on ubuntu, macOS, Windows and both Chromium shards | 04:30Z, 5eb83d2 | green on Linux, macOS, Windows |

## #513 fastapi 0.162.7

Release notes: 0.162.6 drops Python 3.10 (we require 3.12), 0.162.7 fixes cleanup of async `yield` dependencies on
cancellation. The lock diff touches only fastapi (no new transitive dependency). Nothing reaches our use beyond the
bug fix. Merged.

## #515 markdown-it-py 4.3.0

Release notes: two quadratic-time parsing fixes (security), CommonMark 0.31.2 alignment, rule loops raise
`RuntimeError`. Our reader renders through it (`extraction/markdown.py`), so I ran a differential: the same
`read_markdown` on 25 inputs (both corpus Markdown files plus 23 edge cases aimed at each release note) under
markdown-it-py 4.2.0 + mdit 0.6.1, 4.3.0 + 0.6.1 and 4.3.0 + 0.7.0, comparing the rendered HTML and `repr(pages)`.

- Corpus Markdown (`sci2audio-sample-note.md`, `sci2audio-beispiel-notiz.md`): identical. Snapshots and #582's
  figure tests green in CI.
- Changed by 4.3.0, all CommonMark fixes:
  - image alt text keeps backslash escapes, entities and code span text (`![a \* b](u)` → `a * b`, was `a  b`;
    `![the `x` var](u)` → `the x var`, was `the  var`). Better for the spoken figure notice.
  - image alt text keeps hard breaks and inline HTML: `![next <b>bold</b>](u)` → `next <b>bold</b>` (was
    `next bold`). The tags would be read. Filed **#602** (lane:extraction, with criteria).
  - a lowercase `<!doctype html>` now interrupts a paragraph (two lines instead of one).
  - an HTML comment spanning a blank line inside a list item is now hidden (4.2 read `rest -->` aloud).
  - U+001C–U+001F and U+0085 at the ends of lines are kept (they were already kept mid-line; `str.split()`-based
    folding downstream treats them as spaces).
  - IPv6 link hosts keep their brackets in `href`.
  - a table in a blockquote that ends on `>` crashed 4.2.0 with an uncaught `IndexError` inside `read_markdown`
    (only `RecursionError` is caught there); 4.3.0 reads it. Fixed by the bump, no issue needed.
- Maths, footnotes, front matter: no change. Merged.

## #514 mdit-py-plugins 0.7.0

Release notes: plugin renderers escape their output (texmath, dollarmath label, myst, colon_fence, tasklists),
stricter `attrs` defaults, anchors slug change, `attrs.parse` raises on unterminated groups; needs
markdown-it-py ≥ 3.0 (we have 4.3). We load only `dollarmath`, `footnote`, `front_matter`, and render every maths
and footnote token with our own rules and our own `escapeHtml` (`markdown.py`), so the renderer escaping does not
reach us; we load neither `attrs` nor `anchors`. The differential (4.3.0 + 0.6.1 vs 4.3.0 + 0.7.0) shows no change on
any of the 25 inputs, including `$a<b$`, `$x&y$` and a display equation labelled `(eq:1<2&)`: `token.info` and
`token.content` stay raw, so there is no double escaping. Licence unchanged (MIT). The pyproject bound `<0.8` is the
only declared change. ci:full green on all three systems. Merged.

## #512 dev group

Checked locally on main 678fe3c + #512 (Python 3.12, `uv sync --frozen`):

- syrupy 7.0.1: fast suite (`-m "not slow and not benchmark and not browser" -n 4`) 7,598 passed; snapshot report
  77 passed. `--snapshot-update` dry run with the same CI selection and xdist: 77 passed, `git status` clean (no
  snapshot written or deleted). Partial selections (`-k markdown` on one file; one corpus file with `-n 4`) with
  `--snapshot-update`: tree clean. Syrupy 7 behaves; no dependabot.yml ignore needed.
- ruff 0.17.5: `ruff check` and `ruff format --check` clean on main.
- playwright 1.65.2: Chromium r1255. CI's browser legs decide; threads that link `chromium_headless_shell-1254`
  locally will need 1255 after the merge.

Held while web PR #601 (`tests/browser/test_make_while_analysing.py`, `app.js`) was open, so its browser did not
change under review. #601 merged at 04:01Z (ff7bf8d). Branch updated to cf344a6: its ci:full run failed only on
Windows, with the same two `test_web_player.py` readalong tests that #601 had turned red on main (identical asserts),
so the merge waited (MRG-04). After #610 made main green (fc076e9), the branch was updated again to cb19b26: three
systems and both Chromium shards (now r1255) green. Merged 04:30Z as 5eb83d2; main CI green on all three systems.

## For the next docs PR (lane:docs): `THIRD_PARTY_LICENSES.md` version cells

- FastAPI 0.162.5 → **0.162.7**
- markdown-it-py 4.2 → **4.3**
- mdit-py-plugins 0.6 → **0.7**
- Playwright 1.65.1 → **1.65.2**

No licence changed (FastAPI MIT, markdown-it-py MIT, mdit-py-plugins MIT, Playwright Apache-2.0).
