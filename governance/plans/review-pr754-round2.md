# Review PR #754, round 2

- PR: https://github.com/dubidu22/sci2audio/pull/754 (PR A of #723, LW-01, lane:output)
- Head: `e07c3f185886828c05c6f444fe0a6cf408273388` (one fix commit on round 1's `5742b76`, tests only); base `0994f97`
- Thread: review-b005 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (as round 1). Final round.
- **Verdict: approved.** 0 must-fix, 0 should-fix open.

## Verified checks

- Fix commit diff: only `tests/unit/test_output_chapters.py` (+59/−9); no product code changed since round 1, so round 1's byte-identity checks (main vs head `write_audiobook`, `BookWriter` vs main, real clause joins: all identical) still hold for this head.
- Three-system run 45150916921 on e07c3f1: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, `lint and layers`, `licences`, `security`, both Chromium shards, `web paths`, `CI passed` all success; CodeQL (actions, python, javascript-typescript) success. Run 45150926100 on the same head also green on all three systems.
- `governance pr checks` red only because no approving round was recorded yet; this entry is that round.
- Locally (Python 3.12, without torch): `tests/unit/test_output_*.py` 183 passed; ruff check and format clean on the test file.
- Main has moved to `c63fc76` (#751) since the base; #751 changes no file under `src/sci2audio/output/`, `tests/unit/test_output_*` or `docs/readalong-format.md` (no overlap). If the merge needs the branch updated first, MRG-01 applies (merge main in, re-verify, `updated_head`).

## Round 1 findings

- **M1 fixed.** `test_chapter_by_chapter_with_clause_joins_writes_the_same_bytes` now uses `quiet_edged_job`: 6000 silent samples before and 7000 after each tone, every pause `CLAUSE` including a chapter's first chunk, and it asserts the trim: every chunk keeps less than its frames, a chapter's first chunk keeps its lead and its last its tail, inner sides are trimmed. VER-02, checked by this review: with `_trim_joins` removed from `BookWriter.add` both parametrized cases fail; with `write._trim_joins` ignoring chapter starts (`firsts = {0}`) both fail too. So the test now guards both sides of the comparison.
- **S1 fixed.** `OutputSettings(m4b=False, subtitles=True)` is a fifth id (`mp3-and-subtitles`) of the byte-equality test and the second id of the join test.
- N1 to N3 stand as notes; N3 (kept files and the read-along file) is for the PR B review.

## Handoff (THR-07)

- Goal: critical review round 2 of #754.
- Done: fix commit verified, both fixes shown to fail on a wrong case, three-system run green on e07c3f1.
- Next: the coordinator's go `ledger/gos/pr-754.yaml` for head e07c3f1; then this thread runs `ledger_tool.py gate 754`, squash-merges pinned to that head, and records the merge commit here. Not merged yet.
