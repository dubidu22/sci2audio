# Review of PR #582, round 1 (critical, web batch B8)

PR: `web: the player shows figures, tables and formulas where their notice is read (#293)`, closes #293, #534.
Reviewed head: **b146eea** (base 5a605e5). Reviewer: B8 review thread, 19 Nov 2026 ~00:55Z.
Read: plan `plans/web-batch-b8-plan.md` (D-771), AC-293.1 to AC-293.5, CLAUDE.md, rules 1.4.7, review lessons
(`memory/MEMORY-archive-2026-11-18.md`), `plans/audit-web-batch-2026-11-18.md`.

**Verdict: changes requested, 3 fixes (F1 to F3).** No security finding. One fix commit for all three, then Linux CI
green, then hand back to this thread with the new head. `ci:full` is not needed for the fix commit; I run the final
round's three-system run, mutation and seeds myself.

## What I checked and found sound

- **CI on b146eea:** Linux, macOS, Windows tests, Chromium 1/2 and 2/2, Firefox and WebKit legs (reported only), ZAP
  baseline, CodeQL, licences, lint and layers: all success.
- **Locally (Linux, Python 3.13):** `tests/unit/test_extraction_figures.py` and `tests/unit/test_web_figures.py` 77
  passed; `tests/browser/test_player_figures.py` 4 passed (Chromium).
- **AC-293.1 crops on the real corpus:** every placeholder of the 8 corpus papers rendered (89 regions, none failed).
  I looked at a figure (liu p2), a formula (liu p2) and a table (chi p4): each crop is exactly the printed figure,
  formula or table with its margin. One child for 12 regions took 0.2 to 0.85 s; the largest crop is 433 KB, the
  largest paper's crops 1.1 MB in all, far under the 64 MB cap.
- **Path safety (D-310, D-295):** the address holds two `ge=0` integers and an id that `DocumentStore.get` checks
  against `ID` (a `cli-` id and anything else answer 404). The record must name the document (`sha256[:16]`). The EPUB
  `ref` comes from `document.json`, which `markup.picture` already resolved to a zip path; `clean_path(ref) != ref`
  refuses `..`, a leading `/` and an unresolved address; `_Book.read` keeps the 20 MB limit while unpacking.
- **Cache (AC-293.5):** written only inside `store.unchanged(id)` and only when the folder is the same; `mkdir`
  without `parents`; `lstat` + `S_ISREG` + `O_NOFOLLOW`; the `figures/` folder itself checked for a link; atomic
  replace; a full disk still serves. The cache lives in the project data folder, never the user's Documents folder,
  and goes with `DocumentStore.remove`.
- **Headers:** `nosniff`, the CSP (`img-src 'self' data:`) and `Cache-Control: no-store` come from the security
  middleware for every answer (stricter than the plan's `private, no-cache`, fine). Alt text is autoescaped by Jinja.
- **AC-293.3/293.4:** alt order picture alt, caption, notice; no tabindex; a click plays from the notice; `[hidden]`
  wins over `.notice img.figure { display: block }` because of the global `[hidden] { display: none !important }`;
  `check_axe` runs light and dark, in English and German.
- **Extraction touches (D-756):** additive only: two new functions, `Region`, two new limits handed to the child, and
  an optional `extra` argument on `_isolated`. No existing behaviour changes; no golden moves.
- **D-768 CHANGELOG line:** present under Unreleased, Added. **#534:** comment only, value unchanged.
- **ZAP:** the new route is called (404 for a heading). Fine as it is.
- **Reader slots:** a figure request waits for one of the 2 PDF reader slots without a time limit, but the job runner
  runs one job at a time, so a slot is free in practice. No finding.

## Fix list (all three are required)

### F1. An EPUB picture request reads the whole book into memory, with no limit on requests at once (should fix)

`Figures.image` calls `extract_epub_picture(source, ref)` outside any lock, and that function does
`path.read_bytes()` of the whole EPUB (up to the 200 MB upload limit) on every request. A page of lazy images sends up
to 6 at once (the browser's per-host limit). Measured (`plans/b8-review/epubmem.py`): a 150 MB EPUB with 30 pictures;
one request 0.1 s; 6 requests at once raised the server process's peak RSS from 329 MB to 694 MB. At the 200 MB limit
that is about 1.2 GB in the server process, beside a loaded voice.

**Fix (exact):** in `Figures.image`, run the EPUB branch (`extract_epub_picture(source, shown.ref)`) while holding
`self._lock(document_id)`, so one document reads its book once at a time. No change in `extraction/`.
**Test:** in `tests/unit/test_web_figures.py`, 6 threads ask `Figures.image` for the EPUB document's pictures at once;
a wrapper around `figures.extract_epub_picture` counts how many run at the same moment; assert the maximum is 1 and
every answer is the picture.

### F2. No test shows a figure below the first screen loads (test gap)

`player.js` hides an image when `figure.complete && figure.naturalWidth === 0` at start. For a `loading="lazy"` image
that has not started, this relies on `complete` being false; if a browser reports it true, every figure below the
first screen is hidden at start and, being hidden, never loads. In Chromium it is false (probe
`plans/b8-review/test_zz_probe_fold.py`, not committed: 6 text pages, the figure on page 7, top at 3,892 px; before the
scroll `[hidden=false, complete=false, naturalWidth=0]`, after it `[false, true, 924]`). The current browser tests put
the figure on the first screen, so none of the three browser legs checks this path.

**Fix (exact):** add `test_a_figure_below_the_first_screen_loads_when_scrolled_to` to
`tests/browser/test_player_figures.py`: a PDF whose figure is on a later page (its top below the viewport after
`at_rest`); assert before any scroll that the image is not hidden and `naturalWidth == 0`; scroll it into view; wait
for `complete && naturalWidth > 0`; assert it is visible. It must pass in this PR's Chromium, Firefox and WebKit legs.

### F3. `_following` reads every kept crop after the asked one in full, only to learn that it exists

`_following` calls `read_cached`, which opens and reads each kept crop (up to `FILE_LIMIT`, 8 MB) and checks its
signature, for every later figure of the document on every cache miss. With a full cache that is up to 64 MB read and
dropped for one miss.

**Fix (exact):** add `is_kept(folder, name) -> bool` in `web/figures.py` (a real `figures/` folder, `lstat` says a
regular file, size at most `FILE_LIMIT`; no read) and use it in `_following` instead of `read_cached`. `read_cached`
stays the check before a crop is served, so a bad file is still rendered again when it is asked for.
**Test:** in `tests/unit/test_web_figures.py`, with the later crops kept, a miss on the first figure opens none of
them (count `read_cached` calls, or wrap `os.open`, during `_following`), and a kept file that is a link is not
counted as kept.

## Not findings (no change asked)

- The route serves any stored document's images, not only one with an audiobook (`listening`): the answer is the
  same user's own file under the same token and origin checks. Plan deviation, harmless.
- `.part` files left by a killed server are not pruned and do not count against the cap; they go with the project.

## Next

Author: one fix commit for F1 to F3, Linux CI green (including the Firefox and WebKit legs for F2), branch frozen,
new head to this thread. Round 2 is the final round if the fixes hold: three-system `ci:full`, the 13 scoped mutants
from the PR body plus F1 and F3, nightly seeds.
