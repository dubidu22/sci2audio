# PR #490, round 1 fix commit c0c21ba: what changed and why

The fix commit is c0c21ba, on top of 7aac6ba. It adds tests only; no source file changed. ci:full is on again.

## Each finding, and the test that pins it

### S1. Re-anchoring rules (`tests/unit/test_web_markers.py`)

| finding | test | what it checks |
|---|---|---|
| S1a | `test_the_same_sentence_three_times_in_one_block_takes_the_one_nearest_its_old_place` | Three copies of the sentence in one block, with "Added. " put before all three so step 1 fails. `_Finder.find` gives the middle copy at its new offsets. |
| S1b | `test_a_split_sentence_is_looked_for_twenty_blocks_either_side_and_no_further` | A sentence split over two blocks, the first of them 15 blocks after the anchor's block: found, and the marker shows. 25 blocks after: `find` returns None, and the marker is not found. |
| S1c | `test_a_split_sentence_goes_to_the_block_with_the_larger_share_the_earlier_on_a_tie` | Larger share in the earlier block: the earlier block wins. Equal shares ("abcd" and "efgh"): block 0. |
| S1d | `test_a_place_two_chunks_overlap_alike_is_shown_on_the_first` | Two chunks overlap the place by 20 characters each: the marker shows on chunk 0. |
| S1e | `test_runs_of_white_space_read_as_one_space` | Two cases: a run of spaces and a line break inside the sentence, and a double space. Each is found over the full printed range. |
| S1f | `test_soft_hyphens_are_read_through_both_ways` | A soft hyphen now in the block, and a soft hyphen stored in the anchor at an old offset, so step 1 fails. Both are found. |

### S2. The set route's refusals (`tests/unit/test_web_markers_survive.py`)

`test_a_chunk_whose_span_is_empty_or_outside_the_document_is_no_sentence` runs two cases:
- `empty`: the read-along chunk's `end_char` is set to its `start_char`.
- `outside`: `end_char` is set to 10 000.

Each case posts with the new `audiobook_stamp` of the edited read-along. The answer must be 422 `no-such-sentence`, and the markers file must be byte-identical afterwards.

### N1 and N2 (`tests/unit/test_web_markers.py`)

- **N1:** `test_undo_ends_after_ten_minutes_...` now first restores after exactly `UNDO_SECONDS`, then removes again and checks that `UNDO_SECONDS + 0.001` ends the undo.
- **N2:** a new BROKEN case, `more than 2000 markers`: 2001 valid markers with distinct ids, well under 2 MB.

## Mutants

The reviewer's surviving mutants, rebuilt in `plans/pr-b-mutation/round1.py`, run with `pytest -x` on the two marker modules:

| mutant | killed by |
|---|---|
| R3 (first match) | S1a |
| R3b (last match) | S1a |
| R5 (window ±1) | S1b |
| R6b (later block on a tie) | S1c |
| R6c (highest block) | S1c |
| R7 (`>=`, last on a tie) | S1d |
| R9 (white space not folded) | S1e |
| R10 (soft hyphen kept) | S1f |
| S2 (empty span taken) | S2, `empty` |
| S3 (no `check_span`) | S2, `outside` |
| U5 (`>=` at 600 s) | N1 |
| L3 (no limit on read) | N2 |

All of them are killed, and the first failing test is named in each row.

## Runs

- `ruff check` and `ruff format --check`: clean.
- `test_web_markers.py`, `test_web_markers_survive.py` and `test_web_schemathesis.py`: 69 passed, 1 skipped (read-only as root).
- Nightly profile with `--hypothesis-seed` 2024 and 123456, on both marker modules: 68 passed, 1 skipped for each seed.
- CI: Linux is running on c0c21ba. The three-system run follows from the `ci:full` label.
