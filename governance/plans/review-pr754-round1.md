# Review PR #754, round 1

- PR: https://github.com/dubidu22/sci2audio/pull/754 (PR A of #723, LW-01, lane:output; plan `plans/impl-723-plan.md`, approved as D-895)
- Head: `5742b767172b250aeb4e3feb1aef3dda4a09006c`, base `0994f97` (= main, not behind)
- Thread: review-b005 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (CRIT-03): output file writing and the atomic-rename path every output file takes (`write._atomic` gains `vouch`), a safety mechanism; no golden file changes. Carries `risk:high`.
- **Verdict: changes_requested.** 1 must-fix, 1 should-fix, 3 notes.

## Verified checks

- CI run 45145664242 on 5742b76: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` (the author's `ci:full` run, D-698), `lint and layers`, `licences`, `security`, both Chromium browser shards, `web paths`, `CI passed` all success; CodeQL success. `ci:full` has been removed again (labels: `risk:high`, `lane:output`).
- `governance pr checks` red only because no round is recorded yet (expected before this entry).
- Locally (Python 3.12, without torch): `tests/unit/test_output_*.py` 181 passed; ruff check and format clean; lint-imports 3 contracts kept.
- Lanes: `src/sci2audio/output/**`, `tests/unit/test_output_chapters.py`, `docs/readalong-format.md`, as the plan's table names.
- Promised test node IDs: all nine from plan section 5 (PR A) exist under the same names.

### Byte identity (the coordinator's main question)

`write_audiobook` was not split (see N1); its body is unchanged apart from passing the track number explicitly to `_mp3_args` and `_atomic`'s new optional `vouch` (default `None`, no effect). Checked directly, beyond the PR's own tests:

1. **write_audiobook, main vs head:** one script writes the same 12 inputs (6 setting sets: subtitles+all, default, mp3 only, mp3+subtitles without M4B, M4B only, chapter pause 2.5 s with 96k; each with and without clause pauses; JPEG cover) with `src` of main `0994f97` and of head `5742b76`, same ffmpeg, same machine. 98 files, every SHA-256 identical.
2. **BookWriter vs main's write_audiobook:** the same 12 inputs written chapter by chapter (`add` per chapter, `finish`): 98 files, every SHA-256 identical to main's.
3. **Clause joins that really trim:** chunks with 6000+ samples of silent lead and 7000 of silent tail, every pause `CLAUSE` (also at chapter starts), settings "all" and "mp3+subtitles": BookWriter at head equals main's write_audiobook in all 23 files. VER-02: with `_trim_joins` removed from `BookWriter.add` the same script differs, so this check can fail.
4. Mutations of `BookWriter` against the PR's tests: track number `index + 1` instead of `number` fails `test_a_gap_in_the_chapters_keeps_every_number`; feeding one chunk less fails the byte tests. Removing the join trim entirely passes every PR test (M1).

Result: the split leaves `write_audiobook` byte-identical, and `BookWriter` writes the same bytes, including at real clause joins. What is missing is a test in the PR that would catch a join difference (M1).

## Findings

- **M1** (must-fix, kind `vacuous-test`). `test_chapter_by_chapter_with_clause_joins_writes_the_same_bytes` cannot fail on a join difference: `make_job`'s chunks are tones with no quiet edges, so `edge_trim` trims nothing and the join path is never exercised. With `_trim_joins` deleted from `BookWriter.add` the whole file passes (check 4). The PR body names clause joins as one of the guarded risks. Recommended: give that test chunks with quiet lead and tail (as `test_output_joins.speech` makes them), put a `CLAUSE` pause both inside a chapter and on a chapter's first chunk, and assert that some trim happened (for example a `ChunkAudio.kept` shorter than the file, or the M4B shorter than with `Pause.SENTENCE`), so the test fails if trimming stops. The same fixture with `OutputSettings(m4b=False, subtitles=True)` covers S1 too.
- **S1** (should-fix, kind `missing-case`). The byte-equality parametrization lacks `OutputSettings(m4b=False, subtitles=True)`, which becomes the job's path with subtitles once PR B sets `JOB_OUTPUT = OutputSettings(m4b=False)`. It is only reached indirectly in `test_write_book_...`, whose final comparison uses `ALL`. Check 1 and 2 show it is identical today. Recommended: add it as a fifth id (`mp3-and-subtitles`).
- **N1** (note, plan deviation). The plan had `write_audiobook` become the composition of the new parts; the PR keeps its body and adds `BookWriter` beside it, sharing the helpers, because composing would reorder the files the output fault tests pin (MP3s, M4B, then subtitles). The reason holds; the cost is two orchestrations of the same files, held together by the byte-equality tests. That is why M1 matters. No change asked.
- **N2** (note). `test_write_audiobook_output_is_pinned_before_the_split` compares `write_audiobook` with itself in one run and pins the file names, so it cannot detect a change to `write_audiobook`'s bytes. Raw MP3/M4B bytes cannot be pinned across systems (plan section 5), and the read-along golden in `test_output_faults.py` pins the JSON, so this review's main-vs-head comparison (check 1) is the evidence for this head. No change asked.
- **N3** (note, for PR B). `BookWriter.__init__` removes the read-along file even when it is in `keep`, and `add(..., written=True)` trusts the caller that the kept files are whole. PR B's size and SHA-256 check of `chapters.json` must run before `keep` is passed; the review of PR B checks that.

## Handoff (THR-07)

- Goal: critical review round 1 of #754 at 5742b76.
- Done: CI and lanes verified; byte identity of `write_audiobook` (main vs head) and of `BookWriter` (vs main) shown on 12 inputs plus real clause joins; one vacuous test found.
- Next: the author pushes one fix commit for M1 and S1 (tests only, `tests/unit/test_output_chapters.py`), Linux CI green; round 2 checks that the new join test fails with `_trim_joins` removed from `BookWriter.add`, then decides. A three-system run on the final head is still needed before merge (D-580). Ruled out: no product-code difference found; fingerprint inputs are sufficient because chunk file names are the SHA-256 cache key of text, voice, speed and engine (`app/chunks.py chunk_key`).
