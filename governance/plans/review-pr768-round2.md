# Review: PR #768, round 2

- PR: #768 (PR 3 of #725, web: download the whole audiobook), non-critical.
- Head reviewed: 8a2a12a9cf6cafd5c4d386f1c97ae8b14fea4924 (4e742a9, the fix, then 8a2a12a, which only removes review tags from docstrings).
- Thread: review-b005. Date: 2026-11-23.
- **Verdict: approved.** 0 must-fix, 0 should-fix, 0 deferred.

## Round 1 findings

Only `tests/unit/test_web_book.py` changed; no source file. This review re-applied each round 1 mutation on the new head:

| Finding | Mutation | Now fails |
|---|---|---|
| B1 | `or entry.chapters != held` removed in `whole_book` | `test_a_book_built_before_chapters_were_added_is_not_served_as_current` |
| S1 | `_built` returns `folder / name` without the vouch | `test_an_edited_built_file_is_not_served` |
| S2 | `if not book.buildable` removed | `test_an_audiobook_made_before_the_chapter_record_offers_its_own_m4b` |
| S2 | `old = None` (the pre-#723 M4B not served) | the same test |
| S3 | the `missing-chapters` row removed from `_KINDS` | `test_a_build_after_the_speech_cache_was_freed_fails_as_missing_chapters` |

All five are fixed, each with a test that fails on the known-wrong case (VER-02, REV-05 for B1).

## Checks

- Locally: `test_web_book.py` and the review-tag test pass (59 passed); ruff and format are clean on the changed file.
- CI on 8a2a12a is green: tests ubuntu, both Chromium shards, ZAP, governance, CodeQL, lint, licences, `CI passed`. Firefox and WebKit, which are report-only, are green too.

## Notes

- **N1.** Round 2 has two commits, not the one fix commit per round that D-698 asks for. The second only removes the review tags that `test_review_tags` refused, the same as on #762. No action needed.

## Summary

- Done: B1, S1, S2 and S3 verified fixed by mutation on the new head; CI green.
- Not done: none.

## Merge

Squash-merged by review-b005 on the coordinator go D-911, pinned to 8a2a12a, as 1fbff7c. Main CI run 45238098859 on 1fbff7c: tests on ubuntu, macos and windows and CI passed all success.
