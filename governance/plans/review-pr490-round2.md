# Review PR #490, round 2 (markers with a note, #474), CRITICAL, final round

Head reviewed: c0c21ba, the round 1 fix commit on 7aac6ba. It changes tests only: `git diff 7aac6ba c0c21ba -- src` is empty. Round 1: plans/review-pr490-round1.md. The author's answer: plans/review-pr490-round1-fixes.md.

**Verdict: approvable, and merged.**

## The fixes
- **S1a to S1f:** six new tests in `test_web_markers.py`: nearest occurrence in a block, the ±20 window (15 found, 25 not), the larger share either way with a tie going to the earlier block, the step 5 tie, runs of white space, and soft hyphens both ways.
- **S2:** a parametrised test in `test_web_markers_survive.py`. An empty span and a span past the block's end each answer 422 `no-such-sentence`, with the file byte-identical.
- **N1:** a restore at exactly `UNDO_SECONDS` works.
- **N2:** a BROKEN case with 2001 markers.

## Final-round checks on c0c21ba
- **Mutation.** I re-ran the 11 survivors from round 1 with my own scripts (`scratchpad m490/run.sh`, same three test files, clean baseline). All are killed, and each first failure is the new test aimed at it:

  | mutant | killed by |
  |---|---|
  | R3, R3b | `test_web_markers.py:634` |
  | R5 | (17, 0, 23) expected, None found |
  | R6b | `test_web_markers.py:671` |
  | R7 | chunk 1 instead of 0 |
  | R9, R10 | expected place, None found |
  | S2 | the "empty" case |
  | S3 | the "outside" case |
  | U5 | the undo test |
  | L3 | `[more than 2000 markers]` |

- **Mutation totals.** 46 mutants across both rounds:
  - the author's nine: killed;
  - my 37: 28 killed;
  - 8 equivalent (argued in round 1);
  - 1 accepted (N5).
- **Nightly seeds.** 2024 and 123456 on `test_web_markers.py` and `test_web_markers_survive.py`: 68 passed, 1 skipped (read-only as root) each.
- **Unit tests** (the five marker, design, Schemathesis and remove files): 176 passed, 2 skipped.
- **Three systems on c0c21ba:** `tests (macos-latest)`, `tests (windows-latest)` and `tests (ubuntu-latest)` are green, as are browser, ZAP, CodeQL, licences, lint and layers, security and `CI passed`.

## Merge
- **Main had not moved:** it was 5812d2d, which is in the branch.
- **Squash-merged**, pinned to c0c21ba. Main is now **fc7406a**.
- **The tree is identical** to the reviewed head's.
- **Closed:** #474.
