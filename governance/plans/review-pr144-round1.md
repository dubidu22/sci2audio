# Review of PR #144, round 1: the player with read-along (#78)

Reviewed 13 Nov 2026 at head ae01910 (merged with main 1fc7fb6 locally for the test runs). Decisions D-294 to D-303, plan `plans/issue78-player-plan.md` §8.

## What was run

- `ruff check`, `ruff format --check`, `lint-imports` (all contracts kept), `deptry src`: clean.
- Fast suite on the PR merged with today's main: **2181 passed**, 54 snapshots passed.
- Browser suite (Chromium 1243): **27 passed, three runs in a row**, no flakes.
- Nightly Hypothesis profile on `tests/unit/test_web_*.py`: **220 passed**.
- CI at ae01910: all green on Linux, macOS and Windows, browser job, CodeQL, security, licences.
- Throwaway browser probes (not committed): reflow and the player bar's height at 1280×800, 390×844, 320×568 and 320×256 (400 % zoom of 1280×1024); a document whose heading holds `<!--<script>`.

The decisions are implemented as approved: own page (D-294); web-owned record with the §2a path checks, every one of which has a test (D-295); MP3 per chapter with auto-next and the M4B fallback (D-296); chosen chapters, no furniture, printed page markers (D-297); clickable sentences that are not tab stops (D-298); notices from the built-in steps with the printed text in `<details>` (D-299); `aria-current` plus colour and underline (underline 5.4:1 on the light highlight, 8.9:1 in dark), status only after the person's own actions, checked by a test (D-300); following with Back to the reading and the checkbox (D-301); `player.js` only on this page (D-302); the synthetic-voice line (D-303). The two post-open fixes (address built from id and bare name; no highlight while a file loads) are correct.

## Must fix

**M1. A heading with `<!--<script>` in it breaks the whole page.** `pages.listen` puts the player data in `<script type="application/json">` and only escapes `</`. Chapter titles come from the paper's own headings. In HTML's script parser, `<!--` followed by `<script` switches to the "double escaped" state, in which the template's own `</script>` no longer ends the element, so everything after the data block (the player, the chapter list, the text) becomes script text and `JSON.parse` fails. Probe: a PDF with the heading `Intro <!--<script>` → the listen page has 0 chapter buttons and no `#text` element. Not code execution (the block is JSON), but untrusted text decides how the page parses. Fix: escape `<`, `>` and `&` in the JSON as `<`, `>`, `&` (what Jinja's `tojson` does); use the same helper in `script_strings()` so there is one rule. Test: a unit test with such a heading asserting the chapter buttons and the text render (and the data block parses).

**M2. The sticky player bar covers the page at small widths and at zoom (WCAG 1.4.10, 2.4.11).** Measured heights of `.player-bar`: 154 px at 1280×800 (fine), **287 px at 390×844** (a third of the screen), **336 px at 320 px wide**. At 320×256 (1280×1024 at 400 % zoom) the sticky bar is taller than the viewport, so no text can be read at all, and `visible()` never finds the sentence visible. `html { scroll-padding-top: 10rem }` (160 px) is less than the bar at 390 px and below, so a focused element scrolls under the bar: probe at 320×256 focused the first chapter button at y = 192 to 224 under a bar reaching y = 336. The rule is also global, so every other page's anchors get a 160 px gap. Fix (your choice of how): the bar is sticky only where it fits (for example `position: static` below a width or height breakpoint, or a compact layout that keeps it under about a quarter of the viewport), and `scroll-padding-top` is set only on the listen page and only while the bar is sticky, matching its real height. Test: a browser test at 390×844 and 320×256 asserting no horizontal scroll, the bar either not sticky or at most about a quarter of the viewport high, and a focused chapter button not under the bar.

## Should fix

**S1. File the out-of-scope items as issues.** The PR body lists four items and says no follow-up issues were filed. The project rule is that anything deferred gets an issue. Please file milestone v1.1 issues for: a playback speed control in the player for all browsers; remembering the listening position across server runs; a player for audiobooks the command line made into another working folder. Read-along on PDF page images is already decided as after v1.0 in D-102; link an issue if one exists, else file it too. Link them in your answer.

## Note

- N1. `#79` (PR #142) adds `de.toml` with a test that it mirrors `en.toml`. Whichever of #142 and #144 merges second adds the German for `listen.*`, `player.*` and `home.listen`. Not a finding against this PR; the coordinator tells the #79 thread.

## Verdict

Changes requested: M1, M2, S1. After the fixes: re-run the fast suite, the browser suite, and the new tests; I will re-check the probes above.
