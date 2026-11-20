# Review PR #490, round 1 (web lane v1.3 PR B: markers with a note, #474), CRITICAL

Head reviewed: 7aac6ba, which is main 5812d2d (#492) merged into ffa28b9 (20a82f3 plus the ZAP walk). Plan: plans/general-marker-plan.md, approved as D-728. Checks on 7aac6ba are all green:
- the three systems: `tests (macos-latest)`, `tests (windows-latest)`, `tests (ubuntu-latest)`;
- `browser (Linux, Chromium)`, ZAP, CodeQL, licences, lint and layers, security, `CI passed`.

**Verdict: not approvable yet.** There are no functional defects, but there are two should-fixes, both missing tests, and two nits.
- **S1.** Six re-anchoring rules the plan promises are not pinned by any test: the mutants that break them survive.
- **S2.** Two refusals of the set route are not pinned.

The design, the D-728 rulings, the write path, the guard and the fault injection are right as they stand.

## What I checked

### Against the plan and D-728
- **No core change.** `web/markers.py` is the only writer, through `MarkerBook.change` (one lock per work folder, read, edit, atomic `write_texts`). `set`, `note`, `remove` and `restore` all go through it (ruling 2). `markers_text` never writes a file it couldn't read back.
- **Broken file** (bad JSON, other format, version or document, a symlink, larger than 2 MB, deep nesting): reading raises `MarkersBroken`, and nothing is written. The page names the file and disables the button and M, and the API answers 409.
- **Ruling 1.** The guard tests fail without the guard: mutants G1, G2 and G3 are killed. "Never dropped" fails if a marker is dropped from the list or the file: N1, N2 and N3 are killed.
- **Ruling 3.** `_removal` counts from the file as the box is drawn (`count_markers`, None when unreadable). It is pinned by `test_the_removal_box_counts_...` (C1 is killed, and so is my P2). It is a unit test on the #120 path, not the browser `test_remove.py`; the PR body states and explains that deviation, and I accept it.
- **D-718.** `linesOf()` is shared by the bar and the flag. The marker has its own tokens, and PR A's tests pass unchanged. The marker adds no fill.
- **Harness changes 1 to 9** match the PR body. Item 9, the ZAP walk, drives the four routes, and ZAP is green on the head.
- **Security.** Notes and quotes are drawn with `textContent`. The routes are under the token and origin checks (tested), ids are restricted to `^[0-9a-f]{16}$`, and the note is limited to 4000 characters with no NUL, both in the model and in `note_problem`.

### Runs
- **Unit tests** (`test_web_markers.py`, `test_web_markers_survive.py`, `test_web_design.py`, `test_web_schemathesis.py`, `test_web_remove.py`): 166 passed, 2 skipped. The skips are read-only as root here, and junctions, which are Windows only.
- **Browser tests** (`test_markers.py`, `test_focus.py`, `test_listen.py`, Chromium): 46 passed.
- **Nightly seeds** (`HYPOTHESIS_PROFILE=nightly`, `--hypothesis-seed` 2024 and 123456; `test_web_markers.py` with the state machine and the finder property, plus `test_web_documents.py`): 78 passed for each seed.
- **Speed** on `long_book()` (3010 blocks, 30010 chunks):

  | case | time |
  |---|---|
  | 2000 markers found in place | 0.07 s |
  | 2000 markers shifted by one block (step 2) | 1.0 s |
  | 100 markers not found | 0.48 s |

  Fine for v1.3.

### Mutation
- **The author's nine** (G1–G3, N1–N3, U1, U2, C1), re-run from a clean tree with `/mnt/project-files/plans/pr-b-mutation/mutants.py`: all killed, and each first failure names the matching test.
- **My 37**, run with `scratchpad m490/mut.py` and `run.sh`: pytest on `test_web_markers.py`, `test_web_markers_survive.py` and `test_web_schemathesis.py`, `-x -n 4`. The clean run passes. 17 are killed, and 20 survive:

  | survivor | verdict |
  |---|---|
  | R3, R3b: step 2 takes the first or the last match in a block, not the nearest | **S1a** |
  | R5: the ±20 window is ±1 | **S1b** |
  | R6b: step 3 takes the later block | **S1c** |
  | R7: step 5 takes the last of equal overlaps | **S1d** |
  | R9: runs of white space are not folded | **S1e** |
  | R10: soft hyphens are not dropped | **S1f** |
  | S2: an empty chunk is taken | **S2a** |
  | S3: no `check_span` | **S2b** |
  | U5: undo ends at exactly 600 s | **N1** |
  | L3: a file with more than 2000 markers is read | **N2** |
  | R1, R11: step 1 off, or step 1 comparing the raw text | equivalent: step 2 finds the same place in the same block. A Hypothesis counterexample search (20,000 examples, each a slice of random text over `aA b.-` plus newline and soft hyphen) finds differences only for anchors that start or end in white space or inside a line-end hyphen join, and no chunk span does that. |
  | R13: empty spans indexed | equivalent: their overlap is ≤ 0, so they never win |
  | U4, U6: the restore clash checks by anchor and by id | equivalent: the same anchor gives the same placed chunk, so `on_sentence` already refuses it, and a second restore of one id finds nothing kept (410) |
  | U7: no pop before re-keeping a removed id | equivalent: a removed id is not kept twice |
  | L1: the set route's own limit check | equivalent: `markers_text` raises the same `MarkerLimit` |
  | D4: no `parse_constant` | equivalent: NaN or Infinity is a float, and every check needs an int or a string |
  | N5: saving an unchanged note | accepted: only `changed` is set again, and nothing is lost |

## Findings

### S1. Re-anchoring rules the plan names are not pinned (plan section 3, steps 2, 3 and 5; "after shown() normalisation")
Add these tests to `tests/unit/test_web_markers.py`. Each must fail on its mutant, which I will re-run.
1. **S1a, nearest occurrence in a block (R3, R3b).**
   - One block holds the marked sentence three times. Put some text before all three, so step 1 fails.
   - The marker was on the middle one: it is found on the middle one, with its new offsets.
2. **S1b, the ±20 window (R5).**
   - A sentence now spread over two blocks whose first block is 15 blocks after the anchor's block: found.
   - The same with the first block 25 blocks after: not found.
3. **S1c, the larger share wins in either direction (R6b).**
   - A sentence spread over two blocks with the larger share in the EARLIER block: placed in the earlier block.
   - With equal shares: the earlier block, as `-b` breaks the tie.
4. **S1d, step 5's tie rule, "on a tie the first" (R7).**
   - A found place that two chunks overlap by the same number of characters is shown on the first chunk.
5. **S1e, white space folded (R9).**
   - The anchor is "a b" with one space, and the block now reads it with a run of spaces and a line break ("a \n b" or "a  b"): found at step 1 or step 2.
6. **S1f, soft hyphens dropped (R10).**
   - A block whose word now holds a U+00AD finds an anchor without it, and the reverse.

### S2. The set route's refusals of a chunk that is no sentence are not pinned
Add these to `test_web_markers_survive.py`, each with the file byte-identical afterwards:
1. **S2a (S2).** A chunk whose span is empty answers 422 `no-such-sentence`. With the mutant it answers 503, because the empty anchor is refused only by the read-back guard.
2. **S2b (S3).** A chunk whose span lies outside the document answers 422 `no-such-sentence`. Use a read-along with a span past its block's end, as `listen.mismatch` tests make one.

### N1. Undo at exactly 10 minutes (U5)
- `restore` after `clock.advance(UNDO_SECONDS)` puts the marker back.
- The rule is "more than 600 s ends it". One assertion in `test_undo_ends_after_ten_minutes_...`.

### N2. A file with more than 2000 markers is not readable (L3)
- One more case in `test_a_file_this_version_cant_read_is_never_written`: 2001 valid markers, under 2 MB.

## Process
- **One fix commit**, tests only. No source change is expected; if one is needed, say why.
- **Linux CI green**, then round 2. Round 2 re-runs every surviving mutant above and the nightly seeds on the new tests.
- **Three systems.** A critical PR merges only on a head with green macOS, Windows and Linux runs (CLAUDE.md, rule 8). So the fix commit gets the `ci:full` label again: Linux first, then all three systems before the merge.
