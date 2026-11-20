# Review PR #558 (#529 + #535), round 2 (final)

- Head reviewed: 8f147ce (8f147ce28758df069cee8d0d20bfec468afae83e), test-only fix commit on c27ce9d.
- **Verdict: approved and merged** as c51e846 (squash, pinned to 8f147ce), 18 Nov 2026 ~21:40Z. #529 and #535 closed by the PR body.

## Verified

- Diff c27ce9d..8f147ce: `tests/unit/test_layout_contents_labels.py` only (+66), four tests as in `plans/answer-pr558-round1.md`.
- S1 re-checked here: each mutant applied by hand to `furniture.py` on 8f147ce fails exactly its new test: 32 → `test_two_entries_on_one_page_are_both_entries`, 21 → `test_a_lone_number_after_the_title_is_no_entry`, 40 → `test_entries_whose_indent_drifts_away_from_the_first_end_the_contents`. Clean file: 14 passed. The author's correction of my arithmetic in (c) (a 1.5 pt creep cannot pass 20 pt in four entries; 8 pt steps used, plus a separate jitter test with the measured Kehren positions) is right.
- Final-round evidence (REV-03): code unchanged since round 1, so the round-1 mutation run 44398248044 (140 killed; 3 real survivors now killed) and nightly property run 44398253796 (green) stand. CI on 8f147ce: `CI passed` green in runs 44401166737 (PR) and 44401175503 (ci:full); `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` success in both.
- MRG-03: files of the PR vs files changed on main 1797ceb..8622f85: no overlap; GitHub mergeable clean. Main 8622f85 was not red at merge time (its macOS/Windows legs still running).
- No closing keyword in commit messages; squash message set explicitly.
