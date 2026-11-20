# Review PR #492, round 1 (#491: file names drop unassigned code points)

Head reviewed: 7e07e5c, one commit on main 9377cd8. Non-critical, lane:output, labelled `ci:full`. At the coordinator's request, the merge waits for the three-system run.

**Verdict: approvable.** No findings. One deferred item is filed as #493.

## What I checked
- **The rule.** `_UNPRINTABLE` gains `Cn`, so `clean()` now turns every code point that `unicodedata` (Unicode 15.0.0 on Python 3.12) calls unassigned into a space, alongside `Cc`, `Cf`, `Cs`, `Zl` and `Zp`. That covers more than U+E57EE. Probed through `clean("a" + c + "b")`, every one of these gives `"a b"`:

  | code point | category |
  |---|---|
  | U+FDD0 | noncharacter, Cn |
  | U+FFFE | noncharacter, Cn |
  | U+1FFFE | noncharacter, Cn |
  | U+10FFFF | Cn |
  | U+E57EE | Cn |
  | U+D800 | surrogate, Cs |

- **Every writer goes through `clean()`.** The uploaded name (`stored_name`, `documents.py:166`), the pasted text's name (`documents.py:222`), the job's name (`job.py:139`), and the book and chapter names (`book_name`, `chapter_file`). The chapter file takes the book part already cleaned.
- **The tests fail on main.** With main's `names.py` put back, the new `test_stored_names` case and `test_any_name_is_kept_inside_its_folder` fail on Hypothesis seeds 1, 2 and 3. `st.text()` draws from every category except `Cs`, so it generates `Cn` names. With the fix, the four name test files the PR names give 160 passed.
- **Existing names are unchanged.** The rule changes only names that hold a `Cn`. None of the 231 text files under `tests/` holds one. CI's full suite, golden files included, runs on all three systems.

## Deferred: #493 (v1.2.x, lane:output)
- The macOS kernel refuses code points that are unassigned in its own Unicode version (xnu `bsd/sys/unicode.h`), and that version is not necessarily Python's.
- A character that Python 3.12 knows (Unicode 15.0) but an older Mac does not can still be refused.
- The suggested fix: on EILSEQ, retry once with a safe name, pinned by a fault-injection test.
- This is outside #491's acceptance criteria, which name `Cn`, and CI's current macOS runner can't show it.

## Merge
- To follow once `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)` are green on 7e07e5c.
- Done: three systems green on 7e07e5c (`tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`, browser, `CI passed`). Main had not moved (9377cd8). Squash-merged pinned to 7e07e5c: main is now **5812d2d**, tree identical to the reviewed head. #491 closed.
