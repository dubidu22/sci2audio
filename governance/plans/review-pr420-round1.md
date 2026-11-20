# Review PR #420, round 1 (critical: library table and reading shelf, #389)

Head reviewed: **980911d** (b4611a2 plus the main 6ee82d4 merge; that merge changes only #413's test files and the quarantine marker line in pyproject.toml, so the src is the same as b4611a2). Base main 6ee82d4. Batch B plan: working-reader-batch-b-plan.md (D-681).

**Verdict: changes needed.** One blocker: a broken record in one document's folder stops every page from loading. The rest is a privacy-page gap and four test gaps found by mutants. The design of the records, the shelf and Continue listening is sound.

## What I checked and what held

- **Runs on the head, clean worktree:**
  - Fast suite: 6,124 passed, 2 skipped.
  - Browser suite (Chromium): 92 passed, 2 skipped (the #365 quarantine; screens without their label).
  - PR checks on 980911d: all green (lint, tests ubuntu, browser Chromium, licences, security, CodeQL, ZAP).
- **Broken or unwritable records never fail a page** holds for:
  - a missing record;
  - a record over 16 KiB;
  - a link or a folder in place of the record;
  - wrong format or version;
  - a date in the year 9999 or with a -23:59 offset;
  - `pages: 1e400`;
  - a failed write (logged; the page still answers 200).

  It fails for B1 below.
- **Continue listening:**
  - The position is checked against the audiobook's stamp (`audiobook_stamp` of the read-along file, as #373 asks). A position for another document or another audiobook is not offered (mutant killed).
  - `#continue` takes the existing offer in `player.js`. It seeks and never plays (D-300). The browser test checks `paused` and `currentTime`.
- **Connections (#409 B2):** the shelf adds no EventSource and no poll. The new items are drawn by the server. Batch A's single job item is unchanged.
- **No internet:**
  - No new URL, `//`, inline `style=` or external font.
  - Batch A's no-internet test covers the new templates, and it passes.
- **Tokens:**
  - The new CSS uses only batch A's tokens.
  - The listened meter puts `--hl-read` on the bar's value only, never on the element's background.
  - No hard-coded colour.

## Mutants

Command: `python m420.py <clean worktree at b4611a2> "tests/unit/test_web_library.py tests/unit/test_web_player.py tests/unit/test_web_pages.py"`. Each mutant is one source replacement, and the runner restores the file afterwards. Baseline: 135 passed, 1 skipped. 22 mutants: 18 killed, 4 survived.

| Survivor | What is untested |
|---|---|
| `except (OSError, ValueError)` → `except ValueError` in `library._read_record` | a record whose read raises OSError (permission, removed mid-read) |
| `if not found.outside:` → `if True:` before `write_opened` on Listen | Listen of a command-line audiobook must write nothing into its folders (#154: read-only to the server) |
| `or not math.isfinite(time)` removed in `player.recorded_position` | a position with `"time": NaN` or `Infinity` (Python's json reads both) |
| `or not folder.is_absolute()` removed in `library.heard` | a relative folder |

## Findings

**B1. A broken record in one document's folder stops every page from loading (HTTP 500).** `json.loads` raises `RecursionError` on deeply nested input. That is neither a `ValueError` nor an `OSError`, so it passes through every catch. The shelf reads every document's records on every page, so it breaks:
- the library;
- Settings;
- Privacy;
- the document page.

Proven with a TestClient probe on 980911d:

| Record | Content | Result |
|---|---|---|
| `opened.json` | `"[" * 16000` (16 KB, inside `RECORD_LIMIT`) | 500 |
| `about.json` | `"[" * 16000` | 500 |
| `audio.json` | `"[" * 500000 + "]" * 500000` (no size limit) | 500 |
| `position.json` | both shapes | 200 (already safe) |

**S1. The privacy page doesn't say what the new records keep.** Each document's work folder now holds:
- when it was last opened (`opened.json`);
- its title, authors and page count (`about.json`).

Every page also shows where the person stopped listening. D-293 says every statement on that page is checked against the code. The "Working folder" line still names only the copy, the analysis and the speech cache.

**N1. The shelf can offer Continue where Listen offers nothing.** `heard()` accepts any stamped position with `0 < time / duration < 1`. `read_position` also requires `fits(readalong, position)` and `chunks[0].end <= time < chunks[-1].end`. Two examples:
- a position inside the first sentence;
- a position in the silence after the last sentence.

In both, the shelf says "Continue from 0:02". Listen draws no offer, so `#continue` does nothing, and the page opens at the start, paused. This is harmless (it is still paused and the stamp is right), but the promise is wrong.

**N2 (note, no change asked).** For the stamp, `heard()` takes the first folder that holds the read-along file. `locate()` takes the first folder that agrees and holds every audio file. When two folders disagree, the shelf can hide a Continue that Listen would offer. It can never resume the wrong audiobook, because Listen checks again.

**Notes, no change asked:**
- The shelf reads every document's records on every page.
- Recent documents are ordered by `opened.json`'s mtime, not by its content.

Both are fine at a library's size. Name them in the PR's risk section.

## Fix list

1. **B1:**
   - `library._read_record`: catch `RecursionError` with the other two.
   - `player.read_audio_record`: turn a `RecursionError` from `json.loads` into `PlayerError("listen.broken")`.
   - A size limit on `audio.json` is welcome but optional.
   - Test, parametrized over the three records and both shapes above (`"[" * 16000`, and `"[" * 500000 + "]" * 500000`): `/`, `/settings`, `/privacy` and the document page answer 200. The broken document's Listen page shows its "broken" message.
   - Each test must fail without its own catch. Check that by reverting one catch at a time.
2. **S1:**
   - Extend `privacy.work`, in English and German, so it also names: when each document was last opened, its title and authors, and where you stopped listening.
   - Add a point to `test_what_the_privacy_page_says_is_what_the_code_does`:
     - `library.OPENED == "opened.json"` and `library.ABOUT == "about.json"`;
     - both are written under the document's work folder only;
     - the string names them.
3. **Tests for the four survivors:**
   - (a) A record whose `read_text` raises `PermissionError` (monkeypatch) reads as nothing, and the library answers 200.
   - (b) GET Listen of a command-line audiobook (#154) writes no `opened.json` anywhere in its folders, and nothing else changes there.
   - (c) A position with `"time": NaN` and with `Infinity` gives no Continue item, and `read_position` gives None.
   - (d) Either a test that a relative folder is skipped in `heard()`, or remove the check if `in_folder` already refuses relative folders. Say which in the answer.
4. **N1:** give the shelf Listen's condition. Either share `read_position`'s range and `fits` check through a light helper that does not parse the whole read-along file, or file an issue and name it in the PR body. Add a test for a position before the first sentence's end.
5. **PR body:**
   - The mutant command and its baseline, if you claim mutants.
   - The risk section: the per-page reads (notes above).

## For #421 (stacked)

#421 changes `privacy.work` too ("The library and each document's page…"). When S1 lands here, the merge into B2 must keep both changes.

## Next round

This is critical, so the final round runs `ui:screens`, `ci:full` (three systems) and a nightly dispatch on its head.
