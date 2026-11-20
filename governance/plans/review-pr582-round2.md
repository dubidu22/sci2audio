# Review of PR #582, round 2 (critical, web batch B8)

Reviewed head: **065d22c** = the author's fix commit 5f202c2 plus my merge of main 9333ce0 (#572, #577, #583) through
the update-branch button. The merge touched only CHANGELOG.md among the PR's files and resolved without a conflict;
the PR's own diff against main is unchanged apart from that file (checked with `git diff`).
Reviewer: B8 review thread, 19 Nov 2026 ~01:40Z. Answer read: `plans/answer-pr582-round1.md`.

**Verdict: changes requested, 5 test-only fixes (R2-1 to R2-5).** Round 1's F1 to F3 are fixed as asked. There is no
code finding. Five checks in the code have no test that fails without them. Two of them are safety checks (the EPUB
`ref` guard and the cache's link check). The author's branch now has my merge commit, so pull it first
(`git pull`, no rebase), then push one commit with the 5 tests. Keep `src/` unchanged.

## Round 1 fixes: verified

- **F1:** `Figures.image` holds `self._lock(document_id)` around `extract_epub_picture`. The mutant without the
  lock is killed by `test_one_document_reads_its_book_once_at_a_time`.
- **F2:** `test_a_figure_below_the_first_screen_loads_when_scrolled_to` passes in Chromium (local and CI), Firefox
  2/2 and WebKit 2/2 on 5f202c2. Isolation run 44434640839 (WebKit, 3 runs, `test_player_figures.py`) is green. The
  mutant that hides every image with `naturalWidth === 0` at start is killed by it and 3 other tests.
- **F3:** `is_kept` is lstat-only. Both mutants (`_following` back to `read_cached`, and `is_kept` without
  `S_ISREG`) are killed.
- **Firefox 1/2 on 5f202c2:** it failed once in `test_flow.py::test_resume_of_a_paused_replace_never_asks_to_replace_again`
  (the audio job's resume path, which this PR does not touch) and was green on its one allowed re-run. One failure, so
  no quarantine (D-374). Noted for the nightly.

## Final-round checks run

- **Mutation:** 27 mutants were run from a clean worktree at 065d22c (`/home/user/probe/mut582.py`, `mutjs.py`; copies
  in `plans/b8-review/`). The baseline was 80 passed in `tests/unit/test_web_figures.py` and
  `tests/unit/test_extraction_figures.py`, and 5 passed in `tests/browser/test_player_figures.py` (Chromium).
  21 were killed, 5 survived (R2-1 to R2-5 below), and 1 is equivalent:
  - `not view.code` in `build_view`: CODE is not in `KINDS`, so `Catalog.images` already gives nothing for it.
  - Killed, each with a test that plausibly hits it: the id check, `_real_folder` (read and write), write outside
    `unchanged` or with no folder compare, `parents=True`, prune newest first or never, `MAX_IMAGES` 5, pages sorted
    by number, the crop not flipped, the limits not passed to the child, the alt order, the caption ignored,
    `MARGIN` 0, the clip to the page, figures for outside jobs, F1, F3 (two mutants), and `player.js` without its
    error handler.
  - Two of the PR body's claims do not hold. `clean_path(ref) != ref` → `False` survives (R2-1), and so does the
    `S_ISREG` check in `read_cached` (R2-2).
- **Nightly seeds:** `HYPOTHESIS_PROFILE=nightly`, seeds 2024 and 4242, over `test_extraction_epub.py`,
  `test_extraction_pdf_broken.py`, `test_extraction_cover.py`, `test_core_content.py` and
  `test_extraction_legibility.py`. Both seeds gave 356 passed and 1 failed. The failure is
  `test_a_declared_codec_that_is_not_for_text_reads_as_utf_8[punycode]`, and it fails the same way on main 9333ce0
  under Python 3.13 (CI uses 3.12.16). It is not this PR's, so I filed it as #587.
- **Three-system run:** `ci:full` was added on 065d22c. Its result is superseded by the R2 commit, so I run it again
  on that head.

## Fix list (all five are tests; no `src/` change)

### R2-1. The EPUB `ref` guard has no test that fails without it

`_Book.read` looks a member up by its exact name, so `../images/fig1.png` or `/images/fig1.png` is already "not a
member" in today's test book, with or without `clean_path`. The guard matters only for a book that holds a member
literally named that way, and a hostile EPUB can. **Test (in `tests/unit/test_extraction_figures.py`):** a book whose
zip also holds a valid PNG under the literal member name `../images/fig1.png`. Write it with
`zipfile.ZipInfo("../images/fig1.png")` and assert after packing that `namelist()` keeps the name. Then
`extract_epub_picture(path, "../images/fig1.png")` is None. If `zipfile` keeps a leading `/`, add the same case for
`/images/fig1.png`; if it strips it, say so in the answer.

### R2-2. The cache's link check is untested where `O_NOFOLLOW` does not exist (Windows)

`read_cached` refuses a link twice, by `lstat` + `S_ISREG` and by `O_NOFOLLOW`. On Linux `O_NOFOLLOW` alone makes
the link case fail, so removing the `S_ISREG` check passes every test. On Windows `getattr(os, "O_NOFOLLOW", 0)` is 0,
and there the `S_ISREG` check is the only guard. **Test (in `tests/unit/test_web_figures.py`):** with
`monkeypatch.delattr(os, "O_NOFOLLOW", raising=False)`, a cache file that is a link to a real PNG elsewhere is not
read (`read_cached` is None). Skip it where the system cannot make links, as the existing link test does.

### R2-3. The batch size of 12 is not pinned

Changing `len(found) >= BATCH - 1` to `>= BATCH` (13 crops in one child) passes. **Test:** a PDF document with 14
figure placeholders and an empty cache. The first miss calls `extract_pdf_regions` once with exactly 12 regions,
starting with the asked one. Count with the wrapper pattern of `test_one_child_renders_the_next_figures_too`.

### R2-4. "An EPUB table keeps its text view" is not pinned for a table holding a picture

Dropping `block.kind is not BlockKind.TABLE` passes, because the test book's table holds no `<img>`. **Test:** an
EPUB whose `<table>` holds an `<img src=... alt=...>` that the TABLE placeholder's parts reach. That block shows no
image (`Catalog.images` is `[]`), and the route answers 404 for its image 0. First check in the test that the block is
a TABLE placeholder whose parts include the picture, so the test cannot pass vacuously.

### R2-5. The early hide in `player.js` is untested

Removing `if (figure.complete && figure.naturalWidth === 0) hide();` passes, because in the test the 404 arrives after
`player.js` has run. **Test (in `tests/browser/test_player_figures.py`):** hold `**/static/player.js` with
`page.route` (append the route to a list; the pattern is in `sci2audio-app-review-checks`). Answer `**/figures/**`
with 404, reload with `wait_until="commit"`, and wait until the image is `complete` with `naturalWidth == 0`. Then
`continue_()` the held script, wait for `at_rest`, and expect the figure to be hidden.

## Next

Author: `git pull` (the branch has my merge commit 065d22c), one commit with R2-1 to R2-5, Linux CI green, branch
frozen, new head to this thread. Round 3 is then the final round: I check that each of the 5 mutants is killed on
the new head, run `ci:full` on all three systems, and merge pinned to that head if all are green.
